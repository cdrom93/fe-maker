"""Mirrored and rotated tiles, added to a map's tileset (ticket 15).

A map cell holds one metatile number; a metatile is 2 x 2 tiles of 8 x 8 pixels, each with its
own horizontal / vertical flip bits (10 and 11) and palette (bits 12-15) in the tile config.
- Mirrors and half turns only need a new metatile: the same tiles, swapped, with flipped bits.
- Quarter turns need new 8 x 8 tiles (the GBA cannot rotate a background tile): their pixels are
  rotated, then FE Maker looks for an existing tile with that picture (flips allowed) before
  using a free one.

New metatiles go into free slots of the tile config (the unused slots are copies of one filler
metatile); new tiles into tiles of the tileset image no metatile uses. Each tileset image and
tile config is used by a single tileset in the game, so this changes no other map. Tiles 256 to
383 are skipped: tile animations (water...) overwrite them (BMapVSync_UpdateMapImgAnimations,
src/bmio.c, copies the frames to BG_TILE_ADDR(0x140), tile 0x100 of the tileset).

Project data (data/maps.json "tilesets", by tile config name): {"metatiles": {slot: {"tiles":
[4 entries], "terrain": id}}, "tiles": {index: [64 color indices]}}.
"""

from __future__ import annotations

import dataclasses
import struct
import zlib
from pathlib import Path

from PIL import Image

from . import maps

FLIP_H = 0x400
FLIP_V = 0x800
ANIMATED_TILES = range(0x100, 0x180)
OPS = ("h", "v", "180", "cw", "ccw")
SIMILAR_MAX_DIFF = 256 * 40 // 100   # pixels of a metatile that may differ from a similar one of the game


class TileEditError(Exception):
    pass


def layout_for(decomp_dir: Path, config_name: str) -> str | None:
    """A layout using this tile config (its tileset image goes with it)."""
    return next((lid for lid, layout in maps.layouts(decomp_dir).items()
                 if layout["assets"].config.stem == config_name), None)


def _pixels(img: Image.Image) -> list[int]:
    return list(img.tobytes())


def _flip(px: list[int], h: bool, v: bool) -> list[int]:
    rows = [px[y * 8:(y + 1) * 8] for y in range(8)]
    if h:
        rows = [r[::-1] for r in rows]
    if v:
        rows = rows[::-1]
    return [p for r in rows for p in r]


def _rotate(px: list[int], clockwise: bool) -> list[int]:
    if clockwise:
        return [px[(7 - x) * 8 + y] for y in range(8) for x in range(8)]
    return [px[x * 8 + (7 - y)] for y in range(8) for x in range(8)]


