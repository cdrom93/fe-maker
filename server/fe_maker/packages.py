"""Character and class packages: one file (a zip) holding a sheet and everything it needs, to take it from a project
to another (and to the user's library, library.py).

`package.json`: {"format": "fe-maker-package", "version": 1, "kind": "character" | "class", "feMaker": version,
"name", "character": {...}, "classes": [{...}]}; the files under `files/`.

A class: its sheet; its battle animations (`animations`: weapon -> a game animation's number or "new:<key>", the
imported ones in `animationEntries` with their files `files/animations/<key>/...`); its map sprite (`mapSprite`: the
entry, `files/mapsprite/stand.png`, `walk.png`); its generic portrait (`genericPortrait`, see portraits).
A character: its sheet (stats, texts, skills, colours by class); its portrait; its class when the project added it
(a game class is in every project). A portrait: {"game": id} for one of the game's, else {"entry": ..., "file"}.

Importing makes new sheets on free entries (new ids), new portraits, animations and map sprites; links to sheets the
other project does not have (promotions to an added class, supports) are left out and reported. Credits ("source")
travel with the entries.
"""

from __future__ import annotations

import io
import json
import re
import shutil
import zipfile
from pathlib import Path

from . import __version__
from .decomp import mapsprites, portraits
from .decomp.gamedata import ALLY_CHARACTER_END, NEW_CHARACTER_PREFIX, NEW_CLASS_PREFIX, DecompData, GameDataError
from .project import ANIMATIONS_DIR, PORTRAITS_DIR

FORMAT = "fe-maker-package"
VERSION = 1
SUFFIX = {"character": ".femchar", "class": ".femclass"}
MAX_SIZE = 40_000_000


class PackageError(Exception):
    pass


# ---------- export ----------

def _portrait(project, decomp_dir: Path, portrait_id: int, files: dict[str, bytes]) -> dict | None:
    if not portrait_id:
        return None
    entry = project.load("portraits").get(str(portrait_id))
    if not entry or not (project.root / "assets" / entry.get("file", "")).is_file():
        if portraits.is_new(decomp_dir, portrait_id):
            return None
        return {"game": portrait_id}
    name = f"portraits/{portrait_id}.png"
    files[name] = (project.root / "assets" / entry["file"]).read_bytes()
    return {"entry": {k: v for k, v in entry.items() if k != "file"}, "file": name}


def _class_part(project, decomp_dir: Path, class_id: str, files: dict[str, bytes]) -> dict:
    record = next((c for c in project.load("classes") if c["id"] == class_id), None)
    if record is None:
        record = next((c for c in DecompData(decomp_dir).export_classes() if c["id"] == class_id), None)
    if record is None:
        raise PackageError("unknownClass")
    stored = project.load("animations")
    weapons = dict(stored.get("classes", {}).get(class_id, {}))
    entries = {}
    for ref in weapons.values():
        if isinstance(ref, str) and ref.startswith("new:"):
            key = ref[4:]
            folder = project.root / "assets" / ANIMATIONS_DIR / key
            if key in stored.get("animations", {}) and folder.is_dir():
                entries[key] = stored["animations"][key]
                for path in folder.rglob("*"):
                    if path.is_file():
                        files[f"animations/{key}/{path.relative_to(folder).as_posix()}"] = path.read_bytes()
    weapons = {w: r for w, r in weapons.items() if not (isinstance(r, str) and r.startswith("new:")) or r[4:] in entries}
    part = {"record": record, "animations": weapons, "animationEntries": entries}
    sprites = project.load("mapsprites")
    key = sprites.get("classes", {}).get(class_id)
    folder = project.root / "assets" / "mapsprites" / str(key)
    if key and (folder / "stand.png").is_file():
        part["mapSprite"] = sprites.get("sprites", {}).get(key, {})
        for name in ("stand.png", "walk.png"):
            if (folder / name).is_file():
                files[f"mapsprite/{class_id}/{name}"] = (folder / name).read_bytes()
    generic = _portrait(project, decomp_dir, int(record.get("genericPortrait") or 0), files)
    if generic:
        part["genericPortrait"] = generic
    return part


def _is_ally(decomp_dir: Path, character_id: str) -> bool:
    if character_id.startswith(NEW_CHARACTER_PREFIX):
        number = int(character_id.removeprefix(NEW_CHARACTER_PREFIX), 16)
    else:
        number = DecompData(decomp_dir).character_number(character_id)
    return 0 < number < ALLY_CHARACTER_END


