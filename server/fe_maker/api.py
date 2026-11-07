"""Local HTTP API used by the FE Maker interface."""

from __future__ import annotations

import base64
import dataclasses
import io
import os
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import urllib.parse
import zipfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
from PIL import Image
from pydantic import BaseModel

from . import __version__, decompfetch, emulator, ferepo, native, newchapter, scope, validation
from .builder import BuildError
from .checks import run_checks
from .config import Settings, config_dir, default_projects_dir, find_tiled
from .decomp import (
    autotile,
    averagestats,
    banim,
    banim_import,
    battlebg,
    charpalettes,
    combat,
    convoy,
    dialogues,
    events,
    fonts,
    gameoptions,
    itemicons,
    mapobjects,
    maps,
    mapsprites,
    music,
    pieces,
    portraitcolors,
    portraits,
    prep,
    quotes,
    reach,
    skills,
    story,
    supports,
    tiled,
    tileedit,
    units,
)
from .decomp.assets import (
    ITEM_ICON_PALETTE,
    MAP_SPRITE_PALETTES,
    boss_icon,
    card_names,
    card_preview,
    face_preview,
    item_icon_preview,
    map_sprite_sheet,
    portrait_names,
    portrait_preview,
    read_agbpal,
    render_indexed,
)
from .decomp.assets import map_sprite as map_sprite_png
from .decomp.cparse import parse_int
from .decomp.gamedata import (
    ABILITIES,
    AFFINITIES,
    LEVEL_BONUS_FIELDS,
    NAMED_GENERICS,
    NEW_CHARACTER_PREFIX,
    NEW_CLASS_PREFIX,
    RANK_VALUES,
    RANKABLE_TYPES,
    WEAPON_TYPES,
    DecompData,
    GameDataError,
)
from .paths import DECOMP_DIR, REPO_ROOT
from .project import ANIMATIONS_DIR, DATA_FILES, PORTRAITS_DIR, Project, ProjectError, slugify
from .rom import InvalidRomError
from .tickets import TicketError, TicketStore

LANGUAGES = ("fr", "en")  # ui/src/locales (es.json and it.json are set aside for a later version)

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
        "version": __version__,
        "hasRom": s.has_rom,
        "language": s.language,
        "mgbaPath": s.mgba_path,
        "keys": s.keys,
        "gbaButtons": emulator.GBA_BUTTONS,
        "recentProjects": s.recent_projects,
        "defaultProjectsDir": str(default_projects_dir()),
        "project": _project_info(state.project) if state.project else None,
    }


@app.get("/api/checks")
def checks():
    """What this computer still lacks to run FE Maker (checks.py)."""
    return run_checks(state.settings)


@app.post("/api/decomp/download")
def download_decomp():
    """First launch of a release: the decomp is downloaded (decompfetch.py)."""
    try:
        decompfetch.fetch()
    except decompfetch.DecompFetchError as e:
        raise HTTPException(502, str(e)) from e
    return run_checks(state.settings)


@app.post("/api/toolchain/download")
def download_toolchain():
    """First launch on Windows: the build tools that replace Docker (native/), then the first build starts."""
    try:
        native.fetch_toolchain()
    except native.NativeBuildError as e:
        raise HTTPException(502, str(e)) from e
    return run_checks(state.settings)


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

class BlankIn(BaseModel):
    characters: bool = True
    title: str = ""
    hero: str = ""


class CreateProjectIn(BaseModel):
    name: str
    author: str = ""
    folder: str | None = None
    blank: BlankIn | None = None   # ticket 66, newchapter.start_blank


class OpenProjectIn(BaseModel):
    path: str


def _project_info(p: Project) -> dict:
    return {"path": str(p.root), "name": p.name, "meta": p.meta}


def _game_enemies() -> list[str]:
    """The game's named characters only ever met as enemies: they come after the allies in the list (ticket 85)."""
    sides: dict[str, set] = {}
    for group in units.read_unit_groups(DECOMP_DIR).values():
        for unit in group.units:
            sides.setdefault(str(unit.get("character")), set()).add(unit.get("side"))
    return [name for name, seen in sides.items() if name.startswith("CHARACTER_") and seen == {"enemy"}]


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
        project = Project.create(folder, body.name.strip(), body.author.strip())
        # Strength and Magic apart in every new hack (ticket 27); Project.create alone stays the original game
        project.set_game_options({**project.game_options, "strMagSplit": True, "skills": True})
        if body.blank is not None:
            newchapter.start_blank(project, body.blank.characters, body.blank.title, body.blank.hero)
            project.set_show_original(False)
        return _open(project)
    except ProjectError as e:
        raise HTTPException(400, str(e))


@app.post("/api/projects/open")
def open_project(body: OpenProjectIn):
    try:
        project = Project(Path(body.path))
        newchapter.tidy_blank(project)
        newchapter.tidy_scripts(project)
        return _open(project)
    except ProjectError as e:
        raise HTTPException(400, e.code or str(e))


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


class NewCharacterIn(BaseModel):
    ally: bool


@app.post("/api/characters/new")
def new_character(body: NewCharacterIn):
    """Sheet of a character to add, on a free entry of the game's table, and the raw-numbered sheet of that
    entry it replaces in the project's list."""
    project = state.require_project()
    characters = project.load("characters")
    try:
        reuse = project.load("chapters").get("blankCharacters", False)
        record = DecompData(project.decomp_dir).new_character(body.ally, {c["id"] for c in characters}, reuse)
    except GameDataError as e:
        raise HTTPException(409, str(e)) from e
    if not record["id"].startswith(NEW_CHARACTER_PREFIX):
        return {"record": record, "replaces": None}
    number = int(record["id"].removeprefix(NEW_CHARACTER_PREFIX), 16)
    replaces = next((c["id"] for c in characters
                     if not c["id"].startswith("CHARACTER_") and parse_int(c["id"]) == number), None)
    return {"record": record, "replaces": replaces}


class NewClassIn(BaseModel):
    model: str


@app.post("/api/classes/new")
def new_class(body: NewClassIn):
    """Sheet of a class to add after the game's classes, copying a model class."""
    project = state.require_project()
    try:
        return DecompData(project.decomp_dir).new_class(body.model, {c["id"] for c in project.load("classes")})
    except GameDataError as e:
        raise HTTPException(409, str(e)) from e


class NewItemIn(BaseModel):
    model: str


