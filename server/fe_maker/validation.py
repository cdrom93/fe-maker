"""Live validation: catch what would break the game before compiling.

Each problem carries a translation code and parameters; the UI shows the
translated text, `message` is the English fallback.
"""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import asdict, dataclass, field

from .decomp import banim_import, chaptitle, fonts, mapobjects, tileedit, units
from .decomp import dialogues as decomp_dialogues
from .decomp import events as decomp_events
from .decomp import maps as decomp_maps
from .decomp import portraits as decomp_portraits
from .decomp import supports as decomp_supports
from .decomp.gamedata import (
    ABILITIES_REV,
    AFFINITIES_REV,
    CLASS_STATS,
    GROWTHS,
    LAST_ITEM_NUMBER,
    NEW_CHARACTER_PREFIX,
    NEW_CLASS_PREFIX,
    NEW_ITEM_PREFIX,
    PROMO_STATS,
    RANK_VALUES,
    RANKABLE_TYPES,
    STATS,
    WEAPON_TYPES,
    DecompData,
)

NAME_MAX_LENGTH = 12  # longer names overflow the in-game name boxes
MAX_RESERVATION_GROUPS = 6  # generic weapon locks of the engine (see gamedata.GENERIC_LOCKS)
UNITS_PER_SIDE = {"player": 62, "enemy": 50, "ally": 20}  # gUnitArrayBlue/Red/Green sizes (include/bmunit.h)
AI_ACTION_MAX, AI_MOVE_MAX, AI_RECOVERY_MAX = 0x14, 0x12, 4  # last entries of the AI tables (src/cp_data.c)
# decomp/objectives.py TYPES + read-only "special"
OBJECTIVE_TYPES = ("seize", "defeat_all", "defeat_boss", "defense", "area", "special")
METATILE_COUNT = 1024  # metatiles of a tileset (decomp/maps.py, TileConfig)
MAP_MIN_WIDTH, MAP_MIN_HEIGHT = 15, 10  # one screen (DISPLAY_WIDTH / 16, DISPLAY_HEIGHT / 16)
MAP_BUFFER_BYTES = 0x800  # gBmMapBuffer (src/bmmap.c)
MAP_POOL_BYTES = 0x7B8  # MAP_POOL_SIZE (src/bmmap.c)
OBJECTIVE_LINE_MAX = 22  # longest line of the original status texts ("Defeat Fomortiis, the" = 21)


@dataclass
class Problem:
    severity: str          # "error" blocks the build, "warning" does not
    kind: str              # "characters" | "items" | "classes" | "combat" | "chapters" | "maps"
    id: str
    field: str
    code: str
    params: dict = field(default_factory=dict)
    message: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


def _range(problems, kind, rid, fname, value, lo, hi):
    if not isinstance(value, int) or isinstance(value, bool):
        problems.append(Problem("error", kind, rid, fname, "notANumber", {}, f"{rid}.{fname} must be a whole number"))
    elif not lo <= value <= hi:
        problems.append(Problem("error", kind, rid, fname, "outOfRange", {"min": lo, "max": hi},
                                f"{rid}.{fname} must be between {lo} and {hi}"))


# Characters the game's font can draw (set by validate from the decomp's font).
_font: dict[int, int] = dict(fonts._FALLBACK)
_animated: dict[str, list[str]] = {}


def _chars(problems, kind, rid, fname, text, params=None):
    missing = fonts.unsupported(text, _font)
    if missing:
        problems.append(Problem("error", kind, rid, fname, "unsupportedChars", {**(params or {}), "chars": " ".join(missing)},
                                f"{rid}: the game font cannot draw {' '.join(missing)}"))


def _name(problems, kind, rid, name):
    if not isinstance(name, str) or not name.strip():
        problems.append(Problem("error", kind, rid, "name", "nameEmpty", {}, f"{rid} has no name"))
        return
    if any(c in name for c in "[]#"):
        problems.append(Problem("error", kind, rid, "name", "nameForbiddenChars", {"chars": "[ ] #"},
                                f"{rid}: name cannot contain [ ] or #"))
    _chars(problems, kind, rid, "name", name)
    if len(name) > NAME_MAX_LENGTH:
        problems.append(Problem("warning", kind, rid, "name", "nameTooLong", {"max": NAME_MAX_LENGTH},
                                f"{rid}: name longer than {NAME_MAX_LENGTH} characters may overflow"))


def _duplicates(problems, kind, records):
    seen = set()
    for r in records:
        if r["id"] in seen:
            problems.append(Problem("error", kind, r["id"], "id", "duplicateId", {}, f"Duplicate id {r['id']}"))
        seen.add(r["id"])


def animated_weapons(decomp: DecompData, animations: dict | None) -> dict[str, list[str]]:
    """Weapon types each class has a battle animation for: the game's, and those the project gave it (ticket 44).
    A new dict: the decomp data is shared by every project (ticket 50)."""
    result = {class_id: list(weapons) for class_id, weapons in decomp.animated_weapons.items()}
    for class_id, weapons in ((animations or {}).get("classes") or {}).items():
        weapons = [w for w in banim_import.with_groups(weapons) if w not in banim_import.GROUP_ITEMS]
        known = result.setdefault(class_id, [])
        known += [w for w in weapons if w not in known]
    return result


