"""Preview images built from the decomp's graphics (indexed PNG + GBA palette)."""

from __future__ import annotations

import io
import re
import struct
from functools import lru_cache
from pathlib import Path

from PIL import Image

PORTRAIT_TABLE = "src/portrait_data.c"
ITEM_ICON_PALETTE = "graphics/item_icon/item_icon_palette.agbpal"


def read_agbpal(path: Path) -> list[tuple[int, int, int]]:
    """GBA palette: little-endian 15-bit BGR colors."""
    data = path.read_bytes()
    colors = []
    for (value,) in struct.iter_unpack("<H", data[: len(data) // 2 * 2]):
        r, g, b = value & 0x1F, (value >> 5) & 0x1F, (value >> 10) & 0x1F
        colors.append((r << 3 | r >> 2, g << 3 | g >> 2, b << 3 | b >> 2))
    return colors


def render_indexed(png: Path, palette: list[tuple[int, int, int]], scale: int = 1) -> bytes:
    """Apply a GBA palette to an indexed PNG; color 0 is transparent."""
    img = Image.open(png)
    if img.mode != "P":
        img = img.convert("P")
    flat = [c for rgb in palette[:16] for c in rgb]
    img.putpalette(flat + [0] * (768 - len(flat)))
    rgba = img.convert("RGBA")
    pixels = rgba.load()
    src = img.load()
    for y in range(img.height):
        for x in range(img.width):
            if src[x, y] == 0:
                pixels[x, y] = (0, 0, 0, 0)
    if scale > 1:
        rgba = rgba.resize((img.width * scale, img.height * scale), Image.NEAREST)
    out = io.BytesIO()
    rgba.save(out, "PNG")
    return out.getvalue()


@lru_cache(maxsize=4)
def portrait_names(decomp_dir: Path) -> list[str | None]:
    """Portrait name per portrait id, e.g. 'Eirika' (None for empty rows). Portrait ids start at 1
    (GetPortraitData reads portrait_data[fid - 1]): the array's opening "{" line stands for id 0."""
    source = (decomp_dir / PORTRAIT_TABLE).read_text(encoding="utf-8")
    names = []
    for line in source.splitlines():
        line = line.strip()
        if not line.startswith("{"):
            continue
        m = re.match(r"\{\s*portrait_(\w+?)_tileset", line)
        names.append(m.group(1) if m else None)
    return names


# Big portrait (96x80) from its 256x32 tile sheet: (sheet x, y, width, height, face x, y), as the
# face sprite gSprite_Face96x96 puts the tiles (src/face.c, 32 tiles per sheet row).
FACE_PARTS = [(0, 0, 64, 32, 16, 0), (64, 0, 64, 32, 16, 32), (128, 0, 32, 16, 16, 64), (128, 16, 32, 16, 48, 64),
              (160, 0, 16, 32, 0, 48), (176, 0, 16, 32, 80, 48)]


def portrait_preview(decomp_dir: Path, portrait_id: int, scale: int = 3) -> bytes | None:
    names = portrait_names(decomp_dir)
    if not 0 <= portrait_id < len(names) or names[portrait_id] is None:
        return None
    base = decomp_dir / "graphics" / "portrait" / f"portrait_{names[portrait_id]}"
    chibi, palette = Path(f"{base}_chibi.png"), Path(f"{base}_palette.agbpal")
    if not chibi.is_file() or not palette.is_file():
        return None
    return render_indexed(chibi, read_agbpal(palette), scale)


def face_preview(decomp_dir: Path, portrait_id: int, scale: int = 1) -> bytes | None:
    """The big portrait shown in dialogues (generic villagers have no small one)."""
    names = portrait_names(decomp_dir)
    if not 0 <= portrait_id < len(names) or names[portrait_id] is None:
        return None
    base = decomp_dir / "graphics" / "portrait" / f"portrait_{names[portrait_id]}"
    sheet, palette = Path(f"{base}_tileset.png"), Path(f"{base}_palette.agbpal")
    if not sheet.is_file() or not palette.is_file():
        return None
    tiles = Image.open(io.BytesIO(render_indexed(sheet, read_agbpal(palette))))
    face = Image.new("RGBA", (96, 80))
    for sx, sy, w, h, fx, fy in FACE_PARTS:
        face.paste(tiles.crop((sx, sy, sx + w, sy + h)), (fx, fy))
    if scale > 1:
        face = face.resize((96 * scale, 80 * scale), Image.NEAREST)
    out = io.BytesIO()
    face.save(out, "PNG")
    return out.getvalue()


MAP_SPRITE_TABLE = "src/unit_icon_wait_data.c"
MAP_SPRITE_PALETTES = {
    "player": "graphics/unit_icon/palette/unit_icon_pal_player.agbpal",
    "enemy": "graphics/unit_icon/palette/unit_icon_pal_enemy.agbpal",
    "ally": "graphics/unit_icon/palette/unit_icon_pal_npc.agbpal",
}
_SPRITE_SIZES = {"UNIT_ICON_SIZE_16x16": (16, 16), "UNIT_ICON_SIZE_16x32": (16, 32), "UNIT_ICON_SIZE_32x32": (32, 32)}


@lru_cache(maxsize=4)
def map_sprite_table(decomp_dir: Path) -> list[tuple[str, tuple[int, int]]]:
    """Map sprite id (class SMSId) -> (sheet name, frame size), from unit_icon_wait_table."""
    source = (decomp_dir / MAP_SPRITE_TABLE).read_text(encoding="utf-8")
    return [(name, _SPRITE_SIZES.get(size, (16, 16)))
            for size, name in re.findall(r"\{\s*\d+\s*,\s*(\w+)\s*,\s*(\w+)\s*\}", source)]


def map_sprite(decomp_dir: Path, sprite_id: int, side: str = "player", scale: int = 2, trim: bool = False) -> bytes | None:
    """First standing frame of a class's map sprite, in the colors of a side.

    With trim, the transparent margins of the frame are cut off (for lists).
    """
    table = map_sprite_table(decomp_dir)
    if not 0 <= sprite_id < len(table):
        return None
    name, size = table[sprite_id]
    return map_sprite_sheet(decomp_dir, decomp_dir / "graphics" / "unit_icon" / "wait" / f"{name}.png", size, side, scale, trim)


def map_sprite_sheet(decomp_dir: Path, sheet: Path, size: tuple[int, int], side: str = "player", scale: int = 2,
                     trim: bool = False) -> bytes | None:
    """First standing frame of a standing sheet (the game's or one the project imports), in the colors of a side."""
    w, h = size
    palette = decomp_dir / MAP_SPRITE_PALETTES.get(side, MAP_SPRITE_PALETTES["player"])
    if not sheet.is_file() or not palette.is_file():
        return None
    img = Image.open(sheet)
    frame = img.crop((0, 0, min(w, img.width), min(h, img.height)))
    if trim:
        if frame.mode != "P":
            frame = frame.convert("P")
        box = frame.point(lambda i: 255 if i else 0).getbbox()  # color 0 is transparent
        if box:
            frame = frame.crop(box)
    return _render_image(frame, read_agbpal(palette), scale)


def _render_image(img: Image.Image, palette: list[tuple[int, int, int]], scale: int) -> bytes:
    if img.mode != "P":
        img = img.convert("P")
    flat = [c for rgb in palette[:16] for c in rgb]
    img = img.copy()
    img.putpalette(flat + [0] * (768 - len(flat)))
    rgba = img.convert("RGBA")
    src, px = img.load(), rgba.load()
    for y in range(img.height):
        for x in range(img.width):
            if src[x, y] == 0:
                px[x, y] = (0, 0, 0, 0)
    if scale > 1:
        rgba = rgba.resize((img.width * scale, img.height * scale), Image.NEAREST)
    out = io.BytesIO()
    rgba.save(out, "PNG")
    return out.getvalue()


def item_icon_preview(decomp_dir: Path, icon_files: list[str], icon_id: int, scale: int = 3, line: int = 0) -> bytes | None:
    """An icon of the game; `line` is its palette: 0 for items, 1 for affinities and the status screen's other icons."""
    if not 0 <= icon_id < len(icon_files):
        return None
    png = decomp_dir / icon_files[icon_id]
    if not png.is_file():
        return None
    return render_indexed(png, read_agbpal(decomp_dir / ITEM_ICON_PALETTE)[16 * line:], scale)
