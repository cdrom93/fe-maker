"""Chapters and their maps, read from the decomp.

A chapter (src/data/chapter_settings.json) points to entries of the chapter asset
table (gChapterDataAssetTable, data/data_8B363C.s). Each entry names a symbol, and
data/const_data_chapter_maps.s says which file the symbol comes from:

- ObjectTypeN    tileset image (graphics/map/ObjectTypeN.png, 32 tiles of 8x8 per row)
- MapPaletteN    palettes (JASC .pal): 5 normal palettes then 5 faded fog-of-war ones
- TileConfigN    1024 metatiles of 16x16: 4 tile entries each (0x2000 bytes), then one
                 terrain byte per metatile (0x400 bytes)
- <Name>Map      layout (graphics/map/layout/<Name>.mar + .json with width/height):
                 one little-endian u16 per cell, metatile index * 32

Rendering follows ImageUtilMap.DrawMap from FEBuilderGBA (GPL-3.0,
https://github.com/FEBuilderGBA/FEBuilderGBA): each metatile is four 8x8 tiles whose
entries hold the tile number (bits 0-9), horizontal/vertical flip (bits 10, 11)
and palette (bits 12-15).
"""

from __future__ import annotations

import io
import json
import re
import struct
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from PIL import Image

CHAPTER_SETTINGS_FILE = "src/data/chapter_settings.json"
ASSET_TABLE_FILE = "data/data_8B363C.s"
MAP_ASSETS_FILE = "data/const_data_chapter_maps.s"
METATILE_BYTES = 8
TERRAIN_OFFSET = 0x2000


class MapError(Exception):
    pass


@dataclass(frozen=True)
class MapAssets:
    tileset: list[Path]        # one or two tileset images (obj1, obj2)
    palette: Path
    config: Path
    layout: Path               # .mar


def _read(decomp_dir: Path, rel: str) -> str:
    return (decomp_dir / rel).read_text(encoding="utf-8")


@lru_cache(maxsize=4)
def asset_table(decomp_dir: Path) -> list[str | None]:
    """Asset index -> symbol name (None for 0)."""
    words = re.findall(r"^\s*\.word\s+(\w+)", _read(decomp_dir, ASSET_TABLE_FILE), re.MULTILINE)
    return [None if w == "0" else w for w in words]


@lru_cache(maxsize=4)
def asset_files(decomp_dir: Path) -> dict[str, Path]:
    """Map asset symbol -> source file (the editable one, not the compressed build output)."""
    source = _read(decomp_dir, MAP_ASSETS_FILE)
    result = {}
    for symbol, path in re.findall(r"^(\w+):[^\n]*\n\s*\.incbin\s+\"([^\"]+)\"", source, re.MULTILINE):
        built = Path(path)
        name = built.name.split(".")[0]
        folder = decomp_dir / built.parent
        for ext in (".png", ".pal", ".bin", ".mar"):
            candidate = folder / f"{name}{ext}"
            if candidate.is_file():
                result[symbol] = candidate
                break
    return result


@lru_cache(maxsize=4)
def chapter_settings(decomp_dir: Path) -> list[dict]:
    return json.loads(_read(decomp_dir, CHAPTER_SETTINGS_FILE))["chapters"]


def chapter_map_assets(decomp_dir: Path, chapter: dict) -> MapAssets:
    table, files = asset_table(decomp_dir), asset_files(decomp_dir)

    def resolve(index: int) -> Path:
        if not 0 < index < len(table) or table[index] is None or table[index] not in files:
            raise MapError(f"Map asset {index} not found")
        return files[table[index]]

    m = chapter["map"]
    tileset = [resolve(m["obj1Id"])] + ([resolve(m["obj2Id"])] if m.get("obj2Id") else [])
    return MapAssets(tileset, resolve(m["paletteId"]), resolve(m["tileConfigId"]), resolve(m["mainLayerId"]))


# ---------- formats ----------

def read_jasc_palette(path: Path) -> list[tuple[int, int, int]]:
    lines = path.read_text(encoding="utf-8").split()
    if not lines or lines[0] != "JASC-PAL":
        raise MapError(f"Not a JASC palette: {path.name}")
    count = int(lines[2])
    values = [int(v) for v in lines[3: 3 + count * 3]]
    return [tuple(values[i: i + 3]) for i in range(0, len(values), 3)]


