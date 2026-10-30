"""Battle animations made by the community (FEditor / FEBuilder format, as in FE-Repo) converted to the
decomp's own files (ticket 44, see banim.py for the decomp's format).

The source is a script and one 248 x 160 indexed PNG per frame (the 240 x 160 battle screen with the unit on
the right side, facing left, plus an 8 pixel palette strip). The script lists the modes:

    /// - Mode 1          (attack; modes 2 and 4 are copies of 1 and 3 and are left out)
    C03                   (a command: 0x85000003)
    3 p- Sword_001.png    (a frame shown 3/60 s)
    ~~~                   (end of the mode)

Each frame is cut into GBA sprites (8 x 8 to 64 x 64) around its pixels and the sprites are packed into
256 x 64 sheets (a frame's sprites all in one sheet: the engine loads one sheet per frame). The game draws
the right-hand unit with its origin at (0x94, 0x58) (BanimTypesPosRight / gEkrYPosReal in
src/banim-ekrmain.c): sprite offsets are relative to that point. The left-hand side is the mirror.
"""

from __future__ import annotations

import io
import re
import struct
from dataclasses import dataclass, field

from PIL import Image

ORIGIN_X, ORIGIN_Y = 0x94, 0x58
SCREEN_W, SCREEN_H = 240, 160
SHEET_COLS, SHEET_ROWS = 32, 8          # tiles of a 256 x 64 sheet
# Sprite sizes in tiles (width, height) -> (shape, size), biggest first (GBA OBJ attributes).
SPRITES = [((8, 8), (0, 3)), ((8, 4), (1, 3)), ((4, 8), (2, 3)), ((4, 4), (0, 2)), ((4, 2), (1, 2)),
           ((2, 4), (2, 2)), ((2, 2), (0, 1)), ((4, 1), (1, 1)), ((1, 4), (2, 1)), ((2, 1), (1, 0)),
           ((1, 2), (2, 0)), ((1, 1), (0, 0))]
# FEditor's mode numbers -> the decomp's mode names, in the order of the modes table.
MODE_NAMES = ["attack_close", "attack_close_back", "attack_close_critical", "attack_close_critical_back",
              "attack_range", "attack_range_critical", "dodge_close", "dodge_range", "stand_close", "stand",
              "stand_range", "attack_miss"]
COPIED_MODES = {2: 1, 4: 3}             # modes FEditor scripts leave out: copies of another one
MAX_OAM_BYTES = 0x57F0                  # gBanimOaml / gBanimOamr2 buffers (src/banim-ekrmain.c)

_FRAME_RE = re.compile(r"^(\d+)\s+p-\s+(.+?\.png)\s*$", re.IGNORECASE)
_COMMAND_RE = re.compile(r"^C([0-9A-Fa-f]{1,6})$")
_MODE_RE = re.compile(r"^///\s*-\s*Mode\s+(\d+)", re.IGNORECASE)


class ImportError_(Exception):
    """A script or a frame that cannot be converted; args[0] is a code for the UI, args[1:] details."""


@dataclass
class Script:
    modes: dict[int, list[tuple]] = field(default_factory=dict)   # mode -> [("frame", duration, file) | ("code", n)]
    files: list[str] = field(default_factory=list)                # frame files, in order of first use


def parse_script(text: str) -> Script:
    script = Script()
    mode = None
    loop_start = None
    for raw in text.splitlines():
        line = raw.split("#", 1)[0].strip()
        if not line:
            continue
        m = _MODE_RE.match(line)
        if m:
            mode = int(m.group(1))
            script.modes[mode] = []
            continue
        if line.startswith("~~~"):
            mode = None
            continue
        if line.startswith("///") or mode is None:
            continue
        m = _FRAME_RE.match(line)
        if m:
            name = m.group(2).strip()
            script.modes[mode].append(("frame", max(1, int(m.group(1))), name))
            if name not in script.files:
                script.files.append(name)
            continue
        if line.upper() == "L":
            # Loop start (magic: the cast frames repeat until the spell ends). The loop end is the next C01, which
            # gets the number of script words to jump back in its second byte, as FEditor writes it (3 per frame).
            loop_start = len(script.modes[mode])
            continue
        m = _COMMAND_RE.match(line)
        if m:
            code = int(m.group(1), 16)
            if code == 0x01 and loop_start is not None:
                words = sum(3 if step[0] == "frame" else 1 for step in script.modes[mode][loop_start:])
                code |= words << 8
                loop_start = None
            script.modes[mode].append(("code", code))
            continue
        raise ImportError_("badScriptLine", raw.strip())
    for copy, source in COPIED_MODES.items():
        if copy not in script.modes and source in script.modes:
            script.modes[copy] = list(script.modes[source])
    missing = [n for n in range(1, 13) if n not in script.modes]
    if missing:
        raise ImportError_("missingModes", ", ".join(map(str, missing)))
    return script


