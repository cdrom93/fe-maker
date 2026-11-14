"""mGBA downloaded and set up from the home page (ticket 81), Windows only: its portable build from its GitHub release
(MPL-2.0), unpacked with Windows' own tar (libarchive reads 7-Zip) into FE Maker's config dir; the settings then point
to it. Without a tar able to read it (an old Windows 10), the page keeps its link to mGBA's site.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

from . import downloads
from .config import Settings, config_dir
from .ferepo import _ssl_context

VERSION = "0.10.5"
URL = f"https://github.com/mgba-emu/mgba/releases/download/{VERSION}/mGBA-{VERSION}-win64.7z"
MAX_SIZE = 60 * 1024 * 1024


class MgbaFetchError(Exception):
    pass


def available() -> bool:
    return os.name == "nt" and _tar() is not None


def _tar() -> str | None:
    system = Path(os.environ.get("SystemRoot", r"C:\Windows")) / "System32" / "tar.exe"
    return str(system) if system.is_file() else None


def target() -> Path:
    return config_dir() / "mgba"


def install(archive: bytes, folder: Path) -> Path:
    """Unpack the archive into `folder` in one move (a broken download leaves nothing behind); mGBA.exe's path."""
    tar = _tar()
    if tar is None:
        raise MgbaFetchError("noTar")
    temporary = folder.with_name(folder.name + ".download")
    shutil.rmtree(temporary, ignore_errors=True)
    temporary.mkdir(parents=True)
    archive_path = temporary / "mgba.7z"
    archive_path.write_bytes(archive)
    result = subprocess.run([tar, "-xf", str(archive_path), "-C", str(temporary)], capture_output=True,
                            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    archive_path.unlink(missing_ok=True)
    found = next(iter(sorted(temporary.rglob("mGBA.exe"))), None)
    if result.returncode or found is None:
        shutil.rmtree(temporary, ignore_errors=True)
        raise MgbaFetchError("badArchive")
    inner = found.parent.relative_to(temporary)
    shutil.rmtree(folder, ignore_errors=True)
    temporary.rename(folder)
    return folder / inner / "mGBA.exe"


def fetch(settings: Settings) -> None:
    try:
        archive = downloads.get(URL, MAX_SIZE, 300, _ssl_context())
    except OSError as e:
        raise MgbaFetchError("unreachable") from e
    settings.mgba_path = str(install(archive, target()))
    settings.save()
