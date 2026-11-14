"""FE Maker's own updates (question #58): at launch the interface asks for the newest published release on GitHub;
on one click its package (tools/make_release.py's zip) replaces FE Maker's files and FE Maker starts again.

Only a packaged FE Maker updates itself (the launcher beside `server/`, no `.git`): a developer's checkout never does.
Projects, settings, the decomp and the build tools live elsewhere (config_dir(), the projects folder) and are not
touched. The replaced trees are moved aside first (`.update-old/`) and put back if anything fails.
"""

from __future__ import annotations

import io
import json
import re
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request
import zipfile
from pathlib import Path

from . import __version__

REPO = "cdrom93/fe-maker"
API_URL = f"https://api.github.com/repos/{REPO}/releases?per_page=10"
DOWNLOAD_PREFIX = f"https://github.com/{REPO}/releases/download/"
PACKAGE_ROOT = "fe-maker/"
MAX_PACKAGE = 200 * 1024 * 1024
# What a package holds (tools/make_release.py): these trees are replaced whole, the other files one by one.
TREES = ("server/fe_maker", "ui/dist")
STAGES = ("prealpha", "alpha", "beta", "rc")
_CACHE_SECONDS = 3600
_cache: dict = {"at": 0.0, "value": None}


class UpdateError(Exception):
    pass


def parse_version(text: str) -> tuple:
    """"0.1.0-prealpha.15" -> (0, 1, 0, 0, 15); a final version sorts after its pre-releases."""
    m = re.fullmatch(r"v?(\d+)\.(\d+)\.(\d+)(?:-([a-z]+)\.?(\d+)?)?", text.strip())
    if not m:
        return ()
    major, minor, patch, stage, n = m.groups()
    rank = STAGES.index(stage) if stage in STAGES else len(STAGES) if stage is None else -1
    return int(major), int(minor), int(patch), rank, int(n or 0)


def install_dir() -> Path:
    return Path(__file__).resolve().parents[2]


def installable(root: Path | None = None) -> bool:
    """A packaged FE Maker (launcher beside server/), not a git checkout."""
    root = root or install_dir()
    return (root / "lancer-fe-maker.bat").is_file() and not (root / ".git").exists()


def newest(releases: list[dict], current: str = __version__) -> dict | None:
    """The newest published release newer than `current` with a package: {version, url, page}."""
    best = None
    for release in releases:
        if release.get("draft"):
            continue
        version = release.get("tag_name", "").removeprefix("v")
        asset = next((a for a in release.get("assets", [])
                      if re.fullmatch(r"fe-maker-.+\.zip", a.get("name", ""))
                      and str(a.get("browser_download_url", "")).startswith(DOWNLOAD_PREFIX)), None)
        if not asset or not parse_version(version) or parse_version(version) <= parse_version(current):
            continue
        if best is None or parse_version(version) > parse_version(best["version"]):
            best = {"version": version, "url": asset["browser_download_url"], "page": release.get("html_url", "")}
    return best


def _get(url: str, limit: int) -> bytes:
    from .ferepo import _ssl_context
    request = urllib.request.Request(url, headers={"User-Agent": "FE-Maker", "Accept": "application/vnd.github+json"})
    try:
        with urllib.request.urlopen(request, timeout=60, context=_ssl_context()) as response:
            data = response.read(limit + 1)
    except (urllib.error.URLError, OSError) as e:
        raise UpdateError("unreachable") from e
    if len(data) > limit:
        raise UpdateError("tooLarge")
    return data


def check(force: bool = False) -> dict | None:
    """The release to install, if any (asked to GitHub at most once an hour); None when offline."""
    if not force and time.time() - _cache["at"] < _CACHE_SECONDS:
        return _cache["value"]
    try:
        value = newest(json.loads(_get(API_URL, 2 * 1024 * 1024)))
    except (UpdateError, ValueError):
        value = None
    _cache.update(at=time.time(), value=value)
    return value


