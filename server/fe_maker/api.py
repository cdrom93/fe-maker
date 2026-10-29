"""Local HTTP API used by the FE Maker interface."""

from __future__ import annotations

import base64
import dataclasses
import io
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import urllib.parse
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
from PIL import Image
from pydantic import BaseModel

from . import emulator, ferepo
from .builder import BuildError
from .config import Settings, default_projects_dir, find_tiled
from .decomp import (
    banim,
    banim_import,
    convoy,
    dialogues,
    events,
    fonts,
    mapobjects,
    maps,
    pieces,
    portraits,
    quotes,
    story,
    supports,
    tiled,
    tileedit,
    units,
)
from .decomp.assets import face_preview, item_icon_preview, portrait_names, portrait_preview
from .decomp.assets import map_sprite as map_sprite_png
from .decomp.gamedata import ABILITIES, AFFINITIES, RANK_VALUES, RANKABLE_TYPES, WEAPON_TYPES, DecompData, GameDataError
from .paths import DECOMP_DIR, REPO_ROOT
from .project import ANIMATIONS_DIR, DATA_FILES, PORTRAITS_DIR, Project, ProjectError, slugify
from .rom import InvalidRomError
from .tickets import TicketError, TicketStore

LANGUAGES = ("fr", "en", "es", "it")  # ui/src/locales

app = FastAPI(title="FE Maker")


class _State:
    def __init__(self) -> None:
        self.settings = Settings.load()
        self.project: Project | None = None
        self.decomp: DecompData | None = None
        self.build_lock = threading.Lock()
        self.build_status = {"state": "idle", "log": [], "error": None, "patch": None, "launch": False}
        self.emulator = emulator.Emulator()
        # Set by __main__: stops the server (a new launch from the shortcut restarts FE Maker)
        self.stop_server = None

    def get_decomp(self) -> DecompData:
        if self.decomp is None:
            self.decomp = DecompData(DECOMP_DIR)
        return self.decomp

    def require_project(self) -> Project:
        if self.project is None:
            raise HTTPException(409, "No project open")
        return self.project


state = _State()


# ---------- settings and ROM ----------

class SettingsIn(BaseModel):
    language: str | None = None
    mgbaPath: str | None = None
    keys: dict[str, str] | None = None


@app.get("/api/status")
def status():
    s = state.settings
    return {
        "hasRom": s.has_rom,
        "language": s.language,
        "mgbaPath": s.mgba_path,
        "keys": s.keys,
        "gbaButtons": emulator.GBA_BUTTONS,
        "recentProjects": s.recent_projects,
        "defaultProjectsDir": str(default_projects_dir()),
        "project": _project_info(state.project) if state.project else None,
    }


@app.post("/api/shutdown")
def shutdown():
    """Stop the server, for a new launch of FE Maker to replace it; refused while a build runs."""
    if state.build_lock.locked():
        raise HTTPException(409, "buildRunning")
    if state.stop_server is None:
        raise HTTPException(501, "notStoppable")
    state.stop_server()
    return {"stopping": True}


@app.put("/api/settings")
def update_settings(body: SettingsIn):
    if body.language in LANGUAGES:
        state.settings.language = body.language
    if body.mgbaPath is not None:
        state.settings.mgba_path = body.mgbaPath or None
    if body.keys is not None:
        try:
            state.settings.keys = emulator.validate_keys(body.keys)
        except emulator.EmulatorError as e:
            raise HTTPException(400, str(e))
    state.settings.save()
    return status()


@app.post("/api/rom")
async def upload_rom(file: UploadFile = File(...)):
    data = await file.read()
    try:
        state.settings.install_rom(data)
    except InvalidRomError:
        raise HTTPException(400, "invalidRom")
    return status()


# ---------- projects ----------

class CreateProjectIn(BaseModel):
    name: str
    author: str = ""
    folder: str | None = None


class OpenProjectIn(BaseModel):
    path: str


def _project_info(p: Project) -> dict:
    return {"path": str(p.root), "name": p.name, "meta": p.meta}


def _open(p: Project) -> dict:
    state.project = p
    state.settings.add_recent(p.root)
    return _project_info(p)


@app.post("/api/projects")
def create_project(body: CreateProjectIn):
    if not body.name.strip():
        raise HTTPException(400, "nameEmpty")
    folder = Path(body.folder) if body.folder else default_projects_dir() / slugify(body.name)
    try:
        return _open(Project.create(folder, body.name.strip(), body.author.strip()))
    except ProjectError as e:
        raise HTTPException(400, str(e))


@app.post("/api/projects/open")
def open_project(body: OpenProjectIn):
    try:
        return _open(Project(Path(body.path)))
    except ProjectError as e:
        raise HTTPException(400, str(e))


@app.post("/api/projects/close")
def close_project():
    state.project = None
    return status()


# ---------- project data ----------

@app.get("/api/project/data/{kind}")
def get_data(kind: str):
    if kind not in DATA_FILES:
        raise HTTPException(404)
    return state.require_project().load(kind)


@app.put("/api/project/data/{kind}")
def put_data(kind: str, records: list[dict] | dict):
    if kind not in DATA_FILES:
        raise HTTPException(404)
    problems = state.require_project().save(kind, records)
    return {"problems": [p.to_dict() for p in problems]}


@app.get("/api/project/problems")
def get_problems():
    return {"problems": [p.to_dict() for p in state.require_project().validate()]}


@app.get("/api/reference")
def reference():
    """Read-only lists used by the editors (classes, weapon types, ranks)."""
    d = state.get_decomp()
    classes = d.export_classes()
    class_names = {c["id"]: c["name"] for c in classes}
    char_names = {c["id"]: c["name"] for c in d.export_characters()}
    return {
        "classes": classes,  # original game classes (the project's own are in data/classes)
        "classFacts": d.class_facts(),
        "movementTypes": d.movement_types(),
        "effectivenessLists": sorted(d.effectiveness or {}),
        # Item id -> names of the classes / characters allowed to wield it (weapon locks)
        "itemLocks": {
            item: {
                "classes": list(dict.fromkeys(class_names.get(c, c) for c in who["classes"])),
                "characters": [char_names.get(c, c) for c in who["characters"]],
            }
            for item, who in d.item_locks().items()
        },
        # Ability key of a weapon lock ("lock4") -> names of the items it unlocks
        "lockItems": d.lock_items(),
        "affinities": list(AFFINITIES.values()),
        "abilities": list(ABILITIES.values()),
        "weaponTypes": list(WEAPON_TYPES.values()),
        "rankableTypes": RANKABLE_TYPES,
        "ranks": list(RANK_VALUES),
        "iconCount": len(d.item_icon_files()),
        "portraits": _portrait_names(),
        "firstNewPortrait": portraits.first_new_id(DECOMP_DIR),
    }


def _added_portraits() -> dict[int, dict]:
    """Portraits the project adds after the game's ones: id -> entry of data/portraits.json."""
    if state.project is None:
        return {}
    return {int(k): e for k, e in state.project.load("portraits").items()
            if k.isdigit() and portraits.is_new(DECOMP_DIR, int(k))}