def _zip(manifest: dict, files: dict[str, bytes]) -> bytes:
    out = io.BytesIO()
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("package.json", json.dumps(manifest, ensure_ascii=False, indent=1))
        for name, data in sorted(files.items()):
            archive.writestr(f"files/{name}", data)
    return out.getvalue()


def export_class(project, decomp_dir: Path, class_id: str) -> bytes:
    files: dict[str, bytes] = {}
    part = _class_part(project, decomp_dir, class_id, files)
    return _zip({"format": FORMAT, "version": VERSION, "kind": "class", "feMaker": __version__,
                 "name": part["record"].get("name", ""), "classes": [part]}, files)


def export_character(project, decomp_dir: Path, character_id: str) -> bytes:
    record = next((c for c in project.load("characters") if c["id"] == character_id), None)
    if record is None:
        record = next((c for c in DecompData(decomp_dir).export_characters() if c["id"] == character_id), None)
    if record is None:
        raise PackageError("unknownCharacter")
    files: dict[str, bytes] = {}
    character = {"record": record, "ally": _is_ally(decomp_dir, character_id)}
    face = _portrait(project, decomp_dir, int(record.get("portraitId") or 0), files)
    if face:
        character["portrait"] = face
    classes = []
    if str(record.get("class", "")).startswith(NEW_CLASS_PREFIX):
        classes.append(_class_part(project, decomp_dir, record["class"], files))
    return _zip({"format": FORMAT, "version": VERSION, "kind": "character", "feMaker": __version__,
                 "name": record.get("name", ""), "character": character, "classes": classes}, files)


def file_name(kind: str, name: str) -> str:
    return (re.sub(r"[^\w\- ]+", "", name).strip() or kind) + SUFFIX[kind]


# ---------- import ----------

def read(data: bytes) -> tuple[dict, dict[str, bytes]]:
    """The package's manifest and files; PackageError if it is not one."""
    if len(data) > MAX_SIZE:
        raise PackageError("tooBig")
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            manifest = json.loads(archive.read("package.json").decode("utf-8"))
            files = {info.filename.removeprefix("files/"): archive.read(info) for info in archive.infolist()
                     if info.filename.startswith("files/") and not info.is_dir()}
    except (zipfile.BadZipFile, KeyError, ValueError) as e:
        raise PackageError("notPackage") from e
    if manifest.get("format") != FORMAT or manifest.get("kind") not in SUFFIX:
        raise PackageError("notPackage")
    if int(manifest.get("version", 0)) > VERSION:
        raise PackageError("newerPackage")
    for name in files:
        if name.startswith("/") or ".." in name.split("/"):
            raise PackageError("notPackage")
    return manifest, files


def _free_portrait_id(project, decomp_dir: Path) -> int:
    used = {int(k) for k in project.load("portraits") if k.isdigit()}
    for pid in range(portraits.first_new_id(decomp_dir), portraits.MAX_PORTRAIT_ID + 1):
        if pid not in used:
            return pid
    raise PackageError("noFreePortrait")


def _import_portrait(project, decomp_dir: Path, part: dict | None, files: dict[str, bytes]) -> int:
    if not part:
        return 0
    if "game" in part:
        return int(part["game"])
    data = files.get(part.get("file", ""))
    if data is None:
        return 0
    pid = _free_portrait_id(project, decomp_dir)
    rel = f"{PORTRAITS_DIR}/{pid}.png"
    target = project.root / "assets" / rel
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(data)
    stored = project.load("portraits")
    entry = {**part.get("entry", {}), "file": rel}
    entry["name"] = str(entry.get("name") or portraits.new_name(pid))[:40]
    stored[str(pid)] = entry
    project.save("portraits", stored)
    return pid


_SYMBOL = re.compile(r"banim_fem_(\d+)(?!\d)")


