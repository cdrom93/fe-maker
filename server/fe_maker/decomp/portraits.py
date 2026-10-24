"""Portraits imported from a PNG sheet (phase 5), in the community's 128 x 112 layout (FEditor,
FEBuilderGBA: ImagePortraitForm.cs DrawPortraitSeet / BuildPortraitSeet, credited in CREDITS.md):

- the face, 96 x 80, at (0, 0);
- the mini portrait (menus, map), 32 x 32, at (96, 16);
- the eye frames, 32 x 16: half closed at (96, 48), closed at (96, 64);
- six mouth frames, 32 x 16: (0, 80), (32, 80), (64, 80), then (0, 96), (32, 96), (64, 96);
- two more 32 x 16 parts at (96, 80) and (96, 96).

The decomp keeps a portrait as four files (graphics/portrait/portrait_<name>_*): the face and eye
frames on a 256 x 32 tile sheet (_tileset.png, see FACE_PARTS), the mouth frames stacked in a 32 x 96
image (_mouth.png), the mini portrait (_chibi.png) and a 16-color palette (_palette.agbpal); the
portrait table (src/portrait_data.c) gives where the mouth and eye frames go, in 8-pixel tiles from
the face's top-left corner.

Project data: data/portraits.json {portrait id: {"file": sheet in the project's assets folder,
"mouth": [x, y], "eyes": [x, y]}}: an imported sheet replaces the game's portrait with that id.
"""

from __future__ import annotations

import io
import re
import struct
from pathlib import Path

from PIL import Image

from .assets import FACE_PARTS, PORTRAIT_TABLE, portrait_names, read_agbpal

SHEET_SIZE = (128, 112)
FACE = (96, 80)
CHIBI_AT = (96, 16)
EYES_AT = [(96, 48), (96, 64)]            # tile sheet (192, 0) and (192, 16)
EXTRA_AT = [(96, 80), (96, 96)]           # tile sheet (224, 0) and (224, 16)
MOUTHS_AT = [(0, 80), (32, 80), (64, 80), (0, 96), (32, 96), (64, 96)]
FRAME = (32, 16)
FACE_X0 = 0                               # mouth and eye positions count from the face's left edge


class PortraitError(Exception):
    pass


def _files(decomp_dir: Path, name: str) -> dict[str, Path]:
    base = decomp_dir / "graphics" / "portrait" / f"portrait_{name}"
    return {part: Path(f"{base}_{part}.png") for part in ("tileset", "mouth", "chibi")} | \
        {"palette": Path(f"{base}_palette.agbpal")}


def to_sheet(decomp_dir: Path, name: str) -> Image.Image:
    """The game's portrait as a 128 x 112 sheet (indexed, with its palette)."""
    files = _files(decomp_dir, name)
    tiles, mouth, chibi = (Image.open(files[k]) for k in ("tileset", "mouth", "chibi"))
    sheet = Image.new("P", SHEET_SIZE, 0)
    for sx, sy, w, h, fx, fy in FACE_PARTS:
        sheet.paste(tiles.crop((sx, sy, sx + w, sy + h)), (fx, fy))
    for k, at in enumerate(EYES_AT):
        sheet.paste(tiles.crop((192, 16 * k, 224, 16 * k + 16)), at)
    for k, at in enumerate(EXTRA_AT):
        sheet.paste(tiles.crop((224, 16 * k, 256, 16 * k + 16)), at)
    for k, at in enumerate(MOUTHS_AT):
        if 16 * k + 16 <= mouth.height:
            sheet.paste(mouth.crop((0, 16 * k, 32, 16 * k + 16)), at)
    sheet.paste(chibi.crop((0, 0, 32, 32)), CHIBI_AT)
    colors = read_agbpal(files["palette"])[:16]
    sheet.putpalette([c for rgb in colors for c in rgb] + [0] * (768 - 3 * len(colors)))
    return sheet


