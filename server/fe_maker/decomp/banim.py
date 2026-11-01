"""Battle animations of the game, read from the decomp to be shown in FE Maker (ticket 44).

The decomp keeps each animation as text and images:
- src/banim_data.c: the animation table (`banim_data[]`), one entry per animation, named like
  "lorm_sp1" (male lord, spear); entry i is animation number i + 1 in the classes' settings;
- src/data_banimconf.c: for each class, its animations by weapon type (`.wtype = 0x0100 | ITYPE_x`)
  or by item (`.wtype = ITEM_x`), `.index` being the animation number;
- data/banim/<anim>_motion.s: the script of each "mode" (stand, attack close, critical, dodge...),
  a list of `banim_code_frame duration, sheet, frame, oam offset`, and the frames themselves as GBA
  sprites (`banim_frame_oam attr0, attr1, attr2, dx, dy`), one list per side (_r, _l);
- graphics/banim/<sheet>.png: 256 x 64 sheets of 8 x 8 tiles (32 tiles a row), 16 colours;
- graphics/banim/<anim>.agbpal: 4 palettes of 16 BGR555 colours (player, enemy, ally, other).

Rotated sprites (arrows, thrown weapons) are drawn without their rotation.
"""

from __future__ import annotations

import io
import re
import struct
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from PIL import Image

TABLE_FILE = "src/banim_data.c"
CONF_FILE = "src/data_banimconf.c"
MOTION_DIR = "data/banim"
GRAPHICS_DIR = "graphics/banim"
MODES = ("stand", "attack_close", "attack_close_critical", "attack_range", "attack_range_critical",
         "dodge_close", "dodge_range", "attack_miss", "stand_close", "stand_range",
         "attack_close_back", "attack_close_critical_back")
ATTACK_MODES = ("attack_close", "attack_close_critical", "attack_range", "attack_range_critical")
RANGED_MODES = ("attack_range", "attack_range_critical")
PALETTES = ("player", "enemy", "ally", "other")
# GBA sprite sizes by shape (attr0 bits 14-15) and size (attr1 bits 14-15).
SIZES = {0: [(8, 8), (16, 16), (32, 32), (64, 64)], 1: [(16, 8), (32, 8), (32, 16), (64, 32)],
         2: [(8, 16), (8, 32), (16, 32), (32, 64)]}

_ENTRY_RE = re.compile(r'\{\s*"(\w+)",\s*&(\w+?)_modes_bin')
_CONF_RE = re.compile(r"struct\s+BattleAnimDef\s+(\w+)\s*\[\s*\]\s*=\s*\{(.*?)\{\s*0\s*\}", re.DOTALL)
_DEF_RE = re.compile(r"\.wtype\s*=\s*([^,]+?)\s*,\s*\.index\s*=\s*(\w+)")
_OAM_RE = re.compile(r"banim_frame_oam\s+([^\n]+)")
_CAST_RE = re.compile(r"banim_code_call_spell_anim|banim_code_85 0x5$", re.MULTILINE)
_FRAME_RE = re.compile(r"banim_code_frame\s+(\d+),\s*(\w+),\s*(\d+),\s*(\w+)\s*-")


@dataclass
class Animation:
    number: int        # as in the classes' settings (table index + 1)
    name: str          # "lorm_sp1"
    symbol: str        # file stem: "banim_lorm_sp1_2"


@lru_cache(maxsize=2)
@lru_cache(maxsize=2)
def table(decomp_dir: Path) -> list[Animation]:
    source = (decomp_dir / TABLE_FILE).read_text(encoding="utf-8")
    return [Animation(i + 1, m.group(1), m.group(2)) for i, m in enumerate(_ENTRY_RE.finditer(source))]


@lru_cache(maxsize=2)
def configs(decomp_dir: Path) -> dict[str, list[dict]]:
    """Animation settings name (`AnimConf_...`) -> [{"weapon": "ITYPE_SWORD" or an item id, "number"}]."""
    result = {}
    for m in _CONF_RE.finditer((decomp_dir / CONF_FILE).read_text(encoding="utf-8")):
        defs = []
        for wtype, index in _DEF_RE.findall(m.group(2)):
            weapon = wtype.split("|")[-1].strip()
            defs.append({"weapon": weapon, "number": int(index, 0)})
        result[m.group(1)] = defs
    return result


@dataclass
class Motion:
    frames: dict[str, list[tuple[int, int, int, int, int]]]   # oam label -> sprites (right side)
    modes: dict[str, list[tuple[int, str, str]]]               # mode -> [(duration, sheet, oam label)]


@lru_cache(maxsize=32)
def motion(decomp_dir: Path, symbol: str) -> Motion:
    text = (decomp_dir / MOTION_DIR / f"{symbol}_motion.s").read_text(encoding="utf-8")
    frames: dict[str, list] = {}
    modes: dict[str, list] = {}
    current_frame = current_mode = None
    for line in text.splitlines():
        line = line.strip()
        if line.endswith(":"):
            label = line[:-1]
            current_frame = label if label.endswith("_r") and "_oam_frame_" in label else None
            if current_frame:
                frames[current_frame] = []
            mode = re.search(r"_mode_(\w+)$", label)
            current_mode = mode.group(1) if mode else current_mode if not current_frame else None
            if mode:
                modes[current_mode] = []
            continue
        if current_frame:
            m = _OAM_RE.match(line)
            if m:
                frames[current_frame].append(tuple(int(v.strip(), 0) for v in m.group(1).split(",")))
        elif current_mode:
            m = _FRAME_RE.match(line)
            if m:
                modes[current_mode].append((int(m.group(1)), m.group(2), m.group(4)))
    return Motion(frames, modes)


