"""Chapter title images (the strip shown at the start of a chapter and in the save menu, chap_title_data).

A title is a 256 x 16 picture, not a text, so a chapter the project adds would show the title of the slot it took.
FE Maker draws one from the title's text with the game's own letters: they are read from the strips of the user's
decomp (never stored in the project or the repository), each strip giving the letters of its chapter's title. The
letters of a strip are its connected shapes of ink (colors 1 to 4, each letter with its own outline, 5 and 6). A strip
starts with "Ch 3:" and the like, and some letters touch: a letter is kept when several strips agree on it, then
the letters already known find the ones between them.

A letter the game never wrote in a title (x, Y, Z...) comes from the talk font, thickened to 2 pixels (color 1, then
3 on the right), with a light outline on the top left (5) and a dark one on the bottom right (6). An accent is added
to the game's letter. The picture is centered on the visible part of the strip, the 192 pixels of the screen.
"""

from __future__ import annotations

import io
import unicodedata
from collections import Counter, defaultdict
from dataclasses import dataclass
from functools import lru_cache
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
_STRIP_INK = {1, 2, 3, 4}
_SPACE = 5
_NARROW = "!'.,:;Iiljt"


def _letters(decomp_dir: Path) -> tuple[Image.Image, dict[int, int]] | None:
    sheet = fonts.font_sheet(decomp_dir, "talk")
    return (Image.open(io.BytesIO(sheet)), fonts.widths(decomp_dir, "talk")) if sheet else None


def text_width(decomp_dir: Path, title: str, spacing: int = 2) -> int:
    """About the width of a title, from the talk font; used to warn of a title too long."""
    loaded = _letters(decomp_dir)
    if loaded is None:
        return 0
    _sheet, widths = loaded
    return sum((widths.get(fonts.char_byte(c) or 0x20, 6) + spacing) if c != " " else _SPACE for c in title)


@dataclass
class Glyph:
    """A letter: its cells {(x, y): color}, x from the left of its ink."""
    cells: dict[tuple[int, int], int]
    width: int   # of its ink


def _styled(ink: set[tuple[int, int]]) -> dict[tuple[int, int], int]:
    """Cells of a shape in the style of the strips: stroke, then outline."""
    cells = {cell: 1 for cell in ink}
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
    return cells


def _pieces(pixels) -> list[list[tuple[int, int]]]:
    """Shapes of ink of a strip, left to right; shapes above each other (i, !, :) count as one."""
    seen: set[tuple[int, int]] = set()
    found = []
    for x in range(SIZE[0]):
        for y in range(SIZE[1]):
            if (x, y) in seen or pixels[x, y] not in _STRIP_INK:
                continue
            todo, cells = [(x, y)], []
            seen.add((x, y))
            while todo:
                cx, cy = todo.pop()
                cells.append((cx, cy))
                for near in ((cx + 1, cy), (cx - 1, cy), (cx, cy + 1), (cx, cy - 1)):
                    if 0 <= near[0] < SIZE[0] and 0 <= near[1] < SIZE[1] and near not in seen and pixels[near] in _STRIP_INK:
                        seen.add(near)
                        todo.append(near)
            found.append(cells)
    found.sort(key=lambda cells: min(x for x, _y in cells))
    merged: list[list[tuple[int, int]]] = []
    for cells in found:
        if merged and min(x for x, _y in cells) <= max(x for x, _y in merged[-1]):
            merged[-1] += cells
        else:
            merged.append(cells)
    return merged


def _shape(pixels, cells: list[tuple[int, int]]) -> tuple:
    left = min(x for x, _y in cells)
    return tuple(sorted((x - left, y, pixels[x, y]) for x, y in cells))