def validate(characters: list[dict], items: list[dict], decomp: DecompData,
             classes: list[dict] | None = None, combat: dict | None = None,
             chapters: dict | None = None, maps: dict | None = None, dialogues: dict | None = None,
             portraits: dict | None = None, assets_dir=None, animations: dict | None = None,
             unplayed: frozenset | set = frozenset()) -> list[Problem]:
    global _font, _animated
    _animated = animated_weapons(decomp, animations)
    _font = fonts.widths(decomp.decomp_dir)
    problems: list[Problem] = []
    class_ids = {e.fields["number"] for e in decomp.classes.entries}
    # Classes the project adds have their model's battle animations, plus the ones the project gives them.
    new_classes = {c["id"]: c.get("model") for c in classes or [] if c["id"].startswith(NEW_CLASS_PREFIX)}
    class_ids |= set(new_classes)
    for class_id, model in new_classes.items():
        known = _animated.setdefault(class_id, [])
        known += [w for w in _animated.get(model, []) if w not in known]
    icon_count = len(decomp.item_icon_files())
    weapon_types = set(WEAPON_TYPES.values())
    original = {c["id"]: c for c in decomp.export_characters()}
    used_classes = decomp.classes_used_in_game() | set(new_classes)
    first_new = decomp_portraits.first_new_id(decomp.decomp_dir)
    added_portraits = {int(k) for k in (portraits or {}) if str(k).isdigit() and int(k) >= first_new}

    _duplicates(problems, "characters", characters)
    free_numbers = set(decomp.free_character_numbers())
    for ch in characters:
        rid = ch["id"]
        _name(problems, "characters", rid, ch.get("name"))
        if rid.startswith(NEW_CHARACTER_PREFIX) and int(rid.removeprefix(NEW_CHARACTER_PREFIX), 16) not in free_numbers:
            problems.append(Problem("error", "characters", rid, "id", "characterEntryTaken", {},
                                    f"{rid}: this entry of the character table is used by the game"))
        if ch.get("class") not in class_ids:
            problems.append(Problem("error", "characters", rid, "class", "unknownClass", {}, f"{rid}: unknown class"))
        elif (rid not in original or ch["class"] != original[rid]["class"]) and ch["class"] not in used_classes:
            problems.append(Problem("warning", "characters", rid, "class", "unusedClass", {},
                                    f"{rid}: this class is never used in the original game, its graphics may be incomplete"))
        _range(problems, "characters", rid, "level", ch.get("level"), 0, 127)  # 0 for generic units
        _range(problems, "characters", rid, "portraitId", ch.get("portraitId"), 0, 0xFFFF)
        if isinstance(ch.get("portraitId"), int) and ch["portraitId"] >= first_new and ch["portraitId"] not in added_portraits:
            problems.append(Problem("error", "characters", rid, "portraitId", "unknownPortrait", {},
                                    f"{rid}: unknown portrait"))
        if ch.get("affinity") is not None and ch["affinity"] not in AFFINITIES_REV:
            problems.append(Problem("error", "characters", rid, "affinity", "unknownAffinity", {}, f"{rid}: unknown affinity"))
        unknown = [a for a in ch.get("abilities", []) if a not in ABILITIES_REV]
        if unknown:
            problems.append(Problem("error", "characters", rid, "abilities", "unknownAbility", {"names": ", ".join(unknown)},
                                    f"{rid}: unknown abilities {unknown}"))
        for s in STATS:
            _range(problems, "characters", rid, f"bases.{s}", ch["bases"].get(s), -128, 127)
        for s in GROWTHS:
            _range(problems, "characters", rid, f"growths.{s}", ch["growths"].get(s), 0, 255)
        for wtype, rank in ch.get("weaponRanks", {}).items():
            if wtype not in weapon_types:
                problems.append(Problem("error", "characters", rid, "weaponRanks", "unknownWeaponType", {"type": wtype},
                                        f"{rid}: unknown weapon type {wtype}"))
            if isinstance(rank, str) and rank not in RANK_VALUES:
                problems.append(Problem("error", "characters", rid, "weaponRanks", "unknownRank", {"rank": rank},
                                        f"{rid}: unknown weapon rank {rank}"))
            elif isinstance(rank, int):
                _range(problems, "characters", rid, f"weaponRanks.{wtype}", rank, 0, 255)
            # Only what the project changed: a few special original units (summons) have such ranks on purpose.
            orig = original.get(rid)
            changed = orig is None or orig["class"] != ch.get("class") or wtype not in orig["weaponRanks"]
            animated = _animated.get(ch.get("class"), [])
            if changed and rank not in (0, None, "") and animated and wtype not in animated:
                problems.append(Problem("error", "characters", rid, f"weaponRanks.{wtype}", "noBattleAnimation",
                                        {"weapon": wtype},
                                        f"{rid}: the class has no battle animation for {wtype} (the game may crash)"))

    _duplicates(problems, "items", items)
    original_items = {i["id"] for i in decomp.export_items()}
    item_numbers = range(decomp.last_item_number() + 1, LAST_ITEM_NUMBER + 1)
    for it in items:
        rid = it["id"]
        _name(problems, "items", rid, it.get("name"))
        if rid.startswith(NEW_ITEM_PREFIX):
            if int(rid.removeprefix(NEW_ITEM_PREFIX), 16) not in item_numbers:
                problems.append(Problem("error", "items", rid, "id", "itemNumberTaken", {},
                                        f"{rid}: this item number is used by the game"))
            if it.get("model") not in original_items:
                problems.append(Problem("error", "items", rid, "model", "unknownModel", {},
                                        f"{rid}: unknown model weapon"))
        if it.get("weaponType") not in weapon_types:
            problems.append(Problem("error", "items", rid, "weaponType", "unknownWeaponType",
                                    {"type": it.get("weaponType")}, f"{rid}: unknown weapon type"))
        for f in ("might", "hit", "crit", "weight", "uses"):
            _range(problems, "items", rid, f, it.get(f), 0, 255)
        _range(problems, "items", rid, "pricePerUse", it.get("pricePerUse"), 0, 0xFFFF)
        _range(problems, "items", rid, "iconId", it.get("iconId"), 0, max(icon_count - 1, 0))
        rmin, rmax = it["range"].get("min"), it["range"].get("max")
        _range(problems, "items", rid, "range.min", rmin, 0, 15)
        _range(problems, "items", rid, "range.max", rmax, 0, 15)
        # max == 0 is the game's "Magic / 2" range (Physic, Rescue...).
        if isinstance(rmin, int) and isinstance(rmax, int) and rmax != 0 and rmin > rmax:
            problems.append(Problem("error", "items", rid, "range", "rangeInverted", {}, f"{rid}: minimum range above maximum"))
        eff = it.get("effectiveness")
        if eff is not None and decomp.effectiveness is not None and eff not in decomp.effectiveness:
            problems.append(Problem("error", "items", rid, "effectiveness", "unknownEffectiveness", {},
                                    f"{rid}: unknown effectiveness list"))

    _validate_reservations(problems, items, class_ids, {c["id"] for c in characters})

    if classes is not None:
        _validate_classes(problems, classes, decomp, class_ids, weapon_types)
    if combat is not None:
        _validate_combat(problems, combat, class_ids, weapon_types)
    if chapters is not None:
        _validate_chapters(problems, chapters, class_ids, {c["id"] for c in characters}, {i["id"] for i in items}, decomp)
        _validate_unit_weapons(problems, decomp, chapters, characters,
                               classes if classes is not None else decomp.export_classes(), items, unplayed)
    if maps is not None:
        _validate_maps(problems, maps, decomp.decomp_dir)
        if chapters is not None:
            _validate_chapter_maps(problems, decomp, chapters, maps, characters,
                                   classes if classes is not None else decomp.export_classes())
    if portraits:
        _validate_portraits(problems, portraits, decomp, assets_dir)
    if dialogues is not None:
        defs = decomp.decomp_dir / decomp_dialogues.TEXT_DEFS_FILE
        faces = decomp_dialogues.read_faces(defs.read_text(encoding="utf-8")) if defs.is_file() else {}
        faces.update({decomp_portraits.face_code(pid): pid for pid in added_portraits})
        _validate_dialogues(problems, dialogues, faces)
        if dialogues.get("scripts"):
            _validate_scripts(problems, dialogues["scripts"], decomp, characters,
                              set((chapters or {}).get("newGroups", {})),
                              {q.get("key") for q in dialogues.get("quotes", []) if q.get("kind") == "scene"})
        if dialogues.get("supports") is not None:
            original = {tuple(sorted((p["a"], p["b"]))) for p in decomp.original_supports()}
            _validate_supports(problems, dialogues, {c["id"] for c in characters}, original)
    return problems


