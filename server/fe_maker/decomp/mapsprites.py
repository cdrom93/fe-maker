"""Map sprites imported for a class, from FE-Repo ("Map Sprites": "<name> {authors}-stand.png" and "-walk.png") or
the user's PC.

A standing sheet is three frames stacked: 16 x 48 (16 x 16 frames), 16 x 96 (16 x 32) or 32 x 96 (32 x 32); a moving
sheet is 32 x 480 (15 frames of 32 x 32). Both are 16-color pictures whose color 0 is transparent; the game draws
them with the palette of the unit's side, so FE Maker stores them with the player palette's indices (each color
goes to the nearest one of that palette).

At build time (DecompData.apply_map_sprites) each imported sprite gets new sheets after the game's (PNG files in
graphics/unit_icon, compiled by the decomp's generic rules), a row of unit_icon_wait_table (the class's SMSId; the
table is read with id & 0x7F, so 128 standing sprites at most) and the class's row of unit_icon_move_table points
to the new moving sheet, with the walking motion of the class's own sprite.

Project data: data/mapsprites.json {"classes": {class id: key}, "sprites": {key: {"name", "size", "source"}}};
pictures in the project's assets/mapsprites/<key>/stand.png and walk.png.
"""

from __future__ import annotations

import io
import re

from PIL import Image

WAIT_SIZES = {(16, 48): "UNIT_ICON_SIZE_16x16", (16, 96): "UNIT_ICON_SIZE_16x32", (32, 96): "UNIT_ICON_SIZE_32x32"}
MOVE_SIZE = (32, 480)
MAX_WAIT_SPRITES = 128
WAIT_TABLE_FILE = "src/unit_icon_wait_data.c"
WAIT_DATA_FILE = "data/const_data_unit_icon_wait.s"
MOVE_DATA_FILE = "data/const_data_unit_icon_move.s"
POINTERS_FILE = "include/unit_icon_pointer.h"


class MapSpriteError(Exception):
    pass


def to_palette(data: bytes, palette: list[tuple[int, int, int]]) -> Image.Image:
    """A sheet with the indices of `palette` (16 colors): color 0 stays transparent (index 0 of an indexed
    picture, else transparent pixels or the color of the top left pixel), the others go to the nearest color."""
    try:
        img = Image.open(io.BytesIO(data))
        img.load()
    except Exception as e:
        raise MapSpriteError("notAnImage") from e
    if img.mode == "P":
        source = img.getpalette() or []
        colors = [tuple(source[i * 3:i * 3 + 3]) for i in range(len(source) // 3)]
        pixels = list(img.tobytes())
        background = None
    else:
        rgba = img.convert("RGBA")
        raw = rgba.tobytes()
        pixels = [tuple(raw[i:i + 4]) for i in range(0, len(raw), 4)]
        colors = []
        background = pixels[0]

    def nearest(rgb) -> int:
        r, g, b = rgb[:3]
        return 1 + min(range(15), key=lambda i: (palette[i + 1][0] - r) ** 2 + (palette[i + 1][1] - g) ** 2
                       + (palette[i + 1][2] - b) ** 2)

    cache: dict = {}
    out = []
    for p in pixels:
        if background is None:
            transparent = p == 0
            key = p
        else:
            transparent = p[3] < 128 or p == background
            key = p[:3]
        if transparent:
            out.append(0)
        else:
            if key not in cache:
                cache[key] = nearest(colors[key] if background is None else key)
            out.append(cache[key])
    result = Image.new("P", img.size)
    result.putdata(out)
    flat = [c for rgb in palette[:16] for c in rgb]
    result.putpalette(flat + [0] * (768 - len(flat)))
    return result


def convert(stand: bytes, walk: bytes | None, palette: list[tuple[int, int, int]]) -> tuple[bytes, str, bytes | None]:
    """(standing sheet PNG, its UNIT_ICON_SIZE_x, moving sheet PNG or None), in the player palette."""
    wait = to_palette(stand, palette)
    size = WAIT_SIZES.get(wait.size)
    if size is None:
        raise MapSpriteError("badStandSize")
    move = None
    if walk is not None:
        move = to_palette(walk, palette)
        if move.size != MOVE_SIZE:
            raise MapSpriteError("badWalkSize")
    return _png(wait), size, (_png(move) if move is not None else None)


def _png(img: Image.Image) -> bytes:
    buffer = io.BytesIO()
    img.save(buffer, "PNG")
    return buffer.getvalue()


def sheet_name(kind: str, key: str) -> str:
    """unit_icon_wait_FEM_<key>_sheet / unit_icon_move_FEM_<key>_sheet."""
    return f"unit_icon_{kind}_FEM_{key}_sheet"


def safe_key(text: str) -> str:
    return re.sub(r"[^A-Za-z0-9]+", "_", text).strip("_")[:40] or "sprite"


def wait_rows(table_source: str) -> list[str]:
    return re.findall(r"\{\s*\d+\s*,\s*\w+\s*,\s*\w+\s*\}", table_source)


def with_wait_rows(table_source: str, rows: list[str]) -> str:
    """unit_icon_wait_table with `rows` added at its end ("{pattern, size, sheet}")."""
    found = list(re.finditer(r"\{\s*\d+\s*,\s*\w+\s*,\s*\w+\s*\}(,?)", table_source))
    last, count = found[-1], len(found)
    close = table_source.rindex("};")
    comma = "" if last.group(1) else ","   # the game's last row has none
    lines = "".join(f"\t{row}, // {count + i}\n" for i, row in enumerate(rows))
    return table_source[:last.end()] + comma + table_source[last.end():close] + lines + table_source[close:]


def incbin_block(name: str, folder: str) -> str:
    return f"\t.align 2, 0\n\t.global {name}\n{name}:\n\t.incbin \"graphics/unit_icon/{folder}/{name}.4bpp.lz\"\n"
