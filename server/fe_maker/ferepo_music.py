"""FE-Repo-Music (https://github.com/Klokinator/FE-Repo-Music, The Unlicense), FE-Repo's sister repository of songs
for the game's engine: browsed from the Music tab, heard by their recorded previews (.ogg, .mp3), imported as the
project's songs (decomp/songasm.py turns their .s files into MIDI files).

The repository has no index file: its file list is GitHub's tree of the main branch (one API request, cached a
week). Songs are "<Game OSTs | Non-Game OSTs | OC Artist Songs>/<series or artist>/<name> {authors}.s"; most use the
General MIDI instrument set NIMAP2 (decomp/nimap.py).
"""

from __future__ import annotations

import hashlib
import json
import re
import time
import urllib.parse

from . import ferepo

REPO = "Klokinator/FE-Repo-Music"
TREE_URL = f"https://api.github.com/repos/{REPO}/git/trees/main?recursive=1"
RAW_PREFIX = f"https://raw.githubusercontent.com/{REPO}/main/"
PAGE_PREFIX = f"https://github.com/{REPO}/blob/main/"
LICENSE = "Unlicense"
INDEX_FILE = "music_tree.json"
MAX_SONG = 2 * 1024 * 1024
MAX_PREVIEW = 16 * 1024 * 1024
SKIPPED = ("GBA Soundfonts/", "[AA] ")   # instrument sets and the repository's tools, not songs
PREVIEWS = (".ogg", ".mp3")


class FeRepoMusicError(Exception):
    pass


def _download(url: str, limit: int) -> bytes:
    if not url.startswith(RAW_PREFIX) and url != TREE_URL:
        raise FeRepoMusicError("notFeRepo")
    try:
        return ferepo._download_any(url, limit)
    except ferepo.FeRepoError as e:
        raise FeRepoMusicError(str(e)) from e


def load_index(refresh: bool = False) -> tuple[list[dict], float]:
    """The repository's songs ({"path", "name", "authors", "folder", "preview"}) and when the list was downloaded."""
    path = ferepo.cache_dir() / INDEX_FILE
    fresh = path.is_file() and time.time() - path.stat().st_mtime < ferepo.INDEX_MAX_AGE
    if not fresh or refresh:
        try:
            data = _download(TREE_URL, 32 * 1024 * 1024)
            json.loads(data)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
        except (FeRepoMusicError, ValueError):
            if not path.is_file():   # offline: the last list, if any
                raise
    tree = json.loads(path.read_text(encoding="utf-8")).get("tree", [])
    return songs([e["path"] for e in tree if e.get("type") == "blob"]), path.stat().st_mtime


def songs(paths: list[str]) -> list[dict]:
    """The .s files of the repository, each with its recorded preview when it has one."""
    stems = {p.rsplit(".", 1)[0]: p for p in paths if p.lower().endswith(PREVIEWS)}
    out = []
    for p in paths:
        if not p.endswith(".s") or p.startswith(SKIPPED):
            continue
        out.append({**describe(p), "preview": stems.get(p[:-2])})
    out.sort(key=lambda e: (e["folder"].lower(), e["name"].lower()))
    return out


def describe(path: str) -> dict:
    """What a song's path says: its name, authors (in braces, or the artist's folder) and folder."""
    parts = path.split("/")
    stem = parts[-1][:-2] if parts[-1].endswith(".s") else parts[-1]
    authors = [a.strip() for group in re.findall(r"\{([^}]*)\}", stem) for a in group.split(",") if a.strip()]
    name = re.sub(r"\s*\{[^}]*\}", "", stem).strip() or stem
    if not authors and parts[0] == "OC Artist Songs" and len(parts) > 2:
        authors = [parts[1]]
    return {"path": path, "name": name, "authors": authors, "folder": "/".join(parts[:-1])}


def search(entries: list[dict], query: str = "", folder: str = "", offset: int = 0, limit: int = 100):
    """Songs whose name, folder or authors contain all the words of the query; one page from `offset`."""
    words = [w for w in ferepo._fold(query).split() if w]
    found = [e for e in entries
             if (not folder or e["folder"] == folder or e["folder"].startswith(folder + "/"))
             and all(w in ferepo._fold(f"{e['name']} {e['folder']} {' '.join(e['authors'])}") for w in words)]
    return found[offset:offset + limit], len(found)


def folders(entries: list[dict]) -> list[dict]:
    """The folders to browse (series and artists, under their category), with their song count."""
    count: dict[str, int] = {}
    for e in entries:
        count[e["folder"]] = count.get(e["folder"], 0) + 1
    return [{"name": name, "count": n} for name, n in sorted(count.items(), key=lambda kv: kv[0].lower()) if name]


def _url(path: str) -> str:
    if ".." in path.split("/") or path.startswith("/"):
        raise FeRepoMusicError("notFeRepo")
    return RAW_PREFIX + urllib.parse.quote(path)


def fetch_song(path: str) -> str:
    """A song's .s file (2 MB at most)."""
    if not path.endswith(".s"):
        raise FeRepoMusicError("notFeRepo")
    return _download(_url(path), MAX_SONG).decode("utf-8", "replace")


def fetch_preview(path: str) -> tuple[bytes, str]:
    """A song's recorded preview and its media type, cached."""
    ext = path.rsplit(".", 1)[-1].lower()
    if f".{ext}" not in PREVIEWS:
        raise FeRepoMusicError("notFeRepo")
    cached = ferepo.cache_dir() / "music" / (hashlib.sha1(path.encode("utf-8")).hexdigest() + "." + ext)
    if not cached.is_file():
        data = _download(_url(path), MAX_PREVIEW)
        cached.parent.mkdir(parents=True, exist_ok=True)
        cached.write_bytes(data)
    return cached.read_bytes(), "audio/ogg" if ext == "ogg" else "audio/mpeg"


def source(path: str) -> dict:
    """The imported song's origin, for the project's credits (ferepo.credit_line)."""
    entry = describe(path)
    return {"name": entry["name"], "authors": entry["authors"], "license": LICENSE,
            "url": PAGE_PREFIX + urllib.parse.quote(path), "repo": "FE-Repo-Music"}
