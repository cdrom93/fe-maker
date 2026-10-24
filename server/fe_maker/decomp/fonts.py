"""The game's fonts (data/fonts/glyphs_*.h): which characters they can draw and how wide they are.

The US game draws one byte per character, in the Windows-1252 code page: besides ASCII, its fonts
have the accented letters of French, Spanish and Italian (é = 0xE9...), ¡ ¿ œ and curly quotes. The
decomp's text tool writes texts.txt as UTF-8 bytes, so FE Maker writes such a letter as a text code
([é]) that it defines in texts/textdefs.txt with its byte (see texts.TextFile.render).
"""

from __future__ import annotations

import re
from functools import lru_cache
from pathlib import Path

ENCODING = "cp1252"
FONTS = {"talk": ("data/fonts/glyphs_2.h", "TextGlyphs_Talk"), "system": ("data/fonts/glyphs_1.h", "TextGlyphs_System")}
# Without the font files (test decomps): printable ASCII, 6 pixels wide.
_FALLBACK = {b: 6 for b in range(0x20, 0x7F)}

_GLYPH_RE = re.compile(r"struct Glyph (\w+) =\s*\{[^}]*?\.width = (\d+)", re.S)


def read_widths(source: str, array: str) -> dict[int, int]:
    """Byte -> glyph width in pixels, for the bytes the font can draw."""
    widths = {name: int(w) for name, w in _GLYPH_RE.findall(source)}
    m = re.search(rf"{array}\[\]\s*=\s*\{{(.*?)\}};", source, re.S)
    if not m:
        return {}
    names = [n.strip().lstrip("&") for n in m.group(1).split(",") if n.strip()]
    return {i: widths[n] for i, n in enumerate(names) if n != "NULL" and n in widths}


@lru_cache(maxsize=8)
def _load(decomp_dir: str, font: str) -> tuple[tuple[int, int], ...]:
    rel, array = FONTS[font]
    path = Path(decomp_dir) / rel
    if not path.is_file():
        return tuple(_FALLBACK.items())
    return tuple(read_widths(path.read_text(encoding="utf-8"), array).items())


def widths(decomp_dir: Path, font: str = "talk") -> dict[int, int]:
    return dict(_load(str(decomp_dir), font))


def char_byte(ch: str) -> int | None:
    """The game's byte for a character, None when the code page has none."""
    try:
        data = ch.encode(ENCODING)
    except UnicodeEncodeError:
        return None
    return data[0] if len(data) == 1 else None


def char_widths(table: dict[int, int]) -> dict[str, int]:
    """Character -> width, for the editor (same layout as the server)."""
    out = {}
    for b, w in table.items():
        try:
            out[bytes([b]).decode(ENCODING)] = w
        except UnicodeDecodeError:
            continue
    return out


_BITMAP_RE = re.compile(r"struct Glyph (\w+) =\s*\{[^}]*?\.width = \d+,\s*\.bitmap =\s*\{(.*?)\}", re.S)
SHEET_COLORS = {2: (184, 176, 160, 255), 3: (40, 40, 40, 255)}   # shadow, ink (as in the talk box)


def font_sheet(decomp_dir: Path, font: str = "talk") -> bytes | None:
    """PNG of the font's glyphs, 16 x 16 cells of 16 x 16 pixels, cell = byte (for the editor's preview).
    Each bitmap row is a u32 with 2 bits per pixel, leftmost pixel in the low bits."""
    from io import BytesIO

    from PIL import Image

    rel, array = FONTS[font]
    path = Path(decomp_dir) / rel
    if not path.is_file():
        return None
    source = path.read_text(encoding="utf-8")
    bitmaps = {name: [int(v, 16) for v in re.findall(r"0x[0-9A-Fa-f]+", body)] for name, body in _BITMAP_RE.findall(source)}
    m = re.search(rf"{array}\[\]\s*=\s*\{{(.*?)\}};", source, re.S)
    names = [n.strip().lstrip("&") for n in m.group(1).split(",") if n.strip()] if m else []
    img = Image.new("RGBA", (256, 256), (0, 0, 0, 0))
    px = img.load()
    for i, name in enumerate(names[:256]):
        for y, row in enumerate(bitmaps.get(name, [])[:16]):
            for x in range(16):
                color = SHEET_COLORS.get((row >> (2 * x)) & 3)
                if color:
                    px[(i % 16) * 16 + x, (i // 16) * 16 + y] = color
    out = BytesIO()
    img.save(out, "PNG")
    return out.getvalue()


def unsupported(text: str, table: dict[int, int]) -> list[str]:
    """Characters of a text (outside [codes]) the font cannot draw, once each."""
    out: list[str] = []
    for ch in re.sub(r"\[[^\]]*\]", "", text).replace("\n", ""):
        b = char_byte(ch)
        if (b is None or b not in table) and ch not in out:
            out.append(ch)
    return out