@dataclass
class Sprite:
    x: int          # tile column / row of the sprite's top-left corner in the frame's tile grid
    y: int
    w: int          # size in tiles
    h: int
    shape: int
    size: int
    tiles: list[bytes] = field(default_factory=list)   # 8 x 8 tiles (64 palette indexes each), row by row


def _cut(pixels: bytes, width: int, left: int, top: int, cols: int, rows: int) -> tuple[list[list[bytes]], list[list[bool]]]:
    """The frame's 8 x 8 tiles from (left, top) and which ones hold a pixel."""
    tiles, used = [], []
    for ty in range(rows):
        row_tiles, row_used = [], []
        for tx in range(cols):
            tile = bytearray()
            for py in range(8):
                y = top + ty * 8 + py
                for px in range(8):
                    x = left + tx * 8 + px
                    tile.append(pixels[y * width + x] & 15 if 0 <= x < SCREEN_W and 0 <= y < SCREEN_H else 0)
            row_tiles.append(bytes(tile))
            row_used.append(any(tile))
        tiles.append(row_tiles)
        used.append(row_used)
    return tiles, used


def cut_frame(image: Image.Image) -> tuple[list[Sprite], int, int]:
    """Sprites covering a frame's pixels and the position of the tile grid relative to the origin."""
    if image.mode != "P":
        raise ImportError_("notIndexed")
    pixels = image.crop((0, 0, SCREEN_W, SCREEN_H)).tobytes()
    box = Image.frombytes("L", (SCREEN_W, SCREEN_H), bytes(255 if p & 15 else 0 for p in pixels)).getbbox()
    if box is None:
        return [], 0, 0
    left, top = box[0], box[1]
    cols, rows = (box[2] - left + 7) // 8, (box[3] - top + 7) // 8
    tiles, used = _cut(pixels, SCREEN_W, left, top, cols, rows)
    covered = [[False] * cols for _ in range(rows)]
    sprites = []
    for y in range(rows):
        for x in range(cols):
            if not used[y][x] or covered[y][x]:
                continue
            for (w, h), (shape, size) in SPRITES:
                if x + w > cols or y + h > rows:
                    continue
                cells = [(x + i, y + j) for j in range(h) for i in range(w)]
                if any(covered[cy][cx] for cx, cy in cells):
                    continue
                if w * h > 1 and sum(used[cy][cx] for cx, cy in cells) * 2 < w * h:
                    continue   # mostly empty: smaller sprites waste less of the sheet
                for cx, cy in cells:
                    covered[cy][cx] = True
                sprites.append(Sprite(x, y, w, h, shape, size, [tiles[cy][cx] for cx, cy in cells]))
                break
    return sprites, left - ORIGIN_X, top - ORIGIN_Y


class _Sheet:
    def __init__(self) -> None:
        self.free = [[True] * SHEET_COLS for _ in range(SHEET_ROWS)]
        self.tiles: dict[tuple[int, int], bytes] = {}

    def place(self, sprites: list[Sprite]) -> list[int] | None:
        """Tile number of each sprite's corner, all placed in this sheet, or None (the sheet is left unchanged)."""
        taken: list[tuple[int, int, Sprite]] = []
        for s in sorted(sprites, key=lambda s: -s.w * s.h):
            spot = self._find(s.w, s.h)
            if spot is None:
                for tx, ty, t in taken:
                    self._mark(tx, ty, t.w, t.h, True)
                return None
            self._mark(spot[0], spot[1], s.w, s.h, False)
            taken.append((spot[0], spot[1], s))
        where = {id(s): (tx, ty) for tx, ty, s in taken}
        result = []
        for s in sprites:
            tx, ty = where[id(s)]
            for j in range(s.h):
                for i in range(s.w):
                    self.tiles[(tx + i, ty + j)] = s.tiles[j * s.w + i]
            result.append(ty * SHEET_COLS + tx)
        return result

    def _find(self, w: int, h: int) -> tuple[int, int] | None:
        for ty in range(SHEET_ROWS - h + 1):
            for tx in range(SHEET_COLS - w + 1):
                if all(self.free[ty + j][tx + i] for j in range(h) for i in range(w)):
                    return tx, ty
        return None

    def _mark(self, tx: int, ty: int, w: int, h: int, free: bool) -> None:
        for j in range(h):
            for i in range(w):
                self.free[ty + j][tx + i] = free

    def png(self, palette: list[int]) -> bytes:
        image = Image.new("P", (SHEET_COLS * 8, SHEET_ROWS * 8), 0)
        image.putpalette(palette[:48] + [0] * (768 - 48))
        for (tx, ty), tile in self.tiles.items():
            image.paste(Image.frombytes("P", (8, 8), tile), (tx * 8, ty * 8))
        out = io.BytesIO()
        image.save(out, "PNG", bits=4)
        return out.getvalue()


