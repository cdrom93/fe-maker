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
import ssl
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

from .config import config_dir

INDEX_URL = "https://raw.githubusercontent.com/Klokinator/FE-Repo/main/file_urls.json"
URL_PREFIX = "https://raw.githubusercontent.com/Klokinator/FE-Repo/"
INDEX_MAX_AGE = 7 * 24 * 3600   # seconds before the index is downloaded again
MAX_FILE_BYTES = 2 * 1024 * 1024
PORTRAITS = "Portrait Repository"
ANIMATIONS = "Battle Animations"   # listed as folders (GitHub "tree" URLs), one per animation
TREE_PREFIX = "https://github.com/Klokinator/FE-Repo/tree/main/"
API_PREFIX = "https://api.github.com/repos/Klokinator/FE-Repo/contents/"

_NAME_RE = re.compile(r"^(?P<name>.*?)\s*(?:\{(?P<authors>[^}]*)\})?\s*(?P<tags>(?:\[[^\]]*\]\s*)*)$")


class FeRepoError(Exception):
    pass


def cache_dir() -> Path:
    return config_dir() / "ferepo"


def _ssl_context() -> ssl.SSLContext:
    """certifi's certificates: Windows' own store lacked an intermediate certificate of api.github.com
    on the user's PC (29/10/2026)."""
    try:
        import certifi

        return ssl.create_default_context(cafile=certifi.where())
    except ImportError:
        return ssl.create_default_context()


def _download(url: str, limit: int) -> bytes:
    if not url.startswith((URL_PREFIX, API_PREFIX)) and url != INDEX_URL:
        raise FeRepoError("notFeRepo")
    request = urllib.request.Request(url, headers={"User-Agent": "FE-Maker"})
    try:
        with urllib.request.urlopen(request, timeout=30, context=_ssl_context()) as response:
            data = response.read(limit + 1)
    except urllib.error.HTTPError as e:
        # GitHub's API answers 403 once the 60 requests an hour without an account are used
        raise FeRepoError("rateLimited" if e.code in (403, 429) else "unreachable") from e
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
        if not (url.startswith(TREE_PREFIX) if category == ANIMATIONS else url.lower().endswith(".png")):
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
        if url.lower().endswith(".png") or (category == ANIMATIONS and url.startswith(TREE_PREFIX)):
            top = describe(url)["folder"].split("/")[0]
            count[top] = count.get(top, 0) + 1
    return [{"name": name, "count": n} for name, n in sorted(count.items(), key=lambda kv: kv[0].lower()) if name]


def _fold(text: str) -> str:
    import unicodedata

    return "".join(c for c in unicodedata.normalize("NFD", text) if unicodedata.category(c) != "Mn").lower()


def fetch(url: str) -> bytes:
    """A picture of the repository (PNG, or GIF for the animations' previews; 2 MB at most), cached."""
    ext = url.lower().rsplit(".", 1)[-1]
    if not url.startswith(URL_PREFIX) or ext not in ("png", "gif"):
        raise FeRepoError("notFeRepo")
    path = cache_dir() / "files" / (hashlib.sha1(url.encode("utf-8")).hexdigest() + "." + ext)
    if path.is_file():
        return path.read_bytes()
    data = _download(url, MAX_FILE_BYTES)
    if not data.startswith(b"\x89PNG" if ext == "png" else b"GIF8"):
        raise FeRepoError("notAnImage")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return data


def credit_line(source: dict) -> str:
    authors = ", ".join(source.get("authors") or []) or source.get("credits") or "unknown author"
    return f"- {source.get('name', '?')} by {authors} ({source.get('license', 'F2U')}), FE-Repo: {source.get('url', '')}"


def folder_files(url: str) -> list[dict]:
    """Files and subfolders of an animation's folder ({"name", "type": "file" | "dir", "url", "size"}),
    asked to GitHub's API once (60 requests an hour without an account) and cached."""
    if not url.startswith(TREE_PREFIX):
        raise FeRepoError("notFeRepo")
    path = cache_dir() / "folders" / (hashlib.sha1(url.encode("utf-8")).hexdigest() + ".json")
    if path.is_file():
        return json.loads(path.read_text(encoding="utf-8"))
    repo_path = urllib.parse.unquote(url[len(TREE_PREFIX):])
    data = _download(API_PREFIX + urllib.parse.quote(repo_path) + "?ref=main", MAX_FILE_BYTES)
    try:
        listing = json.loads(data)
        # GitHub leaves some characters of its download URLs unencoded (spaces): build them again.
        files = [{"name": f["name"], "type": f["type"], "size": f.get("size", 0),
                  "url": (URL_PREFIX + "main/" if f["type"] == "file" else TREE_PREFIX)
                  + urllib.parse.quote(repo_path + "/" + f["name"])}
                 for f in listing]
    except (ValueError, KeyError, TypeError) as e:
        raise FeRepoError("unreachable") from e
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(files), encoding="utf-8")
    return files


def preview(files: list[dict]) -> str | None:
    """The picture showing an animation: its GIF if the folder has one, else its first PNG."""
    for ext in (".gif", ".png"):
        found = sorted(f["url"] for f in files if f["type"] == "file" and f["name"].lower().endswith(ext))
        if found:
            return found[0]
    return None


def fetch_text(url: str) -> str:
    """A text file of the repository (an animation's script), 1 MB at most, not cached."""
    if not url.startswith(URL_PREFIX) or not url.lower().endswith(".txt"):
        raise FeRepoError("notFeRepo")
    return _download(url, 1024 * 1024).decode("utf-8", errors="replace")


def folder_credits(url: str) -> str:
    """The CREDITS.txt of an animation's folder on one line (its authors when the folder name has none)."""
    try:
        found = [f for f in folder_files(url) if f["type"] == "file" and f["name"].lower() == "credits.txt"]
        text = fetch_text(found[0]["url"]) if found else ""
    except FeRepoError:
        return ""
    lines = [line.strip() for line in text.splitlines() if line.strip() and not re.fullmatch(r"F2[UE](/F2[UE])?", line.strip())]
    return " · ".join(lines)[:300]