class Tileset:
    """A tile config and its tileset image, with the project's added metatiles and tiles."""

    def __init__(self, decomp_dir: Path, layout_id: str, edits: dict | None, painted: dict | None = None):
        self.decomp_dir = decomp_dir
        self.layout = maps.layouts(decomp_dir)[layout_id]
        self.assets = self.layout["assets"]
        if len(self.assets.tileset) != 1:
            raise TileEditError("Tilesets made of two images are not supported")
        metatiles, terrain = maps.read_config(self.assets.config)
        self.metatiles = [list(m) for m in metatiles]
        self.terrain = bytearray(terrain)
        self.tiles = [_pixels(t) for t in maps._tiles(self.assets.tileset)]
        self.original_tile_count = len(self.tiles)
        self.edits = {"metatiles": {}, "tiles": {}, **(edits or {})}
        for index, px in self.edits["tiles"].items():
            self.tiles[int(index)] = list(px)
        for slot, m in self.edits["metatiles"].items():
            self.metatiles[int(slot)] = list(m["tiles"])
            self.terrain[int(slot)] = m["terrain"]
        self.duplicates = maps.duplicate_metatiles(self.assets)
        self.used = self._used_metatiles(painted or {})
        self._pictures: dict[tuple[tuple[int, ...], int], int] | None = None

    @property
    def name(self) -> str:
        return self.assets.config.stem

    def _used_metatiles(self, painted: dict) -> set[int]:
        """Metatiles placed by any map or change using this tileset (original or painted)."""
        used: set[int] = set()
        for layout_id, layout in maps.layouts(self.decomp_dir).items():
            if layout["assets"].config != self.assets.config:
                continue
            used.update(maps.read_layout(layout["assets"].layout)[2])
            if layout["changes"]:
                for c in maps.read_changes(self.decomp_dir, layout["changes"]):
                    used.update(m for row in c["rows"] for m in row)
            if layout_id in painted:
                used.update(m for row in painted[layout_id]["rows"] for m in row)
        return used

    # ---------- tiles ----------

    def _find_tile(self, px: list[int]) -> int | None:
        """Entry bits (number and flips) of an existing tile showing these pixels."""
        for n, tile in enumerate(self.tiles):
            for h in (False, True):
                for v in (False, True):
                    if _flip(tile, h, v) == px:
                        return n | (FLIP_H if h else 0) | (FLIP_V if v else 0)
        return None

    def _free_tile(self) -> int:
        referenced = {e & 0x3FF for m in self.metatiles for e in m}
        for n in range(self.original_tile_count):
            if n not in referenced and n not in ANIMATED_TILES and str(n) not in self.edits["tiles"]:
                return n
        raise TileEditError("noFreeTile")

    def _tile_entry(self, px: list[int], palette_bits: int) -> int:
        found = self._find_tile(px)
        if found is None:
            found = self._free_tile()
            self.tiles[found] = px
            self.edits["tiles"][str(found)] = px
        return found | palette_bits

    def _entry_pixels(self, entry: int) -> list[int]:
        return _flip(self.tiles[entry & 0x3FF], bool(entry & FLIP_H), bool(entry & FLIP_V))

    # ---------- metatiles ----------

    def _transformed_entries(self, m: int, op: str) -> list[int]:
        tl, tr, bl, br = self.metatiles[m]
        if op == "h":
            return [e ^ FLIP_H for e in (tr, tl, br, bl)]
        if op == "v":
            return [e ^ FLIP_V for e in (bl, br, tl, tr)]
        if op == "180":
            return [e ^ FLIP_H ^ FLIP_V for e in (br, bl, tr, tl)]
        clockwise = op == "cw"
        order = (bl, tl, br, tr) if clockwise else (tr, br, tl, bl)
        return [self._tile_entry(_rotate(self._entry_pixels(e), clockwise), e & 0xF000) for e in order]

    def _free_slot(self) -> int:
        for slot, dup in enumerate(self.duplicates):
            if dup and slot not in self.used and str(slot) not in self.edits["metatiles"]:
                return slot
        raise TileEditError("noFreeMetatile")

    def _metatile(self, entries: list[int], terrain: int) -> int:
        """A shown metatile with these tiles and terrain: an existing one, or a new one in a free slot."""
        for n, existing in enumerate(self.metatiles):
            shown = not self.duplicates[n] or str(n) in self.edits["metatiles"]
            if existing == entries and self.terrain[n] == terrain and shown:
                return n
        slot = self._free_slot()
        self.metatiles[slot] = entries
        self.terrain[slot] = terrain
        self.edits["metatiles"][str(slot)] = {"tiles": entries, "terrain": terrain}
        self.used.add(slot)
        return slot

    def _picture(self, entries: list[int]) -> tuple[int, ...]:
        """16 x 16 colors of a metatile (palette * 16 + color; color 0 is the backdrop, whatever the palette)."""
        quarters = [[p | (e >> 12) << 4 if p else 0 for p in self._entry_pixels(e)] for e in entries]
        return tuple(quarters[(y // 8) * 2 + x // 8][(y % 8) * 8 + x % 8] for y in range(16) for x in range(16))

    def _shown_pictures(self) -> dict[tuple[tuple[int, ...], int], int]:
        """(picture, terrain) -> first shown metatile with it (the tileset's own tiles, before any copy)."""
        if self._pictures is None:
            self._pictures = {}
            for n, entries in enumerate(self.metatiles):
                if not self.duplicates[n] or str(n) in self.edits["metatiles"]:
                    self._pictures.setdefault((self._picture(entries), self.terrain[n]), n)
        return self._pictures

    def transform_metatile(self, m: int, op: str) -> int:
        """The metatile mirrored or turned. A metatile of the tileset already showing that picture with
        the same terrain is used as it is (the game's tilesets often have their turned bridges, roads...)."""
        if op not in OPS:
            raise TileEditError(f"Unknown transform {op}")
        pic = self._picture(self.metatiles[m])
        grid = [pic[y * 16:(y + 1) * 16] for y in range(16)]
        if op == "h":
            grid = [row[::-1] for row in grid]
        elif op == "v":
            grid = grid[::-1]
        elif op == "180":
            grid = [row[::-1] for row in grid[::-1]]
        elif op == "cw":
            grid = [tuple(grid[15 - x][y] for x in range(16)) for y in range(16)]
        else:
            grid = [tuple(grid[x][15 - y] for x in range(16)) for y in range(16)]
        found = self._shown_pictures().get((tuple(p for row in grid for p in row), self.terrain[m]))
        if found is not None:
            return found
        slot = self._metatile(self._transformed_entries(m, op), self.terrain[m])
        self._shown_pictures().setdefault((self._picture(self.metatiles[slot]), self.terrain[slot]), slot)
        return slot

    def similar_original(self, m: int) -> int | None:
        """The tileset's own metatile closest to an added one, with the same terrain, when they look alike
        (the game draws its turned bridges and roads again, with the light from the same side: a turned
        copy differs from them by about a third of its pixels)."""
        if str(m) not in self.edits["metatiles"]:
            return None
        pic = self._picture(self.metatiles[m])
        best, best_diff = None, SIMILAR_MAX_DIFF + 1
        for (other, terrain), n in self._shown_pictures().items():
            if terrain != self.terrain[m] or str(n) in self.edits["metatiles"]:
                continue
            diff = sum(a != b for a, b in zip(pic, other))
            if diff < best_diff:
                best, best_diff = n, diff
        return best

    def with_terrain(self, rows: list[list[int]], terrain: int) -> list[list[int]]:
        """The same tiles with another terrain (copies in free slots: the other maps keep theirs)."""
        if not 0 <= terrain < 0x41:
            raise TileEditError(f"Unknown terrain {terrain}")
        return [[self._metatile(list(self.metatiles[m]), terrain) for m in row] for row in rows]

    def transform_block(self, rows: list[list[int]], op: str) -> list[list[int]]:
        """A block of metatiles (rows) mirrored or turned as a whole."""
        if op not in OPS:
            raise TileEditError(f"Unknown transform {op}")
        h, w = len(rows), len(rows[0])
        if op == "h":
            placed = [row[::-1] for row in rows]
        elif op == "v":
            placed = rows[::-1]
        elif op == "180":
            placed = [row[::-1] for row in rows[::-1]]
        elif op == "cw":
            placed = [[rows[h - 1 - j][i] for j in range(h)] for i in range(w)]
        else:
            placed = [[rows[j][w - 1 - i] for j in range(h)] for i in range(w)]
        cache: dict[int, int] = {}
        out = []
        for row in placed:
            out.append([cache.setdefault(m, self.transform_metatile(m, op)) if m not in cache else cache[m] for m in row])
        return out

    # ---------- files ----------

    def config_bytes(self) -> bytes:
        data = bytearray(self.assets.config.read_bytes())
        for slot, m in self.edits["metatiles"].items():
            struct.pack_into("<4H", data, int(slot) * maps.METATILE_BYTES, *m["tiles"])
            data[maps.TERRAIN_OFFSET + int(slot)] = m["terrain"]
        return bytes(data)

    def image_png(self) -> bytes:
        """The tileset image with the added tiles, as the decomp stores it: 4-bit grayscale, inverted
        (gbagfx turns gray level g into color 15 - g)."""
        img = Image.open(self.assets.tileset[0])
        width, height = img.size
        columns = width // 8
        pixels = bytearray(width * height)
        for n, px in enumerate(self.tiles):
            tx, ty = (n % columns) * 8, (n // columns) * 8
            for y in range(8):
                for x in range(8):
                    pixels[(ty + y) * width + tx + x] = 15 - px[y * 8 + x]
        raw = b"".join(b"\x00" + bytes((pixels[y * width + x] << 4) | pixels[y * width + x + 1]
                                       for x in range(0, width, 2)) for y in range(height))

        def chunk(kind: bytes, body: bytes) -> bytes:
            return struct.pack(">I", len(body)) + kind + body + struct.pack(">I", zlib.crc32(kind + body))

        header = struct.pack(">IIBBBBB", width, height, 4, 0, 0, 0, 0)
        return b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", header) + chunk(b"IDAT", zlib.compress(raw, 9)) + chunk(b"IEND", b"")

    def edited_assets(self, folder: Path) -> maps.MapAssets:
        """The layout's assets with the added metatiles and tiles, written to `folder` (to render them)."""
        folder.mkdir(parents=True, exist_ok=True)
        config, image = folder / f"{self.name}.bin", folder / f"{self.name}.png"
        config.write_bytes(self.config_bytes())
        image.write_bytes(self.image_png())
        return dataclasses.replace(self.assets, config=config, tileset=[image])

    def files(self) -> dict[str, bytes]:
        """Decomp-relative path -> new content of the tile config (.bin) and tileset image (.png)."""
        out = {}
        if self.edits["metatiles"]:
            out[self.assets.config.relative_to(self.decomp_dir).as_posix()] = self.config_bytes()
        if self.edits["tiles"]:
            out[self.assets.tileset[0].relative_to(self.decomp_dir).as_posix()] = self.image_png()
        return out