@app.post("/api/items/new")
def new_item(body: NewItemIn):
    """Sheet of an item to add after the game's items, copying a model item (weapon, staff, consumable...)."""
    project = state.require_project()
    try:
        return DecompData(project.decomp_dir).new_item(body.model, {i["id"] for i in project.load("items")})
    except GameDataError as e:
        raise HTTPException(409, str(e)) from e


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
    animated = validation.animated_weapons(d, _project_animations())
    char_names = {c["id"]: c["name"] for c in d.export_characters()}
    return {
        "classes": classes,  # original game classes (the project's own are in data/classes)
        # with the battle animations the project gave the classes (ticket 50: a mage given a sword animation)
        "classFacts": {cid: {**facts, "animatedWeapons": animated.get(cid, facts["animatedWeapons"])}
                       for cid, facts in d.class_facts().items()},
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
        "affinityBonuses": combat.read_affinity_bonuses(DECOMP_DIR),
        "abilities": list(ABILITIES.values()),
        "weaponTypes": list(WEAPON_TYPES.values()),
        "rankableTypes": RANKABLE_TYPES,
        "spellItems": d.spell_items(),
        "ranks": list(RANK_VALUES),
        "iconCount": len(d.item_icon_files()),
        "portraits": _portrait_names(),
        "firstNewPortrait": portraits.first_new_id(DECOMP_DIR),
        "portraitCards": card_names(DECOMP_DIR),
        "gameEnemies": _game_enemies(),
        "namedGenerics": list(NAMED_GENERICS),
        "gameLevels": {c["id"]: c["level"] for c in d.export_characters()},
        "descriptions": state.get_decomp().descriptions(),
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


def _has_prep(index: int, chapter: dict, stored: dict, scripts: dict) -> bool:
    symbol = _event_symbol(chapter)
    scene = units.beginning_scene(DECOMP_DIR, symbol) if symbol else None
    if scene in scripts:
        found = prep.scene_has_it(scripts[scene])
    else:
        found = bool(scene) and prep.SCRIPT in units.scene_text(DECOMP_DIR, scene)
    return prep.default(index, stored, found)


@app.get("/api/chapters")
def list_chapters():
    d = state.get_decomp()
    # titles of the chapters the project adds (newchapter.py)
    stored = state.project.load("chapters") if state.project is not None else {}
    titles = stored.get("titles", {})
    # A blank project's editors only show its own chapters (newchapter.py)
    shown = None
    if stored.get("blank"):
        shown = newchapter.reached_chapters(d.chapter_links(state.project.load("dialogues").get("scripts", {})))
        shown |= {int(k) for k in stored.get("added", {})}
    scripts = state.project.load("dialogues").get("scripts", {}) if state.project is not None else {}
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
            "title": titles.get(str(i)) or (d.texts.get_name(title_id) if title_id in d.texts.messages else ""),
            "added": str(i) in stored.get("added", {}),
            "hidden": shown is not None and i not in shown,
            "map": layout,
            "events": _event_symbol(ch),
            "convoy": convoy.has_convoy(i, stored),   # unless changed (tickets 29, 106)
            "prep": _has_prep(i, ch, stored, scripts),   # unless changed (ticket 107)
            "fog": ch.get("initialFogLevel", 0),   # vision range in fog of war, 0: no fog
            "wallHp": ch.get("mapCrackedWallHeath", 50),
            "weather": ch.get("initialWeather", "fine"),
            "battleBg": ch.get("battleTileSet", 0),
            "camera": [ch.get("initialPosX", 0), ch.get("initialPosY", 0)],
            "levelBonus": {mode: ch.get(field, 0) for mode, field in LEVEL_BONUS_FIELDS.items()},
        })
    return result


class ScopeIn(BaseModel):
    chapters: list[int]
    characters: list[str]
    classes: list[str]
    items: list[str]
    supports: bool = True
    title: str = ""
    hero: str = ""


@app.get("/api/project/scope")
def project_scope():
    """What the project keeps of the game (scope.py, ticket 71)."""
    return scope.contents(state.require_project())


@app.post("/api/project/scope")
def set_project_scope(body: ScopeIn):
    project = state.require_project()
    if state.build_lock.locked():
        raise HTTPException(409, "buildRunning")
    return scope.apply(project, body.chapters, body.characters, body.classes, body.items, body.supports, body.title, body.hero)


class NewChapterIn(BaseModel):
    after: int
    width: int = 15
    height: int = 10
    title: str = ""


@app.post("/api/chapters/new")
def new_chapter(body: NewChapterIn):
    """A chapter after `after`, on a free slot of the game's chapters (newchapter.py)."""
    project = state.require_project()
    try:
        index = newchapter.add_chapter(project, body.after, body.width, body.height, body.title)
    except newchapter.ChapterError as e:
        raise HTTPException(409, str(e)) from e
    return {"index": index, "problems": [p.to_dict() for p in project.validate()]}


@app.get("/api/chapters/{index}/music")
def chapter_music(index: int):
    """The songs the project imported for this chapter, by phase."""
    stored = state.require_project().load("music")
    phases = stored.get("chapters", {}).get(str(index), {})
    return {phase: {"key": key, **stored.get("songs", {}).get(key, {})} for phase, key in phases.items()}


@app.post("/api/chapters/{index}/music")
async def import_chapter_music(index: int, file: UploadFile = File(...), phase: str = Form("bluePhase")):
    """A MIDI file from the PC as this chapter's music for a phase, with the game's player phase instruments."""
    project = state.require_project()
    data = await file.read()
    try:
        music.check_midi(data)
    except music.MusicError as e:
        raise HTTPException(400, str(e)) from e
    if phase not in music.PHASES:
        raise HTTPException(400, "unknownPhase")
    stored = project.load("music")
    name = Path(file.filename or "").stem or "song"
    key = music.safe_key(name)
    folder = project.root / "assets" / "music"
    folder.mkdir(parents=True, exist_ok=True)
    (folder / f"{key}.mid").write_bytes(data)
    stored.setdefault("songs", {})[key] = {"name": name[:60], "voicegroup": music.DEFAULT_VOICEGROUP,
                                           "volume": music.DEFAULT_VOLUME}
    stored.setdefault("chapters", {}).setdefault(str(index), {})[phase] = key
    return {"problems": [p.to_dict() for p in project.save("music", stored)]}


@app.delete("/api/chapters/{index}/music/{phase}")
def remove_chapter_music(index: int, phase: str):
    """The chapter plays the game's music again for that phase."""
    project = state.require_project()
    stored = project.load("music")
    stored.get("chapters", {}).get(str(index), {}).pop(phase, None)
    return {"problems": [p.to_dict() for p in project.save("music", stored)]}


@app.get("/api/chapters/free")
def free_chapters():
    """How many chapters can still be added."""
    project = state.require_project()
    taken = {int(k) for k in project.load("chapters").get("added", {})}
    return {"free": len(newchapter.free_slots(DecompData(project.decomp_dir), project.load("dialogues").get("scripts", {}),
                                               taken, project.load("chapters").get("blank", False)))}


@app.get("/api/chapters/overview")
def chapters_overview():
    """Every chapter's original objective and unit groups (sides only), for the Campaign graph's cards in one
    request; the page applies the project's edits as for the selected chapter's sheet."""
    d = state.get_decomp()
    groups = units.read_unit_groups(DECOMP_DIR)
    result = {}
    for i, ch in enumerate(maps.chapter_settings(DECOMP_DIR)):
        symbol = _event_symbol(ch)
        if not symbol:
            continue
        try:
            objective = _project_objective(d.read_objective(i), i)
        except Exception:
            objective = None
        result[i] = {
            "objective": objective,
            "groups": [{"name": g["name"], "origin": g.get("origin"),
                        "units": [{"side": u.get("side")} for u in (groups[g["name"]].units if g["name"] in groups else [])]}
                       for g in units.chapter_unit_groups(DECOMP_DIR, symbol)],
        }
    return result


@app.get("/api/chapters/links")
def chapter_links():
    """For each chapter (by index), the event commands that start another chapter (story.py), the
    project's edited scripts included: the graph of how chapters follow each other (ticket 31)."""
    edited = state.project.load("dialogues").get("scripts", {}) if state.project else {}
    decomp = state.get_decomp()
    return {"links": decomp.chapter_links(edited), "endings": decomp.chapter_endings(), "kinds": story.CHANGE_OPS,
            "toChapter": list(story.TO_CHAPTER)}


class ReachUnitIn(BaseModel):
    classId: str
    x: int
    y: int
    items: list[str] = []
    ai: list[int] | None = None   # taken into account for enemies
    mag: int = 0   # for staves reaching Mag/2 tiles



class ReachIn(BaseModel):
    units: list[ReachUnitIn]