def palette(decomp_dir: Path, symbol: str, which: int = 0) -> list[tuple[int, int, int]]:
    data = (decomp_dir / GRAPHICS_DIR / f"{symbol}.agbpal").read_bytes()
    colours = struct.unpack_from("<16H", data, 32 * which if len(data) >= 32 * (which + 1) else 0)
    return [((c & 31) * 255 // 31, (c >> 5 & 31) * 255 // 31, (c >> 10 & 31) * 255 // 31) for c in colours]


@lru_cache(maxsize=64)
def _sheet(decomp_dir: Path, sheet: str) -> Image.Image:
    image = Image.open(decomp_dir / GRAPHICS_DIR / f"{sheet}.png")
    image.load()
    return image


def _sprite(sheet: Image.Image, attr0: int, attr1: int, attr2: int,
            colours: list[tuple[int, int, int]]) -> Image.Image:
    width, height = SIZES.get(attr0 >> 14 & 3, SIZES[0])[attr1 >> 14 & 3]
    tile = attr2 & 0x3FF
    x, y = (tile % 32) * 8, (tile // 32) * 8
    part = sheet.crop((x, y, x + width, y + height))
    indexes = part.tobytes() if part.mode == "P" else part.convert("L").tobytes()
    rgba = bytearray()
    for i in indexes:
        r, g, b = colours[i & 15]
        rgba += bytes((r, g, b, 0 if i & 15 == 0 else 255))
    out = Image.frombytes("RGBA", (width, height), bytes(rgba))
    affine = attr0 & 0x100
    if not affine and attr1 & 0x1000:
        out = out.transpose(Image.Transpose.FLIP_LEFT_RIGHT)
    if not affine and attr1 & 0x2000:
        out = out.transpose(Image.Transpose.FLIP_TOP_BOTTOM)
    return out


@lru_cache(maxsize=64)
def mode_strip(decomp_dir: Path, symbol: str, mode: str, which: int = 0,
               colours: tuple[tuple[int, int, int], ...] | None = None) -> tuple[bytes, dict]:
    """PNG strip of a mode's frames side by side (same size, the animation's origin at the same place)
    and {"durations": [...], "width", "height"} (durations in 1/60 s). `colours`: 16, instead of the animation's."""
    m = motion(decomp_dir, symbol)
    steps = m.modes.get(mode)
    if not steps:
        raise KeyError(mode)
    colours = colours or palette(decomp_dir, symbol, which)
    drawn = []
    for _duration, sheet, label in steps:
        sprites = [(_sprite(_sheet(decomp_dir, sheet), a0, a1, a2, colours), dx, dy)
                   for a0, a1, a2, dx, dy in m.frames.get(label, [])]
        drawn.append(sprites)
    boxes = [(dx, dy, dx + s.width, dy + s.height) for sprites in drawn for s, dx, dy in sprites] or [(0, 0, 1, 1)]
    x0, y0 = min(b[0] for b in boxes), min(b[1] for b in boxes)
    width, height = max(b[2] for b in boxes) - x0, max(b[3] for b in boxes) - y0
    strip = Image.new("RGBA", (width * len(steps), height))
    for k, sprites in enumerate(drawn):
        # the first sprite of a frame is drawn on top (GBA priority): paste backwards
        for s, dx, dy in reversed(sprites):
            strip.alpha_composite(s, (k * width + dx - x0, dy - y0))
    out = io.BytesIO()
    strip.save(out, "PNG")
    return out.getvalue(), {"durations": [d for d, _s, _l in steps], "width": width, "height": height}


@lru_cache(maxsize=512)
def _casts(path: str, _modified: int, symbol: str) -> bool:
    text = Path(path).read_text(encoding="utf-8", errors="ignore")
    ranged = text.partition(f"{symbol}_mode_attack_range:")[2].partition(f"{symbol}_mode_attack_range_critical:")[0]
    return _CAST_RE.search(ranged) is not None


def casts_at_range(base: Path, symbol: str) -> bool:
    """An animation's ranged attack calls the spell: what makes it hit from afar. True if its script cannot be read."""
    path = base / MOTION_DIR / f"{symbol}_motion.s"
    return not path.is_file() or _casts(str(path), path.stat().st_mtime_ns, symbol)


def empty_modes(base: Path, symbol: str) -> list[str]:
    """Attacks with at most one picture, and ranged attacks that call no spell: nothing reaches the target."""
    found = motion(base, symbol).modes
    silent = not casts_at_range(base, symbol)
    return [m for m in ATTACK_MODES if len(found.get(m, ())) <= 1 or (silent and m in RANGED_MODES)]


def modes_of(decomp_dir: Path, symbol: str) -> list[str]:
    found = motion(decomp_dir, symbol).modes
    return [m for m in MODES if found.get(m)]


def clear_caches() -> None:
    """After a project's animation was imported or removed (its folder may be reused)."""
    for cached in (motion, _sheet, mode_strip):
        cached.cache_clear()