def _portrait_names() -> list[str | None]:
    """Portrait name per id: the game's, then the project's new portraits (None for unused ids)."""
    names = list(portrait_names(DECOMP_DIR))   # a copy: portrait_names is cached
    added = _added_portraits()
    if added:
        first = len(names)
        names += [(added[pid].get("name") or portraits.new_name(pid)) if pid in added else None
                  for pid in range(first, max(added) + 1)]
    return names


# ---------- chapters (phase 3, read-only for now) ----------

def _chapter(index: int) -> dict:
    chapters = maps.chapter_settings(DECOMP_DIR)
    if not 0 <= index < len(chapters):
        raise HTTPException(404)
    return chapters[index]


def _event_symbol(chapter: dict) -> str | None:
    table = maps.asset_table(DECOMP_DIR)
    index = chapter.get("mapEventDataId", 0)
    return table[index] if 0 < index < len(table) else None


@app.get("/api/chapters")
def list_chapters():
    d = state.get_decomp()
    result = []
    for i, ch in enumerate(maps.chapter_settings(DECOMP_DIR)):
        title_id = ch.get("chapTitleTextId", 0)
        try:
            layout = maps.chapter_map_assets(DECOMP_DIR, ch).layout.stem
        except maps.MapError:
            layout = None
        result.append({
            "index": i,
            "id": ch.get("internalName", str(i)),
            "title": d.texts.get_name(title_id) if title_id in d.texts.messages else "",
            "map": layout,
            "events": _event_symbol(ch),
            "convoy": convoy.has_convoy(i),   # in the game (ticket 29)
            "fog": ch.get("initialFogLevel", 0),   # vision range in fog of war, 0: no fog
        })
    return result


@app.get("/api/chapters/links")
def chapter_links():
    """For each chapter (by index), the event commands that start another chapter (story.py), the
    project's edited scripts included: the graph of how chapters follow each other (ticket 31)."""
    edited = state.project.load("dialogues").get("scripts", {}) if state.project else {}
    return {"links": state.get_decomp().chapter_links(edited), "kinds": story.CHANGE_OPS, "toChapter": list(story.TO_CHAPTER)}


@app.get("/api/chapters/{index}/map.png")
def chapter_map(index: int, fog: bool = False):
    """The chapter's map as painted in the project (the original one if never painted)."""
    try:
        assets = maps.chapter_map_assets(DECOMP_DIR, _chapter(index))
        project_maps = state.project.load("maps") if state.project else {}
        painted = project_maps.get("layouts", {}).get(assets.layout.stem)
        layout = (len(painted["rows"][0]), len(painted["rows"]), [c for row in painted["rows"] for c in row]) if painted else None
        layout_id = assets.layout.stem
        assets = maps.layout_assets(DECOMP_DIR, layout_id, project_maps.get("bases", {}).get(layout_id),
                                    project_maps.get("palettes", {}).get(layout_id))
        edits = project_maps.get("tilesets", {}).get(assets.config.stem)
        with tempfile.TemporaryDirectory() as folder:
            if edits:
                edited = tileedit.Tileset(DECOMP_DIR, _tile_layout(layout_id, assets), edits).edited_assets(Path(folder))
                assets = dataclasses.replace(edited, palette=assets.palette)   # the chapter's palette
            png, _w, _h = maps.render_map(assets, scale=1, fog=fog, layout=layout)
    except (maps.MapError, tileedit.TileEditError) as e:
        raise HTTPException(404, str(e))
    return Response(png, media_type="image/png", headers={"Cache-Control": "no-cache"})


# ---------- maps ----------

def _layout(layout_id: str) -> dict:
    layout = maps.layouts(DECOMP_DIR).get(layout_id)
    if layout is None:
        raise HTTPException(404)
    return layout


def _tile_layout(layout_id: str, assets: maps.MapAssets) -> str:
    """A layout of the game drawn with these assets' tile sheet (tile edits work on it)."""
    if assets.config == _layout(layout_id)["assets"].config:
        return layout_id
    return tileedit.layout_for(DECOMP_DIR, assets.config.stem) or layout_id


def _project_bases() -> dict:
    return state.project.load("maps").get("bases", {}) if state.project else {}


@app.get("/api/maps")
def list_maps():
    result = []
    for layout_id, layout in maps.layouts(DECOMP_DIR).items():
        width, height, _cells = maps.read_layout(layout["assets"].layout)
        result.append({"id": layout_id, "width": width, "height": height, "chapters": layout["chapters"],
                       "tileset": maps.with_base(DECOMP_DIR, layout["assets"], _project_bases().get(layout_id)).config.stem,
                       "originalTileset": layout["assets"].config.stem})
    return result


@app.get("/api/maps/{layout_id}")
def get_map(layout_id: str, base: str | None = None):
    """The original layout, with what the editor needs about its tileset (terrains, duplicate metatiles);
    `base`: another tile sheet of the game chosen for the map (ticket 21)."""
    layout = _layout(layout_id)
    assets = maps.with_base(DECOMP_DIR, layout["assets"], base)
    width, height, cells = maps.read_layout(assets.layout)
    _metatiles, terrain = maps.read_config(assets.config)
    texts = state.get_decomp().texts
    return {
        "id": layout_id,
        "rows": [cells[y * width: (y + 1) * width] for y in range(height)],
        "tileset": assets.config.stem,
        "terrains": list(terrain),
        "duplicates": maps.duplicate_metatiles(assets),
        "terrainNames": [texts.get_name(t) if t in texts.messages else "" for t in maps.terrain_text_ids(DECOMP_DIR)],
        "columns": maps.TILESET_COLUMNS,
        # Palettes of the tileset in the game, and the map's own (ticket 16)
        "palette": maps.palette_symbol(DECOMP_DIR, assets.palette),
        "palettes": [{**p, "colors": _palette_colors(p["id"])} for p in maps.palette_choices(DECOMP_DIR, assets)],
        # Tile sheets of the game the map can be drawn with, and the map's own (ticket 21)
        "originalBase": layout["assets"].config.stem,
        "bases": [{"id": b["id"], "chapters": b["chapters"], "palette": maps.asset_table(DECOMP_DIR)[b["map"]["paletteId"]]}
                  for b in maps.base_choices(DECOMP_DIR)],
        # Original map changes (doors, villages...); None when the map has no change layer
        "changes": maps.read_changes(DECOMP_DIR, layout["changes"]) if layout["changes"] else None,
    }


def _palette_colors(symbol: str) -> list[str]:
    """The 16 colors of a map palette's first line (#rrggbb), as swatches."""
    colors = maps.read_jasc_palette(maps.asset_files(DECOMP_DIR)[symbol])[:16]
    return [f"#{r:02x}{g:02x}{b:02x}" for r, g, b in colors]


class MapObjectsIn(BaseModel):
    rows: list[list[int]]
    changes: list[dict] | None = None   # None: the original change set
    objects: dict = {}
    tileset: dict | None = None         # metatiles added to the tileset (tileedit.py)
    base: str | None = None             # another tile sheet of the game (ticket 21)