def _glyph(pixels, cells: list[tuple[int, int]]) -> Glyph:
    """A letter with the outline around its ink in the strip."""
    left = min(x for x, _y in cells)
    ink = set(cells)
    found = {(x - left, y): pixels[x, y] for x, y in ink}
    for (x, y) in ink:
        for dx, dy, color in ((-1, -1, 5), (-1, 0, 5), (-1, 1, 5), (0, -1, 5), (1, -1, 5),
                              (1, 0, 6), (1, 1, 6), (0, 1, 6), (-1, 1, 6)):
            at = (x + dx, y + dy)
            if at not in ink and 0 <= at[0] < SIZE[0] and 0 <= at[1] < SIZE[1] and pixels[at] == color:
                found[(at[0] - left, at[1])] = color
    return Glyph(found, max(x for x, _y in cells) - left + 1)


def _find(pixels, shape: tuple, right: int, reach: int) -> int | None:
    """Where a known letter is, ending before column `right`, nearest first."""
    width = max(x for x, _y, _c in shape) + 1
    for left in range(right - width, max(right - width - reach, -1), -1):
        ink = sum(pixels[x, y] in _STRIP_INK for x in range(left, left + width) for y in range(SIZE[1]))
        if ink <= len(shape) + 3 and all(pixels[left + x, y] == color for x, y, color in shape):
            return left
    return None


def _learn(strips: list[tuple[str, object]]) -> dict[str, Glyph]:
    votes: dict[str, Counter] = defaultdict(Counter)
    glyphs: dict[tuple, Glyph] = {}

    def vote(letter: str, pixels, cells: list[tuple[int, int]]) -> None:
        shape = _shape(pixels, cells)
        votes[letter][shape] += 1
        glyphs.setdefault(shape, _glyph(pixels, cells))

    for title, pixels in strips:
        letters, found = title.replace(" ", ""), _pieces(pixels)
        if len(found) >= len(letters):
            for letter, cells in zip(letters, found[len(found) - len(letters):]):
                vote(letter, pixels, cells)
    def best(counter: Counter, letter: str, least: int) -> tuple | None:
        shapes = [(shape, n) for shape, n in counter.most_common()
                  if max(x for x, _y, _c in shape) + 1 >= (1 if letter in _NARROW else 4) and n >= least]
        return shapes[0][0] if shapes else None

    known = {letter: shape for letter, counter in votes.items() if (shape := best(counter, letter, 2))}
    for _round in range(3):
        votes = defaultdict(Counter)
        for title, pixels in strips:
            letters = title.replace(" ", "")
            right = 1 + max((x for x in range(SIZE[0]) for y in range(SIZE[1]) if pixels[x, y] in _STRIP_INK), default=-1)
            waiting = None   # a letter not known yet, right of the one looked for
            for letter in reversed(letters):
                if letter not in known:
                    if waiting is not None:
                        break   # two in a row: nothing tells where they part
                    waiting = letter
                    continue
                left = _find(pixels, known[letter], right, 22 if waiting else 8)
                if left is None:
                    break
                if waiting is not None:
                    end = left + max(x for x, _y, _c in known[letter]) + 1
                    cells = [(x, y) for x in range(end, right) for y in range(SIZE[1]) if pixels[x, y] in _STRIP_INK]
                    if cells:
                        vote(waiting, pixels, cells)
                    waiting = None
                right = left
            else:
                if waiting is not None:   # the title's first letter: the shape before it is the prefix's colon
                    before = [cells for cells in _pieces(pixels) if max(x for x, _y in cells) < right]
                    if before:
                        vote(waiting, pixels, before[-1])
        for letter, counter in votes.items():
            shape = best(counter, letter, 1)
            if shape:
                known.setdefault(letter, shape)
    return {letter: glyphs[shape] for letter, shape in known.items()}


@lru_cache(maxsize=4)
def _game_letters(decomp_dir: Path, titles: tuple[tuple[int, str], ...]) -> dict[str, Glyph]:
    strips = []
    for number, title in titles:
        path = decomp_dir / TITLE_FILE.format(n=number)
        if title and path.is_file():
            strips.append((title, Image.open(path).convert("P").load()))
    return _learn(strips)