@app.post("/api/chapters/{index}/reach")
def chapter_reach(index: int, body: ReachIn):
    """Where these units can go and strike on the chapter's map as painted in the project (decomp/reach.py)."""
    project = state.require_project()
    try:
        stem = maps.chapter_map_assets(DECOMP_DIR, _chapter(index)).layout.stem
        stored = project.load("maps")
        painted = stored.get("layouts", {}).get(stem)
        assets = maps.layout_assets(DECOMP_DIR, stem, stored.get("bases", {}).get(stem))
        edits = stored.get("tilesets", {}).get(assets.config.stem)
        terrains = bytes(tileedit.Tileset(DECOMP_DIR, _tile_layout(stem, assets), edits).terrain) if edits \
            else maps.read_config(assets.config)[1]
        width, height, cells = maps.read_layout(assets.layout)
    except (maps.MapError, tileedit.TileEditError) as e:
        raise HTTPException(404, str(e)) from e
    rows = painted["rows"] if painted else [cells[y * width:(y + 1) * width] for y in range(height)]
    terrain = [[terrains[m] if m < len(terrains) else 0 for m in row] for row in rows]
    height, width = len(rows), len(rows[0])
    classes = {c["id"]: c for c in project.load("classes")}
    items = project.load("items")
    costs = maps.movement_costs(DECOMP_DIR)
    moves: set[tuple[int, int]] = set()
    strikes: set[tuple[int, int]] = set()
    heals: set[tuple[int, int]] = set()
    for unit in body.units:
        cls = classes.get(unit.classId)
        table = costs.get(cls.get("movement") or "") if cls else None
        if table is None:
            continue
        can_move, can_strike = reach.ai_reach(unit.ai)
        own = reach.movement(terrain, table, cls["mov"] if can_move else 0, unit.x, unit.y)
        moves |= own
        if can_strike:
            strikes |= reach.strikes(own, reach.weapon_ranges(unit.items, items), width, height)
            heals |= reach.strikes(own, reach.staff_ranges(unit.items, items, unit.mag), width, height)
    return {"move": sorted(moves), "strike": sorted(strikes - moves), "heal": sorted(heals - moves - strikes)}


def _layout_changes(layout_id: str, project_maps: dict) -> list[dict]:
    """The changes of a map: the project's, else the original ones."""
    stored = project_maps.get("changes", {}).get(layout_id)
    if stored is not None:
        return stored
    original = maps.layouts(DECOMP_DIR).get(layout_id, {}).get("changes")
    return maps.read_changes(DECOMP_DIR, original) if original else []


@app.get("/api/chapters/{index}/map.png")
def chapter_map(index: int, fog: bool = False, change: int | None = None):
    """The chapter's map as painted in the project (the original one if never painted), with a change if asked."""
    try:
        assets = maps.chapter_map_assets(DECOMP_DIR, _chapter(index))
        project_maps = state.project.load("maps") if state.project else {}
        painted = project_maps.get("layouts", {}).get(assets.layout.stem)
        layout = (len(painted["rows"][0]), len(painted["rows"]), [c for row in painted["rows"] for c in row]) if painted else None
        layout_id = assets.layout.stem
        for shown in _layout_changes(layout_id, project_maps) if change is not None else []:
            if shown["id"] == change:
                layout = maps.with_change(layout or maps.read_layout(assets.layout), shown)
        assets = maps.layout_assets(DECOMP_DIR, layout_id, project_maps.get("bases", {}).get(layout_id),
                                    project_maps.get("palettes", {}).get(layout_id))
        edits = project_maps.get("tilesets", {}).get(assets.config.stem)
        with tempfile.TemporaryDirectory() as folder:
            assets = maps.with_colors(DECOMP_DIR, assets, project_maps.get("paletteColors", {}), Path(folder))
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
        "terrainEffects": maps.terrain_effects(DECOMP_DIR),
        # Palettes of the tileset in the game, and the map's own (ticket 16)
        "palette": maps.palette_symbol(DECOMP_DIR, assets.palette),
        "palettes": [{**p, "colors": _palette_colors(p["id"])[:16], "lines": _palette_lines(p["id"])}
                     for p in maps.palette_choices(DECOMP_DIR, assets)],
        # Tile sheets of the game the map can be drawn with, and the map's own (ticket 21)
        "originalBase": layout["assets"].config.stem,
        "bases": [{"id": b["id"], "name": maps.SHEET_NAMES.get(b["id"], b["id"]), "chapters": b["chapters"],
                   "palette": maps.asset_table(DECOMP_DIR)[b["map"]["paletteId"]]}
                  for b in maps.base_choices(DECOMP_DIR)],
        # Original map changes (doors, villages...); a map without any gets its change set when one is added
        "changes": maps.read_changes(DECOMP_DIR, layout["changes"]) if layout["changes"] else [],
    }


def _palette_colors(symbol: str) -> list[str]:
    """The colors of a map palette's normal lines (#rrggbb)."""
    colors = maps.read_jasc_palette(maps.asset_files(DECOMP_DIR)[symbol])[:maps.FOG_OFFSET]
    return [f"#{r:02x}{g:02x}{b:02x}" for r, g, b in colors]


def _palette_lines(symbol: str) -> list[list[str]]:
    colors = _palette_colors(symbol)
    return [colors[i: i + 16] for i in range(0, len(colors), 16)]


class MapObjectsIn(BaseModel):
    rows: list[list[int]]
    changes: list[dict] | None = None   # None: the original change set
    objects: dict = {}
    tileset: dict | None = None         # metatiles added to the tileset (tileedit.py)
    base: str | None = None             # another tile sheet of the game (ticket 21)
    offset: tuple[int, int] = (0, 0)    # where the map moved when its left or top side did


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
        objects = mapobjects.map_objects(DECOMP_DIR, layout_id, body.rows, changes, body.objects, terrain, assets, body.offset)
    except (IndexError, ValueError) as e:
        raise HTTPException(400, str(e)) from e
    dx, dy = body.offset
    events = {(x + dx, y + dy): e for (x, y), e in state.get_decomp().map_object_events(layout_id).items()}
    for obj in objects:
        found = next((events[tuple(c)] for c in obj["cells"]
                      if tuple(c) in events and mapobjects.event_matches(events[tuple(c)]["kind"], obj["kind"])), None)
        obj["event"] = {k: v for k, v in found.items() if k != "span"} if found else None
    return {"objects": objects, "defaults": mapobjects.DEFAULTS,
            "faces": [{"id": fid, "portrait": portrait} for fid, portrait in mapobjects.FACES.items()]}


class TilesetIn(BaseModel):
    edits: dict | None = None
    palette: str | None = None   # another palette of the tileset
    base: str | None = None      # another tile sheet of the game
    colors: dict = {}            # retouched palette colors, by palette