def unpack(data: bytes, target: Path) -> None:
    """A package's files under `target` (its "fe-maker/" folder's content); refused if it holds anything else."""
    try:
        archive = zipfile.ZipFile(io.BytesIO(data))
    except zipfile.BadZipFile as e:
        raise UpdateError("badPackage") from e
    names = [n for n in archive.namelist() if not n.endswith("/")]
    if not names or any(not n.startswith(PACKAGE_ROOT) or ".." in Path(n).parts for n in names):
        raise UpdateError("badPackage")
    if f"{PACKAGE_ROOT}server/fe_maker/__init__.py" not in names or f"{PACKAGE_ROOT}ui/dist/index.html" not in names:
        raise UpdateError("badPackage")
    for name in names:
        path = target / name[len(PACKAGE_ROOT):]
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(archive.read(name))


def replace(root: Path, new: Path) -> None:
    """Put the unpacked package `new` in place of FE Maker's files under `root` (trees whole, other files one by one);
    what it replaces goes to root/.update-old, put back if a step fails."""
    old = root / ".update-old"
    shutil.rmtree(old, ignore_errors=True)
    moved: list[tuple[Path, Path]] = []
    try:
        for tree in TREES:
            if (root / tree).exists():
                (old / tree).parent.mkdir(parents=True, exist_ok=True)
                (root / tree).rename(old / tree)
                moved.append((old / tree, root / tree))
            (root / tree).parent.mkdir(parents=True, exist_ok=True)
            shutil.copytree(new / tree, root / tree)
        for path in sorted(new.rglob("*")):
            rel = path.relative_to(new)
            if path.is_dir() or any(rel.as_posix().startswith(t + "/") for t in TREES):
                continue
            if (root / rel).exists():
                (old / rel).parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(root / rel, old / rel)
                moved.append((old / rel, root / rel))
            (root / rel).parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, root / rel)
    except OSError as e:
        for saved, place in reversed(moved):
            if saved.is_dir():
                shutil.rmtree(place, ignore_errors=True)
                saved.rename(place)
            else:
                shutil.copy2(saved, place)
        raise UpdateError("cannotReplace") from e


def install(release: dict, root: Path | None = None) -> None:
    """Download the release's package, put it in place and install its Python dependencies; FE Maker restarts after."""
    root = root or install_dir()
    if not installable(root):
        raise UpdateError("notPackaged")
    if not str(release.get("url", "")).startswith(DOWNLOAD_PREFIX):
        raise UpdateError("badPackage")
    data = _get(release["url"], MAX_PACKAGE)
    staging = root / ".update-new"
    shutil.rmtree(staging, ignore_errors=True)
    try:
        unpack(data, staging)
        replace(root, staging)
    finally:
        shutil.rmtree(staging, ignore_errors=True)
    subprocess.run(pip_command(root), cwd=root, check=False, timeout=600)
    _cache.update(at=0.0, value=None)


def pip_command(root: Path) -> list[str]:
    """Installing the new version's dependencies. Installed with the Windows installer (its own Python in root/python,
    which finds fe_maker through its ._pth file): only the dependencies still missing, never the ones in use replaced;
    from the zip: the editable install of the .venv."""
    if (root / "python" / "python.exe").is_file():
        text = (root / "server" / "pyproject.toml").read_text(encoding="utf-8")
        block = re.search(r"^dependencies = \[(.*?)^\]", text, re.MULTILINE | re.DOTALL)
        needed = re.findall(r'^\s*"([^"]+)"', block.group(1), re.MULTILINE) if block else []
        return [str(root / "python" / "python.exe"), "-m", "pip", "install", "--quiet", "--no-warn-script-location",
                *needed]
    return [sys.executable, "-m", "pip", "install", "--quiet", "-e", str(root / "server")]


def restart(port: int, root: Path | None = None) -> None:
    """Start FE Maker again on the same port in a window of its own: the new launch stops this server
    (/api/shutdown) and takes over."""
    root = root or install_dir()
    flags = getattr(subprocess, "CREATE_NEW_CONSOLE", 0)
    subprocess.Popen([sys.executable, "-m", "fe_maker", "--no-browser", "--port", str(port)], cwd=root,
                     creationflags=flags)
