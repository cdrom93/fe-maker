"""Local HTTP API used by the FE Maker interface."""

from __future__ import annotations

import base64
import tempfile
import threading
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from . import emulator
from .builder import BuildError
from .config import Settings, default_projects_dir
from .decomp import mapobjects, maps, tileedit, units
from .decomp.assets import face_preview, item_icon_preview, portrait_names, portrait_preview
from .decomp.assets import map_sprite as map_sprite_png
from .decomp.gamedata import ABILITIES, AFFINITIES, RANK_VALUES, RANKABLE_TYPES, WEAPON_TYPES, DecompData
from .paths import DECOMP_DIR, REPO_ROOT
from .project import DATA_FILES, Project, ProjectError, slugify
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
        "portraits": portrait_names(DECOMP_DIR),
    }


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
        with tempfile.TemporaryDirectory() as folder:
            if edits:
                assets = tileedit.Tileset(DECOMP_DIR, assets.layout.stem, edits).edited_assets(Path(folder))
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
        # Original map changes (doors, villages...); None when the map has no change layer
        "changes": maps.read_changes(DECOMP_DIR, layout["changes"]) if layout["changes"] else None,
    }


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
                      if tuple(c) in events and events[tuple(c)]["kind"] == obj["kind"]), None)
        obj["event"] = {k: v for k, v in found.items() if k != "span"} if found else None
    return {"objects": objects, "hasChangeLayer": bool(layout["changes"]), "defaults": mapobjects.DEFAULTS,
            "faces": [{"id": fid, "portrait": portrait} for fid, portrait in mapobjects.FACES.items()]}


class TilesetIn(BaseModel):
    edits: dict | None = None


@app.post("/api/maps/{layout_id}/tileset")
def edited_tileset(layout_id: str, body: TilesetIn):
    """The tileset sheet with the project's added metatiles (not saved yet: the editor sends them)."""
    _layout(layout_id)
    try:
        tileset = tileedit.Tileset(DECOMP_DIR, layout_id, body.edits)
        with tempfile.TemporaryDirectory() as folder:
            assets = tileset.edited_assets(Path(folder))
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
    op: str
    edits: dict | None = None
    painted: dict = {}   # project painted layouts: their tiles are not free slots


@app.post("/api/maps/{layout_id}/transform")
def transform_tiles(layout_id: str, body: TransformIn):
    """A block of tiles mirrored or turned: new metatiles (and 8x8 tiles) added to the tileset when needed."""
    _layout(layout_id)
    try:
        tileset = tileedit.Tileset(DECOMP_DIR, layout_id, body.edits, body.painted)
        rows = tileset.transform_block(body.rows, body.op)
    except tileedit.TileEditError as e:
        raise HTTPException(409, str(e)) from e
    return {"rows": rows, "edits": tileset.edits, "tileset": tileset.name}


@app.get("/api/maps/{layout_id}/tileset.png")
def map_tileset(layout_id: str):
    png = maps.render_tileset(_layout(layout_id)["assets"])
    return Response(png, media_type="image/png", headers={"Cache-Control": "max-age=3600"})


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
    """Small portrait (menus), or the big one shown in dialogues with `face`."""
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

UI_DIST = REPO_ROOT / "ui" / "dist"
if UI_DIST.is_dir():
    app.mount("/", StaticFiles(directory=UI_DIST, html=True), name="ui")
