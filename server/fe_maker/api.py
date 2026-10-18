"""Local HTTP API used by the FE Maker interface."""

from __future__ import annotations

import threading
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from . import emulator
from .builder import BuildError
from .config import Settings, default_projects_dir
from .decomp.assets import item_icon_preview, portrait_names, portrait_preview
from .decomp.gamedata import RANK_VALUES, RANKABLE_TYPES, WEAPON_TYPES, DecompData
from .paths import DECOMP_DIR, REPO_ROOT
from .project import DATA_FILES, Project, ProjectError, slugify
from .rom import InvalidRomError

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
    if body.language in ("fr", "en"):
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
def put_data(kind: str, records: list[dict]):
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
        "classes": classes,
        # Item id -> names of the classes / characters allowed to wield it (weapon locks)
        "itemLocks": {
            item: {
                "classes": list(dict.fromkeys(class_names.get(c, c) for c in who["classes"])),
                "characters": [char_names.get(c, c) for c in who["characters"]],
            }
            for item, who in d.item_locks().items()
        },
        "weaponTypes": list(WEAPON_TYPES.values()),
        "rankableTypes": RANKABLE_TYPES,
        "ranks": list(RANK_VALUES),
        "iconCount": len(d.item_icon_files()),
        "portraits": portrait_names(DECOMP_DIR),
    }


@app.get("/api/assets/portrait/{portrait_id}")
def portrait(portrait_id: int):
    png = portrait_preview(DECOMP_DIR, portrait_id)
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


# ---------- interface ----------

UI_DIST = REPO_ROOT / "ui" / "dist"
if UI_DIST.is_dir():
    app.mount("/", StaticFiles(directory=UI_DIST, html=True), name="ui")
