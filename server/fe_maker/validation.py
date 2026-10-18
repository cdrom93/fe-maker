"""Live validation: catch what would break the game before compiling.

Each problem carries a translation code and parameters; the UI shows the
translated text, `message` is the English fallback.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field

from .decomp.gamedata import ABILITIES_REV, AFFINITIES_REV, GROWTHS, RANK_VALUES, STATS, WEAPON_TYPES, DecompData

NAME_MAX_LENGTH = 12  # longer names overflow the in-game name boxes


@dataclass
class Problem:
    severity: str          # "error" blocks the build, "warning" does not
    kind: str              # "characters" | "items"
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


def validate(characters: list[dict], items: list[dict], decomp: DecompData) -> list[Problem]:
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
    return problems