@app.post("/api/maps/{layout_id}/objects")
def map_objects(layout_id: str, body: MapObjectsIn):
    """Villages, houses, chests, doors, walls and snags of the map being painted, with what the build
    does for them (see mapobjects.py) and their original location event, if any."""
    layout = _layout(layout_id)
    changes = body.changes
    if changes is None:
        changes = maps.read_changes(DECOMP_DIR, layout["changes"]) if layout["changes"] else []
    try:
        assets = maps.with_base(DECOMP_DIR, layout["assets"], body.base)
        terrain = bytes(tileedit.Tileset(DECOMP_DIR, _tile_layout(layout_id, assets), body.tileset).terrain) \
            if body.tileset else None
        objects = mapobjects.map_objects(DECOMP_DIR, layout_id, body.rows, changes, body.objects, terrain, assets)
    except (IndexError, ValueError) as e:
        raise HTTPException(400, str(e)) from e
    events = state.get_decomp().map_object_events(layout_id)
    for obj in objects:
        found = next((events[tuple(c)] for c in obj["cells"]
                      if tuple(c) in events and mapobjects.event_matches(events[tuple(c)]["kind"], obj["kind"])), None)
        obj["event"] = {k: v for k, v in found.items() if k != "span"} if found else None
    return {"objects": objects, "hasChangeLayer": bool(layout["changes"]), "defaults": mapobjects.DEFAULTS,
            "faces": [{"id": fid, "portrait": portrait} for fid, portrait in mapobjects.FACES.items()]}


class TilesetIn(BaseModel):
    edits: dict | None = None
    palette: str | None = None   # another palette of the tileset
    base: str | None = None      # another tile sheet of the game


@app.post("/api/maps/{layout_id}/tileset")
def edited_tileset(layout_id: str, body: TilesetIn):
    """The tileset sheet with the project's added metatiles (not saved yet: the editor sends them)."""
    _layout(layout_id)
    assets = maps.layout_assets(DECOMP_DIR, layout_id, body.base, body.palette)
    palette = assets.palette
    try:
        tileset = tileedit.Tileset(DECOMP_DIR, _tile_layout(layout_id, assets), body.edits)
        with tempfile.TemporaryDirectory() as folder:
            assets = dataclasses.replace(tileset.edited_assets(Path(folder)), palette=palette)
            png = maps.render_tileset(assets)
            duplicates = maps.duplicate_metatiles(assets)
    except tileedit.TileEditError as e:
        raise HTTPException(409, str(e)) from e
    # Added metatiles are never hidden, even when they look like another one.
    for slot in (body.edits or {}).get("metatiles", {}):
        duplicates[int(slot)] = False
    return {"sheet": "data:image/png;base64," + base64.b64encode(png).decode(), "terrains": list(tileset.terrain),
            "duplicates": duplicates}


class TransformIn(BaseModel):
    rows: list[list[int]]
    op: str                  # h, v, 180, cw, ccw, or "terrain"
    terrain: int = 0         # with op "terrain": the new terrain of the tiles
    edits: dict | None = None
    painted: dict = {}   # project painted layouts: their tiles are not free slots
    bases: dict = {}     # project tile sheets of the layouts


@app.post("/api/maps/{layout_id}/transform")
def transform_tiles(layout_id: str, body: TransformIn):
    """A block of tiles mirrored or turned: new metatiles (and 8x8 tiles) added to the tileset when needed."""
    _layout(layout_id)
    assets = maps.layout_assets(DECOMP_DIR, layout_id, body.bases.get(layout_id))
    try:
        tileset = tileedit.Tileset(DECOMP_DIR, _tile_layout(layout_id, assets), body.edits, body.painted, body.bases)
        before = set(tileset.edits["metatiles"])
        if body.op == "terrain":
            rows = tileset.with_terrain(body.rows, body.terrain)
            similar = None
        else:
            rows = tileset.transform_block(body.rows, body.op)
            # Tiles the game already draws that way (ticket 18): the editor offers them instead.
            found = {m: tileset.similar_original(m) for row in rows for m in row if str(m) not in before}
            similar = [[found[m] if found.get(m) is not None else m for m in row] for row in rows] \
                if any(v is not None for v in found.values()) else None
    except tileedit.TileEditError as e:
        raise HTTPException(409, str(e)) from e
    return {"rows": rows, "edits": tileset.edits, "tileset": tileset.name, "similar": similar}


@app.get("/api/maps/{layout_id}/tileset.png")
def map_tileset(layout_id: str, palette: str | None = None, base: str | None = None):
    _layout(layout_id)
    png = maps.render_tileset(maps.layout_assets(DECOMP_DIR, layout_id, base, palette))
    return Response(png, media_type="image/png", headers={"Cache-Control": "max-age=3600"})


@app.get("/api/maps/{layout_id}/pieces")
def map_pieces(layout_id: str, base: str | None = None):
    """Whole buildings (villages, castles...) of the game's maps drawn with this map's tile sheet (ticket 41)."""
    _layout(layout_id)
    return {"pieces": list(pieces.pieces(DECOMP_DIR, maps.layout_assets(DECOMP_DIR, layout_id, base).config))}


class TiledExportIn(BaseModel):
    rows: list[list[int]]
    changes: list[dict] | None = None   # None: the original change set
    edits: dict | None = None           # tiles the project added to the tileset
    palette: str | None = None
    base: str | None = None


def _tiled_file(layout_id: str) -> Path:
    if not state.project:
        raise HTTPException(409, "noProject")
    return state.project.root / "tiled" / f"{layout_id}.tmx"