FACTIONS = ("player", "enemy", "ally", "other")
# The game recolours the player's blue parts (armour, cloth) for the other armies: red for enemies, green for
# allies, grey for the fourth palette (src/banim_data.c's palettes). Hue in degrees, None: greyed.
FACTION_HUES = {"enemy": 0, "ally": 120, "other": None}


def _rgb16(rgb: list[int]) -> list[tuple[int, int, int]]:
    rgb = (rgb or [])[:48]
    rgb = rgb + [0] * (48 - len(rgb))
    return [tuple(rgb[i:i + 3]) for i in range(0, 48, 3)]


def recolour(colours: list[tuple[int, int, int]], faction: str) -> list[tuple[int, int, int]]:
    """The player's palette for another army: strong blues (hue 190-250 degrees, saturated, not too light:
    the army's colour, not metal or skies) turned red, green or grey, keeping their lightness. Colour 0
    (transparent) and the others are left as they are."""
    import colorsys

    target = FACTION_HUES[faction]
    out = []
    for k, (r, g, b) in enumerate(colours):
        h, light, sat = colorsys.rgb_to_hls(r / 255, g / 255, b / 255)
        if k == 0 or sat < 0.4 or light > 0.8 or not 190 <= h * 360 <= 250:
            out.append((r, g, b))
            continue
        if target is None:
            nr, ng, nb = colorsys.hls_to_rgb(h, light, sat * 0.15)
        else:
            nr, ng, nb = colorsys.hls_to_rgb(target / 360, light, sat)
        out.append((round(nr * 255), round(ng * 255), round(nb * 255)))
    return out


def palette_bytes(image: Image.Image, others: dict[str, list[int]] | None = None) -> bytes:
    """The 4 GBA palettes (player, enemy, ally, other) in BGR555: the frame's colours, and for the other
    armies the palettes the animation's authors made (`others`: faction -> RGB list), else recoloured ones."""
    player = _rgb16(image.getpalette() or [])
    data = b""
    for faction in FACTIONS:
        colours = player if faction == "player" else (
            _rgb16(others[faction]) if others and others.get(faction) else recolour(player, faction))
        data += struct.pack("<16H", *[(r >> 3) | (g >> 3) << 5 | (b >> 3) << 10 for r, g, b in colours])
    return data


@dataclass
class Converted:
    motion: str                  # data/banim/<symbol>_motion.s
    sheets: list[bytes]          # graphics/banim/<symbol>_sheet_<n>.png
    palette: bytes               # graphics/banim/<symbol>.agbpal
    frames: int
    oam_bytes: int