@app.post("/api/maps/{layout_id}/tileset")
def edited_tileset(layout_id: str, body: TilesetIn):
    """The tileset sheet with the project's added metatiles (not saved yet: the editor sends them)."""
    _layout(layout_id)
    assets = maps.layout_assets(DECOMP_DIR, layout_id, body.base, body.palette)
    try:
        tileset = tileedit.Tileset(DECOMP_DIR, _tile_layout(layout_id, assets), body.edits)
        with tempfile.TemporaryDirectory() as folder:
            palette = maps.with_colors(DECOMP_DIR, assets, body.colors, Path(folder)).palette
            assets = dataclasses.replace(tileset.edited_assets(Path(folder)), palette=palette)
            png = maps.render_tileset(assets)
            codes = maps.render_tileset(assets, coded=True)
            duplicates = maps.duplicate_metatiles(assets)
    except tileedit.TileEditError as e:
        raise HTTPException(409, str(e)) from e
    # Added metatiles are never hidden, even when they look like another one.
    for slot in (body.edits or {}).get("metatiles", {}):
        duplicates[int(slot)] = False
    return {"sheet": "data:image/png;base64," + base64.b64encode(png).decode(), "terrains": list(tileset.terrain),
            "codes": "data:image/png;base64," + base64.b64encode(codes).decode(),
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
def map_tileset(layout_id: str, palette: str | None = None, base: str | None = None, coded: bool = False):
    _layout(layout_id)
    png = maps.render_tileset(maps.layout_assets(DECOMP_DIR, layout_id, base, palette), coded)
    return Response(png, media_type="image/png", headers={"Cache-Control": "max-age=3600"})


class MapFillIn(BaseModel):
    rows: list[list[int]]
    keep: list[tuple[int, int]] = []
    base: str | None = None


class AutotileIn(BaseModel):
    rows: list[list[int]]
    cells: list[tuple[int, int]]
    base: str | None = None


@app.get("/api/maps/{layout_id}/brushes")
def map_brushes(layout_id: str, base: str | None = None):
    """The ground terrains of this map's tile sheet, for the brushes whose tiles join by themselves."""
    _layout(layout_id)
    config = maps.layout_assets(DECOMP_DIR, layout_id, base).config
    return {"brushes": autotile.brushes(autotile.learn(DECOMP_DIR, config))}


@app.post("/api/maps/{layout_id}/autotile")
def map_autotile(layout_id: str, body: AutotileIn):
    """Join the painted cells with what is around them, as the game's maps do."""
    _layout(layout_id)
    config = maps.layout_assets(DECOMP_DIR, layout_id, body.base).config
    return {"rows": autotile.paint(autotile.learn(DECOMP_DIR, config), body.rows, body.cells)}


@app.post("/api/maps/{layout_id}/fill")
def map_fill(layout_id: str, body: MapFillIn):
    """Patches of other grounds in the map's empty space, joined as the game's maps do."""
    _layout(layout_id)
    config = maps.layout_assets(DECOMP_DIR, layout_id, body.base).config
    costs = maps.terrain_effects(DECOMP_DIR)["foot"]
    return {"rows": autotile.fill(autotile.learn(DECOMP_DIR, config), body.rows, costs, body.keep)}


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


MESSAGE_ARGS = {"Text": 0, "TEXTSHOW": 0, "TEXTCONT": 0, "Text_BG": 1}


def script_message_ids(commands: list[dict]) -> list[int]:
    """The game's messages a sequence shows, in order (the project's own, "new:<key>", are listed by the editor)."""
    ids: list[int] = []
    for c in commands:
        at = MESSAGE_ARGS.get(c.get("op", ""))
        args = c.get("args") or []
        if at is None or at >= len(args):
            continue
        try:
            value = int(str(args[at]).strip(), 0)
        except ValueError:
            continue
        if value not in ids:
            ids.append(value)
    return ids


@app.get("/api/chapters/{index}/dialogues")
def chapter_dialogues(index: int):
    """Scenes of a chapter that show messages (what starts them) and their messages as steps,
    as in the original game (the editor adds the project's edits)."""
    _chapter(index)
    decomp = state.get_decomp()
    scenes = decomp.chapter_dialogues(index)
    if state.project is not None and index in state.project.load("chapters").get("cleared", []):
        # its events are emptied at build time (newchapter.py): only its opening and ending are left, rewritten
        scenes = [{**s, "messages": []} for s in scenes if s["trigger"]["kind"] in ("beginning", "ending")
                  and not s["trigger"].get("via")]
    if state.project is not None:
        # a sequence edited in the project shows the game's messages it uses now (ticket 160)
        edited = state.project.load("dialogues").get("scripts", {})
        scenes = [{**s, "messages": script_message_ids(edited[s["script"]])} if s["script"] in edited else s for s in scenes]
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
    if state.project is not None:
        # those of characters out of the project's list stay in the game, nobody meets them (ticket 100)
        kept = {c["id"] for c in state.project.load("characters")}
        scenes = [s for s in scenes if all(not who or who in kept for who in (s["trigger"].get("a"), s["trigger"].get("b")))]
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
            "addable": list(events.ADDABLE), "memoryFlags": list(events.MEMORY_FLAGS),
            "chapters": [{"index": i, "title": c["title"]} for i, c in enumerate(list_chapters()) if not c["hidden"]],
            "songs": constants("include/constants/songs.h", "SONG_"),
            "backgrounds": constants("include/constants/backgrounds.h", "BG_"), "scripts": state.get_decomp().script_names(),
            "items": [{"id": i["id"], "name": i["name"]} for i in
                      (state.project.load("items") if state.project else state.get_decomp().export_items())]}


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


class UnitStatsIn(BaseModel):
    character: str
    classId: str
    level: int
    autolevel: bool
    side: str
    items: list[str] = []


@app.post("/api/units/stats")
def unit_stats(body: UnitStatsIn):
    """Stats of a unit entering a chapter, as the game computes them (decomp/averagestats.py)."""
    project = state.require_project()
    classes = {c["id"]: c for c in project.load("classes")}
    cls = classes.get(body.classId)
    if cls is None:
        raise HTTPException(404, f"Unknown class {body.classId}")
    character = next((c for c in project.load("characters") if c["id"] == body.character), None)
    by_id = {i["id"]: i for i in project.load("items")}
    return {
        "stats": averagestats.average_stats(character, cls, body.level, body.autolevel, body.side,
                                            state.get_decomp().character_number(body.character),
                                            classes if project.game_options.get("strMagSplit") else None),
        "ranks": validation.unit_ranks(character, cls, [by_id[i] for i in body.items if i in by_id], body.autolevel),
    }


@app.get("/api/chapters/{index}/units")
def chapter_units(index: int):
    ch = _chapter(index)
    symbol = _event_symbol(ch)
    groups = units.read_unit_groups(DECOMP_DIR)
    # Groups edited in the project replace the original ones.
    edited = state.project.load("chapters").get("unitGroups", {}) if state.project else {}
    changes: list[dict] = []
    try:
        layout_path = maps.chapter_map_assets(DECOMP_DIR, ch).layout
        width, height, _cells = maps.read_layout(layout_path)
    except maps.MapError:
        width = height = 0
    else:
        changes = _layout_changes(layout_path.stem, state.project.load("maps") if state.project else {})
        # A painted map may have another size (ticket 40: the picture was squeezed into the old grid).
        painted = (state.project.load("maps").get("layouts", {}).get(layout_path.stem) if state.project else None)
        if painted and painted.get("rows"):
            width, height = len(painted["rows"][0]), len(painted["rows"])

    def group_units(name: str) -> list[dict]:
        if name in edited:
            # Groups edited before units could be added or removed have no "slot": units were in order.
            macros = units.ai_macros(DECOMP_DIR)
            drops = {u["slot"]: u["itemDrop"] for u in groups[name].units} if name in groups else {}
            return [{**({"slot": i} if "slot" not in u else {}), "itemDrop": drops.get(u.get("slot", i), False), **u,
                     # Projects saved before the AI was editable store it as the original C text.
                     "ai": units.parse_ai(u["ai"], macros) if isinstance(u.get("ai"), str) else u.get("ai", [0, 0, 0, 0])}
                    for i, u in enumerate(edited[name])]
        return groups[name].units if name in groups else []

    return {
        "width": width,
        "height": height,
        "changes": [{key: c[key] for key in ("id", "x", "y", "w", "h")} for c in changes],
        "groups": [
            {**g, "units": group_units(g["name"]), "edited": g["name"] in edited}
            for g in (units.chapter_unit_groups(DECOMP_DIR, symbol) if symbol else [])
        ],
        "loadedBy": _new_groups_scenes(index),
    }


LOAD_OPS = {"LOAD1", "LOAD2", "LOAD3"}


def _new_groups_scenes(index: int) -> dict[str, list[str]]:
    """The scenes (their scripts, edited in the project) that bring each group the project made for this chapter."""
    if state.project is None:
        return {}
    made = [n for n, g in state.project.load("chapters").get("newGroups", {}).items() if g.get("chapter") == index]
    dialogues = state.project.load("dialogues")
    # an event's sequence edited in the project, or an event made in the Dialogues tab ("new:<kind>", ticket 159)
    sequences = list(dialogues.get("scripts", {}).items())
    sequences += [(f"new:{q.get('kind')}", q["commands"]) for q in dialogues.get("quotes", [])
                  if q.get("commands") and q.get("chapter") == index]
    return {name: sorted({script for script, commands in sequences
                          if any(c.get("op") in LOAD_OPS and name in (c.get("args") or []) for c in commands)})
            for name in made}


@app.get("/api/chapters/{index}/objective")
def chapter_objective(index: int):
    """The chapter's original objective (the project's edit, if any, is in data/chapters.json)."""
    _chapter(index)
    return _project_objective(state.get_decomp().read_objective(index), index)


def _project_objective(objective: dict, index: int) -> dict:
    """A chapter the project cleared (newchapter.py) has no boss of the game's story to start from (ticket 149)."""
    if state.project and index in state.project.load("chapters").get("cleared", []):
        return {**objective, "boss": None}
    return objective