def indexed(img: Image.Image) -> tuple[Image.Image, list[tuple[int, int, int]]]:
    """The sheet with at most 16 colors, color 0 being the background (the top-left pixel's color)."""
    if img.size != SHEET_SIZE:
        raise PortraitError("badSize")
    rgb = img.convert("RGB")
    background = rgb.getpixel((0, 0))
    counts = rgb.getcolors(maxcolors=4096)
    if counts is None or len(counts) > 16:
        raise PortraitError("tooManyColors")
    # Background first, then the others by frequency (a stable order).
    colors = [background] + [c for _n, c in sorted(counts, key=lambda nc: (-nc[0], nc[1])) if c != background]
    index = {c: i for i, c in enumerate(colors)}
    out = Image.new("P", SHEET_SIZE)
    raw = rgb.tobytes()
    out.frombytes(bytes(index[tuple(raw[i:i + 3])] for i in range(0, len(raw), 3)))
    out.putpalette([c for rgb_ in colors for c in rgb_] + [0] * (768 - 3 * len(colors)))
    return out, colors


def agbpal(colors: list[tuple[int, int, int]]) -> bytes:
    """16 GBA colors (15-bit BGR), little endian."""
    padded = list(colors[:16]) + [(0, 0, 0)] * (16 - len(colors[:16]))
    return b"".join(struct.pack("<H", (r >> 3) | (g >> 3) << 5 | (b >> 3) << 10) for r, g, b in padded)


def _png4(img: Image.Image) -> bytes:
    out = io.BytesIO()
    img.save(out, "PNG", bits=4)
    return out.getvalue()


def from_sheet(sheet: Image.Image) -> dict[str, bytes]:
    """The decomp's four portrait files from an indexed sheet (see `indexed`)."""
    tiles = Image.new("P", (256, 32), 0)
    for sx, sy, w, h, fx, fy in FACE_PARTS:
        tiles.paste(sheet.crop((fx, fy, fx + w, fy + h)), (sx, sy))
    for k, (x, y) in enumerate(EYES_AT):
        tiles.paste(sheet.crop((x, y, x + 32, y + 16)), (192, 16 * k))
    for k, (x, y) in enumerate(EXTRA_AT):
        tiles.paste(sheet.crop((x, y, x + 32, y + 16)), (224, 16 * k))
    mouth = Image.new("P", (32, 96), 0)
    for k, (x, y) in enumerate(MOUTHS_AT):
        mouth.paste(sheet.crop((x, y, x + 32, y + 16)), (0, 16 * k))
    chibi = sheet.crop((CHIBI_AT[0], CHIBI_AT[1], CHIBI_AT[0] + 32, CHIBI_AT[1] + 32))
    palette = sheet.getpalette()[:48]
    colors = [tuple(palette[i:i + 3]) for i in range(0, 48, 3)]
    for img in (tiles, mouth, chibi):
        img.putpalette(sheet.getpalette())
    return {"tileset": _png4(tiles), "mouth": _png4(mouth), "chibi": _png4(chibi), "palette": agbpal(colors)}


def cut_pixels(sheet: Image.Image) -> int:
    """Drawn pixels the game cannot show: the face's top corners outside its tile parts (the game's
    "hackbox"), and the unused top-right corner of the sheet."""
    used = Image.new("1", SHEET_SIZE, 0)
    for _sx, _sy, w, h, fx, fy in FACE_PARTS:
        used.paste(1, (fx, fy, fx + w, fy + h))
    used.paste(1, (FACE[0], 16, SHEET_SIZE[0], SHEET_SIZE[1]))
    used.paste(1, (0, FACE[1], SHEET_SIZE[0], SHEET_SIZE[1]))
    return sum(1 for p, u in zip(sheet.tobytes(), used.convert("L").tobytes()) if p and not u)