def _accented(base: Glyph, mark: str) -> Glyph:
    """A letter of the game with an accent above it (or a cedilla below), when there is room: not on capitals."""
    ink = [(x, y) for (x, y), color in base.cells.items() if color in _STRIP_INK]
    top, bottom, middle = min(y for _x, y in ink), max(y for _x, y in ink), base.width // 2
    shape = {"\u0301": [(middle + 1, top - 3), (middle, top - 2)], "\u0300": [(middle - 1, top - 3), (middle, top - 2)],
             "\u0302": [(middle - 1, top - 2), (middle, top - 3), (middle + 1, top - 2)],
             "\u0308": [(middle - 2, top - 2), (middle + 1, top - 2)], "\u0327": [(middle, bottom + 1)]}.get(mark)
    if not shape or min(y for _x, y in shape) < 0:
        return base
    return Glyph({**_styled(set(shape)), **base.cells}, base.width)


def _font_glyph(sheet: Image.Image, byte: int) -> Glyph:
    """A letter of the talk font, its capitals' top on row 1 like the game's."""
    ink_color = fonts.SHEET_COLORS[INK]
    ink = {(gx, gy) for gy in range(16) for gx in range(16)
           if sheet.getpixel(((byte % 16) * 16 + gx, (byte // 16) * 16 + gy)) == ink_color}
    capital = ord("H")
    tops = [gy for gy in range(16) for gx in range(16)
            if sheet.getpixel(((capital % 16) * 16 + gx, (capital // 16) * 16 + gy)) == ink_color]
    shift = 1 - min(tops, default=1)
    left = min((x for x, _y in ink), default=0)
    moved = {(x - left, y + shift) for x, y in ink}
    return Glyph(_styled(moved), max((x for x, _y in moved), default=0) + 2)


def _layout(decomp_dir: Path, title: str, known: dict[str, Glyph], spacing: int) -> tuple[list[tuple[int, Glyph]], int]:
    """Each letter with its place, and the width of the text."""
    loaded = _letters(decomp_dir)
    pen, placed = 0, []
    for c in title:
        if c == " ":
            pen += _SPACE
            continue
        plain = unicodedata.normalize("NFD", c)
        if c in known:
            glyph = known[c]
        elif plain[0] in known:
            glyph = _accented(known[plain[0]], plain[1:2])
        elif loaded is not None:
            glyph = _font_glyph(loaded[0], fonts.char_byte(c) or 0x3F)
        else:
            raise FileNotFoundError("font")
        placed.append((pen, glyph))
        pen += glyph.width + spacing
    return placed, max(pen - spacing, 0)


def strip(decomp_dir: Path, title: str, template: Path, game_titles: dict[int, str] | None = None) -> bytes:
    """PNG of a title strip, with the palette of `template` (one of the game's strips); `game_titles`: the texts of the
    game's strips by number, where the letters are read from."""
    known = _game_letters(decomp_dir, tuple(sorted((game_titles or {}).items())))
    spacing = 1
    placed, width = _layout(decomp_dir, title, known, spacing)
    while spacing > 0 and width > VISIBLE_WIDTH - 4:
        spacing -= 1
        placed, width = _layout(decomp_dir, title, known, spacing)
    x0 = max(2, (VISIBLE_WIDTH - width) // 2)
    img = Image.new("P", SIZE, 0)
    img.putpalette(Image.open(template).getpalette())
    pixels = img.load()
    for pen, glyph in placed:
        for (x, y), color in glyph.cells.items():
            at = (x0 + pen + x, y)
            if 0 <= at[0] < SIZE[0] and 0 <= y < SIZE[1] and (color in _STRIP_INK or pixels[at] not in _STRIP_INK):
                pixels[at] = color
    out = io.BytesIO()
    img.save(out, "PNG")
    return out.getvalue()