def _validate_dialogues(problems, data: dict, faces: dict[str, int]):
    """Edited messages and new quotes ("new<n>"): steps the writer knows, existing portraits, text the
    game font can show."""
    edited = list(data.get("messages", {}).items())
    for n, quote in enumerate(data.get("quotes", [])):
        edited.append((f"new{n}", quote.get("steps", [])))
        if quote.get("kind") == "scene":
            continue   # a new message of an event script: no character needed
        if not quote.get("a") or (quote.get("kind") in ("talk", "support") and not quote.get("b")):
            problems.append(Problem("error", "dialogues", f"new{n}", "a", "quoteWithoutCharacter", {},
                                    "new quote without character"))
    for key, steps in edited:
        for n, step in enumerate(steps if isinstance(steps, list) else []):
            kind = step.get("kind")
            rid = f"{key}#{n}"
            if kind == "face" and faces and step.get("face") not in faces:
                problems.append(Problem("error", "dialogues", rid, "face", "unknownFace", {"face": str(step.get("face"))},
                                        f"{key}: unknown portrait"))
            if kind == "say" and not str(step.get("text", "")).strip():
                problems.append(Problem("warning", "dialogues", rid, "text", "emptyLine", {}, f"{key}: empty line"))
            if kind == "say":
                _chars(problems, "dialogues", rid, "text", str(step.get("text", "")))
            for pos in (step.get("pos"), step.get("to")):
                if pos is not None and pos not in decomp_dialogues.POSITIONS:
                    problems.append(Problem("error", "dialogues", rid, "pos", "unknownPosition", {}, f"{key}: unknown position"))
        try:
            decomp_dialogues.render(steps)
        except (decomp_dialogues.DialogueError, KeyError, TypeError, AttributeError):
            problems.append(Problem("error", "dialogues", key, "steps", "badDialogue", {}, f"{key}: malformed dialogue"))


def _validate_portraits(problems, data: dict, decomp: DecompData, assets_dir):
    """Imported portrait sheets: an existing portrait, a readable 128 x 112 sheet of 16 colors at most,
    mouth and eyes on the face."""
    from PIL import Image, UnidentifiedImageError

    for key, entry in data.items():
        rid = f"portrait:{key}"
        try:
            if not decomp_portraits.is_new(decomp.decomp_dir, int(key)):
                decomp_portraits.portrait_name(decomp.decomp_dir, int(key))
        except (decomp_portraits.PortraitError, ValueError):
            problems.append(Problem("error", "characters", rid, "portraitId", "unknownPortrait", {}, f"{rid}: unknown portrait"))
            continue
        path = (assets_dir / entry.get("file", "")) if assets_dir is not None else None
        if path is not None:
            try:
                with Image.open(path) as img:
                    sheet, _colors = decomp_portraits.indexed(img)
                if decomp_portraits.cut_pixels(sheet):
                    problems.append(Problem("warning", "characters", rid, "file", "portrait.cut", {},
                                            f"{rid}: parts of the picture the game does not show"))
            except decomp_portraits.PortraitError as e:
                problems.append(Problem("error", "characters", rid, "file", f"portrait.{e}", {}, f"{rid}: {e}"))
            except (OSError, UnidentifiedImageError):
                problems.append(Problem("error", "characters", rid, "file", "portrait.notAnImage", {}, f"{rid}: no image"))
        for part, (max_x, max_y) in (("mouth", (8, 8)), ("eyes", (8, 8))):
            pos = entry.get(part)
            if not (isinstance(pos, list) and len(pos) == 2 and all(isinstance(v, int) for v in pos)
                    and 0 <= pos[0] <= max_x and 0 <= pos[1] <= max_y):
                problems.append(Problem("error", "characters", rid, part, "outOfRange", {"min": 0, "max": max_x},
                                        f"{rid}: {part} outside the face"))


def _script_constants(decomp: DecompData) -> dict[str, set[str]]:
    """Names a script argument may take, by kind (unit groups, songs, backgrounds)."""
    def constants(rel: str, prefix: str) -> set[str]:
        path = decomp.decomp_dir / rel
        return set(decomp_events.read_constants(path.read_text(encoding="utf-8"), prefix)) if path.is_file() else set()
    try:
        groups = set(units.read_unit_groups(decomp.decomp_dir))
    except FileNotFoundError:
        groups = set()
    return {"group": groups, "song": constants("include/constants/songs.h", "SONG_"),
            "background": constants("include/constants/backgrounds.h", "BG_")}


def _validate_scripts(problems, scripts: dict, decomp: DecompData, characters: list[dict] | None = None,
                      new_groups: set[str] | None = None, scene_messages: set[str] | None = None):
    """Event scripts edited in the visual editor ("script:<name>#<n>"): known script, well-formed
    commands, existing messages, and unit groups, characters, songs and backgrounds the game has
    (else the build stops with a compiler error)."""
    known = _script_constants(decomp)
    known["group"] |= new_groups or set()
    if characters:
        known["character"] = {c["id"] for c in characters if c["id"].startswith("CHARACTER_")}
    for name, commands in scripts.items():
        if decomp.find_script(name) is None:
            problems.append(Problem("error", "dialogues", f"script:{name}", "commands", "unknownScript", {},
                                    f"{name}: unknown event script"))
            continue
        for n, c in enumerate(commands if isinstance(commands, list) else []):
            rid = f"script:{name}#{n}"
            code = decomp_events.validate_command(c)
            if code:
                problems.append(Problem("error", "dialogues", rid, "args", code, {}, f"{rid}: {code}"))
                continue
            spec = decomp_events.COMMANDS.get(c.get("op"), [])
            for (arg, kind), value in zip(spec, c.get("args") or []):
                if kind == "message":
                    try:
                        if str(value).startswith(decomp_dialogues.SCENE_MESSAGE):
                            found = str(value)[len(decomp_dialogues.SCENE_MESSAGE):] in (scene_messages or set())
                        else:
                            found = int(str(value), 0) in decomp.texts.messages
                    except ValueError:
                        found = True   # a constant: the compiler checks it
                    if not found:
                        problems.append(Problem("error", "dialogues", rid, arg, "unknownMessage", {"id": str(value)},
                                                f"{rid}: unknown message {value}"))
                elif known.get(kind) and not re.fullmatch(r"-?(0x[0-9a-fA-F]+|\d+)", str(value).strip()) \
                        and str(value).strip() not in known[kind]:
                    problems.append(Problem("error", "dialogues", rid, arg, "unknownName", {"name": str(value)},
                                            f"{rid}: unknown {kind} {value}"))


