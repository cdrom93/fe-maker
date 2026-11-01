"""Item icons imported into a project (ticket 139).

The game keeps a 16 x 16 icon sheet with one shared palette, and only tracks 224 icons (MAX_ICON_COUNT, src/icon.c):
imported icons take the places the game leaves unused. Project data: data/icons.json {"icons": {"<icon id>": {name,
source}}}, the pictures in assets/icons/<icon id>.png, already in the game's palette.
"""

import io
from pathlib import Path

from .mapsprites import MapSpriteError, to_palette

FOLDER = "icons"
SIZE = (16, 16)


def free_slots(icon_files: list[str]) -> list[int]:
    """The ids of the icons the game does not use."""
    return [i for i, name in enumerate(icon_files) if "_unused_" in Path(name).name]


def convert(data: bytes, palette: list[tuple[int, int, int]]) -> bytes:
    """An icon picture as an indexed PNG in the icons' palette."""
    icon = to_palette(data, palette)
    if icon.size != SIZE:
        raise MapSpriteError("badIconSize")
    out = io.BytesIO()
    icon.save(out, format="PNG", transparency=0)
    return out.getvalue()
