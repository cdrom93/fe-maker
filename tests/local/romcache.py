"""Playtests' built ROMs, cached by what the build reads: a playtest run again with the same project, the same decomp and
the same build scripts reuses the ROM and its linker map instead of compiling again.

The key hashes the overlay the project writes (every decomp file it changes), the decomp's commit, the build scripts
(native/, builder.py and docker/), the BUGFIX option and the ROM's size. Cache folder: FE_MAKER_PLAYTEST_CACHE, else
`playtest-cache` in FE Maker's config folder (FE_MAKER_HOME); the newest KEEP builds are kept.
FE_MAKER_PLAYTEST_CACHE=off builds every time.
"""

import hashlib
import os
import shutil
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "server"))

from fe_maker.config import config_dir  # noqa: E402
from fe_maker.paths import DECOMP_COMMIT, DOCKER_DIR  # noqa: E402
from fe_maker.project import BuildOutput, Project, ProjectError  # noqa: E402

KEEP = 40
BUILD_SCRIPTS = [REPO_ROOT / "server" / "fe_maker" / "native", REPO_ROOT / "server" / "fe_maker" / "builder.py", DOCKER_DIR]
FILES = ("test.gba", "fireemblem8.map")


def cache_dir() -> Path | None:
    setting = os.environ.get("FE_MAKER_PLAYTEST_CACHE", "")
    if setting.lower() == "off":
        return None
    return Path(setting) if setting else config_dir() / "playtest-cache"


def _hash_tree(digest, root: Path) -> None:
    if root.is_file():
        digest.update(root.read_bytes())
        return
    for path in sorted(p for p in root.rglob("*") if p.is_file() and "__pycache__" not in p.parts):
        digest.update(path.relative_to(root).as_posix().encode() + b"\0")
        digest.update(path.read_bytes() + b"\0")


def key(project: Project, rom: Path, overlay: Path) -> str:
    digest = hashlib.sha256()
    digest.update(f"{DECOMP_COMMIT}|{project.meta.get('bugfix', False)}|{rom.stat().st_size}".encode())
    for folder in (overlay, *BUILD_SCRIPTS):
        digest.update(b"\1" + folder.name.encode())
        _hash_tree(digest, folder)
    return digest.hexdigest()[:24]


def build(project: Project, rom: Path, on_output=None) -> BuildOutput:
    """`project.build(rom, for_test=True)`, from the cache when the same build was made before."""
    folder = cache_dir()
    if folder is None:
        return project.build(rom, on_output=on_output, for_test=True)
    errors = [p for p in project.validate() if p.severity == "error"]
    if errors:
        raise ProjectError("Fix these problems before building: " + "; ".join(p.message for p in errors))
    entry = folder / key(project, rom, project.generate_overlay(for_test=True))
    out_dir = project.root / "build"
    if all((entry / name).is_file() for name in FILES):
        for name in FILES:
            shutil.copyfile(entry / name, out_dir / name)
        os.utime(entry)   # most recently used: kept longest
        print(f"[romcache] reused {entry.name}")
        return BuildOutput(out_dir / "test.gba", None, False, out_dir / "fireemblem8.map")
    out = project.build(rom, on_output=on_output, for_test=True)
    entry.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(out.rom_path, entry / "test.gba")
    shutil.copyfile(out.map_path, entry / "fireemblem8.map")
    for old in sorted((p for p in folder.iterdir() if p.is_dir()), key=lambda p: p.stat().st_mtime)[:-KEEP]:
        shutil.rmtree(old, ignore_errors=True)
    return out