def _game_class(class_id: str):
    """The game's class entry for a class id; a class the project adds shows its model's sprites and animations."""
    if class_id.startswith(NEW_CLASS_PREFIX) and state.project is not None:
        class_id = next((c.get("model") for c in state.project.load("classes") if c["id"] == class_id), class_id)
    return next((e for e in state.get_decomp().classes.entries if e.fields["number"] == class_id), None)


def _imported_map_sprite(class_id: str) -> tuple[Path, tuple[int, int]] | None:
    """The folder and frame size of the map sprite the project imports for a class, if any."""
    if state.project is None:
        return None
    stored = state.project.load("mapsprites")
    key = stored.get("classes", {}).get(class_id)
    info = stored.get("sprites", {}).get(key) if key else None
    if not info:
        return None
    w, h = next(s for s, c in mapsprites.WAIT_SIZES.items() if c == info["size"])
    return state.project.root / "assets" / "mapsprites" / key, (w, h // 3)


def _import_map_sprite(class_id: str, stand: bytes, walk: bytes | None, name: str, source: dict | None = None) -> dict:
    """A map sprite (standing sheet, moving sheet if given) for a class, converted to the player palette."""
    project = state.require_project()
    if not any(c["id"] == class_id for c in project.load("classes")):
        raise HTTPException(404, "unknownClass")
    try:
        stand_png, size, walk_png = mapsprites.convert(stand, walk, read_agbpal(DECOMP_DIR / MAP_SPRITE_PALETTES["player"]))
    except mapsprites.MapSpriteError as e:
        raise HTTPException(400, str(e)) from e
    stored = project.load("mapsprites")
    key = mapsprites.safe_key(class_id.removeprefix("CLASS_"))
    folder = project.root / "assets" / "mapsprites" / key
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "stand.png").write_bytes(stand_png)
    if walk_png is not None:
        (folder / "walk.png").write_bytes(walk_png)
    elif (folder / "walk.png").exists():
        (folder / "walk.png").unlink()
    entry = {"name": name[:60], "size": size, "walk": walk_png is not None}
    if source:
        entry["source"] = source
    stored.setdefault("sprites", {})[key] = entry
    stored.setdefault("classes", {})[class_id] = key
    problems = project.save("mapsprites", stored)
    project.update_credits()
    return {"entry": entry, "problems": [p.to_dict() for p in problems]}


class MapSpriteFeRepoIn(BaseModel):
    stand: str
    walk: str | None = None


@app.post("/api/classes/{class_id}/mapsprite/ferepo")
def import_ferepo_map_sprite(class_id: str, body: MapSpriteFeRepoIn):
    """A map sprite of FE-Repo for a class; its authors and license go to the project's credits."""
    try:
        stand = ferepo.fetch(body.stand)
        walk = ferepo.fetch(body.walk) if body.walk else None
    except ferepo.FeRepoError as e:
        raise HTTPException(400, str(e)) from e
    source = ferepo.describe(body.stand)
    return _import_map_sprite(class_id, stand, walk, source["name"], source)


@app.post("/api/classes/{class_id}/mapsprite")
async def import_local_map_sprite(class_id: str, stand: UploadFile = File(...), walk: UploadFile | None = File(None)):
    """A map sprite from the user's PC: a standing sheet, and a moving sheet if given."""
    return _import_map_sprite(class_id, await stand.read(), await walk.read() if walk else None,
                              Path(stand.filename or "").stem or class_id)


@app.delete("/api/classes/{class_id}/mapsprite")
def remove_map_sprite(class_id: str):
    """The class gets back the game's map sprite."""
    project = state.require_project()
    stored = project.load("mapsprites")
    key = stored.get("classes", {}).pop(class_id, None)
    if key and key not in stored["classes"].values():
        stored.get("sprites", {}).pop(key, None)
        shutil.rmtree(project.root / "assets" / "mapsprites" / key, ignore_errors=True)
    problems = project.save("mapsprites", stored)
    project.update_credits()
    return {"problems": [p.to_dict() for p in problems]}


@app.get("/api/ferepo/mapsprites")
def ferepo_map_sprites(q: str = "", refresh: bool = False, folder: str = "", offset: int = 0, f2e: bool = False):
    """Standing map sprites of FE-Repo matching a search, each with its moving sheet if there is one."""
    try:
        index, when = ferepo.load_index(refresh)
    except ferepo.FeRepoError as e:
        raise HTTPException(503, str(e)) from e
    entries, total = ferepo.map_sprites(index, q, folder=folder, offset=max(0, offset), f2e_only=f2e)
    return {"entries": entries, "total": total, "indexDate": when, "folders": ferepo.folders(index, ferepo.MAP_SPRITES)}


@app.get("/api/assets/map-sprite/{class_id}")
def map_sprite(class_id: str, side: str = "player", trim: bool = False):
    imported = _imported_map_sprite(class_id)
    if imported is not None:
        folder, size = imported
        png = map_sprite_sheet(DECOMP_DIR, folder / "stand.png", size, side, trim=trim)
        if png is None:
            raise HTTPException(404)
        return Response(png, media_type="image/png", headers={"Cache-Control": "no-cache"})
    entry = _game_class(class_id)
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


ATTACK_WEAPONS = ("sword", "lance", "axe", "bow", "anima", "light", "dark")


def _usable_weapons(class_id: str) -> list[dict]:
    if state.project is None:
        return []
    classes, characters = state.project.load("classes"), state.project.load("characters")
    return [i for i in state.project.load("items") if class_id in validation.weapon_users(i, classes, characters)]


def _reaches(item: dict, mode: str) -> bool:
    """A weapon uses this attack: `max` 0 is a reach that follows Magic."""
    reach = item.get("range") or {}
    return reach.get("max", 1) != 1 if mode in banim.RANGED_MODES else reach.get("min", 1) <= 1


@app.get("/api/classes/{class_id}/animations")
def class_animations(class_id: str):
    """The class's battle animations, by weapon type or item (ticket 44), with the project's changes: an
    animation imported for a weapon type ("ref" "new-<key>") or another game animation."""
    entry = _game_class(class_id)
    if entry is None:
        raise HTTPException(404)
    conf = entry.fields.get("pBattleAnimDef", "").lstrip("&").strip()
    animations = {a.number: a for a in banim.table(DECOMP_DIR)}
    project = _project_animations()
    imported = project.get("animations", {})
    changed = banim_import.with_groups(project.get("classes", {}).get(class_id, {}))
    left = dict(changed)
    usable = _usable_weapons(class_id)
    own_line = {d["weapon"] for d in banim.configs(DECOMP_DIR).get(conf, [])} | set(changed)   # weapons with their own animation

    def empty(wtype, item_id, base, symbol) -> dict[str, list[str]]:
        """Empty movements of an attacking weapon -> the weapons of the class that need them."""
        if wtype not in ATTACK_WEAPONS and not item_id:
            return {}
        same_type = [i for i in usable if i["weaponType"] == wtype and i["id"] not in own_line]
        weapons = [i for i in usable if i["id"] == item_id] if item_id else same_type
        return {m: [i["name"] for i in weapons if _reaches(i, m)] for m in banim.empty_modes(base, symbol)}

    def describe(wtype, item_id, anim) -> dict | None:
        if isinstance(anim, str) and anim.startswith("new:") and anim[4:] in imported:
            key = anim[4:]
            base, symbol = state.project.root / "assets" / ANIMATIONS_DIR / key, banim_import.symbol_of(key)
            return {"wtype": wtype, "item": item_id, "ref": f"new-{key}", "number": None,
                    "name": imported[key].get("name", key), "imported": True, "modes": banim.modes_of(base, symbol),
                    "empty": empty(wtype, item_id, base, symbol), "source": imported[key].get("source")}
        game = animations.get(anim) if isinstance(anim, int) else None
        if game is None:
            return None
        return {"wtype": wtype, "item": item_id, "ref": str(game.number), "number": game.number, "name": game.name,
                "imported": False, "modes": banim.modes_of(DECOMP_DIR, game.symbol),
                "empty": empty(wtype, item_id, DECOMP_DIR, game.symbol)}

    result = []
    for d in banim.configs(DECOMP_DIR).get(conf, []):
        weapon = d["weapon"]
        wtype = WEAPON_TYPES.get(weapon)
        key = wtype or weapon   # an item of its own (throwing axes) is set by its id
        anim = left.pop(key, d["number"])
        found = describe(wtype, None if weapon in WEAPON_TYPES else weapon, anim)
        if found:
            result.append({**found, "changed": key in changed})
    for key, anim in left.items():   # weapon types (or throwing axes) the class had no animation for
        item = key in banim_import.GROUP_ITEMS
        found = describe(None if item else key, key if item else None, anim)
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