def _validate_supports(problems, data: dict, character_ids: set[str], original: set[tuple[str, str]]):
    """Support pairs ("support:A:B"): known characters, 7 partners at most, points in range, and the
    conversations of the new pairs."""
    seen: set[tuple[str, str]] = set()
    partners: dict[str, int] = {}
    talks = {(tuple(sorted((q.get("a"), q.get("b")))), int(q.get("rank", 0)))
             for q in data.get("quotes", []) if q.get("kind") == "support" and q.get("a") and q.get("b")}
    for p in data["supports"]:
        a, b = p.get("a"), p.get("b")
        rid = f"support:{a}:{b}"
        for who in (a, b):
            if who not in character_ids:
                problems.append(Problem("error", "dialogues", rid, "a", "unknownCharacter", {}, f"{rid}: unknown character"))
        if a == b:
            problems.append(Problem("error", "dialogues", rid, "b", "supportSelf", {}, f"{rid}: a character with themself"))
            continue
        key = tuple(sorted((a, b)))
        if key in seen:
            problems.append(Problem("error", "dialogues", rid, "b", "supportDuplicate", {}, f"{rid}: pair listed twice"))
        seen.add(key)
        for who in (a, b):
            partners[who] = partners.get(who, 0) + 1
        _range(problems, "dialogues", rid, "base", p.get("base"), 0, decomp_supports.MAX_POINTS)
        _range(problems, "dialogues", rid, "growth", p.get("growth"), 0, decomp_supports.MAX_POINTS)
        numbers = isinstance(p.get("base"), int) and isinstance(p.get("growth"), int)
        if numbers and decomp_supports.turns_to(1, p["base"], p["growth"]) is None:
            problems.append(Problem("warning", "dialogues", rid, "growth", "supportNever", {}, f"{rid}: never reaches C"))
        skipped = decomp_supports.skipped_levels(p["base"]) if numbers else []
        if skipped:
            ranks = ", ".join("CBA"[r - 1] for r in skipped)
            problems.append(Problem("warning", "dialogues", rid, "base", "supportSkipsTalk",
                                    {"ranks": ranks, "max": decomp_supports.LEVEL_POINTS[0] - 1},
                                    f"{rid}: starts past level {ranks}, its conversation is never seen"))
        if key not in original:
            missing = [r for r in (1, 2, 3) if (key, r) not in talks]
            if missing:
                problems.append(Problem("warning", "dialogues", rid, "talks", "supportNoTalk",
                                        {"ranks": ", ".join("CBA"[r - 1] for r in missing)}, f"{rid}: conversations missing"))
    for who, n in partners.items():
        if n > decomp_supports.MAX_PARTNERS:
            problems.append(Problem("error", "dialogues", f"support:{who}", "partners", "supportTooMany",
                                    {"max": decomp_supports.MAX_PARTNERS}, f"{who}: too many support partners"))