def convert(symbol: str, script_text: str, frames: dict[str, Image.Image],
            palettes: dict[str, list[int]] | None = None) -> Converted:
    """`frames`: frame file name (as the script writes it) -> its image; `palettes`: the authors' palettes
    for the other armies, if any (faction -> RGB list)."""
    script = parse_script(script_text)
    by_name = {k.lower(): v for k, v in frames.items()}
    missing = [f for f in script.files if f.lower() not in by_name]
    if missing:
        raise ImportError_("missingFrames", ", ".join(missing[:5]))
    first = by_name[script.files[0].lower()]
    sheets: list[_Sheet] = [_Sheet()]
    # frame file -> (sheet number, [(attr0, attr1, attr2, dx, dy)] on the right side)
    built: dict[str, tuple[int, list[tuple[int, int, int, int, int]]]] = {}
    for name in script.files:
        sprites, gx, gy = cut_frame(by_name[name.lower()])
        if sum(s.w * s.h for s in sprites) > SHEET_COLS * SHEET_ROWS:
            raise ImportError_("frameTooBig", name)
        corners = sheets[-1].place(sprites)
        if corners is None:
            sheets.append(_Sheet())
            corners = sheets[-1].place(sprites)
        oam = [(s.shape << 14, s.size << 14, corner, gx + s.x * 8, gy + s.y * 8) for s, corner in zip(sprites, corners)]
        built[name] = (len(sheets) - 1, oam)
    oam_bytes = sum(12 * (len(o) + 1) for _s, o in built.values())
    if oam_bytes > MAX_OAM_BYTES:
        raise ImportError_("tooManySprites", str(oam_bytes))
    index = {name: i for i, name in enumerate(script.files)}
    sizes = {(shape, size): (w * 8, h * 8) for (w, h), (shape, size) in SPRITES}

    lines = ["@ Battle animation converted by FE Maker from a FEditor / FEBuilder script",
             f"\t.global {symbol}_script", f"\t.global {symbol}_oam_r", f"\t.global {symbol}_oam_l",
             '\t.include "../include/banim_sheet.inc"', '\t.include "../include/banim_code.inc"',
             '\t.include "../include/banim_code_frame.inc"']
    for side in ("l", "r"):
        lines += [f"\t.section .data.oam_{side}", f"{symbol}_oam_{side}:"]
        for name in script.files:
            lines.append(f"{symbol}_oam_frame_{index[name]}_{side}:")
            for attr0, attr1, attr2, dx, dy in built[name][1]:
                if side == "l":   # the mirror: flipped sprite, offset measured from the other edge
                    width = sizes[(attr0 >> 14, attr1 >> 14)][0]
                    attr1, dx = attr1 | 0x1000, -dx - width
                lines.append(f"\tbanim_frame_oam 0x{attr0:X}, 0x{attr1:X}, 0x{attr2:X}, {dx}, {dy}")
            lines.append("\tbanim_frame_end")
    lines += ["\t.section .data.script", f"{symbol}_script:"]
    for number, mode in enumerate(MODE_NAMES, start=1):
        lines.append(f"{symbol}_mode_{mode}:")
        for step in script.modes[number]:
            if step[0] == "code":
                lines.append(f"\tbanim_code_85 0x{step[1]:X}")
            else:
                _kind, duration, name = step
                sheet, _oam = built[script.files[index[name]]]
                lines.append(f"\tbanim_code_frame {duration}, {symbol}_sheet_{sheet}, {index[name]}, "
                             f"{symbol}_oam_frame_{index[name]}_r - {symbol}_oam_r")
        lines.append("\tbanim_code_end_mode")
    lines.append("\t.section .data.modes")
    lines += [f"\t.word {symbol}_mode_{mode} - {symbol}_script" for mode in MODE_NAMES]
    lines += ["\t.word 0"] * 12
    palette = (first.getpalette() or [])[:48]
    return Converted("\n".join(lines) + "\n", [s.png(palette) for s in sheets], palette_bytes(first, palettes),
                     len(script.files), oam_bytes)


# ---------- the project's animations in the decomp ----------

LINKER_SCRIPT = "linker_script_banim.txt"
TABLE_FILE = "src/banim_data.c"
POINTERS_FILE = "include/banim_pointer.h"
SHEETS_INCLUDE = "include/banim_sheet.inc"
CONF_FILE = "src/data_banimconf.c"
# Items with their own entry in the game's class settings that follow the animation the project gives their weapon
# type (ticket 49): the throwing axes.
FOLLOWING_ITEMS = {"axe": ("ITEM_AXE_HANDAXE", "ITEM_AXE_TOMAHAWK", "ITEM_AXE_HATCHET")}
# The caster moves the same way with every tome, only the spell differs (it comes with the tome): an animation given to
# one of these types goes to the others too, unless they have one of their own (ticket 51).
TOMES = ("anima", "light", "dark")


def with_shared_tomes(weapons: dict) -> dict:
    """A class's project animations with the tomes it has none for taking another tome's (TOMES)."""
    shared = next((weapons[t] for t in TOMES if t in weapons), None)
    return {**({t: shared for t in TOMES} if shared is not None else {}), **weapons}


def set_class_animation(weapons: dict, wtype: str, animation) -> None:
    """Give a class's weapon type an animation (None: back to the game's); the other tomes follow (TOMES)."""
    old = weapons.get(wtype)
    for w in TOMES if wtype in TOMES else (wtype,):
        if w == wtype or weapons.get(w) == old:
            if animation is None:
                weapons.pop(w, None)
            else:
                weapons[w] = animation
