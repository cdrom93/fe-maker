"""Live validation: catch what would break the game before compiling.

Each problem carries a translation code and parameters; the UI shows the
translated text, `message` is the English fallback.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field

from .decomp import dialogues as decomp_dialogues
from .decomp import mapobjects, units
from .decomp import maps as decomp_maps
from .decomp.gamedata import (
    ABILITIES_REV,
    AFFINITIES_REV,
    CLASS_STATS,
    GROWTHS,
    PROMO_STATS,
    RANK_VALUES,
    STATS,
    WEAPON_TYPES,
    DecompData,
)

NAME_MAX_LENGTH = 12  # longer names overflow the in-game name boxes
MAX_RESERVATION_GROUPS = 6  # generic weapon locks of the engine (see gamedata.GENERIC_LOCKS)
UNITS_PER_SIDE = {"player": 62, "enemy": 50, "ally": 20}  # gUnitArrayBlue/Red/Green sizes (include/bmunit.h)
AI_ACTION_MAX, AI_MOVE_MAX, AI_RECOVERY_MAX = 0x14, 0x12, 4  # last entries of the AI tables (src/cp_data.c)
OBJECTIVE_TYPES = ("seize", "defeat_all", "defeat_boss", "defense", "special")  # decomp/objectives.py TYPES + read-only "special"
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


def _name(problems, kind, rid, name):
    if not isinstance(name, str) or not name.strip():
        problems.append(Problem("error", kind, rid, "name", "nameEmpty", {}, f"{rid} has no name"))
        return
    if any(c in name for c in "[]#"):
        problems.append(Problem("error", kind, rid, "name", "nameForbiddenChars", {"chars": "[ ] #"},
                                f"{rid}: name cannot contain [ ] or #"))
    if not name.isascii():
        problems.append(Problem("error", kind, rid, "name", "nameNonAscii", {},
                                f"{rid}: the game font has no accented letters"))
    if len(name) > NAME_MAX_LENGTH:
        problems.append(Problem("warning", kind, rid, "name", "nameTooLong", {"max": NAME_MAX_LENGTH},
                                f"{rid}: name longer than {NAME_MAX_LENGTH} characters may overflow"))


def _duplicates(problems, kind, records):
    seen = set()
    for r in records:
        if r["id"] in seen:
            problems.append(Problem("error", kind, r["id"], "id", "duplicateId", {}, f"Duplicate id {r['id']}"))
        seen.add(r["id"])


def validate(characters: list[dict], items: list[dict], decomp: DecompData,
             classes: list[dict] | None = None, combat: dict | None = None,
             chapters: dict | None = None, maps: dict | None = None, dialogues: dict | None = None) -> list[Problem]:
    problems: list[Problem] = []
    class_ids = {e.fields["number"] for e in decomp.classes.entries}
    icon_count = len(decomp.item_icon_files())
    weapon_types = set(WEAPON_TYPES.values())
    original = {c["id"]: c for c in decomp.export_characters()}
    used_classes = decomp.classes_used_in_game()

    _duplicates(problems, "characters", characters)
    for ch in characters:
        rid = ch["id"]
        _name(problems, "characters", rid, ch.get("name"))
        if ch.get("class") not in class_ids:
            problems.append(Problem("error", "characters", rid, "class", "unknownClass", {}, f"{rid}: unknown class"))
        elif rid in original and ch["class"] != original[rid]["class"] and ch["class"] not in used_classes:
            problems.append(Problem("warning", "characters", rid, "class", "unusedClass", {},
                                    f"{rid}: this class is never used in the original game, its graphics may be incomplete"))
        _range(problems, "characters", rid, "level", ch.get("level"), 0, 127)  # 0 for generic units
        _range(problems, "characters", rid, "portraitId", ch.get("portraitId"), 0, 0xFFFF)
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
            animated = decomp.animated_weapons.get(ch.get("class"), [])
            if changed and rank not in (0, None, "") and animated and wtype not in animated:
                problems.append(Problem("error", "characters", rid, f"weaponRanks.{wtype}", "noBattleAnimation",
                                        {"weapon": wtype},
                                        f"{rid}: the class has no battle animation for {wtype} (the game may crash)"))

    _duplicates(problems, "items", items)
    for it in items:
        rid = it["id"]
        _name(problems, "items", rid, it.get("name"))
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
        _validate_chapters(problems, chapters, class_ids, {c["id"] for c in characters}, {i["id"] for i in items})
    if maps is not None:
        _validate_maps(problems, maps, decomp.decomp_dir)
        if chapters is not None:
            _validate_chapter_maps(problems, decomp, chapters, maps, characters,
                                   classes if classes is not None else decomp.export_classes())
    if dialogues is not None:
        defs = decomp.decomp_dir / decomp_dialogues.TEXT_DEFS_FILE
        faces = decomp_dialogues.read_faces(defs.read_text(encoding="utf-8")) if defs.is_file() else {}
        _validate_dialogues(problems, dialogues, faces)
    return problems


def _validate_dialogues(problems, data: dict, faces: dict[str, int]):
    """Edited messages and new quotes ("new<n>"): steps the writer knows, existing portraits, text the
    game font can show."""
    edited = list(data.get("messages", {}).items())
    for n, quote in enumerate(data.get("quotes", [])):
        edited.append((f"new{n}", quote.get("steps", [])))
        if not quote.get("a") or (quote.get("kind") == "talk" and not quote.get("b")):
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
            if kind == "say" and not str(step.get("text", "")).isascii():
                problems.append(Problem("error", "dialogues", rid, "text", "nameNonAscii", {},
                                        f"{key}: the game font has no accented letters"))
            for pos in (step.get("pos"), step.get("to")):
                if pos is not None and pos not in decomp_dialogues.POSITIONS:
                    problems.append(Problem("error", "dialogues", rid, "pos", "unknownPosition", {}, f"{key}: unknown position"))
        try:
            decomp_dialogues.render(steps)
        except (decomp_dialogues.DialogueError, KeyError, TypeError, AttributeError):
            problems.append(Problem("error", "dialogues", key, "steps", "badDialogue", {}, f"{key}: malformed dialogue"))


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
    _validate_map_objects(problems, maps_data, known_layouts, decomp_dir, sizes)


def _validate_map_objects(problems, maps_data: dict, known_layouts: dict, decomp_dir, sizes: dict):
    """New villages, chests, doors...: their used state must be known, and their texts readable."""
    painted = maps_data.get("layouts", {})
    settings = maps_data.get("objects", {})
    for layout_id, objects in settings.items():
        for key, s in objects.items():
            text = s.get("text") if isinstance(s, dict) else None
            if isinstance(text, str) and not text.isascii():
                problems.append(Problem("error", "maps", layout_id, "objects", "nameNonAscii", {"at": key},
                                        f"{layout_id} {key}: the game font has no accented letters"))
    for layout_id, layout in painted.items():
        if layout_id not in known_layouts or layout_id not in sizes:
            continue
        try:
            found = mapobjects.map_objects(decomp_dir, layout_id, layout["rows"], maps_data.get("changes", {}).get(
                layout_id, decomp_maps.read_changes(decomp_dir, known_layouts[layout_id]["changes"])
                if known_layouts[layout_id]["changes"] else []), settings.get(layout_id))
        except (IndexError, TypeError, ValueError):
            continue  # malformed rows: reported above
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
        assets = layout["assets"]
        for index in layout["chapters"]:
            groups = [g for g in groups_by_chapter.get(index, []) if g["origin"] != "cutscene"]
            if layout_id not in painted and not any(g["name"] in edited_groups for g in groups) \
                    and str(index) not in objectives_by_chapter:
                continue
            original_map = decomp_maps.read_layout(assets.layout)
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
                return terrain[m] if m < len(terrain) else 0

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
        if kind == "defeat_boss" and o.get("boss") and o["boss"] not in character_ids:
            problems.append(Problem("error", "chapters", rid, "boss", "unknownCharacter", {}, f"{rid}: unknown boss"))
        text = o.get("statusText")
        if text is not None:
            lines = text.strip().split("\n")
            if not text.strip():
                problems.append(Problem("error", "chapters", rid, "statusText", "nameEmpty", {}, f"{rid}: empty objective text"))
            elif any(ord(c) > 127 for c in text):
                problems.append(Problem("error", "chapters", rid, "statusText", "nameNonAscii", {}, f"{rid}: accented letters"))
            elif len(lines) > 2 or any(len(line) > OBJECTIVE_LINE_MAX for line in lines):
                problems.append(Problem("warning", "chapters", rid, "statusText", "objectiveTextTooLong",
                                        {"lines": 2, "max": OBJECTIVE_LINE_MAX}, f"{rid}: objective text may not fit"))


def _validate_chapters(problems, chapters, class_ids, character_ids, item_ids):
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
        if cl.get("name"):  # some engine-only classes have no name in the original game
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
        animated = decomp.animated_weapons.get(rid, [])
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
