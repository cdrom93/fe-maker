"""Convert characters, items and classes between the decomp and FE Maker's JSON.

Project JSON exposes player-facing fields with readable names. Every other
field of the C struct is kept untouched under "engine" so it can be written
back exactly.
"""

from __future__ import annotations

import re
from pathlib import Path

from .cparse import (
    parse_array,
    parse_designated_list,
    parse_int,
    render_array,
    render_designated_list,
)
from .texts import TextFile

CHARACTERS_FILE = "src/data_characters.c"
CLASSES_FILE = "src/data_classes.c"
ITEMS_FILE = "src/data_items.c"
TEXTS_FILE = "texts/texts.txt"
ITEM_ICONS_FILE = "data/data_item_icon.s"
BATTLE_ANIM_CONF_FILE = "src/data_banimconf.c"
BATTLE_ANIM_TABLE_FILE = "src/banim_data.c"
# Unit placements of every chapter (struct UnitDefinition arrays)
UNIT_DEF_FILES = ["src/events_udefs.c", "src/events/*-eventudefs.h"]

STATS = ["hp", "pow", "skl", "spd", "def", "res", "lck", "con"]
GROWTHS = ["hp", "pow", "skl", "spd", "def", "res", "lck"]
# JSON stat key -> suffix of the C field (baseHP, growthPow, ...)
STAT_SUFFIX = {"hp": "HP", "pow": "Pow", "skl": "Skl", "spd": "Spd", "def": "Def", "res": "Res", "lck": "Lck", "con": "Con"}

# include/bmitem.h
WEAPON_TYPES = {
    "ITYPE_SWORD": "sword", "ITYPE_LANCE": "lance", "ITYPE_AXE": "axe", "ITYPE_BOW": "bow",
    "ITYPE_STAFF": "staff", "ITYPE_ANIMA": "anima", "ITYPE_LIGHT": "light", "ITYPE_DARK": "dark",
    "ITYPE_BLLST": "ballista", "ITYPE_ITEM": "item", "ITYPE_DRAGN": "dragonstone",
    "ITYPE_MONSTER": "monster", "ITYPE_DANCE": "dance",
}
WEAPON_TYPES_REV = {v: k for k, v in WEAPON_TYPES.items()}
RANKABLE_TYPES = ["sword", "lance", "axe", "bow", "staff", "anima", "light", "dark"]

WEAPON_RANKS = {"WPN_EXP_E": "E", "WPN_EXP_D": "D", "WPN_EXP_C": "C", "WPN_EXP_B": "B", "WPN_EXP_A": "A", "WPN_EXP_S": "S"}
WEAPON_RANKS_REV = {v: k for k, v in WEAPON_RANKS.items()}
RANK_VALUES = {"E": 1, "D": 31, "C": 71, "B": 121, "A": 181, "S": 251}

# Character/class attributes (include/bmunit.h), in bit order -> readable key.
ABILITIES = {
    "CA_MOUNTEDAID": "mountedAid", "CA_CANTO": "canto", "CA_STEAL": "steal", "CA_THIEF": "thiefSkills",
    "CA_DANCE": "dance", "CA_PLAY": "play", "CA_CRITBONUS": "critBonus", "CA_BALLISTAE": "ballista",
    "CA_PROMOTED": "promoted", "CA_SUPPLY": "supply", "CA_MOUNTED": "mounted", "CA_WYVERN": "wyvern",
    "CA_PEGASUS": "pegasus", "CA_LORD": "lord", "CA_FEMALE": "female", "CA_BOSS": "boss",
    "CA_LOCK_1": "lock1", "CA_LOCK_2": "lock2", "CA_LOCK_3": "lock3", "CA_MAXLEVEL10": "maxLevel10",
    "CA_UNSELECTABLE": "unselectable", "CA_TRIANGLEATTACK_PEGASI": "triangleAttackPegasi",
    "CA_TRIANGLEATTACK_ARMORS": "triangleAttackArmors", "CA_BIT_23": "bit23",
    "CA_NEGATE_LETHALITY": "negateLethality", "CA_ASSASSIN": "lethality", "CA_MAGICSEAL": "magicSeal",
    "CA_SUMMON": "summon", "CA_LOCK_4": "lock4", "CA_LOCK_5": "lock5", "CA_LOCK_6": "lock6", "CA_LOCK_7": "lock7",
}
ABILITIES_REV = {v: k for k, v in ABILITIES.items()}