def map_size_problem(width: int, height: int) -> dict | None:
    """Why the engine cannot hold a map of this size (None if it can). See src/bmmap.c:
    gBmMapBuffer holds 2 + 2 * width * height bytes (0x800), each BmMap pool (y + 4) row pointers
    and rows of x + 2 cells (MAP_POOL_SIZE = 0x7B8); the screen shows 15 x 10 cells."""
    if width < MAP_MIN_WIDTH or height < MAP_MIN_HEIGHT:
        return {"code": "mapTooSmall", "params": {"width": MAP_MIN_WIDTH, "height": MAP_MIN_HEIGHT}}
    if 2 + 2 * width * height > MAP_BUFFER_BYTES or (height + 4) * 4 + (height + 4) * (width + 2) > MAP_POOL_BYTES:
        return {"code": "mapTooBig", "params": {"cells": (MAP_BUFFER_BYTES - 2) // 2}}
    return None


def _validate_maps(problems, maps_data: dict, decomp_dir=None):
    sizes = {}
    for layout_id, layout in maps_data.get("layouts", {}).items():
        rows = layout.get("rows")
        if not rows or not isinstance(rows, list) or any(not isinstance(r, list) or len(r) != len(rows[0]) for r in rows) \
                or not rows[0]:
            problems.append(Problem("error", "maps", layout_id, "rows", "badLayout", {},
                                    f"{layout_id}: rows of different lengths"))
            continue
        sizes[layout_id] = (len(rows[0]), len(rows))
        if any(not isinstance(c, int) or not 0 <= c < METATILE_COUNT for row in rows for c in row):
            problems.append(Problem("error", "maps", layout_id, "rows", "badTile", {"max": METATILE_COUNT - 1},
                                    f"{layout_id}: tile numbers go from 0 to {METATILE_COUNT - 1}"))
        size = map_size_problem(*sizes[layout_id])
        if size:
            problems.append(Problem("error", "maps", layout_id, "size", size["code"], size["params"], f"{layout_id}: map size"))
    edited_changes = dict(maps_data.get("changes", {}))
    known_layouts = {}
    if decomp_dir is not None:
        try:
            known_layouts = decomp_maps.layouts(decomp_dir)
        except FileNotFoundError:
            pass  # decomp without chapters (test fixtures)
    bases = maps_data.get("bases", {})
    for layout_id, symbol in bases.items():
        if layout_id in known_layouts and decomp_maps.base_of(decomp_dir, symbol) is None:
            problems.append(Problem("error", "maps", layout_id, "base", "unknownTileSheet", {},
                                    f"{layout_id}: unknown tile sheet {symbol}"))
    for layout_id, symbol in maps_data.get("palettes", {}).items():
        if layout_id in known_layouts and symbol not in {p["id"] for p in decomp_maps.palette_choices(
                decomp_dir, decomp_maps.with_base(decomp_dir, known_layouts[layout_id]["assets"], bases.get(layout_id)))}:
            problems.append(Problem("error", "maps", layout_id, "palette", "paletteNotForTileset", {},
                                    f"{layout_id}: palette {symbol} does not go with its tileset"))
    # A resized map must still hold its original changes.
    for layout_id in sizes:
        if layout_id not in edited_changes and known_layouts.get(layout_id, {}).get("changes"):
            edited_changes[layout_id] = decomp_maps.read_changes(decomp_dir, known_layouts[layout_id]["changes"])
    for layout_id, changes in edited_changes.items():
        if layout_id not in sizes and layout_id in known_layouts:
            width, height, _cells = decomp_maps.read_layout(known_layouts[layout_id]["assets"].layout)
            sizes[layout_id] = (width, height)
        width, height = sizes.get(layout_id, (64, 64))
        seen = set()
        for c in changes:
            cid = c.get("id")
            if not isinstance(cid, int) or not 0 <= cid <= decomp_maps.MAX_CHANGE_ID or cid in seen:
                problems.append(Problem("error", "maps", layout_id, "changes", "badChangeId",
                                        {"id": str(cid), "max": decomp_maps.MAX_CHANGE_ID},
                                        f"{layout_id}: change ids must be different numbers"))
            seen.add(cid)
            rows = c.get("rows") or []
            w, h = c.get("w", 0), c.get("h", 0)
            sized = isinstance(w, int) and isinstance(h, int) and w >= 1 and h >= 1
            if not sized or len(rows) != h or any(len(r) != w for r in rows):
                problems.append(Problem("error", "maps", layout_id, "changes", "badLayout", {},
                                        f"{layout_id}: change {cid} malformed"))
            elif c["x"] < 0 or c["y"] < 0 or c["x"] + w > width or c["y"] + h > height:
                problems.append(Problem("error", "maps", layout_id, "changes", "changeOutOfMap", {"id": str(cid)},
                                        f"{layout_id}: change {cid} goes past the edge of the map"))
    if known_layouts:
        _validate_missing_tiles(problems, maps_data, known_layouts, decomp_dir)
    _validate_map_objects(problems, maps_data, known_layouts, decomp_dir, sizes)


def _validate_missing_tiles(problems, maps_data: dict, known_layouts: dict, decomp_dir):
    """Painted cells on a free slot of their tileset that the project does not fill (an added tile
    removed while the map still used it, ticket 22): the game would show whatever the slot holds."""
    free_slots: dict[str, set[int]] = {}
    bases = maps_data.get("bases", {})
    edited = maps_data.get("tilesets", {})
    grids: dict[str, list] = {}
    for layout_id, layout in maps_data.get("layouts", {}).items():
        grids.setdefault(layout_id, []).append(layout.get("rows") or [])
    for layout_id, changes in maps_data.get("changes", {}).items():
        grids.setdefault(layout_id, []).extend(c.get("rows") or [] for c in changes)
    for layout_id, layout_grids in grids.items():
        if layout_id not in known_layouts:
            continue
        config = decomp_maps.with_base(decomp_dir, known_layouts[layout_id]["assets"], bases.get(layout_id)).config.stem
        if config not in free_slots:
            tile_layout = tileedit.layout_for(decomp_dir, config)
            try:
                tileset = tileedit.Tileset(decomp_dir, tile_layout, None) if tile_layout else None
            except tileedit.TileEditError:
                tileset = None
            free_slots[config] = _filler_slots(tileset) if tileset else set()
        filled = {int(k) for k in edited.get(config, {}).get("metatiles", {})}
        missing = {m for grid in layout_grids for row in grid for m in row if isinstance(m, int)} & (free_slots[config] - filled)
        if missing:
            problems.append(Problem("warning", "maps", layout_id, "rows", "missingTile",
                                    {"tiles": ", ".join(str(m) for m in sorted(missing))},
                                    f"{layout_id}: tiles {sorted(missing)} were removed from the tileset"))


def _filler_slots(tileset) -> set[int]:
    """Empty slots of a tileset: copies of its filler metatile (the most common duplicate), which shows
    garbage. Other duplicates are real tiles of the game (copies of an earlier one) a map may use."""
    dups = Counter((tuple(tileset.metatiles[n]), tileset.terrain[n]) for n, dup in enumerate(tileset.duplicates) if dup)
    if not dups:
        return set()
    filler = dups.most_common(1)[0][0]
    return {n for n, dup in enumerate(tileset.duplicates)
            if dup and (tuple(tileset.metatiles[n]), tileset.terrain[n]) == filler}


def _validate_map_objects(problems, maps_data: dict, known_layouts: dict, decomp_dir, sizes: dict):
    """New villages, chests, doors...: their used state must be known, and their texts readable."""
    painted = maps_data.get("layouts", {})
    settings = maps_data.get("objects", {})
    for layout_id, objects in settings.items():
        for key, s in objects.items():
            text = s.get("text") if isinstance(s, dict) else None
            if isinstance(text, str):
                _chars(problems, "maps", layout_id, "objects", text, {"at": key})
    for layout_id, layout in painted.items():
        if layout_id not in known_layouts or layout_id not in sizes:
            continue
        try:
            found = mapobjects.map_objects(decomp_dir, layout_id, layout["rows"], maps_data.get("changes", {}).get(
                layout_id, decomp_maps.read_changes(decomp_dir, known_layouts[layout_id]["changes"])
                if known_layouts[layout_id]["changes"] else []), settings.get(layout_id))
        except (IndexError, TypeError, ValueError):
            continue  # malformed rows: reported above
        # A change drawn by hand for an object is applied only through the object's own cell: moved
        # off it, it never shows (the passage of a snag drawn beside the snag).
        cells = {(o["x"], o["y"]) for o in found if o["kind"] in mapobjects.CHANGE_KINDS}
        for c in maps_data.get("changes", {}).get(layout_id) or []:
            if c.get("manual") and not any(c["x"] <= x < c["x"] + c["w"] and c["y"] <= y < c["y"] + c["h"] for x, y in cells):
                problems.append(Problem("warning", "maps", layout_id, "changes", "manualChangeOffObject", {"id": c["id"]},
                                        f"{layout_id}: change {c['id']} drawn for an object does not hold its cell"))
        for obj in found:
            params = {"object": obj["kind"], "x": obj["x"], "y": obj["y"]}
            if obj["noAfter"]:
                problems.append(Problem("warning", "maps", layout_id, "objects", "noUsedState", params,
                                        f"{layout_id}: {obj['kind']} at {obj['x']}, {obj['y']}: no used state known"))
            off = settings.get(layout_id, {}).get(f"{obj['x']},{obj['y']}", {}).get("off")
            if not obj["noAfter"] and obj["new"] and obj["change"] is None and obj["kind"] in mapobjects.CHANGE_KINDS \
                    and not off:
                code = "noChangeLayer" if not known_layouts[layout_id]["changes"] else "tooManyChanges"
                problems.append(Problem("warning", "maps", layout_id, "objects", code, params,
                                        f"{layout_id}: {obj['kind']} at {obj['x']}, {obj['y']} will not change"))


def _validate_chapter_maps(problems, decomp, chapters: dict, maps_data: dict, characters: list[dict], classes: list[dict]):
    """Units and seize tiles of the chapters whose map, units or objective were edited: inside the map,
    and on a terrain their class can stand on. Only what the project changed is reported: the original
    game has units outside their map (groups used elsewhere) and units under roofs that a map change
    removes."""
    painted = maps_data.get("layouts", {})
    edited_groups = chapters.get("unitGroups", {})
    objectives_by_chapter = chapters.get("objectives", {})
    if not painted and not edited_groups and not objectives_by_chapter:
        return
    decomp_dir = decomp.decomp_dir
    try:
        layouts = decomp_maps.layouts(decomp_dir)
        groups_by_chapter = units.all_chapter_unit_groups(decomp_dir)
    except (FileNotFoundError, decomp_maps.MapError):
        return  # decomp without chapters (test fixtures)
    original_groups = units.read_unit_groups(decomp_dir)
    costs = decomp_maps.movement_costs(decomp_dir)
    movement = {c["id"]: c.get("movement") for c in classes}
    char_class = {c["id"]: c["class"] for c in characters}
    for layout_id, layout in layouts.items():
        assets = decomp_maps.with_base(decomp_dir, layout["assets"], maps_data.get("bases", {}).get(layout_id))
        for index in layout["chapters"]:
            groups = [g for g in groups_by_chapter.get(index, []) if g["origin"] != "cutscene"]
            if layout_id not in painted and layout_id not in maps_data.get("bases", {}) \
                    and not any(g["name"] in edited_groups for g in groups) \
                    and str(index) not in objectives_by_chapter:
                continue
            original_map = decomp_maps.read_layout(assets.layout)
            _metatiles, original_terrain = decomp_maps.read_config(layout["assets"].config)
            if layout_id in painted and painted[layout_id].get("rows"):
                rows = painted[layout_id]["rows"]
                width, height, cells = len(rows[0]), len(rows), [c for row in rows for c in row]
            else:
                width, height, cells = original_map
            _metatiles, terrain = decomp_maps.read_config(assets.config)

            def terrain_at(layout_map, x, y):
                w, h, c = layout_map
                if not (0 <= x < w and 0 <= y < h):
                    return None
                m = c[y * w + x]
                table = original_terrain if layout_map is original_map else terrain
                return table[m] if m < len(table) else 0

            for g in groups:
                original_units = original_groups[g["name"]].units if g["name"] in original_groups else []
                unit_list = edited_groups.get(g["name"])
                if unit_list is None:
                    unit_list = original_units
                # Units as in the original game (same character, class and tile): their problems are the game's own.
                unchanged = {(o.get("character"), o.get("class"), o.get("endX"), o.get("endY")) for o in original_units}
                for n, u in enumerate(unit_list):
                    rid = f"{g['name']}#{n}"
                    x, y = u.get("endX"), u.get("endY")
                    if not isinstance(x, int) or not isinstance(y, int):
                        continue
                    where = {"x": x, "y": y, "map": layout_id, "chapter": index}
                    t = terrain_at((width, height, cells), x, y)
                    if (u.get("character"), u.get("class"), x, y) in unchanged and t == terrain_at(original_map, x, y):
                        continue
                    if t is None:
                        problems.append(Problem("error", "chapters", rid, "position", "unitOutOfMap", where,
                                                f"{rid}: unit outside the map"))
                        continue
                    character = str(u.get("character", ""))
                    cls = char_class.get(character) if character.startswith("CHARACTER_") else u.get("class")
                    table = costs.get(movement.get(cls) or "")
                    if table and t < len(table) and table[t] < 0:
                        problems.append(Problem("warning", "chapters", rid, "position", "impassableTile", {**where, "terrain": t},
                                                f"{rid}: its class cannot stand on this terrain"))
            o = objectives_by_chapter.get(str(index))
            if o and o.get("type") == "seize":
                for tile in o.get("seize", []):
                    if not (0 <= tile.get("x", -1) < width and 0 <= tile.get("y", -1) < height):
                        problems.append(Problem("error", "chapters", f"objective#{index}", "seize", "seizeOutOfMap",
                                                {"map": layout_id, "chapter": index},
                                                f"chapter {index}: tile to seize outside the map"))



def _rank_value(rank) -> int:
    if isinstance(rank, str):
        return RANK_VALUES.get(rank, 0)
    return rank if isinstance(rank, int) else 0


def weapon_problem(item: dict, character: dict | None, cls: dict | None) -> tuple[str, dict] | None:
    """Why a unit (its character and class) cannot use a weapon or staff it carries, as CanUnitUseWeapon
    (src/bmitem.c) decides: reserved for other classes or characters (weapon locks), a monster weapon,
    or a weapon rank too low (the character's rank for the type, else its class's). None: it can."""
    wtype = item.get("weaponType")
    if wtype not in RANKABLE_TYPES and not item.get("monsterWeapon"):
        return None   # not a weapon or a staff
    char_id = character["id"] if character else ""
    class_id = cls["id"] if cls else ""
    abilities = set((character or {}).get("abilities", [])) | set((cls or {}).get("abilities", []))
    if item.get("monsterWeapon"):
        return None if "lock3" in abilities else ("weaponReserved", {})
    res = item.get("reservedFor") or {}
    if (res.get("classes") or res.get("characters")) and class_id not in res.get("classes", []) \
            and char_id not in res.get("characters", []):
        return ("weaponReserved", {})
    need = _rank_value(item.get("weaponRank"))
    have = _rank_value((character or {}).get("weaponRanks", {}).get(wtype)) \
        or _rank_value((cls or {}).get("weaponRanks", {}).get(wtype))
    if have < need:
        rank = next((r for r, v in RANK_VALUES.items() if v == need), str(need))
        return ("weaponRank", {"rank": rank, "wtype": wtype})
    return None


def _validate_unit_weapons(problems, decomp, chapters: dict, characters: list[dict], classes: list[dict], items: list[dict],
                           unplayed=frozenset()):
    """Weapons that units of the chapters carry but cannot use. Only what the project changed is
    reported (a unit edited, or a character, class or item that changed): the original game gives
    enemies weapons they only drop."""
    try:
        original_groups = units.read_unit_groups(decomp.decomp_dir)
    except FileNotFoundError:
        return
    edited = chapters.get("unitGroups", {})

    def unusable(groups, chars, class_list, item_list):
        by_char = {c["id"]: c for c in chars}
        by_class = {c["id"]: c for c in class_list}
        by_item = {i["id"]: i for i in item_list}
        found = {}
        for name, unit_list in groups.items():
            for n, u in enumerate(unit_list):
                character = by_char.get(str(u.get("character", "")))
                named = character and str(u.get("character", "")).startswith("CHARACTER_")
                class_id = character["class"] if named else u.get("class")
                for item_id in u.get("items", []):
                    item = by_item.get(item_id)
                    why = item and weapon_problem(item, character, by_class.get(class_id))
                    if why:
                        found[(name, n, item_id)] = (u.get("character"), why)
        return found

    current = {name: edited.get(name, g.units) for name, g in original_groups.items()}
    current.update({name: unit_list for name, unit_list in edited.items() if name not in current})
    current = {name: unit_list for name, unit_list in current.items() if name not in unplayed}
    original_items = {i["id"]: i for i in decomp.export_items()}
    before = unusable({name: g.units for name, g in original_groups.items()}, decomp.export_characters(),
                      decomp.export_classes(), list(original_items.values()))
    known = {(name, char, item) for (name, _n, item), (char, _why) in before.items()}
    names = {i["id"]: i.get("name") or i["id"] for i in items}
    # Units of edited groups get their own warning; the others changed through a character, class or
    # item sheet: one warning there for all of them (the item when it changed, else the named character).
    changed_items = {i["id"] for i in items if original_items.get(i["id"]) != i}
    carried: dict[tuple, int] = {}
    for (name, n, item_id), (char, (code, params)) in unusable(current, characters, classes, items).items():
        if (name, char, item_id) in known:
            continue
        if name in edited:
            rid = f"{name}#{n}"
            problems.append(Problem("warning", "chapters", rid, "items", code, {"item": names.get(item_id, item_id), **params},
                                    f"{rid}: cannot use {item_id}"))
            continue
        if str(char).startswith("CHARACTER_") and item_id not in changed_items:
            key = ("characters", char, "class")
        else:
            key = ("items", item_id, "weaponRank" if code == "weaponRank" else "reservedFor")
        key = key + (item_id, code, tuple(sorted(params.items())))
        carried[key] = carried.get(key, 0) + 1
    for (kind, rid, field_name, item_id, code, params), count in carried.items():
        problems.append(Problem("warning", kind, rid, field_name, "carried" + code[len("weapon"):],
                                {"item": names.get(item_id, item_id), "count": count, **dict(params)},
                                f"{rid}: {count} units carry {item_id} and cannot use it"))


def _validate_objectives(problems, objectives_by_chapter: dict, character_ids=frozenset()):
    for index, o in objectives_by_chapter.items():
        rid = f"objective#{index}"
        kind = o.get("type")
        if kind not in OBJECTIVE_TYPES:
            problems.append(Problem("error", "chapters", rid, "type", "unknownObjective", {}, f"{rid}: unknown objective type"))
        if kind == "seize":
            if not o.get("seize"):
                problems.append(Problem("error", "chapters", rid, "seize", "noSeizeTile", {}, f"{rid}: no tile to seize"))
            for tile in o.get("seize", []):
                _range(problems, "chapters", rid, "seize", tile.get("x"), 0, 63)
                _range(problems, "chapters", rid, "seize", tile.get("y"), 0, 63)
        if kind == "defense":
            _range(problems, "chapters", rid, "turns", o.get("turns"), 1, 99)
        if kind == "area" and not o.get("area"):
            problems.append(Problem("error", "chapters", rid, "area", "noArea", {}, f"{rid}: no area to reach"))
        for key in ("areaWho", "protect"):
            if o.get(key) and o[key] not in character_ids:
                problems.append(Problem("error", "chapters", rid, key, "unknownCharacter", {}, f"{rid}: unknown character"))
        by_boss = kind == "defeat_boss" or (kind == "defense" and o.get("orBoss"))
        if by_boss and o.get("boss") and o["boss"] not in character_ids:
            problems.append(Problem("error", "chapters", rid, "boss", "unknownCharacter", {}, f"{rid}: unknown boss"))
        text = o.get("statusText")
        if text is not None:
            lines = text.strip().split("\n")
            if not text.strip():
                problems.append(Problem("error", "chapters", rid, "statusText", "nameEmpty", {}, f"{rid}: empty objective text"))
            elif fonts.unsupported(text, _font):
                _chars(problems, "chapters", rid, "statusText", text)
            elif len(lines) > 2 or any(len(line) > OBJECTIVE_LINE_MAX for line in lines):
                problems.append(Problem("warning", "chapters", rid, "statusText", "objectiveTextTooLong",
                                        {"lines": 2, "max": OBJECTIVE_LINE_MAX}, f"{rid}: objective text may not fit"))


def _validate_chapters(problems, chapters, class_ids, character_ids, item_ids, decomp=None):
    if decomp is not None:
        for index, title in chapters.get("titles", {}).items():
            if chaptitle.text_width(decomp.decomp_dir, title, 0) > chaptitle.VISIBLE_WIDTH - 4:
                problems.append(Problem("warning", "chapters", str(index), "title", "titleTooLong", {},
                                        f"Chapter {index}: the title does not fit in its picture"))
    _validate_objectives(problems, chapters.get("objectives", {}), character_ids)
    for group, unit_list in chapters.get("unitGroups", {}).items():
        for side, limit in UNITS_PER_SIDE.items():
            count = sum(1 for u in unit_list if u.get("side") == side)
            if count > limit:
                problems.append(Problem("error", "chapters", f"{group}#", "side", "tooManyUnits", {"max": limit, "side": side},
                                        f"{group}: at most {limit} {side} units"))
        seen: dict[tuple, int] = {}
        for n, unit in enumerate(unit_list):
            rid = f"{group}#{n}"
            tile = (unit.get("endX"), unit.get("endY"))
            if tile in seen:
                problems.append(Problem("warning", "chapters", rid, "position", "sameTile", {"x": tile[0], "y": tile[1]},
                                        f"{rid}: another unit of the group starts on the same tile"))
            seen.setdefault(tile, n)
            char = unit.get("character", "")
            if char in ("", "0", "0x0", "0x00"):
                # Character 0 is the end-of-group marker: the unit and the ones after it would vanish.
                problems.append(Problem("error", "chapters", rid, "character", "noCharacter", {}, f"{rid}: no character"))
            # Generic units use raw ids (0x80...) rather than CHARACTER_ names.
            if char.startswith("CHARACTER_") and char not in character_ids:
                problems.append(Problem("error", "chapters", rid, "character", "unknownCharacter", {},
                                        f"{rid}: unknown character"))
            # A named character's class comes from its sheet (see units._apply_unit_fields).
            if not char.startswith("CHARACTER_") and unit.get("class") not in class_ids:
                problems.append(Problem("error", "chapters", rid, "class", "unknownClass", {}, f"{rid}: unknown class"))
            _range(problems, "chapters", rid, "level", unit.get("level"), 0, 31)  # 5-bit field
            _range(problems, "chapters", rid, "endX", unit.get("endX"), 0, 63)  # 6-bit fields
            _range(problems, "chapters", rid, "endY", unit.get("endY"), 0, 63)
            ai = unit.get("ai")
            if isinstance(ai, list):
                # Indexes into gAi1ScriptTable, gAi2ScriptTable and gAI3HealingThresholdTable (src/cp_data.c).
                if len(ai) != 4 or ai[0] > AI_ACTION_MAX or ai[1] > AI_MOVE_MAX or ai[2] & 0x7 > AI_RECOVERY_MAX or ai[3] > 255:
                    problems.append(Problem("error", "chapters", rid, "ai", "badAi", {},
                                            f"{rid}: AI value outside the engine tables"))
            item_list = unit.get("items", [])
            if len(item_list) > 4:
                problems.append(Problem("error", "chapters", rid, "items", "tooManyItems", {"max": 4}, f"{rid}: at most 4 items"))
            for it in item_list:
                if it not in item_ids:
                    problems.append(Problem("error", "chapters", rid, "items", "unknownItem", {}, f"{rid}: unknown item {it}"))


def _validate_reservations(problems, items, class_ids, character_ids):
    groups = set()
    for it in items:
        res = it.get("reservedFor")
        if not res or not (res.get("classes") or res.get("characters")):
            continue
        for c in res.get("classes", []):
            if c not in class_ids:
                problems.append(Problem("error", "items", it["id"], "reservedFor", "unknownClass", {},
                                        f"{it['id']}: unknown class {c}"))
        for c in res.get("characters", []):
            if c not in character_ids:
                problems.append(Problem("error", "items", it["id"], "reservedFor", "unknownCharacter", {},
                                        f"{it['id']}: unknown character {c}"))
        groups.add((frozenset(res.get("classes", [])), frozenset(res.get("characters", []))))
    if len(groups) > MAX_RESERVATION_GROUPS:
        problems.append(Problem("error", "items", "", "reservedFor", "tooManyReservations", {"max": MAX_RESERVATION_GROUPS},
                                f"At most {MAX_RESERVATION_GROUPS} different 'reserved for' lists (engine weapon locks)"))


def _validate_classes(problems, classes, decomp, class_ids, weapon_types):
    original = {c["id"]: c for c in decomp.export_classes()}
    movement_types = set(decomp.movement_types())
    _duplicates(problems, "classes", classes)
    for cl in classes:
        rid = cl["id"]
        if rid.startswith(NEW_CLASS_PREFIX):
            _name(problems, "classes", rid, cl.get("name"))
            if cl.get("model") not in original:
                problems.append(Problem("error", "classes", rid, "model", "unknownModel", {}, f"{rid}: unknown model class"))
        elif cl.get("name"):  # some engine-only classes have no name in the original game
            _name(problems, "classes", rid, cl["name"])
        for s in CLASS_STATS:
            _range(problems, "classes", rid, f"bases.{s}", cl["bases"].get(s), 0, 127)
            _range(problems, "classes", rid, f"maxes.{s}", cl["maxes"].get(s), 0, 127)
            base, cap = cl["bases"].get(s), cl["maxes"].get(s)
            if isinstance(base, int) and isinstance(cap, int) and base > cap:
                problems.append(Problem("warning", "classes", rid, f"maxes.{s}", "baseAboveMax", {},
                                        f"{rid}: base {s} above its maximum"))
        _range(problems, "classes", rid, "mov", cl.get("mov"), 0, 15)
        for s in GROWTHS:
            _range(problems, "classes", rid, f"growths.{s}", cl["growths"].get(s), 0, 127)
        for s in PROMO_STATS:
            _range(problems, "classes", rid, f"promotionGains.{s}", cl["promotionGains"].get(s), 0, 255)
        _range(problems, "classes", rid, "relativePower", cl.get("relativePower"), -128, 127)
        unknown = [a for a in cl.get("abilities", []) if a not in ABILITIES_REV]
        if unknown:
            problems.append(Problem("error", "classes", rid, "abilities", "unknownAbility", {"names": ", ".join(unknown)},
                                    f"{rid}: unknown abilities {unknown}"))
        promos = cl.get("promotions", [])
        if len(promos) > 2:
            problems.append(Problem("error", "classes", rid, "promotions", "tooManyPromotions", {},
                                    f"{rid}: at most two promotions"))
        for p in promos:
            if p not in class_ids:
                problems.append(Problem("error", "classes", rid, "promotions", "unknownClass", {}, f"{rid}: unknown class {p}"))
        if cl.get("movement") is not None and cl["movement"] not in movement_types:
            problems.append(Problem("error", "classes", rid, "movement", "unknownMovement", {}, f"{rid}: unknown movement"))
        if cl.get("terrainBonus") not in (None, "Common", "Fly"):
            problems.append(Problem("error", "classes", rid, "terrainBonus", "unknownTerrainBonus", {},
                                    f"{rid}: unknown terrain bonus"))
        orig = original.get(rid, {})
        animated = _animated.get(rid, [])
        for wtype, rank in cl.get("weaponRanks", {}).items():
            if wtype not in weapon_types:
                problems.append(Problem("error", "classes", rid, "weaponRanks", "unknownWeaponType", {"type": wtype},
                                        f"{rid}: unknown weapon type {wtype}"))
            elif isinstance(rank, str) and rank not in RANK_VALUES:
                problems.append(Problem("error", "classes", rid, "weaponRanks", "unknownRank", {"rank": rank},
                                        f"{rid}: unknown weapon rank {rank}"))
            elif rank not in (0, None, "") and animated and wtype not in animated \
                    and wtype not in orig.get("weaponRanks", {}):
                problems.append(Problem("error", "classes", rid, f"weaponRanks.{wtype}", "noBattleAnimation",
                                        {"weapon": wtype},
                                        f"{rid}: the class has no battle animation for {wtype} (the game may crash)"))


def _validate_combat(problems, combat, class_ids, weapon_types):
    for i, rule in enumerate(combat.get("triangle", [])):
        rid = f"triangle.{i}"
        for side in ("attacker", "defender"):
            if rule.get(side) not in weapon_types:
                problems.append(Problem("error", "combat", rid, side, "unknownWeaponType", {"type": rule.get(side)},
                                        f"{rid}: unknown weapon type"))
        _range(problems, "combat", rid, "hit", rule.get("hit"), -128, 127)
        _range(problems, "combat", rid, "damage", rule.get("damage"), -128, 127)
    for name, members in combat.get("effectiveness", {}).items():
        for cls in members:
            if cls not in class_ids:
                problems.append(Problem("error", "combat", name, "effectiveness", "unknownClass", {},
                                        f"{name}: unknown class {cls}"))