CLASSES_FILE = "src/data_classes.c"
MAX_ANIMATIONS = (0x2000 - 8) // 32     # banim_data[] sits between 0xC00008 and 0xC02000 (ldscript.txt)
_TABLE_END = '};\n__attribute__((section(".data.banim_array_len")))'


def symbol_of(key: str) -> str:
    return f"banim_fem_{key}"


def stored_files(symbol: str, converted: Converted) -> dict[str, str | bytes]:
    """The converted animation's decomp files (decomp-relative paths), as stored in the project too."""
    files: dict[str, str | bytes] = {f"data/banim/{symbol}_motion.s": converted.motion,
                                     f"graphics/banim/{symbol}.agbpal": converted.palette}
    for i, sheet in enumerate(converted.sheets):
        files[f"graphics/banim/{symbol}_sheet_{i}.png"] = sheet
    return files


def register(sources: dict[str, str], animations: list[tuple[str, int]], first_number: int) -> dict[str, str]:
    """Add the animations (symbol, number of sheets) after the game's in the table, its declarations and the
    compressing linker's list. `sources`: the current text of those files; returns them changed."""
    table, pointers = sources[TABLE_FILE], sources[POINTERS_FILE]
    sheets, linker = sources[SHEETS_INCLUDE], sources[LINKER_SCRIPT]
    if _TABLE_END not in table:
        raise ImportError_("tableNotFound")
    if first_number - 1 + len(animations) > MAX_ANIMATIONS:
        raise ImportError_("tableFull", str(MAX_ANIMATIONS))
    rows = ""
    for k, (symbol, sheet_count) in enumerate(animations):
        index = first_number - 1 + k
        abbr = symbol.replace("banim_", "")[:11]
        rows += (f'\t{{"{abbr}", &{symbol}_modes_bin, &{symbol}_motion_o, &{symbol}_oam_r_bin, '
                 f"&{symbol}_oam_l_bin, &{symbol}_agbpal}}, // 0x{index:X} (FE Maker)\n")
        pointers += (f"// battle animation 0x{index:X} (FE Maker)\nextern int {symbol}_modes_bin;\n"
                     f"extern char {symbol}_motion_o;\nextern char {symbol}_oam_r_bin;\n"
                     f"extern char {symbol}_oam_l_bin;\nextern char {symbol}_agbpal;\n")
        sheets += "".join(f"\t.extern {symbol}_sheet_{i}\n" for i in range(sheet_count))
        linker = linker.rstrip("\n") + "\n" + "".join(f"graphics/banim/{symbol}_sheet_{i}.4bpp.lz\n" for i in range(sheet_count))
        linker += (f"graphics/banim/{symbol}.agbpal.lz\ndata/banim/{symbol}_oam_l.bin.lz\n"
                   f"data/banim/{symbol}_oam_r.bin.lz\ndata/banim/{symbol}_motion.o|.data.script>lz\n"
                   f"data/banim/{symbol}_modes.bin\n")
    return {TABLE_FILE: table.replace(_TABLE_END, rows + _TABLE_END, 1), POINTERS_FILE: pointers,
            SHEETS_INCLUDE: sheets, LINKER_SCRIPT: linker}


def class_configs(conf_source: str, defs_by_class: dict[str, list[dict]]) -> tuple[str, dict[str, str]]:
    """New animation settings for the classes the project changed: one `AnimConf_FEM_<class>` array each,
    appended to data_banimconf.c. `defs_by_class`: class id -> [{"weapon": "ITYPE_x" or item id,
    "number"}]. Returns the new source and class id -> array name."""
    names = {}
    for class_id, defs in sorted(defs_by_class.items()):
        name = f"AnimConf_FEM_{class_id.replace('CLASS_', '')}"
        rows = ""
        for d in defs:
            weapon = d["weapon"]
            wtype = f"0x0100 | {weapon}" if weapon.startswith("ITYPE_") else weapon
            rows += f"    {{\n        .wtype = {wtype},\n        .index = 0x{d['number']:04X},\n    }},\n"
        conf_source = conf_source.rstrip("\n") + f"\n\nCONST_DATA struct BattleAnimDef {name}[] = {{\n{rows}    {{ 0 }}\n}};\n"
        names[class_id] = name
    return conf_source, names


# ---------- a game animation in FEditor's format (the other way round) ----------

_MACRO_RE = re.compile(r"\.macro\s+(\w+)\s*\n\s*\.word\s+(0x[0-9A-Fa-f]+)\s*\n\s*\.endm")


