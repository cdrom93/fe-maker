"""Live validation: catch what would break the game before compiling.

Each problem carries a translation code and parameters; the UI shows the
translated text, `message` is the English fallback.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field

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
OBJECTIVE_LINE_MAX = 22  # longest line of the original status texts ("Defeat Fomortiis, the" = 21)


@dataclass
class Problem:
    severity: str          # "error" blocks the build, "warning" does not
    kind: str              # "characters" | "items" | "classes" | "combat" | "chapters"
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
             chapters: dict | None = None) -> list[Problem]:
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
    return problems


def _validate_objectives(problems, objectives_by_chapter: dict):
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
    _validate_objectives(problems, chapters.get("objectives", {}))
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
            if unit.get("class") not in class_ids:
                problems.append(Problem("error", "chapters", rid, "class", "unknownClass", {}, f"{rid}: unknown class"))
            _range(problems, "chapters", rid, "level", unit.get("level"), 0, 31)  # 5-bit field
            _range(problems, "chapters", rid, "endX", unit.get("endX"), 0, 63)  # 6-bit fields
            _range(problems, "chapters", rid, "endY", unit.get("endY"), 0, 63)
            ai = unit.get("ai")
            if isinstance(ai, list):
                # Indexes into gAi1ScriptTable, gAi2ScriptTable and gAI3HealingThresholdTable (src/cp_data.c).
                if len(ai) != 4 or ai[0] > AI_ACTION_MAX or ai[1] > AI_MOVE_MAX or ai[2] & 0x7 > AI_RECOVERY_MAX or ai[3] > 255:
                    problems.append(Problem("error", "chapters", rid, "ai", "badAi", {}, f"{rid}: AI value outside the engine tables"))
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
        if not res:
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