AFFINITIES = {
    "UNIT_AFFIN_FIRE": "fire", "UNIT_AFFIN_THUNDER": "thunder", "UNIT_AFFIN_WIND": "wind", "UNIT_AFFIN_ICE": "ice",
    "UNIT_AFFIN_DARK": "dark", "UNIT_AFFIN_LIGHT": "light", "UNIT_AFFIN_ANIMA": "anima",
}
AFFINITIES_REV = {v: k for k, v in AFFINITIES.items()}


def _split_flags(value: str) -> list[str]:
    return [t.strip() for t in value.split("|") if t.strip() not in ("", "0", "CA_NONE")]


def _abilities(value: str) -> list[str]:
    """'CA_BOSS | CA_FEMALE' -> ['female', 'boss'] (bit order). Unknown tokens are ignored."""
    tokens = set(_split_flags(value))
    return [key for flag, key in ABILITIES.items() if flag in tokens]


class GameDataError(Exception):
    pass


def _to_s8(value: int) -> int:
    """Some original data writes 255 in signed 8-bit fields; the game reads -1."""
    value &= 0xFF
    return value - 256 if value > 127 else value


def _int_field(fields: dict[str, str], name: str, signed: bool = False) -> int:
    value = parse_int(fields.get(name, "0"))
    return _to_s8(value) if signed else value


def _set_int(fields: dict[str, str], name: str, value: int, signed: bool = False) -> None:
    """Write an int field, keeping the original spelling when the value is unchanged."""
    if name in fields and _int_field(fields, name, signed) == value:
        return
    if name not in fields and value == 0:
        return
    fields[name] = str(int(value))


def _rank_to_json(value: str) -> str | int:
    if value in WEAPON_RANKS:
        return WEAPON_RANKS[value]
    return parse_int(value)


def _rank_to_c(value: str | int) -> str:
    if isinstance(value, str):
        if value not in WEAPON_RANKS_REV:
            raise GameDataError(f"Unknown weapon rank {value!r}")
        return WEAPON_RANKS_REV[value]
    return str(int(value))


def _rank_value(value: str | int) -> int:
    return RANK_VALUES[value] if isinstance(value, str) else int(value)