def _class_palette(class_id: str) -> list[list[str]]:
    """The 5 lines of colours a character starts from: those of the class's first animation."""
    animations = class_animations(class_id)
    if not animations:
        raise HTTPException(404)
    base, symbol = _animation_source(str(animations[0]["ref"]))
    lines = [["#{:02x}{:02x}{:02x}".format(*c) for c in banim.palette(base, symbol, which)] for which in range(4)]
    return lines + [lines[0]]


@app.get("/api/characters/{character_id}/battle-colors/{class_id}")
def character_battle_colors(character_id: str, class_id: str):
    """A character's colours for a class: the class's, the game's own for this character, and those of the other
    characters the game gives colours in this class (a palette only fits the animation it was made for)."""
    source = (DECOMP_DIR / charpalettes.CONFIG_FILE).read_text(encoding="utf-8")
    symbols = charpalettes.game_palettes((DECOMP_DIR / charpalettes.TABLE_FILE).read_text(encoding="utf-8"))
    rows = {c: slots[class_id] for c, slots in charpalettes.game_slots(source).items() if class_id in slots}
    own = rows.pop(character_id, None)
    others = {}   # one character can have several entries (Orson), the same colours once
    for character, row in rows.items():
        if row != own:
            others.setdefault(row, character)
    return {
        "base": _class_palette(class_id),
        "game": None if own is None else charpalettes.read_lines(DECOMP_DIR, symbols[own]),
        "others": [{"character": c, "lines": charpalettes.read_lines(DECOMP_DIR, symbols[row])} for row, c in others.items()],
    }


def _face(portrait_id: int):
    """The big portrait as an image: the project's sheet when it replaced this one."""
    sheet = _imported_sheet(portrait_id)
    png = portraits.face_png(sheet) if sheet is not None else face_preview(DECOMP_DIR, portrait_id)
    if png is None:
        raise HTTPException(404)
    return Image.open(io.BytesIO(png))


@app.get("/api/classes/{class_id}/portrait-colors")
def portrait_colors(class_id: str, portrait: int, line: int = 0):
    """The 16 colours of a line of this class's palette, with the character's parts taken from a portrait."""
    if not 0 <= line < charpalettes.LINES:
        raise HTTPException(400, "line")
    animations = class_animations(class_id)
    if not animations:
        raise HTTPException(404)
    entry = _game_class(class_id)
    base_lines = _class_palette(class_id)
    # The game's palettes fit the game's animation only
    game = []
    if not animations[0].get("imported"):
        source = (DECOMP_DIR / charpalettes.CONFIG_FILE).read_text(encoding="utf-8")
        symbols = charpalettes.game_palettes((DECOMP_DIR / charpalettes.TABLE_FILE).read_text(encoding="utf-8"))
        rows = {slots[class_id] for slots in charpalettes.game_slots(source).values() if class_id in slots}
        game = [[charpalettes.to_rgb(c) for c in charpalettes.read_lines(DECOMP_DIR, symbols[row])[line]] for row in rows]
    base_folder, symbol = _animation_source(str(animations[0]["ref"]))
    modes = banim.modes_of(base_folder, symbol)
    mode = "stand" if "stand" in modes else modes[0]
    try:
        strip, info = banim.mode_strip(base_folder, symbol, mode, 0, portraitcolors.CODED)
    except (KeyError, FileNotFoundError):
        raise HTTPException(404)
    seen = portraitcolors.usage(Image.open(io.BytesIO(strip)), info["width"])
    colours = portraitcolors.from_portrait([charpalettes.to_rgb(c) for c in base_lines[line]], game, seen,
                                           portraitcolors.portrait_ramps(_face(portrait)),
                                           wyvern="CA_WYVERN" in entry.fields.get("attributes", ""))
    return {"colours": ["#{:02x}{:02x}{:02x}".format(*c) for c in colours]}


def _colours(text: str | None) -> tuple[tuple[int, int, int], ...] | None:
    """16 "rrggbb" separated by commas, from the URL of a strip drawn with a character's colours."""
    if text is None:
        return None
    colours = text.split(",")
    if len(colours) != 16 or not all(re.fullmatch(r"[0-9a-fA-F]{6}", c) for c in colours):
        raise HTTPException(400, "colors")
    return tuple(charpalettes.to_rgb("#" + c) for c in colours)


@app.get("/api/animations/{ref}/{mode}.json")
def animation_mode(ref: str, mode: str, palette: int = 0):
    base, symbol = _animation_source(ref)
    try:
        _png, info = banim.mode_strip(base, symbol, mode, palette)
    except (KeyError, FileNotFoundError):
        raise HTTPException(404)
    return info


@app.get("/api/animations/{ref}/{mode}.png")
def animation_strip(ref: str, mode: str, palette: int = 0, colors: str | None = None):
    """The mode's frames side by side; their durations come from the .json route."""
    base, symbol = _animation_source(ref)
    try:
        png, _info = banim.mode_strip(base, symbol, mode, palette, _colours(colors))
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


def _palette_pictures(names, read, found: dict[str, list[int]]) -> None:
    """Add to found the palettes of the palette pictures among the file names (read(name): the file's bytes)."""
    for original in names:
        name = original.lower()
        if not name.endswith(".png") or name[:1].isdigit() and "_" in name:
            continue
        for faction, words in _FACTION_FILES.items():
            if faction not in found and any(w in name for w in words):
                try:
                    image = Image.open(io.BytesIO(read(original)))
                except (ferepo.FeRepoError, OSError):
                    continue
                if image.mode == "P" and image.getpalette():
                    found[faction] = image.getpalette()[:48]


def _faction_palettes(*folders: str) -> dict[str, list[int]]:
    """The animation's own palettes for the other armies, read from the palette pictures of its folders."""
    found: dict[str, list[int]] = {}
    for folder in folders:
        try:
            files = {f["name"]: f["url"] for f in ferepo.folder_files(folder) if f["type"] == "file"}
        except ferepo.FeRepoError:
            continue
        _palette_pictures(files, lambda n, files=files: ferepo.fetch(files[n]), found)
    return found


def _script_of(names, read) -> str:
    """The animation script among the files: a .txt with FEditor's modes (the one without comments first)."""
    scripts = [n for n in names if n.lower().endswith(".txt") and n.lower() not in ("readme.txt", "credits.txt")]
    for name in sorted(scripts, key=lambda n: "without_comment" not in n.lower()):
        text = read(name)
        if "/// - Mode" in text:
            return text
    raise banim_import.ImportError_("noScript")


def _new_animation_key(project) -> tuple[dict, str]:
    data = project.load("animations")
    data.setdefault("animations", {})
    data.setdefault("classes", {})
    return data, str(max((int(k) for k in data["animations"]), default=0) + 1)


def _keep_animation(project, data: dict, key: str, converted, entry: dict, class_id: str, wtype: str) -> dict:
    """Keep a converted animation in the project and give it to the class for that weapon type (or group)."""
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
    data["animations"][key] = {**entry, "frames": converted.frames, "sheets": len(converted.sheets)}
    banim_import.set_class_animation(data["classes"].setdefault(class_id, {}), wtype, f"new:{key}")
    problems = project.save("animations", data)
    project.update_credits()
    banim.clear_caches()
    return {"key": key, "problems": [p.to_dict() for p in problems]}


