"""Local HTTP API used by the FE Maker interface."""

from __future__ import annotations

import base64
import dataclasses
import os
import tempfile
import threading
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from . import emulator, ferepo
from .builder import BuildError
from .config import Settings, default_projects_dir
from .decomp import dialogues, events, fonts, mapobjects, maps, portraits, quotes, supports, tileedit, units
from .decomp.assets import face_preview, item_icon_preview, portrait_names, portrait_preview
from .decomp.assets import map_sprite as map_sprite_png
from .decomp.gamedata import ABILITIES, AFFINITIES, RANK_VALUES, RANKABLE_TYPES, WEAPON_TYPES, DecompData, GameDataError
from .paths import DECOMP_DIR, REPO_ROOT
from .project import DATA_FILES, PORTRAITS_DIR, Project, ProjectError, slugify
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
        })
    return result


@app.get("/api/chapters/{index}/map.png")
def chapter_map(index: int, fog: bool = False):
    """The chapter's map as painted in the project (the original one if never painted)."""
    try:
        assets = maps.chapter_map_assets(DECOMP_DIR, _chapter(index))
        project_maps = state.project.load("maps") if state.project else {}
        painted = project_maps.get("layouts", {}).get(assets.layout.stem)
        layout = (len(painted["rows"][0]), len(painted["rows"]), [c for row in painted["rows"] for c in row]) if painted else None
        edits = project_maps.get("tilesets", {}).get(assets.config.stem)
        assets = maps.with_palette(DECOMP_DIR, assets, project_maps.get("palettes", {}).get(assets.layout.stem))
        with tempfile.TemporaryDirectory() as folder:
            if edits:
                edited = tileedit.Tileset(DECOMP_DIR, assets.layout.stem, edits).edited_assets(Path(folder))
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


@app.get("/api/maps")
def list_maps():
    result = []
    for layout_id, layout in maps.layouts(DECOMP_DIR).items():
        width, height, _cells = maps.read_layout(layout["assets"].layout)
        result.append({"id": layout_id, "width": width, "height": height, "chapters": layout["chapters"],
                       "tileset": layout["assets"].config.stem})
    return result


@app.get("/api/maps/{layout_id}")
def get_map(layout_id: str):
    """The original layout, with what the editor needs about its tileset (terrains, duplicate metatiles)."""
    layout = _layout(layout_id)
    assets = layout["assets"]
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


@app.post("/api/maps/{layout_id}/objects")
def map_objects(layout_id: str, body: MapObjectsIn):
    """Villages, houses, chests, doors, walls and snags of the map being painted, with what the build
    does for them (see mapobjects.py) and their original location event, if any."""
    layout = _layout(layout_id)
    changes = body.changes
    if changes is None:
        changes = maps.read_changes(DECOMP_DIR, layout["changes"]) if layout["changes"] else []
    try:
        terrain = bytes(tileedit.Tileset(DECOMP_DIR, layout_id, body.tileset).terrain) if body.tileset else None
        objects = mapobjects.map_objects(DECOMP_DIR, layout_id, body.rows, changes, body.objects, terrain)
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


@app.post("/api/maps/{layout_id}/tileset")
def edited_tileset(layout_id: str, body: TilesetIn):
    """The tileset sheet with the project's added metatiles (not saved yet: the editor sends them)."""
    palette = maps.with_palette(DECOMP_DIR, _layout(layout_id)["assets"], body.palette).palette
    try:
        tileset = tileedit.Tileset(DECOMP_DIR, layout_id, body.edits)
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


@app.post("/api/maps/{layout_id}/transform")
def transform_tiles(layout_id: str, body: TransformIn):
    """A block of tiles mirrored or turned: new metatiles (and 8x8 tiles) added to the tileset when needed."""
    _layout(layout_id)
    try:
        tileset = tileedit.Tileset(DECOMP_DIR, layout_id, body.edits, body.painted)
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
def map_tileset(layout_id: str, palette: str | None = None):
    png = maps.render_tileset(maps.with_palette(DECOMP_DIR, _layout(layout_id)["assets"], palette))
    return Response(png, media_type="image/png", headers={"Cache-Control": "max-age=3600"})


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
    faces = [{"id": fid, "portrait": pid} for fid, pid in dialogues.read_faces(defs.read_text(encoding="utf-8")).items()]
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
        width, height, _cells = maps.read_layout(maps.chapter_map_assets(DECOMP_DIR, ch).layout)
    except maps.MapError:
        width = height = 0

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


@app.get("/api/assets/portrait/{portrait_id}")
def portrait(portrait_id: int, face: bool = False):
    """Small portrait (menus), or the big one shown in dialogues with `face` (the project's imported
    sheet when it replaced this portrait)."""
    sheet = _imported_sheet(portrait_id)
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
def ferepo_portraits(q: str = "", refresh: bool = False):
    """Portraits of FE-Repo matching a search (name, folder, authors)."""
    try:
        index, when = ferepo.load_index(refresh)
    except ferepo.FeRepoError as e:
        raise HTTPException(503, str(e)) from e
    entries, total = ferepo.search(index, ferepo.PORTRAITS, q)
    return {"entries": entries, "total": total, "indexDate": when}


@app.get("/api/ferepo/image")
def ferepo_image(url: str):
    """A FE-Repo picture (thumbnails of the browser), downloaded once then cached."""
    try:
        data = ferepo.fetch(url)
    except ferepo.FeRepoError as e:
        raise HTTPException(400, str(e)) from e
    return Response(data, media_type="image/png", headers={"Cache-Control": "max-age=86400"})


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
