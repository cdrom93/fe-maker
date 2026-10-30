"""First launch of a release (alpha, step 4): the decomp has no license, so FE Maker does not carry it: it downloads
it from GitHub, at the commit it is written against, into the user's config directory.
"""

from __future__ import annotations

import io
import shutil
import urllib.error
import urllib.request
import zipfile
from pathlib import Path

from .ferepo import _ssl_context
from .paths import DECOMP_COMMIT, DECOMP_DIR

ARCHIVE_URL = f"https://github.com/FireEmblemUniverse/fireemblem8u/archive/{DECOMP_COMMIT}.zip"
MAX_SIZE = 400 * 1024 * 1024


class DecompFetchError(Exception):
    pass


def _download() -> bytes:
    request = urllib.request.Request(ARCHIVE_URL, headers={"User-Agent": "FE-Maker"})
    try:
        with urllib.request.urlopen(request, timeout=120, context=_ssl_context()) as response:
            return response.read(MAX_SIZE)
    except OSError as e:
        raise DecompFetchError("unreachable") from e


def extract(archive: bytes, target: Path) -> None:
    """The archive's one top folder becomes `target`, in one move: a broken download leaves nothing behind."""
    temporary = target.with_name(target.name + ".download")
    shutil.rmtree(temporary, ignore_errors=True)
    temporary.mkdir(parents=True)
    root = temporary.resolve()
    try:
        with zipfile.ZipFile(io.BytesIO(archive)) as z:
            for info in z.infolist():
                relative = info.filename.partition("/")[2]
                if not relative or info.is_dir():
                    continue
                path = (temporary / relative).resolve()
                if not path.is_relative_to(root):
                    raise DecompFetchError("badArchive")
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(z.read(info))
    except zipfile.BadZipFile as e:
        raise DecompFetchError("badArchive") from e
    if not (temporary / "Makefile").is_file():
        raise DecompFetchError("badArchive")
    shutil.rmtree(target, ignore_errors=True)
    temporary.rename(target)


def fetch(target: Path = DECOMP_DIR) -> None:
    extract(_download(), target)
