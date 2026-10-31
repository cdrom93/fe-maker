"""Projects across FE Maker versions: format number, conversions, copies made before them.

A change that a project's JSON files cannot take as it is (a field renamed, moved, or meaning something else) adds one
function to MIGRATIONS, which raises FORMAT_VERSION. A field or data file that is only new needs none: see
`Project.load`. Steps never change `assets/`: the copy made before them holds `data/` and the project file only.
"""

from __future__ import annotations

import json
import shutil
import time
from collections.abc import Callable
from pathlib import Path

PROJECT_FILE = "fe-maker.json"
BACKUPS_DIR = "backups"
# MIGRATIONS[n] takes a project from format n + 1 to n + 2: it edits the files of `data/` and the project file's dict.
MIGRATIONS: list[Callable[[Path, dict], None]] = []
FORMAT_VERSION = 1 + len(MIGRATIONS)


class ProjectError(Exception):
    code: str | None = None  # interface string to show instead of the message


class ProjectTooNew(ProjectError):
    code = "project.tooNew"


class MigrationFailed(ProjectError):
    code = "project.migrationFailed"


def backup(root: Path, label: str = "") -> Path:
    """Copy `data/` and the project file into `backups/<time>`, as they are."""
    stamp = time.strftime("%Y-%m-%d-%H%M%S")
    target = root / BACKUPS_DIR / (f"{stamp}-{label}" if label else stamp)
    shutil.copytree(root / "data", target)
    shutil.copy2(root / PROJECT_FILE, target / PROJECT_FILE)
    return target


def migrate(root: Path, meta: dict) -> None:
    """Bring a project read from `root` to this version's format; an interrupted step leaves it as it was."""
    version = meta.get("formatVersion", 1)
    if version > FORMAT_VERSION:
        raise ProjectTooNew(f"{root} has format {version}, this FE Maker reads up to {FORMAT_VERSION}")
    if version == FORMAT_VERSION:
        return
    saved = backup(root, f"format-{version}")
    try:
        for step in MIGRATIONS[version - 1:]:
            step(root, meta)
        meta["formatVersion"] = FORMAT_VERSION
        temporary = root / f"{PROJECT_FILE}.new"
        temporary.write_text(json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8")
        temporary.replace(root / PROJECT_FILE)
    except Exception as e:
        shutil.rmtree(root / "data")
        shutil.copytree(saved, root / "data", ignore=shutil.ignore_patterns(PROJECT_FILE))
        raise MigrationFailed(f"Could not convert {root}: {e}") from e
