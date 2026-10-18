"""User ROM validation. FE Maker only accepts Fire Emblem: The Sacred Stones (US)."""

import hashlib
from pathlib import Path

FE8_US_SHA1 = "c25b145e37456171ada4b0d440bf88a19f4d509f"


class InvalidRomError(Exception):
    pass


def sha1_of(path: Path) -> str:
    h = hashlib.sha1()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def check_rom(path: Path) -> None:
    if not path.is_file():
        raise InvalidRomError(f"ROM not found: {path}")
    if sha1_of(path) != FE8_US_SHA1:
        raise InvalidRomError("This ROM is not Fire Emblem: The Sacred Stones (US).")