def _difference(sheet: Image.Image, frame_at: tuple[int, int], x: int, y: int) -> int:
    fx, fy = frame_at
    frame = sheet.crop((fx, fy, fx + 32, fy + 16)).tobytes()
    face = sheet.crop((x, y, x + 32, y + 16)).tobytes()
    return sum(a != b for a, b in zip(frame, face))


def detect(sheet: Image.Image) -> dict[str, list[int]]:
    """Where the mouth and eye frames fit on the face (tiles from its top-left corner):
    the place where they differ the least from the face, the face showing a mouth and open eyes that
    look like the frames."""
    def best(frames: list[tuple[int, int]]) -> list[int]:
        candidates = [(tx, ty) for ty in range(0, (FACE[1] - 16) // 8 + 1) for tx in range(0, (FACE[0] - FACE_X0 - 32) // 8 + 1)]
        score = {c: sum(_difference(sheet, f, FACE_X0 + 8 * c[0], 8 * c[1]) for f in frames) for c in candidates}
        tx, ty = min(candidates, key=lambda c: (score[c], c[1], c[0]))
        return [tx, ty]

    return {"mouth": best(MOUTHS_AT), "eyes": best(EYES_AT)}


def _rgba(img: Image.Image, scale: int) -> bytes:
    """An indexed image as an RGBA PNG, color 0 transparent."""
    rgba = img.convert("RGBA")
    alpha = Image.frombytes("L", img.size, bytes(0 if i == 0 else 255 for i in img.tobytes()))
    rgba.putalpha(alpha)
    if scale > 1:
        rgba = rgba.resize((img.width * scale, img.height * scale), Image.NEAREST)
    out = io.BytesIO()
    rgba.save(out, "PNG")
    return out.getvalue()


def face_png(sheet: Image.Image, scale: int = 1) -> bytes:
    return _rgba(sheet.crop((0, 0, *FACE)), scale)


def chibi_png(sheet: Image.Image, scale: int = 1) -> bytes:
    return _rgba(sheet.crop((CHIBI_AT[0], CHIBI_AT[1], CHIBI_AT[0] + 32, CHIBI_AT[1] + 32)), scale)


# ---------- portrait table ----------

_ROW_RE = re.compile(r"\{\s*portrait_(\w+?)_tileset\s*,([^}]*)\}")


def read_positions(decomp_dir: Path) -> dict[str, dict[str, list[int]]]:
    """Portrait name -> {"mouth": [x, y], "eyes": [x, y]} from the portrait table."""
    out = {}
    for name, rest in _ROW_RE.findall((decomp_dir / PORTRAIT_TABLE).read_text(encoding="utf-8")):
        values = [v.strip() for v in rest.split(",")]
        try:
            numbers = [int(v, 0) for v in values[4:8]]
        except (ValueError, IndexError):
            continue
        out.setdefault(name, {"mouth": numbers[0:2], "eyes": numbers[2:4]})
    return out


def write_positions(source: str, name: str, mouth: list[int], eyes: list[int]) -> str:
    """The portrait table with new mouth and eye positions for every row of a portrait."""
    def row(m: re.Match) -> str:
        if m.group(1) != name:
            return m.group(0)
        values = [v.strip() for v in m.group(2).split(",")]
        values[4:8] = [str(int(mouth[0])), str(int(mouth[1])), str(int(eyes[0])), str(int(eyes[1]))]
        return f"{{portrait_{name}_tileset, {', '.join(values)}}}"
    return _ROW_RE.sub(row, source)


def portrait_name(decomp_dir: Path, portrait_id: int) -> str:
    names = portrait_names(decomp_dir)
    if not 0 <= portrait_id < len(names) or names[portrait_id] is None:
        raise PortraitError("unknownPortrait")
    return names[portrait_id]


def overlay_files(decomp_dir: Path, name: str, files: dict[str, bytes]) -> dict[str, bytes]:
    """Decomp-relative path -> content of a replaced portrait's files."""
    paths = _files(decomp_dir, name)
    return {paths[k].relative_to(decomp_dir).as_posix(): v for k, v in files.items()}
