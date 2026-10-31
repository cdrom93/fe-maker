"""A character's own colours in battle, by class (FEBuilder's "Unit Palette").

The game keeps them in src/classchg-data.c: for each character, up to seven slots of gAnimCharaPalConfig give a class
and the same slots of gAnimCharaPalIt give a row (from 1, 0: none) of character_battle_animation_palette_table
(src/banim_pal_chara.c). Each row points to a compressed palette of 5 lines of 16 colours, for the sides of the unit.

Characters' "battleColors" (data/characters.json): {class id: 5 lines of 16 "#rrggbb", or null for the class's colours};
a class left out keeps what the game does. New palettes are added after the game's, only when a project sets some.
"""

from __future__ import annotations

import re
import struct
from pathlib import Path

CONFIG_FILE = "src/classchg-data.c"
TABLE_FILE = "src/banim_pal_chara.c"
DATA_FILE = "data/data_banim_pal.s"
PALETTE_DIR = "graphics/banim/character_palette"
LINES = 5
SLOTS = 7
LAST_ROW = 0xFF  # the table's rows are bytes


class PaletteError(Exception):
    pass


def _block(source: str, name: str) -> tuple[int, int]:
    """Start and end of the entries of a two-level array, `name`."""
    start = source.index("{", re.search(name + r"\[0x100\]\[7\]\s*=", source).end()) + 1
    return start, source.index("\n};", start)


def _entries(body: str) -> dict[str, dict[int, str]]:
    return {m.group(1): {int(s): v for s, v in re.findall(r"\[(\d)\]\s*=\s*(\w+)", m.group(2))}
            for m in re.finditer(r"\[(\w+) - 1\]\s*=\s*\{(.*?)\}", body, re.S)}


def game_slots(source: str) -> dict[str, dict[str, int]]:
    """Character -> class -> row of the palette table (from 0), as the game has them; a row 0 in the file is no palette."""
    begin, end = _block(source, "gAnimCharaPalConfig")
    classes = _entries(source[begin:end])
    begin, end = _block(source, "gAnimCharaPalIt")
    rows = _entries(source[begin:end])
    out: dict[str, dict[str, int]] = {}
    for character, slots in classes.items():
        for slot, class_id in slots.items():
            row = int(rows.get(character, {}).get(slot, "0"), 0)
            if row:
                out.setdefault(character, {})[class_id] = row - 1
    return out


def game_palettes(source: str) -> list[str]:
    """Symbols of the palette table, by row."""
    return re.findall(r'\{"\w+",\s*(banim_pal_\w+)\}', source)


def read_lines(decomp_dir: Path, symbol: str) -> list[list[str]]:
    data = (decomp_dir / PALETTE_DIR / f"{symbol}.agbpal").read_bytes()
    return [[to_hex(c) for c in struct.unpack_from("<16H", data, 32 * line)] for line in range(LINES)]


def to_hex(colour: int) -> str:
    r, g, b = colour & 31, colour >> 5 & 31, colour >> 10 & 31
    return f"#{r * 255 // 31:02x}{g * 255 // 31:02x}{b * 255 // 31:02x}"


def to_rgb(value: str) -> tuple[int, int, int]:
    return int(value[1:3], 16), int(value[3:5], 16), int(value[5:7], 16)


def encode(lines: list[list[str]]) -> bytes:
    """The 5 lines as an .agbpal file."""
    if len(lines) != LINES or any(len(line) != 16 for line in lines):
        raise PaletteError("A character's palette has 5 lines of 16 colours")
    colours = [to_rgb(c) for line in lines for c in line]
    return struct.pack("<80H", *(r >> 3 | (g >> 3) << 5 | (b >> 3) << 10 for r, g, b in colours))


def _rewritten(source: str, name: str, character: str, slots: dict[int, str]) -> str:
    begin, end = _block(source, name)
    body = source[begin:end]
    entry = f"    [{character} - 1] = {{\n" + "".join(f"        [{s}] = {v},\n" for s, v in sorted(slots.items())) + "    },"
    pattern = re.compile(r" *\[" + re.escape(character) + r" - 1\]\s*=\s*\{.*?\},?", re.S)
    body = pattern.sub(entry, body, count=1) if pattern.search(body) else body.rstrip() + "\n" + entry
    return source[:begin] + body + source[end:]


def apply(sources: dict[str, str], edits: dict[str, dict[str, list | None]]) -> tuple[dict[str, str | bytes], int | None]:
    """The files that change for characters' `edits` ("battleColors") and the first new palette's row, if any.
    `sources`: the current text of CONFIG_FILE, TABLE_FILE and DATA_FILE."""
    config, table, data = sources[CONFIG_FILE], sources[TABLE_FILE], sources[DATA_FILE]
    first = len(game_palettes(table))
    current = game_slots(config)
    new: dict[bytes, int] = {}
    for character, colours in edits.items():
        wanted = dict(current.get(character, {}))
        for class_id, lines in colours.items():
            if lines is None:
                wanted.pop(class_id, None)
            else:
                wanted[class_id] = new.setdefault(encode(lines), first + len(new))
        if len(wanted) > SLOTS:
            raise PaletteError(f"{character}: {len(wanted)} classes with their own colours, the game has room for {SLOTS}")
        classes = dict(enumerate(wanted))
        rows = {slot: str(wanted[class_id] + 1) for slot, class_id in classes.items()}
        config = _rewritten(config, "gAnimCharaPalConfig", character, classes)
        config = _rewritten(config, "gAnimCharaPalIt", character, rows)
    if first + len(new) >= LAST_ROW:
        raise PaletteError("Too many battle palettes")
    files: dict[str, str | bytes] = {CONFIG_FILE: config}
    if not new:
        return files, None
    declared = rows = ""
    for row in new.values():
        symbol = f"banim_pal_fem_{row}"
        declared += f"extern char {symbol}[];\n"
        rows += f'\t{{"fem", {symbol}}}, // {row}\n'
        data = data.rstrip("\n") + (f"\n\t.global {symbol}\n{symbol}:\n"
                                    f'\t.incbin "{PALETTE_DIR}/{symbol}.agbpal.lz"\n\t.align 2, 0\n')
    begin = table.index("{", table.index("character_battle_animation_palette_table[]"))
    end = table.index("};", begin)
    include = table.index('#include "banim_data.h"\n') + len('#include "banim_data.h"\n')
    files[TABLE_FILE] = table[:include] + declared + table[include:end] + rows + table[end:]
    files[DATA_FILE] = data
    files.update({f"{PALETTE_DIR}/banim_pal_fem_{row}.agbpal": palette for palette, row in new.items()})
    return files, first