def read_layout(mar: Path) -> tuple[int, int, list[int]]:
    """(width, height, metatile index per cell)."""
    info = json.loads(mar.with_suffix(".json").read_text(encoding="utf-8"))
    data = mar.read_bytes()
    cells = [v >> 5 for (v,) in struct.iter_unpack("<H", data[: len(data) // 2 * 2])]
    return info["width"], info["height"], cells


def read_config(path: Path) -> tuple[list[tuple[int, int, int, int]], bytes]:
    """(4 tile entries per metatile, terrain byte per metatile)."""
    data = path.read_bytes()
    metatiles = [struct.unpack_from("<4H", data, i) for i in range(0, TERRAIN_OFFSET, METATILE_BYTES)]
    return metatiles, data[TERRAIN_OFFSET: TERRAIN_OFFSET + len(metatiles)]


# ---------- rendering ----------

def _tiles(tileset_paths: list[Path]) -> list[Image.Image]:
    """All 8x8 tiles (palette indices 0-15), in order, across the tileset images."""
    tiles = []
    for path in tileset_paths:
        img = Image.open(path)
        if img.mode == "L":
            # The decomp stores 4bpp tilesets as inverted grayscale: value = (15 - index) * 17
            # (gbagfx inverts the colors of images without a palette, tools/gbagfx/gfx.c).
            img = Image.frombytes("P", img.size, img.tobytes().translate(bytes(15 - round(v / 17) for v in range(256))))
        elif img.mode != "P":
            img = img.convert("P")
        for ty in range(img.height // 8):
            for tx in range(img.width // 8):
                tiles.append(img.crop((tx * 8, ty * 8, tx * 8 + 8, ty * 8 + 8)))
    return tiles


TILESET_COLUMNS = 32  # metatiles per row of the tileset sheet


def _metatile_painter(assets: MapAssets, fog: bool = False):
    """(palette, draw(canvas, metatile, x, y)) for the chapter's tileset."""
    pal_base = 5 if fog else 0
    metatiles, _terrain = read_config(assets.config)
    palette = read_jasc_palette(assets.palette)
    tiles = _tiles(assets.tileset)
    # 16 palettes of 16 colors -> one 256-color palette; tile pixel = palette * 16 + index.
    flat = [c for rgb in palette for c in rgb]
    flat += [0] * (768 - len(flat))
    cache: dict[int, Image.Image] = {}

    def tile_image(entry: int) -> Image.Image:
        if entry not in cache:
            number, pal = entry & 0x3FF, (entry >> 12) & 0xF
            pal = (pal + pal_base) & 0xF
            raw = tiles[number].tobytes() if number < len(tiles) else bytes(64)
            # Pixel = color index 0-15 within the tile's palette -> index in the combined palette.
            img = Image.frombytes("P", (8, 8), raw.translate(bytes((pal * 16 + (i & 0xF)) & 0xFF for i in range(256))))
            if entry & 0x400:
                img = img.transpose(Image.FLIP_LEFT_RIGHT)
            if entry & 0x800:
                img = img.transpose(Image.FLIP_TOP_BOTTOM)
            cache[entry] = img
        return cache[entry]

    def draw(canvas: Image.Image, metatile: int, x: int, y: int) -> None:
        if metatile >= len(metatiles):
            return
        for k, entry in enumerate(metatiles[metatile]):
            canvas.paste(tile_image(entry), (x + (k % 2) * 8, y + (k // 2) * 8))

    return flat, draw


def _png(canvas: Image.Image, scale: int = 1) -> bytes:
    out = canvas.convert("RGB")
    if scale > 1:
        out = out.resize((out.width * scale, out.height * scale), Image.NEAREST)
    buffer = io.BytesIO()
    out.save(buffer, "PNG")
    return buffer.getvalue()


def render_map(assets: MapAssets, scale: int = 1, fog: bool = False,
               layout: tuple[int, int, list[int]] | None = None) -> tuple[bytes, int, int]:
    """PNG of the map, plus its size in cells. `layout` (width, height, cells) replaces the original one.

    The palette file holds two sets of 5 palettes: the normal ones, then faded ones for cells
    hidden by fog of war (DisplayBmTile in src/bmmap.c adds 6 for visible cells, 11 otherwise;
    gBmMapFog is non-zero for visible cells). Checked against an in-game screenshot.
    """
    width, height, cells = layout or read_layout(assets.layout)
    palette, draw = _metatile_painter(assets, fog)
    canvas = Image.new("P", (width * 16, height * 16))
    canvas.putpalette(palette)
    for i, metatile in enumerate(cells[: width * height]):
        draw(canvas, metatile, (i % width) * 16, (i // width) * 16)
    return _png(canvas, scale), width, height


def render_tileset(assets: MapAssets) -> bytes:
    """PNG of all the tileset's metatiles, TILESET_COLUMNS per row (the map editor's palette)."""
    metatiles, _terrain = read_config(assets.config)
    palette, draw = _metatile_painter(assets)
    rows = -(-len(metatiles) // TILESET_COLUMNS)
    canvas = Image.new("P", (TILESET_COLUMNS * 16, rows * 16))
    canvas.putpalette(palette)
    for i in range(len(metatiles)):
        draw(canvas, i, (i % TILESET_COLUMNS) * 16, (i // TILESET_COLUMNS) * 16)
    return _png(canvas)


def duplicate_metatiles(assets: MapAssets) -> list[bool]:
    """Metatiles identical to an earlier one (same tiles, same terrain): hidden from the palette.
    Unused slots of a tileset are all copies of one filler metatile."""
    metatiles, terrain = read_config(assets.config)
    seen: set[tuple] = set()
    result = []
    for i, m in enumerate(metatiles):
        key = (m, terrain[i])
        result.append(key in seen)
        seen.add(key)
    return result


def encode_layout(layout_id: str, width: int, height: int, cells: list[int]) -> tuple[bytes, str]:
    """(.mar bytes, .json text) of a layout, in the decomp's format (see scripts/mar_to_map.py)."""
    mar = b"".join(struct.pack("<H", c << 5) for c in cells[: width * height])
    return mar, json.dumps({"id": layout_id, "width": width, "height": height})


@lru_cache(maxsize=4)
def layouts(decomp_dir: Path) -> dict[str, dict]:
    """Layout id (file stem) -> {"mar": decomp-relative path, "chapters": [indices], "assets": MapAssets}."""
    result: dict[str, dict] = {}
    for i, chapter in enumerate(chapter_settings(decomp_dir)):
        try:
            assets = chapter_map_assets(decomp_dir, chapter)
        except MapError:
            continue
        entry = result.setdefault(assets.layout.stem, {
            "mar": assets.layout.relative_to(decomp_dir).as_posix(), "chapters": [], "assets": assets})
        entry["chapters"].append(i)
    return result


def terrain_grid(assets: MapAssets) -> list[list[int]]:
    """Terrain type of each cell (rows of columns)."""
    width, height, cells = read_layout(assets.layout)
    _metatiles, terrain = read_config(assets.config)
    return [[terrain[cells[y * width + x]] if cells[y * width + x] < len(terrain) else 0
             for x in range(width)] for y in range(height)]


TERRAINS_HEADER = "include/constants/terrains.h"
TERRAIN_DATA_FILE = "src/data_terrains.c"


@lru_cache(maxsize=4)
def terrain_text_ids(decomp_dir: Path) -> list[int]:
    """Text id of each terrain's in-game name, by terrain id (gUnknown_0880D374, GetTerrainName)."""
    constants = {name: int(value, 0) for name, value in
                 re.findall(r"^\s*(TERRAIN_\w+)\s*=\s*(0x[0-9A-Fa-f]+|\d+)", _read(decomp_dir, TERRAINS_HEADER), re.MULTILINE)}
    source = _read(decomp_dir, TERRAIN_DATA_FILE)
    table = source[source.index("gUnknown_0880D374[]"):]
    table = table[: table.index("};")]
    ids = [0] * constants.get("TERRAIN_COUNT", 0x41)
    for name, text in re.findall(r"\[(TERRAIN_\w+)\]\s*=\s*(0x[0-9A-Fa-f]+|\d+)", table):
        if name in constants and constants[name] < len(ids):
            ids[constants[name]] = int(text, 0)
    return ids
