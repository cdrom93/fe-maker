"""Battle background previews (ticket 141).

A chapter's battle background set (`battleTileSet`, 0..0x14) picks, for each terrain, a background in
gBattleBGDataTable (gBanimBGLutNN in src/data_terrains.c, values counted from 1). Each background is
tiles + tilemap + palette (data/data_btl_bg.s): most tiles are a whole 240 x 160 indexed PNG, a few are
an 8-pixel-wide tile sheet with a 30 x 20 tilemap (.bin). Palettes are 10 x 16 colors (.pal), or the PNG's own.
"""

from __future__ import annotations

import io
import re
import struct
from functools import lru_cache
from pathlib import Path

from PIL import Image

from .maps import read_jasc_palette

TABLE = "data/data_btl_bg.s"
FOLDER = "graphics/btl_bg"
TERRAIN_PLAINS = 1
WIDTH, HEIGHT = 30, 20  # tiles
SHOWN = 104  # pixels above the battle panels


@lru_cache(maxsize=2)
def _sets(decomp_dir: Path) -> dict[int, int]:
    """Background set -> its plains background (index in gBattleBGDataTable)."""
    text = (decomp_dir / "src/data_terrains.c").read_text(encoding="utf-8")
    sets = {}
    for name, body in re.findall(r"gBanimBGLut(\w+)\[\] = \{(.*?)\};", text, re.S):
        plains = re.search(r"\[TERRAIN_PLAINS\] = (\d+)", body)
        if plains:
            sets[0 if name == "Default" else int(name, 16)] = int(plains.group(1)) - 1
    return sets


@lru_cache(maxsize=2)
def _table(decomp_dir: Path) -> list[tuple[str, str, str]]:
    """gBattleBGDataTable: (tiles, tilemap, palette) file stems."""
    text = (decomp_dir / TABLE).read_text(encoding="utf-8").split("btl_bg_0_tiles:")[0]
    return [tuple(n.rsplit("_", 1)[0] for n in row)
            for row in re.findall(r"\.word (\w+), (\w+), (\w+)", text)]


def _from_sheet(folder: Path, stem: str) -> Image.Image:
    """Tile sheet + tilemap -> 240 x 160 image of color indexes (palette row * 16 + color)."""
    sheet = Image.open(folder / f"{stem}.png").convert("L")
    entries = struct.unpack(f"<{WIDTH * HEIGHT}H", (folder / f"{stem}.bin").read_bytes()[: WIDTH * HEIGHT * 2])
    out = Image.new("L", (WIDTH * 8, HEIGHT * 8))
    for n, entry in enumerate(entries):
        tile = sheet.crop((0, (entry & 0x3FF) * 8, 8, (entry & 0x3FF) * 8 + 8)).point(lambda v: 15 - v // 17 + (entry >> 12) * 16)
        if entry & 0x400:
            tile = tile.transpose(Image.FLIP_LEFT_RIGHT)
        if entry & 0x800:
            tile = tile.transpose(Image.FLIP_TOP_BOTTOM)
        out.paste(tile, (n % WIDTH * 8, n // WIDTH * 8))
    return Image.frombytes("P", out.size, out.tobytes())  # L -> P would remap the indexes


def preview(decomp_dir: Path, bg_set: int) -> bytes | None:
    """The plains background of a set, as the game shows it in battle."""
    index = _sets(decomp_dir).get(bg_set)
    table = _table(decomp_dir)
    if index is None or not 0 <= index < len(table):
        return None
    tiles, _, palette = table[index]
    folder = decomp_dir / FOLDER
    if (folder / f"{tiles}.bin").is_file():
        img = _from_sheet(folder, tiles)
    else:
        img = Image.open(folder / f"{tiles}.png").copy()
    pal = folder / f"{palette}.pal"
    colors = read_jasc_palette(pal) if pal.is_file() else None
    if colors is None:
        own = Image.open(folder / f"{palette}.png").getpalette() or []
        colors = [tuple(own[i: i + 3]) for i in range(0, len(own), 3)]
    flat = [c for rgb in colors for c in rgb]
    img.putpalette(flat + [0] * (768 - len(flat)))
    out = io.BytesIO()
    img.convert("RGB").crop((0, 0, WIDTH * 8, SHOWN)).save(out, "PNG")
    return out.getvalue()