class DecompData:
    """The decomp files FE Maker reads and writes, loaded from a decomp checkout."""

    def __init__(self, decomp_dir: Path):
        self.decomp_dir = decomp_dir
        self.characters = parse_array(self._read(CHARACTERS_FILE), "gCharacterData")
        self.classes = parse_array(self._read(CLASSES_FILE), "gClassData")
        self.items = parse_array(self._read(ITEMS_FILE), "gItemData")
        self.texts = TextFile(self._read(TEXTS_FILE))
        self.unit_defs: dict[str, str] = {}
        for pattern in UNIT_DEF_FILES:
            for path in sorted(decomp_dir.glob(pattern)):
                rel = path.relative_to(decomp_dir).as_posix()
                self.unit_defs[rel] = self._read(rel)
        self._original_unit_defs = dict(self.unit_defs)
        self.animated_weapons = self._read_animated_weapons()

    def _read(self, rel: str) -> str:
        with open(self.decomp_dir / rel, encoding="utf-8", newline="") as f:
            return f.read()

    def _read_animated_weapons(self) -> dict[str, list[str]]:
        """Class id -> weapon types its battle animations cover (src/data_banimconf.c).

        A unit can wield any weapon type it has a rank in, but if its class has no
        animation for that type the battle shows a wrong animation or crashes.
        """
        path = self.decomp_dir / BATTLE_ANIM_CONF_FILE
        confs: dict[str, list[str]] = {}
        if path.is_file():
            source = self._read(BATTLE_ANIM_CONF_FILE)
            for m in re.finditer(r"struct\s+BattleAnimDef\s+(\w+)\s*\[\s*\]\s*=\s*\{(.*?)\{\s*0\s*\}", source, re.DOTALL):
                types = re.findall(r"\.wtype\s*=\s*0x0100\s*\|\s*(ITYPE_\w+)", m.group(2))
                confs[m.group(1)] = [WEAPON_TYPES[t] for t in dict.fromkeys(types) if t in WEAPON_TYPES]
        result = {}
        for entry in self.classes.entries:
            conf = entry.fields.get("pBattleAnimDef", "").lstrip("&").strip()
            result[entry.fields["number"]] = confs.get(conf, [])
        return result

    def class_genders(self) -> dict[str, str | None]:
        """Class id -> "male", "female" or None (monsters, unknown).

        The game has no gender flag on classes; it is visual. Battle animation
        names encode it in their 4th letter ("lorf_sw1" = female lord,
        "thim_sw1" = male thief), see src/banim_data.c.
        """
        conf_path, table_path = self.decomp_dir / BATTLE_ANIM_CONF_FILE, self.decomp_dir / BATTLE_ANIM_TABLE_FILE
        if not conf_path.is_file() or not table_path.is_file():
            return {}
        first_index = {
            m.group(1): int(m.group(2), 0)
            for m in re.finditer(r"struct\s+BattleAnimDef\s+(\w+)\s*\[\s*\]\s*=\s*\{\s*\{[^}]*?\.index\s*=\s*(\w+)",
                                 self._read(BATTLE_ANIM_CONF_FILE))
        }
        names = re.findall(r'^\s*\{\s*"(\w+)"', self._read(BATTLE_ANIM_TABLE_FILE), re.MULTILINE)
        result: dict[str, str | None] = {}
        for entry in self.classes.entries:
            f = entry.fields
            gender = None
            conf = f.get("pBattleAnimDef", "").lstrip("&").strip()
            index = first_index.get(conf)
            monster = "CA_LOCK_3" in f.get("attributes", "")
            if index and 0 < index <= len(names) and not monster and len(names[index - 1]) >= 4:
                gender = {"m": "male", "f": "female"}.get(names[index - 1][3])
            # Some female classes reuse the male battle animation (CLASS_HERO_F...):
            # the "_F" class id is the more reliable hint for them.
            suffix = re.search(r"_([MF])\d?$", f["number"])
            if suffix and not monster:
                gender = "female" if suffix.group(1) == "F" else "male"
            result[f["number"]] = gender
        return result

    def lock_items(self) -> dict[str, list[str]]:
        """Ability key of each weapon lock ("lock4") -> names of the items needing it."""
        result: dict[str, list[str]] = {}
        for e in self.items.entries:
            for n in re.findall(r"\bIA_LOCK_(\d)\b", e.fields.get("attributes", "")):
                result.setdefault(f"lock{n}", []).append(self._text_name(e.fields))
        return result

    def item_locks(self) -> dict[str, dict[str, list[str]]]:
        """Item id -> who can wield it despite its weapon locks.

        CanUnitUseWeapon (src/bmitem.c) requires, for each IA_LOCK_n of the item,
        the flag CA_LOCK_n on the unit, i.e. on its character or its class.
        Items without locks are left out. Lists hold ids (characters, classes).
        """
        def locks(attributes: str, prefix: str) -> set[str]:
            return set(re.findall(rf"\b{prefix}_LOCK_(\d)\b", attributes))

        class_locks = {e.fields["number"]: locks(e.fields.get("attributes", ""), "CA") for e in self.classes.entries}
        char_locks = {e.fields["number"]: locks(e.fields.get("attributes", ""), "CA") for e in self.characters.entries}
        result = {}
        for e in self.items.entries:
            needed = locks(e.fields.get("attributes", ""), "IA")
            if not needed:
                continue
            result[e.fields["number"]] = {
                "classes": [c for c, have in class_locks.items() if needed <= have],
                "characters": [c for c, have in char_locks.items() if needed <= have],
            }
        return result

    def classes_used_in_game(self) -> set[str]:
        """Classes the original game actually uses (units, characters and their promotions).
        The others are leftovers whose graphics and animations may be incomplete."""
        used = set()
        for source in self._original_unit_defs.values():
            used |= set(re.findall(r"\.classIndex\s*=\s*(CLASS_\w+)", source))
        used |= {e.original_fields.get("defaultClass", "") for e in self.characters.entries}
        for e in self.classes.entries:
            if e.fields["number"] in used and e.fields.get("promotion"):
                used.add(e.fields["promotion"])
        return used

    def _retarget_unit_class(self, character: str, old_class: str, new_class: str) -> None:
        """Give a character its new class in every chapter where it had the old one."""
        pattern = re.compile(
            rf"(\.charIndex\s*=\s*{re.escape(character)}\s*,\s*\.classIndex\s*=\s*){re.escape(old_class)}\b"
        )
        for rel, source in self.unit_defs.items():
            self.unit_defs[rel] = pattern.sub(lambda m: m.group(1) + new_class, source)

    # ---------- import (decomp -> project JSON) ----------

    def _text_name(self, fields: dict[str, str]) -> str:
        return self.texts.get_name(_int_field(fields, "nameTextId"))

    def export_classes(self) -> list[dict]:
        """Read-only class list (class editing comes in phase 2)."""
        used = self.classes_used_in_game()
        genders = self.class_genders()
        return [
            {
                "id": f["number"],
                "name": self._text_name(f),
                "bases": {s: _int_field(f, "base" + STAT_SUFFIX[s]) for s in STATS if s != "lck"} | {"lck": 0},
                "mov": _int_field(f, "baseMov"),
                "abilities": _abilities(f.get("attributes", "0")),
                "animatedWeapons": self.animated_weapons.get(f["number"], []),
                "usedInGame": f["number"] in used,
                "gender": genders.get(f["number"]),
            }
            for f in (e.fields for e in self.classes.entries)
        ]

    def export_characters(self) -> list[dict]:
        result = []
        for entry in self.characters.entries:
            f = entry.fields
            ranks = parse_designated_list(f.get("baseRanks", "{ }"))
            result.append({
                "id": f["number"],
                "name": self._text_name(f),
                "class": f["defaultClass"],
                "level": _int_field(f, "baseLevel"),
                "portraitId": _int_field(f, "portraitId"),
                "bases": {s: _int_field(f, "base" + STAT_SUFFIX[s], signed=True) for s in STATS},
                "growths": {s: _int_field(f, "growth" + STAT_SUFFIX[s]) for s in GROWTHS},
                "weaponRanks": {WEAPON_TYPES[k]: _rank_to_json(v) for k, v in ranks.items()},
                "affinity": AFFINITIES.get(f.get("affinity", "0")),
                "abilities": _abilities(f.get("attributes", "0")),
            })
        return result

    def export_items(self) -> list[dict]:
        result = []
        for entry in self.items.entries:
            f = entry.fields
            if f.get("number") == "ITEM_NONE":
                continue
            rng = _int_field(f, "encodedRange")
            rank = f.get("weaponRank", "0")
            result.append({
                "id": f["number"],
                "name": self._text_name(f),
                "weaponType": WEAPON_TYPES.get(f.get("weaponType", "ITYPE_SWORD"), f.get("weaponType")),
                "might": _int_field(f, "might"),
                "hit": _int_field(f, "hit"),
                "crit": _int_field(f, "crit"),
                "weight": _int_field(f, "weight"),
                "range": {"min": rng >> 4, "max": rng & 0xF},
                "uses": _int_field(f, "maxUses"),
                "pricePerUse": _int_field(f, "costPerUse"),
                "weaponRank": _rank_to_json(rank) if rank in WEAPON_RANKS else parse_int(rank),
                "iconId": _int_field(f, "iconId"),
            })
        return result

    # ---------- export (project JSON -> decomp files) ----------

    def apply_characters(self, characters: list[dict]) -> None:
        entries = {e.fields["number"]: e for e in self.characters.entries}
        for ch in characters:
            entry = entries.get(ch["id"])
            if entry is None:
                raise GameDataError(f"Unknown character {ch['id']}")
            f = entry.fields
            self.texts.set_name(_int_field(f, "nameTextId"), ch["name"])
            if f["defaultClass"] != ch["class"]:
                original_class = entry.original_fields["defaultClass"]
                # In game, chapters load units with an explicit class: defaultClass alone
                # only matters when a chapter leaves it out. Retarget the chapters too.
                self._retarget_unit_class(ch["id"], original_class, ch["class"])
                f["defaultClass"] = ch["class"]
            _set_int(f, "baseLevel", ch["level"])
            _set_int(f, "portraitId", ch["portraitId"])
            # Fields added after a project was created may be missing: leave them as they are.
            if "affinity" in ch:
                self._apply_affinity(f, ch["affinity"])
            if "abilities" in ch:
                self._apply_abilities(f, ch["abilities"])
            for s in STATS:
                _set_int(f, "base" + STAT_SUFFIX[s], ch["bases"][s], signed=True)
            for s in GROWTHS:
                _set_int(f, "growth" + STAT_SUFFIX[s], ch["growths"][s])

            old = parse_designated_list(f.get("baseRanks", "{ }"))
            new = {WEAPON_TYPES_REV[t]: r for t, r in ch["weaponRanks"].items() if r not in (0, "", None)}
            old_values = {k: _rank_value(_rank_to_json(v)) for k, v in old.items()}
            new_values = {k: _rank_value(v) for k, v in new.items()}
            if old_values != new_values:
                f["baseRanks"] = render_designated_list({k: _rank_to_c(v) for k, v in new.items()})

    @staticmethod
    def _apply_affinity(f: dict[str, str], affinity: str | None) -> None:
        if AFFINITIES.get(f.get("affinity", "0")) == affinity:
            return
        if affinity is None:
            if "affinity" in f:
                f["affinity"] = "0"
            return
        if affinity not in AFFINITIES_REV:
            raise GameDataError(f"Unknown affinity {affinity!r}")
        f["affinity"] = AFFINITIES_REV[affinity]

    @staticmethod
    def _apply_abilities(f: dict[str, str], abilities: list[str]) -> None:
        current = f.get("attributes", "0")
        if set(_abilities(current)) == set(abilities):
            return
        unknown = [a for a in abilities if a not in ABILITIES_REV]
        if unknown:
            raise GameDataError(f"Unknown abilities {unknown}")
        # Keep tokens FE Maker does not know (raw numbers...), then known flags in bit order.
        kept = [t for t in _split_flags(current) if t not in ABILITIES]
        flags = kept + [flag for flag, key in ABILITIES.items() if key in abilities]
        f["attributes"] = " | ".join(flags) if flags else "0"

    def apply_items(self, items: list[dict]) -> None:
        entries = {e.fields["number"]: e for e in self.items.entries}
        for it in items:
            entry = entries.get(it["id"])
            if entry is None:
                raise GameDataError(f"Unknown item {it['id']}")
            f = entry.fields
            self.texts.set_name(_int_field(f, "nameTextId"), it["name"])
            wtype = WEAPON_TYPES_REV.get(it["weaponType"], it["weaponType"])
            if f.get("weaponType") != wtype:
                f["weaponType"] = wtype
            for key, field in (("might", "might"), ("hit", "hit"), ("crit", "crit"), ("weight", "weight"),
                               ("uses", "maxUses"), ("pricePerUse", "costPerUse"), ("iconId", "iconId")):
                _set_int(f, field, it[key])
            _set_int(f, "encodedRange", (it["range"]["min"] << 4) | it["range"]["max"])
            rank = it["weaponRank"]
            current = f.get("weaponRank", "0")
            if _rank_value(rank if isinstance(rank, (str, int)) else 0) != _rank_value(
                _rank_to_json(current) if current in WEAPON_RANKS else parse_int(current)
            ):
                f["weaponRank"] = _rank_to_c(rank)

    def changed_files(self) -> dict[str, str]:
        """Decomp-relative path -> new content, for files that differ from the decomp."""
        out = {}
        for rel, parsed in ((CHARACTERS_FILE, self.characters), (ITEMS_FILE, self.items)):
            if any(e.fields != e.original_fields for e in parsed.entries):
                out[rel] = render_array(parsed)
        if self.texts.edits:
            out[TEXTS_FILE] = self.texts.render()
        for rel, source in self.unit_defs.items():
            if source != self._original_unit_defs[rel]:
                out[rel] = source
        return out

    # ---------- assets ----------

    def item_icon_files(self) -> list[str]:
        """Icon PNG paths (decomp-relative), indexed by iconId."""
        source = self._read(ITEM_ICONS_FILE)
        return [m.replace(".4bpp", ".png") for m in re.findall(r'\.incbin\s+"([^"]+\.4bpp)"', source)]