def _import_class(project, decomp_dir: Path, part: dict, files: dict[str, bytes], warnings: list[str]) -> str:
    record = dict(part["record"])
    classes = project.load("classes")
    known = {c["id"] for c in classes} | {c["id"] for c in DecompData(decomp_dir).export_classes()}
    model = record.get("model") or record["id"]
    if model.startswith(NEW_CLASS_PREFIX) or model not in known:
        raise PackageError("unknownModel")
    try:
        fresh = DecompData(decomp_dir).new_class(model, {c["id"] for c in classes})
    except GameDataError as e:
        raise PackageError(str(e)) from e
    new_id = fresh["id"]
    promotions = [p for p in record.get("promotions", []) if p in known and not p.startswith(NEW_CLASS_PREFIX)]
    if promotions != record.get("promotions", []):
        warnings.append("promotionsLeft")
    record.update(id=new_id, model=model, promotions=promotions)
    if part.get("genericPortrait"):
        record["genericPortrait"] = _import_portrait(project, decomp_dir, part["genericPortrait"], files) \
            or fresh.get("genericPortrait", 0)
    classes.append({**fresh, **record})
    project.save("classes", classes)

    stored = project.load("animations")
    stored.setdefault("animations", {})
    keys: dict[str, str] = {}
    for old, entry in part.get("animationEntries", {}).items():
        key = str(max((int(k) for k in stored["animations"]), default=0) + 1)
        keys[old] = key
        prefix = f"animations/{old}/"
        folder = project.root / "assets" / ANIMATIONS_DIR / key
        for name, data in files.items():
            if not name.startswith(prefix):
                continue
            rel = _SYMBOL.sub(lambda m: f"banim_fem_{key}" if m.group(1) == old else m.group(0), name[len(prefix):])
            path = folder / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            if rel.endswith(".s"):
                text = data.decode("utf-8")
                path.write_text(_SYMBOL.sub(lambda m: f"banim_fem_{key}" if m.group(1) == old else m.group(0), text),
                                encoding="utf-8", newline="\n")
            else:
                path.write_bytes(data)
        stored["animations"][key] = entry
    weapons = {}
    for weapon, ref in part.get("animations", {}).items():
        if isinstance(ref, str) and ref.startswith("new:"):
            if ref[4:] in keys:
                weapons[weapon] = f"new:{keys[ref[4:]]}"
        else:
            weapons[weapon] = ref
    if weapons:
        stored.setdefault("classes", {})[new_id] = weapons
        project.save("animations", stored)

    old_id = part["record"]["id"]
    if part.get("mapSprite") is not None and f"mapsprite/{old_id}/stand.png" in files:
        sprites = project.load("mapsprites")
        key = mapsprites.safe_key(new_id.removeprefix("CLASS_"))
        folder = project.root / "assets" / "mapsprites" / key
        if folder.exists():
            shutil.rmtree(folder)
        folder.mkdir(parents=True)
        for name in ("stand.png", "walk.png"):
            if f"mapsprite/{old_id}/{name}" in files:
                (folder / name).write_bytes(files[f"mapsprite/{old_id}/{name}"])
        sprites.setdefault("sprites", {})[key] = part["mapSprite"]
        sprites.setdefault("classes", {})[new_id] = key
        project.save("mapsprites", sprites)
    return new_id


def import_package(project, decomp_dir: Path, data: bytes) -> dict:
    """Add the package's sheets to the project: {"kind", "id" (the new character or class), "classes": {old: new},
    "warnings": [...]}."""
    manifest, files = read(data)
    warnings: list[str] = []
    classes = {}
    for part in manifest.get("classes", []):
        classes[part["record"]["id"]] = _import_class(project, decomp_dir, part, files, warnings)
    if manifest["kind"] == "class":
        new_id = next(iter(classes.values()), "")
    else:
        part = manifest["character"]
        record = dict(part["record"])
        characters = project.load("characters")
        try:
            reuse = project.load("chapters").get("blankCharacters", False)
            fresh = DecompData(decomp_dir).new_character(bool(part.get("ally", True)), {c["id"] for c in characters}, reuse)
        except GameDataError as e:
            raise PackageError(str(e)) from e
        new_id = fresh["id"]
        known = {c["id"] for c in project.load("classes")} | {c["id"] for c in DecompData(decomp_dir).export_classes()}
        cls = classes.get(record.get("class"), record.get("class"))
        if cls not in known:
            warnings.append("classLeft")
            cls = fresh.get("class")
        colors = {classes.get(c, c): v for c, v in (record.get("battleColors") or {}).items() if classes.get(c, c) in known}
        record.update(id=new_id, **{"class": cls})
        if record.get("battleColors"):
            record["battleColors"] = colors
        record["portraitId"] = _import_portrait(project, decomp_dir, part.get("portrait"), files)
        if new_id.startswith(NEW_CHARACTER_PREFIX):   # a raw-numbered sheet of that entry goes (as /api/characters/new)
            number = int(new_id.removeprefix(NEW_CHARACTER_PREFIX), 16)
            characters = [c for c in characters if c["id"].startswith("CHARACTER_") or not c["id"][:1].isdigit()
                          or int(c["id"], 0) != number]
        characters = [c for c in characters if c["id"] != new_id]
        characters.append({**fresh, **record})
        project.save("characters", characters)
    project.update_credits()
    return {"kind": manifest["kind"], "id": new_id, "classes": classes, "warnings": warnings}
