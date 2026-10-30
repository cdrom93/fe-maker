"""Chapter title images (the strip shown at the start of a chapter and in the save menu, chap_title_data).

A title is a 256 x 16 picture, not a text, so a chapter the project adds would show the title of the slot it took.
FE Maker draws one from the title's text, in the style of the game's: the letters of the game's talk font thickened
to 2 pixels (color 1, then 3 on the right), with a light outline on the top left (5) and a dark one on the bottom
right (6). The picture is centered on the visible part of the strip, the 192 pixels of the screen.
"""

from __future__ import annotations

import io
from pathlib import Path

from PIL import Image

from . import fonts

TITLE_FILE = "graphics/chap_title/chap_title_{n}.png"
TABLE_FILE = "src/chap_title_data.c"
DATA_FILE = "data/data_chap_title.s"
POINTERS_FILE = "include/chap_title_pointer.h"
SIZE = (256, 16)
VISIBLE_WIDTH = 192
FIRST_NEW_ID = 0x58   # chapTitleId is one byte, PutChapterTitleGfx accepts up to 0x108
LAST_NEW_ID = 0xFF
INK = 3   # the font's letters; 2 is their shadow
_SPACE = 4


def _letters(decomp_dir: Path) -> tuple[Image.Image, dict[int, int]] | None:
    sheet = fonts.font_sheet(decomp_dir, "talk")
    return (Image.open(io.BytesIO(sheet)), fonts.widths(decomp_dir, "talk")) if sheet else None


def text_width(decomp_dir: Path, title: str, spacing: int = 2) -> int:
    """Width of a title drawn with `spacing` pixels added after each letter."""
    loaded = _letters(decomp_dir)
    if loaded is None:
        return 0
    _sheet, widths = loaded
    return sum((widths.get(fonts.char_byte(c) or 0x20, 6) + spacing) if c != " " else _SPACE for c in title)


def strip(decomp_dir: Path, title: str, template: Path) -> bytes:
    """PNG of a title strip, with the palette of `template` (one of the game's strips)."""
    loaded = _letters(decomp_dir)
    if loaded is None:
        raise FileNotFoundError("font")
    sheet, widths = loaded
    ink_color = fonts.SHEET_COLORS[INK]
    spacing = 2
    while spacing > 0 and text_width(decomp_dir, title, spacing) > VISIBLE_WIDTH - 4:
        spacing -= 1
    x0 = max(2, (VISIBLE_WIDTH - text_width(decomp_dir, title, spacing)) // 2)
    pen, ink = x0, set()
    for c in title:
        byte = fonts.char_byte(c) or 0x3F
        if c != " ":
            for gy in range(16):
                for gx in range(16):
                    if sheet.getpixel(((byte % 16) * 16 + gx, (byte // 16) * 16 + gy)) == ink_color:
                        ink.add((pen + gx, gy))
            pen += widths.get(byte, 6) + spacing
        else:
            pen += _SPACE
    # the game's letters sit from row 1 to row 12
    top = min((y for _x, y in ink), default=0)
    ink = {(x, y - top + 1) for x, y in ink}
    cells: dict[tuple[int, int], int] = {}
    for x, y in ink:
        cells[(x, y)] = 1
    for x, y in ink:
        if (x + 1, y) not in ink:
            cells[(x + 1, y)] = 3
    filled = dict(cells)
    for (x, y) in filled:
        for dx, dy in ((-1, 0), (0, -1), (-1, -1), (1, -1), (-1, 1)):
            cells.setdefault((x + dx, y + dy), 5)
    for (x, y) in filled:
        for dx, dy in ((1, 0), (0, 1), (1, 1)):
            if cells.get((x + dx, y + dy), 0) in (0, 5):
                cells[(x + dx, y + dy)] = 6
    img = Image.new("P", SIZE, 0)
    img.putpalette(Image.open(template).getpalette())
    for (x, y), color in cells.items():
        if 0 <= x < SIZE[0] and 0 <= y < SIZE[1]:
            img.putpixel((x, y), color)
    out = io.BytesIO()
    img.save(out, "PNG")
    return out.getvalue()