@app.post("/api/animations/import")
def import_animation(body: AnimationImportIn):
    """Download a FE-Repo animation (one weapon), convert it to the decomp's format, keep it in the project and
    give it to the class for that weapon type (ticket 44). The authors go to the project's CREDITS.txt."""
    project = state.require_project()
    if not _animation_target(body.wtype):
        raise HTTPException(400, "unknownWeaponType")
    data, key = _new_animation_key(project)
    try:
        files = ferepo.folder_files(body.url)
        urls = {f["name"]: f["url"] for f in files if f["type"] == "file"}
        script_text = _script_of(urls, lambda n: ferepo.fetch_text(urls[n]))
        script = banim_import.parse_script(script_text)
        frames = _download_frames(files, script.files)
        converted = banim_import.convert(banim_import.symbol_of(key), script_text, frames,
                                         _faction_palettes(body.animation, body.url))
    except ferepo.FeRepoError as e:
        raise HTTPException(503 if str(e) in ("unreachable", "rateLimited") else 400, str(e)) from e
    except banim_import.ImportError_ as e:
        raise HTTPException(400, e.args[0]) from e
    source = ferepo.describe(body.animation)
    if not source["authors"]:
        source["credits"] = ferepo.folder_credits(body.animation)
    weapon_folder = urllib.parse.unquote(body.url.rstrip("/")).split("/")[-1]
    return _keep_animation(project, data, key, converted, {"name": source["name"], "weapon": weapon_folder, "source": source},
                           body.classId, body.wtype)


def _local_files(uploads: list[tuple[str, bytes]]) -> dict[str, bytes]:
    """The files of an animation chosen on the user's PC, by name without folders: a weapon's folder, or a .zip."""
    files: dict[str, bytes] = {}
    for name, content in uploads:
        if name.lower().endswith(".zip"):
            try:
                with zipfile.ZipFile(io.BytesIO(content)) as archive:
                    for info in archive.infolist():
                        if not info.is_dir() and info.file_size < 8_000_000:
                            files.setdefault(info.filename.replace("\\", "/").split("/")[-1], archive.read(info))
            except zipfile.BadZipFile as e:
                raise banim_import.ImportError_("badZip") from e
        else:
            files.setdefault(name.replace("\\", "/").split("/")[-1], content)
    return files


@app.post("/api/animations/import/local")
async def import_local_animation(classId: str = Form(...), wtype: str = Form(...), name: str = Form(""),  # noqa: N803
                                 files: list[UploadFile] = File(...)):
    """An animation from the user's PC (ticket 53): a weapon's folder (FEditor script and frames) or its .zip,
    converted and given to the class like a FE-Repo one."""
    project = state.require_project()
    if not _animation_target(wtype):
        raise HTTPException(400, "unknownWeaponType")
    try:
        local = _local_files([(f.filename or "", await f.read()) for f in files])
        by_lower = {n.lower(): n for n in local}
        data, key = _new_animation_key(project)
        script_text = _script_of(local, lambda n: local[n].decode("utf-8", errors="replace"))
        script = banim_import.parse_script(script_text)
        missing = [n for n in script.files if n.lower() not in by_lower]
        if missing:
            raise banim_import.ImportError_("missingFrames", ", ".join(missing[:5]))
        frames = {}
        for n in script.files:
            image = Image.open(io.BytesIO(local[by_lower[n.lower()]]))
            image.load()
            frames[n] = image
        palettes: dict[str, list[int]] = {}
        _palette_pictures(local, local.__getitem__, palettes)
        converted = banim_import.convert(banim_import.symbol_of(key), script_text, frames, palettes)
    except banim_import.ImportError_ as e:
        raise HTTPException(400, e.args[0]) from e
    except OSError as e:
        raise HTTPException(400, "notIndexed") from e
    title = name.strip()[:60] or Path(files[0].filename or "animation").stem
    return _keep_animation(project, data, key, converted, {"name": title, "weapon": "", "local": True},
                           classId, wtype)


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


def _animation_target(target: str) -> bool:
    """A weapon type, a group of linked weapons or one of its items (tickets 49, 51)."""
    return target in WEAPON_TYPES.values() or target in banim_import.GROUPS or target in banim_import.GROUP_ITEMS


class ClassAnimationIn(BaseModel):
    wtype: str
    animation: str | int | None    # a game animation's number, "new:<key>", or None: the game's own again


@app.put("/api/classes/{class_id}/animations")
def set_class_animation(class_id: str, body: ClassAnimationIn):
    if not _animation_target(body.wtype):
        raise HTTPException(400, "unknownWeaponType")
    project = state.require_project()
    data = project.load("animations")
    banim_import.set_class_animation(data.setdefault("classes", {}).setdefault(class_id, {}), body.wtype, body.animation)
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
    png = card_preview(DECOMP_DIR, portrait_id) or (face_preview if face else portrait_preview)(DECOMP_DIR, portrait_id)
    if png is None:
        raise HTTPException(404)
    return Response(png, media_type="image/png")


def _icon_answer(project) -> dict:
    icons = project.load("icons")["icons"]
    free = [i for i in itemicons.free_slots(state.get_decomp().item_icon_files()) if str(i) not in icons]
    return {"imported": sorted(int(i) for i in icons), "free": len(free), "next": free[0] if free else None}


def _import_item_icon(data: bytes, name: str, source: dict | None = None) -> dict:
    """An icon takes a place left free by the game (decomp/itemicons.py)."""
    project = state.require_project()
    stored = project.load("icons")
    same = next((k for k, e in stored["icons"].items() if source and e.get("source", {}).get("url") == source["url"]), None)
    if same is not None:
        return {**_icon_answer(project), "icon": int(same)}
    icon = _icon_answer(project)["next"]
    if icon is None:
        raise HTTPException(400, "noFreeIcon")
    try:
        png = itemicons.convert(data, read_agbpal(DECOMP_DIR / ITEM_ICON_PALETTE)[:16])
    except mapsprites.MapSpriteError as e:
        raise HTTPException(400, str(e)) from e
    folder = project.root / "assets" / itemicons.FOLDER
    folder.mkdir(parents=True, exist_ok=True)
    (folder / f"{icon}.png").write_bytes(png)
    stored["icons"][str(icon)] = {"name": name[:60], **({"source": source} if source else {})}
    project.save("icons", stored)
    project.update_credits()
    return {**_icon_answer(project), "icon": icon}


class IconFeRepoIn(BaseModel):
    url: str


@app.get("/api/items/icons")
def imported_icons():
    return _icon_answer(state.require_project())


@app.post("/api/items/icons/ferepo")
def import_ferepo_icon(body: IconFeRepoIn):
    """An item icon of FE-Repo; its authors and license go to the project's credits."""
    try:
        data = ferepo.fetch(body.url)
    except ferepo.FeRepoError as e:
        raise HTTPException(400, str(e)) from e
    source = ferepo.describe(body.url)
    return _import_item_icon(data, source["name"], source)


@app.post("/api/items/icons")
async def import_local_icon(file: UploadFile = File(...)):
    """An item icon from the user's PC."""
    return _import_item_icon(await file.read(), Path(file.filename or "").stem or "icon")


@app.delete("/api/items/icons/{icon_id}")
def remove_icon(icon_id: int):
    project = state.require_project()
    stored = project.load("icons")
    if stored["icons"].pop(str(icon_id), None) is not None:
        (project.root / "assets" / itemicons.FOLDER / f"{icon_id}.png").unlink(missing_ok=True)
        project.save("icons", stored)
        project.update_credits()
    return _icon_answer(project)


@app.get("/api/ferepo/icons")
def ferepo_icons(q: str = "", refresh: bool = False, folder: str = "", offset: int = 0, f2e: bool = False):
    """Item icons of FE-Repo matching a search."""
    try:
        index, when = ferepo.load_index(refresh)
    except ferepo.FeRepoError as e:
        raise HTTPException(503, str(e)) from e
    entries, total = ferepo.search(index, ferepo.ITEM_ICONS, q, folder=folder, offset=max(0, offset), f2e_only=f2e)
    return {"entries": entries, "total": total, "indexDate": when, "folders": ferepo.folders(index, ferepo.ITEM_ICONS)}


