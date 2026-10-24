"""FE-Repo (https://github.com/Klokinator/FE-Repo), the community's resource repository, browsed from
FE Maker (phase 5).

Its root file_urls.json lists every file by category ({"Portrait Repository": [raw URLs]...}); file
names say what the resource is, who made it and how it may be used:
"Amelia (Knight) {Nuramon, Plant_Academy, UltraFenix} [F2E].png". F2E: free to use and to edit;
without a tag, the repository's README says to assume F2U (free to use, not to edit). Either way the
authors must be credited: FE Maker writes them in the project's CREDITS.txt.

The index and the downloaded files are cached in the user's config folder (ferepo/).
"""

from __future__ import annotations

import hashlib
import json
import re
import time
import urllib.parse
import urllib.request
from pathlib import Path

from .config import config_dir

INDEX_URL = "https://raw.githubusercontent.com/Klokinator/FE-Repo/main/file_urls.json"
URL_PREFIX = "https://raw.githubusercontent.com/Klokinator/FE-Repo/"
INDEX_MAX_AGE = 7 * 24 * 3600   # seconds before the index is downloaded again
MAX_FILE_BYTES = 2 * 1024 * 1024
PORTRAITS = "Portrait Repository"

_NAME_RE = re.compile(r"^(?P<name>.*?)\s*(?:\{(?P<authors>[^}]*)\})?\s*(?P<tags>(?:\[[^\]]*\]\s*)*)$")


class FeRepoError(Exception):
    pass


def cache_dir() -> Path:
    return config_dir() / "ferepo"


def _download(url: str, limit: int) -> bytes:
    if not url.startswith(URL_PREFIX) and url != INDEX_URL:
        raise FeRepoError("notFeRepo")
    request = urllib.request.Request(url, headers={"User-Agent": "FE-Maker"})
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            data = response.read(limit + 1)
    except OSError as e:
        raise FeRepoError("unreachable") from e
    if len(data) > limit:
        raise FeRepoError("tooBig")
    return data


def load_index(refresh: bool = False) -> tuple[dict[str, list[str]], float]:
    """The repository's index and when it was downloaded (cached for a week)."""
    path = cache_dir() / "file_urls.json"
    if path.is_file() and not refresh and time.time() - path.stat().st_mtime < INDEX_MAX_AGE:
        return json.loads(path.read_text(encoding="utf-8")), path.stat().st_mtime
    try:
        data = _download(INDEX_URL, 64 * 1024 * 1024)
        index = json.loads(data)
    except (FeRepoError, ValueError):
        if path.is_file():   # offline: the last index
            return json.loads(path.read_text(encoding="utf-8")), path.stat().st_mtime
        raise
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return index, path.stat().st_mtime


def describe(url: str) -> dict:
    """What a file name says: {"url", "folder", "name", "authors": [...], "license": "F2E" | "F2U"}."""
    path = urllib.parse.unquote(url.split("/main/", 1)[-1])
    parts = path.split("/")
    stem = re.sub(r"\.[A-Za-z0-9]+$", "", parts[-1])
    m = _NAME_RE.match(stem)
    tags = re.findall(r"\[([^\]]*)\]", m.group("tags") or "") if m else []
    authors = [a.strip() for a in (m.group("authors") or "").split(",") if a.strip()] if m else []
    return {"url": url, "folder": "/".join(parts[1:-1]), "name": (m.group("name") if m else stem).strip(),
            "authors": authors, "license": "F2E" if any(t.upper() == "F2E" for t in tags) else "F2U"}


def search(index: dict[str, list[str]], category: str, query: str = "", limit: int = 120, folder: str = "",
           offset: int = 0, f2e_only: bool = False) -> tuple[list[dict], int]:
    """PNG files of a category whose name, folder or authors contain all the words of the query; `folder`:
    only that folder (and its subfolders); `f2e_only`: only files free to edit. One page from `offset`."""
    words = [w for w in _fold(query).split() if w]
    found = []
    for url in index.get(category, []):
        if not url.lower().endswith(".png"):
            continue
        entry = describe(url)
        if folder and entry["folder"] != folder and not entry["folder"].startswith(folder + "/"):
            continue
        if f2e_only and entry["license"] != "F2E":
            continue
        text = _fold(f"{entry['name']} {entry['folder']} {' '.join(entry['authors'])}")
        if all(w in text for w in words):
            found.append(entry)
    # Parts to build portraits with (the "Assistive..." folder) and loose files of the repository
    # (references, tutorials) after the portraits themselves.
    found.sort(key=lambda e: (not e["folder"] or e["folder"].startswith("Assistive"), e["folder"], e["name"]))
    return found[offset:offset + limit], len(found)


def folders(index: dict[str, list[str]], category: str) -> list[dict]:
    """Top folders of a category (games, artists, generic portraits...) with their PNG count, to browse."""
    count: dict[str, int] = {}
    for url in index.get(category, []):
        if url.lower().endswith(".png"):
            top = describe(url)["folder"].split("/")[0]
            count[top] = count.get(top, 0) + 1
    return [{"name": name, "count": n} for name, n in sorted(count.items(), key=lambda kv: kv[0].lower()) if name]


def _fold(text: str) -> str:
    import unicodedata

    return "".join(c for c in unicodedata.normalize("NFD", text) if unicodedata.category(c) != "Mn").lower()


def fetch(url: str) -> bytes:
    """A file of the repository (PNG only, 2 MB at most), cached."""
    if not url.startswith(URL_PREFIX) or not url.lower().endswith(".png"):
        raise FeRepoError("notFeRepo")
    path = cache_dir() / "files" / (hashlib.sha1(url.encode("utf-8")).hexdigest() + ".png")
    if path.is_file():
        return path.read_bytes()
    data = _download(url, MAX_FILE_BYTES)
    if not data.startswith(b"\x89PNG"):
        raise FeRepoError("notAnImage")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return data


def credit_line(source: dict) -> str:
    authors = ", ".join(source.get("authors") or []) or "unknown author"
    return f"- {source.get('name', '?')} by {authors} ({source.get('license', 'F2U')}), FE-Repo: {source.get('url', '')}"
