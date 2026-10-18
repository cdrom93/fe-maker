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
    """Portrait name per portrait id, e.g. 'Eirika' (None for empty rows)."""
    source = (decomp_dir / PORTRAIT_TABLE).read_text(encoding="utf-8")
    names = []
    for line in source.splitlines():
        line = line.strip()
        if not line.startswith("{"):
            continue
        m = re.match(r"\{\s*portrait_(\w+?)_tileset", line)
        names.append(m.group(1) if m else None)
    return names


def portrait_preview(decomp_dir: Path, portrait_id: int, scale: int = 3) -> bytes | None:
    names = portrait_names(decomp_dir)
    if not 0 <= portrait_id < len(names) or names[portrait_id] is None:
        return None
    base = decomp_dir / "graphics" / "portrait" / f"portrait_{names[portrait_id]}"
    chibi, palette = Path(f"{base}_chibi.png"), Path(f"{base}_palette.agbpal")
    if not chibi.is_file() or not palette.is_file():
        return None
    return render_indexed(chibi, read_agbpal(palette), scale)


def item_icon_preview(decomp_dir: Path, icon_files: list[str], icon_id: int, scale: int = 3) -> bytes | None:
    if not 0 <= icon_id < len(icon_files):
        return None
    png = decomp_dir / icon_files[icon_id]
    if not png.is_file():
        return None
    return render_indexed(png, read_agbpal(decomp_dir / ITEM_ICON_PALETTE), scale)