def _code_macros(decomp_dir) -> dict[str, int]:
    """Script commands of include/banim_code.inc that are one 0x85 word: name -> number."""
    text = (decomp_dir / "include/banim_code.inc").read_text(encoding="utf-8")
    return {name: int(value, 16) & 0xFFFFFF for name, value in _MACRO_RE.findall(text) if int(value, 16) >> 24 == 0x85}


def export_feditor(decomp_dir, symbol: str) -> tuple[str, dict[str, Image.Image]]:
    """A game animation as a FEditor script and its 248 x 160 frames (rotated sprites drawn unrotated)."""
    from . import banim

    text = (decomp_dir / banim.MOTION_DIR / f"{symbol}_motion.s").read_text(encoding="utf-8")
    macros = _code_macros(decomp_dir)
    motion = banim.motion(decomp_dir, symbol)
    colours = banim.palette(decomp_dir, symbol)
    flat = [c for rgb in colours for c in rgb]
    frames: dict[str, Image.Image] = {}
    names: dict[tuple[str, str], str] = {}
    script = []
    mode = None
    modes_seen: dict[str, list[str]] = {}
    for raw in text.splitlines():
        line = raw.strip()
        m = re.match(r".*_mode_(\w+):$", line)
        if m:
            mode = m.group(1)
            modes_seen[mode] = []
            continue
        if mode is None or not line.startswith("banim_code_"):
            continue
        macro = line.split()[0]
        if macro == "banim_code_end_mode":
            mode = None
            continue
        if macro == "banim_code_frame":
            duration, sheet, _number, label = [p.strip() for p in line[len(macro):].split(",")]
            label = label.split("-")[0].strip()
            key = (sheet, label)
            if key not in names:
                names[key] = f"{symbol}_{len(names):03d}.png"
                frames[names[key]] = _frame_image(banim._sheet(decomp_dir, sheet), motion.frames.get(label, []), flat)
            modes_seen[mode].append(f"{int(duration)} p- {names[key]}")
        elif macro == "banim_code_85":
            modes_seen[mode].append(f"C{int(line.split()[1], 0):02X}")
        elif macro in macros:
            modes_seen[mode].append(f"C{macros[macro]:02X}")
    for number, name in enumerate(MODE_NAMES, start=1):
        if number in COPIED_MODES:
            continue
        script += [f"/// - Mode {number}", *modes_seen.get(name, []), "~~~"]
    script.append("/// - End of animation")
    return "\n".join(script) + "\n", frames


def _frame_image(sheet: Image.Image, sprites, palette: list[int]) -> Image.Image:
    from . import banim

    image = Image.new("P", (SCREEN_W + 8, SCREEN_H), 0)
    image.putpalette(palette + [0] * (768 - len(palette)))
    indexes = sheet if sheet.mode == "P" else sheet.convert("L")
    for attr0, attr1, attr2, dx, dy in reversed(sprites):
        width, height = banim.SIZES.get(attr0 >> 14 & 3, banim.SIZES[0])[attr1 >> 14 & 3]
        tile = attr2 & 0x3FF
        part = indexes.crop(((tile % 32) * 8, (tile // 32) * 8, (tile % 32) * 8 + width, (tile // 32) * 8 + height))
        if not attr0 & 0x100 and attr1 & 0x1000:
            part = part.transpose(Image.Transpose.FLIP_LEFT_RIGHT)
        if not attr0 & 0x100 and attr1 & 0x2000:
            part = part.transpose(Image.Transpose.FLIP_TOP_BOTTOM)
        data = part.tobytes()
        mask = Image.frombytes("L", part.size, bytes(255 if p & 15 else 0 for p in data))
        image.paste(Image.frombytes("P", part.size, bytes(p & 15 for p in data)), (ORIGIN_X + dx, ORIGIN_Y + dy), mask)
    return image


MAIN_FILE = "src/banim-ekrmain.c"
_UNIQUE_PALETTE = "        if (chara_pal != -1) {\n"


def without_unique_palettes(source: str, game_count: int) -> str:
    """A character's own battle palette (gAnimCharaPalConfig: Seth as a Paladin...) is drawn for the
    game's animation of his class: not over an imported animation, whose colours it would spoil."""
    if source.count(_UNIQUE_PALETTE) != 2:
        raise ImportError_("paletteCodeNotFound")
    return source.replace(_UNIQUE_PALETTE, f"        if (chara_pal != -1 && bid < 0x{game_count:X}) {{"
                          "   /* FE Maker: imported animations keep their colours */\n")
