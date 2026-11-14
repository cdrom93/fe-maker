"""The user's library, shared by all their projects (kept in FE Maker's config dir, never in a project).

Favourites: FE-Repo files the user starred in the browsers (portraits, map sprites, item icons, battle animations,
songs), by their address (a song: its path in FE-Repo-Music); `library/favorites.json`.
"""

from __future__ import annotations

import json
from pathlib import Path

from .config import config_dir

KINDS = ("portraits", "mapsprites", "icons", "animations", "music")


class LibraryError(Exception):
    pass


def library_dir() -> Path:
    return config_dir() / "library"


def _favorites_path() -> Path:
    return library_dir() / "favorites.json"


def favorites() -> dict[str, list[str]]:
    """{kind: [address, ...]} for every kind, the latest starred last."""
    try:
        data = json.loads(_favorites_path().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        data = {}
    return {kind: [k for k in data.get(kind, []) if isinstance(k, str)] for kind in KINDS}


def favorite_set(kind: str) -> set[str]:
    return set(favorites().get(kind, []))


def set_favorite(kind: str, key: str, on: bool) -> list[str]:
    """Star (on) or unstar a file; the kind's favourites after."""
    if kind not in KINDS:
        raise LibraryError("unknownKind")
    if not key or len(key) > 2000:
        raise LibraryError("badKey")
    data = favorites()
    keys = [k for k in data[kind] if k != key]
    if on:
        keys.append(key)
    data[kind] = keys
    path = _favorites_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    tmp.replace(path)
    return keys