@app.get("/api/assets/boss-icon")
def boss_mark():
    """The mark the map puts on bosses (ticket 140)."""
    png = boss_icon(DECOMP_DIR, state.settings.rom_path)
    if png is None:
        raise HTTPException(404)
    return Response(png, media_type="image/png")


@app.get("/api/assets/terrain-icon/{terrain}")
def terrain_icon(terrain: int):
    """The tile the game's maps use most for a terrain (ticket 140: a fort for seizing)."""
    png = maps.terrain_icon(DECOMP_DIR, terrain, 2)
    if png is None:
        raise HTTPException(404)
    return Response(png, media_type="image/png")


@app.get("/api/assets/battle-bg/{bg_set}")
def battle_bg(bg_set: int):
    """The plains background of a battle background set (ticket 141)."""
    png = battlebg.preview(DECOMP_DIR, bg_set)
    if png is None:
        raise HTTPException(404)
    return Response(png, media_type="image/png")


@app.get("/api/assets/item-icon/{icon_id}")
def item_icon(icon_id: int, line: int = 0):
    imported = state.project.root / "assets" / itemicons.FOLDER / f"{icon_id}.png" if state.project else None
    if imported is not None and imported.is_file() and not line:
        return Response(render_indexed(imported, read_agbpal(DECOMP_DIR / ITEM_ICON_PALETTE)[:16], 3), media_type="image/png")
    png = item_icon_preview(DECOMP_DIR, state.get_decomp().item_icon_files(), icon_id, line=1 if line else 0)
    if png is None:
        raise HTTPException(404)
    return Response(png, media_type="image/png")


@app.get("/api/skills")
def skills_catalogue():
    """Skills offered on the character and class sheets (game option skills), and the game's class abilities shown
    as skills."""
    return {"skills": skills.catalogue(), "game": skills.game_catalogue(), "maxPerSheet": skills.MAX_PER_SHEET}


@app.get("/api/skills/{skill_id}/icon.png")
def skill_icon(skill_id: str):
    try:
        path = skills.icon_path(skill_id)
    except skills.SkillError as e:
        raise HTTPException(404 if str(e) == "unknownSkill" else 502, str(e))
    return Response(render_indexed(path, read_agbpal(DECOMP_DIR / ITEM_ICON_PALETTE)[:16], 3), media_type="image/png",
                    headers={"Cache-Control": "max-age=86400"})


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
def ferepo_animations(q: str = "", refresh: bool = False, folder: str = "", offset: int = 0, f2e: bool = False,
                      wtype: str = "", ranged: bool = False):
    """Battle animations of the FE-Repo (one folder each), searched like the portraits (ticket 44); `wtype`: weapon
    types, comma-separated, the animation must have them all (tickets 47, 48; the weapons of each top folder are asked
    to GitHub once a week, the folders in parallel); `ranged`: its sword, lance or axe casts a spell from afar (a list
    FE Maker comes with, so these three weapons need no question to GitHub)."""
    wanted = {w for w in wtype.split(",") if w}
    melee = wanted & set(ferepo.MELEE_WEAPONS) if ranged else set()
    wanted -= melee
    try:
        index, when = ferepo.load_index(refresh)
    except ferepo.FeRepoError as e:
        raise HTTPException(503, str(e)) from e
    weapons: dict[str, list[str]] = {}
    missing: list[str] = []   # top folders whose weapons GitHub did not give (limit of 60 requests an hour)
    if wanted:
        def ask(top: str) -> dict[str, list[str]] | None:
            try:
                return ferepo.animation_weapons(top)
            except ferepo.FeRepoError:
                return None

        tops = [folder.split("/")[0]] if folder else [f["name"] for f in ferepo.folders(index, ferepo.ANIMATIONS)]
        first = ask(tops[0])   # also lists the top folders, once
        with ThreadPoolExecutor(8) as pool:
            for top, found in zip(tops, [first, *pool.map(ask, tops[1:])]):
                if found is None:
                    missing.append(top)
                else:
                    weapons.update(found)

    def types(url: str) -> list[str]:
        return sorted({t for w in weapons.get(ferepo.animation_path(url), []) if (t := ferepo.weapon_type(w))})

    def casts(url: str) -> bool:
        found = ferepo.ranged_animations().get(ferepo.animation_path(url), [])
        return bool(found) and melee <= set(found)

    def keep(url: str) -> bool:
        return wanted <= set(types(url)) and (not ranged or casts(url))

    entries, total = ferepo.search(index, ferepo.ANIMATIONS, q, limit=60, folder=folder, offset=max(0, offset), f2e_only=f2e,
                                   keep=keep if wanted or ranged else None)
    if wanted:
        entries = [{**e, "weapons": types(e["url"])} for e in entries]
        if len(missing) == len(tops):
            raise HTTPException(503, "rateLimited")
    return {"entries": entries, "total": total, "indexDate": when, "folders": ferepo.folders(index, ferepo.ANIMATIONS),
            "missingFolders": len(missing)}


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

class ShowOriginalIn(BaseModel):
    show: bool


@app.put("/api/project/show-original")
def put_show_original(body: ShowOriginalIn):
    state.require_project().set_show_original(body.show)
    return {"show": body.show}


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


@app.get("/api/project/game-options")
def get_game_options():
    """Options of the built game the project changes, and what can be set (decomp/gameoptions.py)."""
    return {"options": state.require_project().game_options, "groups": gameoptions.SWITCH_GROUPS,
            "choices": {k: list(values) for k, values in gameoptions.CHOICES.items()},
            "defaults": {k: {"game": game, "values": list(values)} for k, (_f, game, values) in gameoptions.DEFAULTS.items()}}


@app.put("/api/project/game-options")
def put_game_options(options: dict):
    project = state.require_project()
    try:
        project.set_game_options(options)
    except ProjectError as e:
        raise HTTPException(400, str(e)) from e
    return get_game_options()


class BuildIn(BaseModel):
    launch: bool = False


# Lines a first build prints (make's ~1800 commands, measured 05/11/2026), before any build was counted (ticket 156).
FIRST_BUILD_LINES = 2000


def _build_lines_file() -> Path:
    return config_dir() / "build-lines.txt"


def expected_build_lines() -> int:
    """The last finished build's line count: the best guess of how long this one is, for a progress bar."""
    try:
        return max(1, int(_build_lines_file().read_text(encoding="utf-8")))
    except (OSError, ValueError):
        return FIRST_BUILD_LINES


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
        try:
            _build_lines_file().parent.mkdir(parents=True, exist_ok=True)
            _build_lines_file().write_text(str(len(st["log"])), encoding="utf-8")
        except OSError:
            pass
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
    state.build_status = {
        "state": "running", "log": [], "error": None, "patch": None, "launch": body.launch,
        "expected": expected_build_lines(),
    }
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


class TicketCommentIn(BaseModel):
    body: str
    images: list[str] = []  # data URLs


@app.post("/api/tickets/{ticket_id}/comments")
def add_ticket_comment(ticket_id: str, body: TicketCommentIn):
    try:
        return tickets.add_comment(ticket_id, body.body, body.images)
    except KeyError:
        raise HTTPException(404)
    except TicketError as e:
        raise HTTPException(400, str(e))


@app.delete("/api/tickets/{ticket_id}/comments/{comment_id}")
def delete_ticket_comment(ticket_id: str, comment_id: str):
    try:
        return tickets.delete_comment(ticket_id, comment_id)
    except KeyError:
        raise HTTPException(404)


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


class _UiFiles(StaticFiles):
    """The page is asked again each time: after an update, a browser would keep showing the old interface."""

    async def get_response(self, path, scope):
        response = await super().get_response(path, scope)
        if path in (".", "index.html"):
            response.headers["Cache-Control"] = "no-cache"
        return response


if UI_DIST.is_dir():
    app.mount("/", _UiFiles(directory=UI_DIST, html=True), name="ui")
