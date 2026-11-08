"""How long each build took (ticket 30), kept in FE Maker's settings folder to compare builds and find what is slow."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from .config import config_dir

KEEP = 200   # the most recent builds kept


def _file() -> Path:
    return config_dir() / "build-times.json"


def recent(count: int = KEEP) -> list[dict]:
    """The last builds, most recent first."""
    try:
        entries = json.loads(_file().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    return entries[::-1][:count] if isinstance(entries, list) else []


def record(project: str, seconds: float, native: bool, test: bool, compiled: int, lines: int) -> dict:
    """Add a finished build to the history; the entry."""
    entry = {"date": datetime.now().isoformat(timespec="seconds"), "project": project, "seconds": round(seconds, 1),
             "native": native, "test": test, "compiled": compiled, "lines": lines}
    entries = recent()[::-1] + [entry]
    try:
        _file().parent.mkdir(parents=True, exist_ok=True)
        _file().write_text(json.dumps(entries[-KEEP:], indent=1) + "\n", encoding="utf-8")
    except OSError:
        pass
    return entry