@app.post("/api/maps/{layout_id}/tiled")
def export_tiled(layout_id: str, body: TiledExportIn):
    """The map as painted, written for Tiled in the project's tiled/ folder (ticket 25), and Tiled opened
    on it when installed. The editor reads it back with GET."""
    layout = _layout(layout_id)
    target = _tiled_file(layout_id)
    assets = maps.layout_assets(DECOMP_DIR, layout_id, body.base, body.palette)
    changes = body.changes
    if changes is None:
        changes = maps.read_changes(DECOMP_DIR, layout["changes"]) if layout["changes"] else []
    try:
        with tempfile.TemporaryDirectory() as folder:
            if body.edits:
                palette = assets.palette
                assets = dataclasses.replace(
                    tileedit.Tileset(DECOMP_DIR, _tile_layout(layout_id, assets), body.edits).edited_assets(Path(folder)),
                    palette=palette)
            png = maps.render_tileset(assets)
    except tileedit.TileEditError as e:
        raise HTTPException(409, str(e)) from e
    target.parent.mkdir(parents=True, exist_ok=True)
    sheet = target.with_name(f"{layout_id}-tiles.png")
    sheet.write_bytes(png)
    with Image.open(sheet) as img:
        size = img.size
    target.write_text(tiled.write_tmx(body.rows, changes, sheet.name, size, maps.TILESET_COLUMNS,
                                      {"TileConfig": assets.config.stem}), encoding="utf-8")
    program = find_tiled()
    if program:
        # detached, like mGBA: closing FE Maker leaves Tiled open
        detach = ({"creationflags": subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP}
                  if sys.platform == "win32" else {"start_new_session": True})
        subprocess.Popen([program, str(target)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                         stdin=subprocess.DEVNULL, **detach)
    return {"path": str(target), "launched": bool(program), "modified": target.stat().st_mtime}


@app.get("/api/maps/{layout_id}/tiled")
def import_tiled(layout_id: str):
    """The map and changes of the project's tiled/<layout>.tmx, as saved in Tiled."""
    _layout(layout_id)
    target = _tiled_file(layout_id)
    if not target.is_file():
        raise HTTPException(404, "noTiledFile")
    try:
        return {**tiled.read_tmx(target.read_text(encoding="utf-8")), "modified": target.stat().st_mtime}
    except tiled.TiledError as e:
        raise HTTPException(400, str(e)) from e


class TmxIn(BaseModel):
    text: str


@app.post("/api/maps/{layout_id}/tiled/read")
def read_tiled(layout_id: str, body: TmxIn):
    """A .tmx chosen by the user (made in Tiled, or from FE-Repo): its map and changes."""
    _layout(layout_id)
    try:
        return tiled.read_tmx(body.text)
    except tiled.TiledError as e:
        raise HTTPException(400, str(e)) from e


class ConvertIn(BaseModel):
    rows: list[list[int]]
    changes: list[dict] | None = None   # None: the original change set
    base: str | None = None             # the map's tile sheet now (None: its own)
    to: str                             # the tile sheet to draw it with
    edits: dict | None = None           # tiles the project added to the current sheet (their terrains)


@app.post("/api/maps/{layout_id}/convert")
def convert_map(layout_id: str, body: ConvertIn):
    """The map and its changes redrawn with another tile sheet of the game, tile by tile by terrain
    (ticket 21): the map plays the same, the user then touches it up."""
    layout = _layout(layout_id)
    if maps.base_of(DECOMP_DIR, body.to) is None:
        raise HTTPException(400, "unknownTileSheet")
    source = maps.with_base(DECOMP_DIR, layout["assets"], body.base)
    try:
        terrain = bytes(tileedit.Tileset(DECOMP_DIR, _tile_layout(layout_id, source), body.edits).terrain) \
            if body.edits else maps.read_config(source.config)[1]
    except tileedit.TileEditError as e:
        raise HTTPException(409, str(e)) from e
    changes = body.changes
    if changes is None:
        changes = maps.read_changes(DECOMP_DIR, layout["changes"]) if layout["changes"] else []
    target = maps.with_base(DECOMP_DIR, layout["assets"], body.to)
    if target.config == source.config:
        return {"rows": body.rows, "changes": changes, "missingTerrains": []}
    grids, missing = maps.convert_by_terrain(DECOMP_DIR, terrain, target, [body.rows] + [c["rows"] for c in changes])
    return {"rows": grids[0], "changes": [{**c, "rows": g} for c, g in zip(changes, grids[1:])], "missingTerrains": missing}


@app.get("/api/chapters/{index}/dialogues")
def chapter_dialogues(index: int):
    """Scenes of a chapter that show messages (what starts them) and their messages as steps,
    as in the original game (the editor adds the project's edits)."""
    _chapter(index)
    decomp = state.get_decomp()
    scenes = decomp.chapter_dialogues(index)
    ids = {i for s in scenes for i in s["messages"]}
    messages = {}
    for i in sorted(ids):
        if i in decomp.texts.messages:
            messages[str(i)] = dialogues.parse(decomp.texts.raw(i))
    return {"scenes": scenes, "messages": messages}


@app.get("/api/dialogues/common")
def common_dialogues():
    """Quotes of every chapter (the playable characters' last words...), like a chapter's dialogues."""
    decomp = state.get_decomp()
    scenes = decomp.quote_scenes(quotes.ANY_CHAPTER)
    messages = {str(i): dialogues.parse(decomp.texts.raw(i)) for s in scenes for i in s["messages"] if i in decomp.texts.messages}
    return {"scenes": scenes, "messages": messages}


@app.get("/api/dialogues/supports")
def support_dialogues():
    """The game's support pairs (points at the start, points per turn side by side, C/B/A conversations),
    as scenes of the dialogue editor, with their messages as steps."""
    decomp = state.get_decomp()
    pairs = decomp.original_supports()
    scenes = [{"script": f"support:{p['a']}:{p['b']}", "trigger": {"kind": "support", "a": p["a"], "b": p["b"]},
               "messages": [m for m in (p["messages"] or []) if m]} for p in pairs]
    messages = {str(i): dialogues.parse(decomp.texts.raw(i)) for s in scenes for i in s["messages"] if i in decomp.texts.messages}
    return {"pairs": [{k: p[k] for k in ("a", "b", "base", "growth")} for p in pairs], "scenes": scenes, "messages": messages,
            "levelPoints": list(supports.LEVEL_POINTS), "maxPartners": supports.MAX_PARTNERS}


@app.get("/api/events/reference")
def events_reference():
    """What the visual event editor offers: known commands and their arguments, songs, backgrounds."""
    def constants(rel: str, prefix: str) -> list[str]:
        path = DECOMP_DIR / rel
        return events.read_constants(path.read_text(encoding="utf-8"), prefix) if path.is_file() else []

    return {"commands": {op: [{"name": n, "kind": k} for n, k in spec] for op, spec in events.COMMANDS.items()},
            "addable": list(events.ADDABLE), "songs": constants("include/constants/songs.h", "SONG_"),
            "backgrounds": constants("include/constants/backgrounds.h", "BG_")}


@app.get("/api/events/scripts/{name}")
def event_script(name: str):
    """An event script of the game as commands (the project's edit, if any, is in data/dialogues.json)."""
    decomp = state.get_decomp()
    try:
        commands = decomp.script_commands(name)
    except (GameDataError, events.EventError) as e:
        raise HTTPException(404, str(e)) from e
    rel, _start, _end = decomp.find_script(name)
    return {"name": name, "file": rel, "commands": commands}


@app.get("/api/dialogues/font")
def dialogue_font():
    """The talk font for the editor's layout and preview: character -> [byte, width in pixels], and the
    box sizes (the same layout as the build, see dialogues.layout)."""
    table = fonts.widths(DECOMP_DIR)
    chars = {ch: [fonts.char_byte(ch), w] for ch, w in fonts.char_widths(table).items()}
    return {"chars": chars, "talkWidth": dialogues.TALK_WIDTH, "battleWidth": dialogues.BATTLE_WIDTH,
            "boxLines": dialogues.BOX_LINES}


@app.get("/api/dialogues/font.png")
def dialogue_font_sheet():
    png = fonts.font_sheet(DECOMP_DIR)
    if png is None:
        raise HTTPException(404, "No font")
    return Response(png, media_type="image/png", headers={"Cache-Control": "max-age=3600"})


@app.get("/api/dialogues/faces")
def dialogue_faces():
    """Portraits a dialogue can show: text code (FID_...) and portrait id."""
    defs = DECOMP_DIR / dialogues.TEXT_DEFS_FILE
    # A character given another portrait shows it in their dialogues (DecompData._follow_portraits)
    moves: dict[int, int] = {}
    if state.project:
        original = {c["id"]: c["portraitId"] for c in state.get_decomp().export_characters()}
        now = {c["id"]: c.get("portraitId") for c in state.project.load("characters")}
        for cid, pid in now.items():
            if cid in original and pid != original[cid] and original[cid]:
                moves[original[cid]] = pid
        moves = {old: new for old, new in moves.items() if old not in now.values()}
    faces = [{"id": fid, "portrait": moves.get(pid, pid)}
             for fid, pid in dialogues.read_faces(defs.read_text(encoding="utf-8")).items()]
    return faces + [{"id": portraits.face_code(pid), "portrait": pid, "name": e.get("name") or portraits.new_name(pid)}
                    for pid, e in sorted(_added_portraits().items())]


@app.get("/api/chapters/{index}/units")
def chapter_units(index: int):
    ch = _chapter(index)
    symbol = _event_symbol(ch)
    groups = units.read_unit_groups(DECOMP_DIR)
    # Groups edited in the project replace the original ones.
    edited = state.project.load("chapters").get("unitGroups", {}) if state.project else {}
    try:
        layout_path = maps.chapter_map_assets(DECOMP_DIR, ch).layout
        width, height, _cells = maps.read_layout(layout_path)
    except maps.MapError:
        width = height = 0
    else:
        # A painted map may have another size (ticket 40: the picture was squeezed into the old grid).
        painted = (state.project.load("maps").get("layouts", {}).get(layout_path.stem) if state.project else None)
        if painted and painted.get("rows"):
            width, height = len(painted["rows"][0]), len(painted["rows"])

    def group_units(name: str) -> list[dict]:
        if name in edited:
            # Groups edited before units could be added or removed have no "slot": units were in order.
            macros = units.ai_macros(DECOMP_DIR)
            return [{**({"slot": i} if "slot" not in u else {}), **u,
                     # Projects saved before the AI was editable store it as the original C text.
                     "ai": units.parse_ai(u["ai"], macros) if isinstance(u.get("ai"), str) else u.get("ai", [0, 0, 0, 0])}
                    for i, u in enumerate(edited[name])]
        return groups[name].units if name in groups else []

    return {
        "width": width,
        "height": height,
        "groups": [
            {**g, "units": group_units(g["name"]), "edited": g["name"] in edited}
            for g in (units.chapter_unit_groups(DECOMP_DIR, symbol) if symbol else [])
        ],
    }


@app.get("/api/chapters/{index}/objective")
def chapter_objective(index: int):
    """The chapter's original objective (the project's edit, if any, is in data/chapters.json)."""
    _chapter(index)
    return state.get_decomp().read_objective(index)


@app.get("/api/assets/map-sprite/{class_id}")
def map_sprite(class_id: str, side: str = "player", trim: bool = False):
    entry = next((e for e in state.get_decomp().classes.entries if e.fields["number"] == class_id), None)
    if entry is None:
        raise HTTPException(404)
    try:
        sprite_id = int(entry.fields.get("SMSId", "0"), 0)
    except ValueError:
        raise HTTPException(404)
    png = map_sprite_png(DECOMP_DIR, sprite_id, side, trim=trim)
    if png is None:
        raise HTTPException(404)
    return Response(png, media_type="image/png", headers={"Cache-Control": "max-age=3600"})


def _project_animations() -> dict:
    return state.project.load("animations") if state.project else {"animations": {}, "classes": {}}


def _animation_source(ref: str) -> tuple[Path, str]:
    """(base folder, symbol) of an animation: a game animation's number, or "new-<key>" for one the project
    imported (its decomp files are kept in the project's assets/animations/<key>/)."""
    if ref.startswith("new-"):
        key = ref[4:]
        if not state.project or key not in _project_animations().get("animations", {}):
            raise HTTPException(404)
        return state.project.root / "assets" / ANIMATIONS_DIR / key, banim_import.symbol_of(key)
    try:
        number = int(ref)
    except ValueError:
        raise HTTPException(404)
    anim = next((a for a in banim.table(DECOMP_DIR) if a.number == number), None)
    if anim is None:
        raise HTTPException(404)
    return DECOMP_DIR, anim.symbol


@app.get("/api/classes/{class_id}/animations")
def class_animations(class_id: str):
    """The class's battle animations, by weapon type or item (ticket 44), with the project's changes: an
    animation imported for a weapon type ("ref" "new-<key>") or another game animation."""
    entry = next((e for e in state.get_decomp().classes.entries if e.fields["number"] == class_id), None)
    if entry is None:
        raise HTTPException(404)
    conf = entry.fields.get("pBattleAnimDef", "").lstrip("&").strip()
    animations = {a.number: a for a in banim.table(DECOMP_DIR)}
    project = _project_animations()
    imported = project.get("animations", {})
    changed = project.get("classes", {}).get(class_id, {})
    left = dict(changed)

    def describe(wtype, item_id, anim) -> dict | None:
        if isinstance(anim, str) and anim.startswith("new:") and anim[4:] in imported:
            key = anim[4:]
            base, symbol = state.project.root / "assets" / ANIMATIONS_DIR / key, banim_import.symbol_of(key)
            return {"wtype": wtype, "item": item_id, "ref": f"new-{key}", "number": None,
                    "name": imported[key].get("name", key), "imported": True, "modes": banim.modes_of(base, symbol)}
        game = animations.get(anim) if isinstance(anim, int) else None
        if game is None:
            return None
        return {"wtype": wtype, "item": item_id, "ref": str(game.number), "number": game.number, "name": game.name,
                "imported": False, "modes": banim.modes_of(DECOMP_DIR, game.symbol)}

    result = []
    for d in banim.configs(DECOMP_DIR).get(conf, []):
        weapon = d["weapon"]
        wtype = WEAPON_TYPES.get(weapon)
        anim = left.pop(wtype, d["number"]) if wtype else d["number"]
        found = describe(wtype, None if weapon in WEAPON_TYPES else weapon, anim)
        if found:
            result.append({**found, "changed": bool(wtype) and wtype in changed})
    for wtype, anim in left.items():   # weapon types the class had no animation for
        found = describe(wtype, None, anim)
        if found:
            result.append({**found, "changed": True})
    return result


@app.get("/api/animations")
def animations():
    """Every battle animation of the game: number, name ("lorm_sp1") and the classes using it."""
    users: dict[int, list[str]] = {}
    confs = banim.configs(DECOMP_DIR)
    for e in state.get_decomp().classes.entries:
        for d in confs.get(e.fields.get("pBattleAnimDef", "").lstrip("&").strip(), []):
            users.setdefault(d["number"], [])
            if e.fields["number"] not in users[d["number"]]:
                users[d["number"]].append(e.fields["number"])
    return [{"number": a.number, "name": a.name, "classes": users.get(a.number, [])} for a in banim.table(DECOMP_DIR)]


@app.get("/api/animations/{ref}/{mode}.json")
def animation_mode(ref: str, mode: str, palette: int = 0):
    base, symbol = _animation_source(ref)
    try:
        _png, info = banim.mode_strip(base, symbol, mode, palette)
    except (KeyError, FileNotFoundError):
        raise HTTPException(404)
    return info


@app.get("/api/animations/{ref}/{mode}.png")
def animation_strip(ref: str, mode: str, palette: int = 0):
    """The mode's frames side by side; their durations come from the .json route."""
    base, symbol = _animation_source(ref)
    try:
        png, _info = banim.mode_strip(base, symbol, mode, palette)
    except (KeyError, FileNotFoundError):
        raise HTTPException(404)
    return Response(png, media_type="image/png", headers={"Cache-Control": "no-cache"})


class AnimationImportIn(BaseModel):
    url: str                # FE-Repo folder of one weapon ("1. Sword"), holding the script and its frames
    animation: str          # the animation's own folder (name, authors, license)
    classId: str
    wtype: str


def _download_frames(files: list[dict], names: list[str]) -> dict[str, Image.Image]:
    by_name = {f["name"].lower(): f for f in files if f["type"] == "file"}
    missing = [n for n in names if n.lower() not in by_name]
    if missing:
        raise banim_import.ImportError_("missingFrames", ", ".join(missing[:5]))
    with ThreadPoolExecutor(8) as pool:
        data = list(pool.map(lambda n: ferepo.fetch(by_name[n.lower()]["url"]), names))
    frames = {}
    for name, raw in zip(names, data):
        image = Image.open(io.BytesIO(raw))
        image.load()
        frames[name] = image
    return frames


# Palette pictures some FE-Repo animations come with ("Enemy Unit.png", "Green Unit.png"...).
_FACTION_FILES = {"enemy": ("enemy", "red"), "ally": ("green", "ally", "npc"), "other": ("purple", "other", "4th")}


def _faction_palettes(*folders: str) -> dict[str, list[int]]:
    """The animation's own palettes for the other armies, read from the palette pictures of its folders."""
    found: dict[str, list[int]] = {}
    for folder in folders:
        try:
            files = ferepo.folder_files(folder)
        except ferepo.FeRepoError:
            continue
        for f in files:
            name = f["name"].lower()
            if f["type"] != "file" or not name.endswith(".png") or name[:1].isdigit() and "_" in name:
                continue
            for faction, words in _FACTION_FILES.items():
                if faction not in found and any(w in name for w in words):
                    try:
                        image = Image.open(io.BytesIO(ferepo.fetch(f["url"])))
                    except (ferepo.FeRepoError, OSError):
                        continue
                    if image.mode == "P" and image.getpalette():
                        found[faction] = image.getpalette()[:48]
    return found


@app.post("/api/animations/import")
def import_animation(body: AnimationImportIn):
    """Download a FE-Repo animation (one weapon), convert it to the decomp's format, keep it in the project and
    give it to the class for that weapon type (ticket 44). The authors go to the project's CREDITS.txt."""
    project = state.require_project()
    if body.wtype not in WEAPON_TYPES.values():
        raise HTTPException(400, "unknownWeaponType")
    data = project.load("animations")
    data.setdefault("animations", {})
    data.setdefault("classes", {})
    key = str(max((int(k) for k in data["animations"]), default=0) + 1)
    try:
        files = ferepo.folder_files(body.url)
        scripts = [f for f in files if f["type"] == "file" and f["name"].lower().endswith(".txt")
                   and f["name"].lower() not in ("readme.txt", "credits.txt")]
        script_text = None
        for f in sorted(scripts, key=lambda f: "without_comment" not in f["name"].lower()):
            text = ferepo.fetch_text(f["url"])
            if "/// - Mode" in text:
                script_text = text
                break
        if script_text is None:
            raise banim_import.ImportError_("noScript")
        script = banim_import.parse_script(script_text)
        frames = _download_frames(files, script.files)
        converted = banim_import.convert(banim_import.symbol_of(key), script_text, frames,
                                         _faction_palettes(body.animation, body.url))
    except ferepo.FeRepoError as e:
        raise HTTPException(503 if str(e) in ("unreachable", "rateLimited") else 400, str(e)) from e
    except banim_import.ImportError_ as e:
        raise HTTPException(400, e.args[0]) from e
    folder = project.root / "assets" / ANIMATIONS_DIR / key
    if folder.exists():
        shutil.rmtree(folder)
    for rel, content in banim_import.stored_files(banim_import.symbol_of(key), converted).items():
        path = folder / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        if isinstance(content, bytes):
            path.write_bytes(content)
        else:
            path.write_text(content, encoding="utf-8", newline="\n")
    source = ferepo.describe(body.animation)
    if not source["authors"]:
        source["credits"] = ferepo.folder_credits(body.animation)
    weapon_folder = urllib.parse.unquote(body.url.rstrip("/")).split("/")[-1]
    data["animations"][key] = {"name": source["name"], "weapon": weapon_folder, "frames": converted.frames,
                               "sheets": len(converted.sheets), "source": source}
    data["classes"].setdefault(body.classId, {})[body.wtype] = f"new:{key}"
    problems = project.save("animations", data)
    project.update_credits()
    banim.clear_caches()
    return {"key": key, "problems": [p.to_dict() for p in problems]}


@app.delete("/api/animations/project/{key}")
def remove_animation(key: str):
    """Remove an imported animation: the classes using it get the game's animation back."""
    project = state.require_project()
    data = project.load("animations")
    data.get("animations", {}).pop(key, None)
    for weapons in data.get("classes", {}).values():
        for wtype in [w for w, a in weapons.items() if a == f"new:{key}"]:
            del weapons[wtype]
    data["classes"] = {c: w for c, w in data.get("classes", {}).items() if w}
    shutil.rmtree(project.root / "assets" / ANIMATIONS_DIR / key, ignore_errors=True)
    problems = project.save("animations", data)
    project.update_credits()
    banim.clear_caches()
    return {"problems": [p.to_dict() for p in problems]}


class ClassAnimationIn(BaseModel):
    wtype: str
    animation: str | int | None    # a game animation's number, "new:<key>", or None: the game's own again


@app.put("/api/classes/{class_id}/animations")
def set_class_animation(class_id: str, body: ClassAnimationIn):
    project = state.require_project()
    data = project.load("animations")
    weapons = data.setdefault("classes", {}).setdefault(class_id, {})
    if body.animation is None:
        weapons.pop(body.wtype, None)
    else:
        weapons[body.wtype] = body.animation
    data["classes"] = {c: w for c, w in data["classes"].items() if w}
    problems = project.save("animations", data)
    return {"problems": [p.to_dict() for p in problems]}


@app.get("/api/project/animations")
def project_animations():
    return _project_animations()


@app.get("/api/assets/portrait/{portrait_id}")
def portrait(portrait_id: int, face: bool = False, smile: bool = False, eyes: str | None = None):
    """Small portrait (menus), or the big one shown in dialogues with `face` (the project's imported
    sheet when it replaced this portrait); `smile` and `eyes` ("half", "closed"): the face as the
    dialogue's expression codes leave it."""
    sheet = _imported_sheet(portrait_id)
    if face and (smile or eyes):
        return _face_with_expression(portrait_id, sheet, smile, eyes)
    if sheet is not None:
        png = portraits.face_png(sheet) if face else portraits.chibi_png(sheet, scale=3)
        return Response(png, media_type="image/png", headers={"Cache-Control": "no-cache"})
    png = face_preview(DECOMP_DIR, portrait_id) if face else portrait_preview(DECOMP_DIR, portrait_id)
    if png is None:
        raise HTTPException(404)
    return Response(png, media_type="image/png")


@app.get("/api/assets/item-icon/{icon_id}")
def item_icon(icon_id: int):
    png = item_icon_preview(DECOMP_DIR, state.get_decomp().item_icon_files(), icon_id)
    if png is None:
        raise HTTPException(404)
    return Response(png, media_type="image/png")


def _face_with_expression(portrait_id: int, sheet, smile: bool, eyes: str | None) -> Response:
    if sheet is not None:
        positions = state.project.load("portraits").get(str(portrait_id))
    else:
        try:
            name = portraits.portrait_name(DECOMP_DIR, portrait_id)
            sheet = portraits.to_sheet(DECOMP_DIR, name)
        except (portraits.PortraitError, FileNotFoundError) as e:
            raise HTTPException(404, str(e)) from e
        positions = portraits.read_positions(DECOMP_DIR).get(name)
    png = portraits.face_png(sheet, smile=smile, eyes=eyes, positions=positions)
    return Response(png, media_type="image/png", headers={"Cache-Control": "no-cache"})


# ---------- imported portraits (phase 5) ----------

def _imported_sheet(portrait_id: int):
    """The project's sheet replacing a portrait (indexed), or None."""
    if state.project is None:
        return None
    entry = state.project.load("portraits").get(str(portrait_id))
    path = state.project.root / "assets" / entry["file"] if entry else None
    if path is None or not path.is_file():
        return None
    from PIL import Image

    with Image.open(path) as img:
        try:
            return portraits.indexed(img)[0]
        except portraits.PortraitError:
            return None


@app.get("/api/portraits/{portrait_id}/sheet.png")
def portrait_sheet(portrait_id: int):
    """The portrait as a 128 x 112 sheet: the project's imported one, else the game's."""
    import io

    sheet = _imported_sheet(portrait_id)
    if sheet is None:
        try:
            sheet = portraits.to_sheet(DECOMP_DIR, portraits.portrait_name(DECOMP_DIR, portrait_id))
        except (portraits.PortraitError, FileNotFoundError) as e:
            raise HTTPException(404, str(e)) from e
    out = io.BytesIO()
    sheet.save(out, "PNG")
    return Response(out.getvalue(), media_type="image/png", headers={"Cache-Control": "no-cache"})


@app.get("/api/portraits/{portrait_id}")
def portrait_info(portrait_id: int):
    """What the editor shows about a portrait: its name, the ids sharing its pictures, where its mouth
    and eyes go in the game, and the project's import."""
    imported = state.project.load("portraits").get(str(portrait_id)) if state.project else None
    if portraits.is_new(DECOMP_DIR, portrait_id):
        if imported is None:
            raise HTTPException(404, "unknownPortrait")
        return {"id": portrait_id, "name": imported.get("name") or portraits.new_name(portrait_id), "sharedWith": [],
                "original": None, "imported": imported, "added": True}
    try:
        name = portraits.portrait_name(DECOMP_DIR, portrait_id)
    except portraits.PortraitError as e:
        raise HTTPException(404, str(e)) from e
    names = portrait_names(DECOMP_DIR)
    return {"id": portrait_id, "name": name, "sharedWith": [i for i, n in enumerate(names) if n == name and i != portrait_id],
            "original": portraits.read_positions(DECOMP_DIR).get(name), "imported": imported, "added": False}


def _free_portrait_id() -> int:
    """The first id after the game's portraits that the project does not use yet."""
    used = set(_added_portraits())
    for pid in range(portraits.first_new_id(DECOMP_DIR), portraits.MAX_PORTRAIT_ID + 1):
        if pid not in used:
            return pid
    raise HTTPException(400, "noFreePortrait")


def _import_portrait(portrait_id: int, data: bytes, source: dict | None = None, name: str | None = None) -> dict:
    """Replace a portrait with a 128 x 112 sheet (16 colors at most): stored in the project's assets,
    mouth and eyes placed automatically; `source`: where it comes from (FE-Repo), for the credits.
    An id after the game's portraits adds a new portrait, called `name`."""
    import io

    from PIL import Image, UnidentifiedImageError

    project = state.require_project()
    try:
        if not portraits.is_new(DECOMP_DIR, portrait_id):
            portraits.portrait_name(DECOMP_DIR, portrait_id)
        with Image.open(io.BytesIO(data)) as img:
            sheet, _colors = portraits.indexed(img)
    except portraits.PortraitError as e:
        raise HTTPException(400, str(e)) from e
    except (UnidentifiedImageError, OSError) as e:
        raise HTTPException(400, "notAnImage") from e
    rel = f"{PORTRAITS_DIR}/{portrait_id}.png"
    target = project.root / "assets" / rel
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(data)
    entry = {"file": rel, **portraits.detect(sheet)}
    if source:
        entry["source"] = source
    stored = project.load("portraits")
    if portraits.is_new(DECOMP_DIR, portrait_id):
        old = stored.get(str(portrait_id)) or {}
        entry["name"] = (name or old.get("name") or (source or {}).get("name") or portraits.new_name(portrait_id))[:40]
    stored[str(portrait_id)] = entry
    problems = project.save("portraits", stored)
    project.update_credits()
    return {"id": portrait_id, "entry": entry, "problems": [p.to_dict() for p in problems]}


# Declared before /api/portraits/{portrait_id}: "new" is not a portrait id.
@app.post("/api/portraits/new")
async def add_portrait(file: UploadFile = File(...)):
    """A new portrait, after the game's ones, from a 128 x 112 sheet (named after the file)."""
    return _import_portrait(_free_portrait_id(), await file.read(), name=Path(file.filename or "").stem or None)


class PortraitNameIn(BaseModel):
    name: str


@app.patch("/api/portraits/{portrait_id}")
def rename_portrait(portrait_id: int, body: PortraitNameIn):
    """Rename a portrait the project adds (the name shown in the editors)."""
    project = state.require_project()
    stored = project.load("portraits")
    entry = stored.get(str(portrait_id))
    if entry is None or not portraits.is_new(DECOMP_DIR, portrait_id):
        raise HTTPException(404, "unknownPortrait")
    entry["name"] = body.name.strip()[:40] or portraits.new_name(portrait_id)
    return {"entry": entry, "problems": [p.to_dict() for p in project.save("portraits", stored)]}


@app.post("/api/portraits/{portrait_id}")
async def import_portrait(portrait_id: int, file: UploadFile = File(...)):
    return _import_portrait(portrait_id, await file.read())


class FeRepoIn(BaseModel):
    url: str


@app.post("/api/portraits/new/ferepo")
def add_ferepo_portrait(body: FeRepoIn):
    """A new portrait from FE-Repo; its authors and license go to the project's credits."""
    try:
        data = ferepo.fetch(body.url)
    except ferepo.FeRepoError as e:
        raise HTTPException(400, str(e)) from e
    return _import_portrait(_free_portrait_id(), data, ferepo.describe(body.url))


@app.post("/api/portraits/{portrait_id}/ferepo")
def import_ferepo_portrait(portrait_id: int, body: FeRepoIn):
    """A portrait of FE-Repo replaces this one; its authors and license go to the project's credits."""
    try:
        data = ferepo.fetch(body.url)
    except ferepo.FeRepoError as e:
        raise HTTPException(400, str(e)) from e
    return _import_portrait(portrait_id, data, ferepo.describe(body.url))


@app.get("/api/ferepo/portraits")
def ferepo_portraits(q: str = "", refresh: bool = False, folder: str = "", offset: int = 0, f2e: bool = False):
    """Portraits of FE-Repo matching a search (name, folder, authors), one page; and the folders to browse."""
    try:
        index, when = ferepo.load_index(refresh)
    except ferepo.FeRepoError as e:
        raise HTTPException(503, str(e)) from e
    entries, total = ferepo.search(index, ferepo.PORTRAITS, q, folder=folder, offset=max(0, offset), f2e_only=f2e)
    return {"entries": entries, "total": total, "indexDate": when, "folders": ferepo.folders(index, ferepo.PORTRAITS)}


@app.get("/api/ferepo/image")
def ferepo_image(url: str):
    """A FE-Repo picture (thumbnails of the browser), downloaded once then cached."""
    try:
        data = ferepo.fetch(url)
    except ferepo.FeRepoError as e:
        raise HTTPException(400, str(e)) from e
    kind = "image/gif" if data.startswith(b"GIF8") else "image/png"
    return Response(data, media_type=kind, headers={"Cache-Control": "max-age=86400"})


@app.get("/api/ferepo/animations")
def ferepo_animations(q: str = "", refresh: bool = False, folder: str = "", offset: int = 0, f2e: bool = False):
    """Battle animations of the FE-Repo (one folder each), searched like the portraits (ticket 44)."""
    try:
        index, when = ferepo.load_index(refresh)
    except ferepo.FeRepoError as e:
        raise HTTPException(503, str(e)) from e
    entries, total = ferepo.search(index, ferepo.ANIMATIONS, q, limit=60, folder=folder, offset=max(0, offset), f2e_only=f2e)
    return {"entries": entries, "total": total, "indexDate": when, "folders": ferepo.folders(index, ferepo.ANIMATIONS)}


@app.get("/api/ferepo/animation")
def ferepo_animation(url: str):
    """An animation's folder: its files, its weapons (subfolders) and its preview picture."""
    try:
        files = ferepo.folder_files(url)
    except ferepo.FeRepoError as e:
        raise HTTPException(503 if str(e) == "unreachable" else 400, str(e)) from e
    shown = ferepo.preview(files)
    weapons = [f for f in files if f["type"] == "dir"]
    if shown is None and weapons:   # no picture at the top: the first weapon's folder
        try:
            shown = ferepo.preview(ferepo.folder_files(weapons[0]["url"]))
        except ferepo.FeRepoError:
            pass
    return {"files": files, "weapons": [w["name"] for w in weapons], "preview": shown, **ferepo.describe(url)}


@app.delete("/api/portraits/{portrait_id}")
def remove_portrait(portrait_id: int):
    """Back to the game's portrait, or a new portrait removed (the imported sheet is deleted from the project)."""
    project = state.require_project()
    stored = project.load("portraits")
    entry = stored.pop(str(portrait_id), None)
    if entry:
        (project.root / "assets" / entry["file"]).unlink(missing_ok=True)
    problems = project.save("portraits", stored)
    project.update_credits()
    return {"problems": [p.to_dict() for p in problems]}


# ---------- build and test ----------

class TestOptionsIn(BaseModel):
    start: str | None = None
    simplePrologue: bool | None = None
    chapter: int | None = None


@app.get("/api/project/test-options")
def get_test_options():
    return state.require_project().test_options


@app.put("/api/project/test-options")
def put_test_options(body: TestOptionsIn):
    project = state.require_project()
    try:
        project.set_test_options(body.model_dump(exclude_none=True))
    except ProjectError as e:
        raise HTTPException(400, str(e))
    return project.test_options


class WorldMapIn(BaseModel):
    worldMap: bool


@app.get("/api/project/world-map")
def get_world_map():
    return {"worldMap": state.require_project().world_map}


@app.put("/api/project/world-map")
def put_world_map(body: WorldMapIn):
    """Ticket 39: chapters follow each other with or without the world map (exported patch too)."""
    project = state.require_project()
    project.set_world_map(body.worldMap)
    return {"worldMap": project.world_map}


class BuildIn(BaseModel):
    launch: bool = False


def _run_build(project: Project, launch: bool) -> None:
    st = state.build_status
    try:
        output = project.build(
            state.settings.rom_path, on_output=lambda line: st["log"].append(line.rstrip("\n")), for_test=launch
        )
        st["patch"] = str(output.patch_path) if output.patch_path else None
        if launch:
            state.emulator.launch(state.settings.mgba_path, output.rom_path, state.settings.keys)
        st["state"] = "done"
    except (ProjectError, BuildError, InvalidRomError, emulator.EmulatorError) as e:
        st["error"] = str(e)
        st["state"] = "error"
    except Exception as e:  # keep the server alive and report
        st["error"] = f"{type(e).__name__}: {e}"
        st["state"] = "error"
    finally:
        state.build_lock.release()


@app.post("/api/project/build")
def start_build(body: BuildIn):
    project = state.require_project()
    if not state.settings.has_rom:
        raise HTTPException(409, "noRom")
    if not state.build_lock.acquire(blocking=False):
        raise HTTPException(409, "buildRunning")
    state.build_status = {"state": "running", "log": [], "error": None, "patch": None, "launch": body.launch}
    threading.Thread(target=_run_build, args=(project, body.launch), daemon=True).start()
    return state.build_status


@app.get("/api/project/build")
def build_status(since: int = 0):
    st = state.build_status
    return {**st, "log": st["log"][since:], "logSize": len(st["log"])}


@app.get("/api/project/patch")
def download_patch():
    patch = state.build_status.get("patch")
    if not patch or not Path(patch).is_file():
        raise HTTPException(404)
    return FileResponse(patch, filename=Path(patch).name, media_type="application/octet-stream")


# ---------- feedback tickets ----------

tickets = TicketStore()


class TicketIn(BaseModel):
    body: str
    kind: str = "bug"
    priority: str = "normal"
    context: dict = {}
    images: list[str] = []  # data URLs


@app.get("/api/tickets")
def list_tickets():
    return tickets.list()


@app.post("/api/tickets")
def create_ticket(body: TicketIn):
    context = dict(body.context)
    if state.project:
        context.setdefault("project", state.project.meta.get("name", ""))
    try:
        return tickets.create(body.body, body.kind, body.priority, context, body.images)
    except TicketError as e:
        raise HTTPException(400, str(e))


@app.patch("/api/tickets/{ticket_id}")
def update_ticket(ticket_id: str, changes: dict):
    try:
        return tickets.update(ticket_id, changes)
    except KeyError:
        raise HTTPException(404)
    except TicketError as e:
        raise HTTPException(400, str(e))


@app.delete("/api/tickets/{ticket_id}")
def delete_ticket(ticket_id: str):
    try:
        tickets.delete(ticket_id)
    except KeyError:
        raise HTTPException(404)
    return {"ok": True}


@app.get("/api/tickets/images/{name}")
def ticket_image(name: str):
    path = tickets.image_path(name)
    if path is None:
        raise HTTPException(404)
    return FileResponse(path)


# ---------- interface ----------

# FE_MAKER_UI_DIST: another build of the interface (a second dev server beside the user's one)
UI_DIST = Path(os.environ.get("FE_MAKER_UI_DIST") or REPO_ROOT / "ui" / "dist")
if UI_DIST.is_dir():
    app.mount("/", StaticFiles(directory=UI_DIST, html=True), name="ui")
