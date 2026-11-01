"""Convert characters, items and classes between the decomp and FE Maker's JSON.

Project JSON exposes player-facing fields with readable names. Every other
field of the C struct is kept untouched under "engine" so it can be written
back exactly.
"""

from __future__ import annotations

import json
import re
from collections import Counter
from pathlib import Path

from . import (
    banim,
    banim_import,
    chapterflags,
    chaptitle,
    charpalettes,
    combat,
    convoy,
    danceanim,
    dialogues,
    events,
    fonts,
    mapobjects,
    maps,
    mapsprites,
    music,
    objectives,
    portraits,
    prep,
    quotes,
    seize,
    story,
    supports,
    tileedit,
    units,
    unitstats,
    weaponrange,
)
from .cparse import (
    Entry,
    parse_array,
    parse_designated_list,
    parse_int,
    render_array,
    render_designated_list,
)
from .texts import TextFile, name_message, textdefs_with

CHARACTERS_FILE = "src/data_characters.c"
CLASSES_FILE = "src/data_classes.c"
ITEMS_FILE = "src/data_items.c"
TEXTS_FILE = "texts/texts.txt"
ITEM_ICONS_FILE = "data/data_item_icon.s"
BATTLE_ANIM_CONF_FILE = "src/data_banimconf.c"
BATTLE_ANIM_TABLE_FILE = "src/banim_data.c"
CHARACTER_CONSTANTS_FILE = "include/constants/characters.h"
# A character the project adds takes a free entry of the table (the game's are numbered 1-0xFF, no room
# to grow): "CHARACTER_NEW_1B" is entry 0x1B, given that constant in characters.h at build time.
NEW_CHARACTER_PREFIX = "CHARACTER_NEW_"
# BWL_ARRAY_NUM (include/bmsave.h): only characters below it keep their battle stats in the save
# (epilogue, support points): playable characters take a number below it.
ALLY_CHARACTER_END = 0x46
GENERIC_CHARACTER_START = 0x80   # the named characters end here
# Named in the decomp, generic in use: chapters of any project can use them, the list folds them with the generics.
NAMED_GENERICS = ("CHARACTER_SOLDIER_83", "CHARACTER_MONSTER_BA", "CHARACTER_CITIZEN")
ITEM_CONSTANTS_FILE = "include/constants/items.h"
SPELL_ASSOC_FILE = "src/spellassoc-data.c"
ITEM_BONUS_FILE = "src/data_itembonus.c"
# An item the project adds is a weapon after the game's table, copying a model weapon (its spell and its own
# battle animations, chosen by item number). Item numbers are one byte; 0xFF is left out.
NEW_ITEM_PREFIX = "ITEM_NEW_"
LAST_ITEM_NUMBER = 0xFE
CLASS_CONSTANTS_FILE = "include/constants/classes.h"
MOVING_SPRITES_FILE = "src/unit_icon_move_data.c"
# Levels the game adds to or takes from a chapter's enemies, by difficulty (chapter settings, 4 bits each)
LEVEL_BONUS_FIELDS = {"easy": "easyModeLevelMalus", "normal": "normalModeLevelMalus", "hard": "difficultModeLevelBonus"}


def _set_level_bonus(settings: list[dict], edits: dict) -> None:
    for index, bonus in edits.items():
        for mode, field in LEVEL_BONUS_FIELDS.items():
            if mode in bonus:
                settings[int(index)][field] = max(0, min(int(bonus[mode]), 15))


# A class the project adds copies a model class (stats, battle animations, map sprites, promotions), numbered
# from 0x80 after the game's classes. unit_icon_move_table has one row per class, in order: new classes follow.
NEW_CLASS_PREFIX = "CLASS_NEW_"
FIRST_NEW_CLASS, LAST_NEW_CLASS = 0x80, 0xFE
# Unit placements of every chapter (struct UnitDefinition arrays)
UNIT_DEF_FILES = ["src/events_udefs.c", "src/events/*-eventudefs.h"]
# Chapter event groups and their event lists (objectives); unit definition files excluded.
EVENT_INFO_FILES = ["src/events/*.h", "src/events_info.c"]

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
# Attributes the sheet shows as boxes. IA_WEAPON and IA_STAFF follow the item's type; the weapon locks are its "reserved for".
ITEM_PROPERTIES = {
    "IA_MAGIC": "magic", "IA_MAGICDAMAGE": "magicSword", "IA_UNBREAKABLE": "unbreakable", "IA_UNSELLABLE": "unsellable",
    "IA_BRAVE": "brave", "IA_UNCOUNTERABLE": "uncounterable", "IA_REVERTTRIANGLE": "reverseTriangle",
    "IA_NEGATE_DEFENSE": "negateDefense", "IA_NEGATE_FLYING": "negateFlying", "IA_NEGATE_CRIT": "negateCrit",
    "IA_HAMMERNE": "noRepair",
}
WEAPON_EFFECTS = {"WPN_EFFECT_POISON": "poison", "WPN_EFFECT_HPDRAIN": "drain", "WPN_EFFECT_HPHALVE": "halve",
                  "WPN_EFFECT_DEVIL": "devil", "WPN_EFFECT_PETRIFY": "petrify"}
WEAPON_EFFECTS_REV = {v: k for k, v in WEAPON_EFFECTS.items()}
ITEM_BONUS_STATS = ("hp", "pow", "skl", "spd", "def", "res", "lck", "mov", "con")
NEW_BONUS_PREFIX = "ItemBonus_FEM_"
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
# Weapon locks FE Maker assigns itself from the items' "reserved for" lists. Lock 3 is not one of
# them: the engine treats it as "monster weapon" (no rank needed, unbreakable...).
GENERIC_LOCKS = ["1", "2", "4", "5", "6", "7"]
GENERIC_LOCK_KEYS = {f"lock{n}" for n in GENERIC_LOCKS}
# Locks the original game does not use first, when a new reservation needs a free lock.
LOCK_PREFERENCE = ["7", "1", "6", "5", "2", "4"]

AFFINITIES = {
    "UNIT_AFFIN_FIRE": "fire", "UNIT_AFFIN_THUNDER": "thunder", "UNIT_AFFIN_WIND": "wind", "UNIT_AFFIN_ICE": "ice",
    "UNIT_AFFIN_DARK": "dark", "UNIT_AFFIN_LIGHT": "light", "UNIT_AFFIN_ANIMA": "anima",
}
AFFINITIES_REV = {v: k for k, v in AFFINITIES.items()}


CLASS_STATS = ["hp", "pow", "skl", "spd", "def", "res", "con"]  # classes have no base/max luck
PROMO_STATS = ["hp", "pow", "skl", "spd", "def", "res"]
PROMO_SUFFIX = {"hp": "Hp", "pow": "Pow", "skl": "Skl", "spd": "Spd", "def": "Def", "res": "Res"}


def _effectiveness_name(value: str) -> str | None:
    """'ItemEffectiveness_Horse' -> same; NULL / 0 / missing -> None."""
    value = value.strip().lstrip("&")
    return value if value.startswith("ItemEffectiveness_") else None


def _movement_group(value: str) -> str | None:
    """'{ TerrainTable_MovCost_HorseT2Normal, ... }' -> 'HorseT2'."""
    m = re.search(r"TerrainTable_MovCost_(\w+?)(?:Normal|Rain|Snow)?\b", value)
    return m.group(1) if m else None


def _movement_tables(group: str) -> str:
    # One family (DemonKing) has a single table used for every weather.
    if group == "DemonKing":
        names = [f"TerrainTable_MovCost_{group}"] * 3
    else:
        names = [f"TerrainTable_MovCost_{group}{weather}" for weather in ("Normal", "Rain", "Snow")]
    return "{ " + " ".join(f"{n}," for n in names) + " }"


def _terrain_group(value: str) -> str | None:
    """'TerrainTable_Avo_Fly' -> 'Fly'."""
    m = re.search(r"TerrainTable_Avo_(\w+)", value)
    return m.group(1) if m else None


def _split_flags(value: str) -> list[str]:
    return [t.strip() for t in value.split("|") if t.strip() not in ("", "0", "CA_NONE")]


def _set_flags(fields: dict[str, str], wanted: list[str], managed: tuple[str, ...]) -> None:
    """Attributes: among the `managed` flags keep only the `wanted` ones, the others as they are."""
    tokens = _split_flags(fields.get("attributes", "0"))
    flags = [t for t in tokens if t not in managed or t in wanted] + [t for t in wanted if t not in tokens]
    if flags != tokens:
        fields["attributes"] = " | ".join(flags) or "0"


def _type_flags(weapon_type: str) -> list[str]:
    """What the engine asks of an item of this type: it can be equipped, or used as a staff."""
    if weapon_type == "staff":
        return ["IA_STAFF"]
    return [] if weapon_type in ("item", "dance") else ["IA_WEAPON"]


def _read_item_bonuses(source: str) -> dict[str, dict[str, int]]:
    """Name of each ItemStatBonuses -> its stats ('hp': 7)."""
    return {name: {stat.lower(): _to_s8(parse_int(value)) for stat, value in re.findall(r"\.(\w+)Bonus\s*=\s*(-?\w+)", body)}
            for name, body in re.findall(r"\b(ItemBonus_\w+)\s*=\s*\{(.*?)\};", source, re.DOTALL)}


def _abilities(value: str) -> list[str]:
    """'CA_BOSS | CA_FEMALE' -> ['female', 'boss'] (bit order). Unknown tokens are ignored."""
    tokens = set(_split_flags(value))
    return [key for flag, key in ABILITIES.items() if flag in tokens and key not in GENERIC_LOCK_KEYS]


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
        bonuses = self.decomp_dir / ITEM_BONUS_FILE
        self.item_bonuses = _read_item_bonuses(bonuses.read_text(encoding="utf-8")) if bonuses.is_file() else {}
        self.spell_choices: dict[str, str] = {}   # item -> the item whose spell it takes
        self.texts = TextFile(self._read(TEXTS_FILE))
        self.unit_defs: dict[str, str] = {}
        for pattern in UNIT_DEF_FILES:
            for path in sorted(decomp_dir.glob(pattern)):
                rel = path.relative_to(decomp_dir).as_posix()
                self.unit_defs[rel] = self._read(rel)
        self._original_unit_defs = dict(self.unit_defs)
        # Imported graphics (decomp-relative path -> content), see apply_portraits
        self.asset_files: dict[str, bytes | str] = {}
        # Who opens the convoy and the chapters without it, when the project changes them (convoy.py)
        self.convoy_openers: list[str] | None = None
        # Characters given another portrait (original id -> new id) and every character's portrait:
        # their dialogues follow the new portrait (ticket 36, _follow_portraits)
        self.portrait_moves: dict[int, int] = {}
        self.character_portraits: dict[str, int] = {}
        # Who can seize, when the project changes it (seize.py)
        self.first_new_palette: int | None = None   # charpalettes.py
        self.seizers: list[str] | None = None
        self.other_ranges = False   # a weapon has a range the game does not list (weaponrange.py)
        self._new_quote_flags = False  # quotes numbered past the game's chapter flags (chapterflags.py)
        self.other_dancers = False  # a class or character without a dancer's sprite dances (danceanim.py)
        self.no_convoy: list[int] | None = None
        # Ids of the portraits the project adds (their text codes go to textdefs.txt)
        self.new_faces: list[int] = []
        # Supports edited in the project (see _apply_supports)
        self.support_source: str | None = None
        self.support_talks: str | None = None
        self.new_support_blocks: list[str] = []
        self.new_anim_confs: list[str] = []   # AnimConf arrays FE Maker adds (declared in data_classes.c)
        self.new_characters: dict[str, int] = {}   # characters the project adds -> their number
        self.new_items: dict[str, tuple[int, str]] = {}   # weapons the project adds -> their number, model
        self.new_classes: dict[str, tuple[int, str]] = {}   # classes the project adds -> their number, model
        # Map sprites imported for classes (mapsprites.py): class id -> {"key", "move"}; key -> (number, table row)
        self.map_sprites: dict[str, dict] = {}
        self.map_sprite_ids: dict[str, tuple[int, str]] = {}
        # Map layouts painted in the project (decomp-relative path -> .mar bytes or .json text)
        self.map_files: dict[str, bytes | str] = {}
        # Chapter settings and events, loaded on first use (objectives).
        self.chapter_settings: dict | None = None
        self.event_sources: dict[str, str] = {}
        self._original_event_sources: dict[str, str] = {}
        self._settings_raw = ''
        self.animated_weapons = self._read_animated_weapons()
        # Combat tables (optional: absent from minimal test decomps)
        self._sources: dict[str, str] = {}
        for rel in (combat.PROMOTIONS_FILE, combat.EFFECTIVENESS_FILE, combat.TRIANGLE_FILE):
            if (decomp_dir / rel).is_file():
                self._sources[rel] = self._read(rel)
        self.promotions = combat.parse_promotions(self._sources[combat.PROMOTIONS_FILE]) \
            if combat.PROMOTIONS_FILE in self._sources else None
        self._original_promotions = {k: list(v) for k, v in (self.promotions or {}).items()}
        self.effectiveness = combat.parse_effectiveness(self._sources[combat.EFFECTIVENESS_FILE]) \
            if combat.EFFECTIVENESS_FILE in self._sources else None
        self._original_effectiveness = {k: list(v) for k, v in (self.effectiveness or {}).items()}
        self.triangle = combat.parse_triangle(self._sources[combat.TRIANGLE_FILE]) \
            if combat.TRIANGLE_FILE in self._sources else None
        self._original_triangle = [dict(r) for r in (self.triangle or [])]

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
        # Follow promotions transitively: the promotion table (with branches) and the
        # class's own promotion field.
        promotions = {k: list(v) for k, v in self._original_promotions.items()}
        for e in self.classes.entries:
            if e.original_fields.get("promotion"):
                promotions.setdefault(e.fields["number"], []).append(e.original_fields["promotion"])
        todo = list(used)
        while todo:
            for nxt in promotions.get(todo.pop(), []):
                if nxt not in used:
                    used.add(nxt)
                    todo.append(nxt)
        return used

    # ---------- combat tables ----------

    def export_combat(self) -> dict:
        return {
            "triangle": [
                {"attacker": WEAPON_TYPES[r["attacker"]], "defender": WEAPON_TYPES[r["defender"]],
                 "hit": r["hit"], "damage": r["damage"]}
                for r in (self.triangle or [])
            ],
            "effectiveness": {name: list(classes) for name, classes in (self.effectiveness or {}).items()},
        }

    # ---------- chapters ----------

    @staticmethod
    def export_chapters() -> dict:
        """Project chapter data. Unit groups and objectives (by chapter index) are stored
        only once edited (see units.py and objectives.py). New groups (reinforcements):
        "newGroups" {name: {"chapter", "turn", "phase"}}, their units in "unitGroups".
        "convoy" {chapter index: bool}: convoy available, once changed (convoy.py).
        "fog" {chapter index: vision range}: fog of war (0: none), once changed.
        "wallHp" {chapter index: HP}: cracked walls' HP, once changed."""
        return {"unitGroups": {}, "objectives": {}}

    def _with_sheet_levels(self, chapters: dict) -> dict:
        """A named ally has the level of their sheet: when the project added the unit, or changed the sheet (then in every
        group, edited or not; the game's units keep theirs otherwise). Units that level up by themselves are left alone."""
        sheets = {e.fields["number"]: (_int_field(e.fields, "baseLevel"), _int_field(e.original_fields, "baseLevel"))
                  for e in self.characters.entries}
        changed = {character for character, (now, game) in sheets.items() if now != game}

        def level(unit: dict) -> int | None:
            character = unit.get("character", "")
            if unit.get("side") != "player" or not units.is_named_character(character) or character not in sheets \
                    or unit.get("autolevel") or (unit.get("slot") is not None and character not in changed):
                return None
            return min(sheets[character][0], units.MAX_LEVEL)

        groups = dict(chapters.get("unitGroups", {}))
        if changed:
            for name, group in units.read_unit_groups(self.decomp_dir).items():
                if name not in groups and any(u.get("character") in changed for u in group.units):
                    groups[name] = group.units
        fixed = {name: [u if (n := level(u)) is None else {**u, "level": n} for u in group] for name, group in groups.items()}
        return {**chapters, "unitGroups": fixed} if fixed else chapters

    def apply_chapters(self, chapters: dict) -> None:
        chapters = self._with_sheet_levels(chapters)
        new_groups = chapters.get("newGroups", {})
        edits = {k: v for k, v in chapters.get("unitGroups", {}).items() if k not in new_groups}
        if edits:
            self.unit_defs = units.apply_unit_groups(self.unit_defs, edits, units.ai_macros(self.decomp_dir))
        for index, objective in chapters.get("objectives", {}).items():
            self.apply_objective(int(index), objective)
        for index in chapters.get("cleared", []):   # chapters the project cleared (newchapter.py)
            self._load_chapter_events()
            self.event_sources = objectives.clear_events(
                self.event_sources, self._chapter_event_symbol(self.chapter_settings["chapters"][index]))
        # After the clearing, which would take their events away
        for name, meta in new_groups.items():
            group_units = chapters.get("unitGroups", {}).get(name, [])
            if group_units:
                self._add_reinforcements(name, meta, group_units)
        self._apply_group_turns(chapters)
        # Fog of war: the units' vision range, 0 for none (chapter settings' initialFogLevel, ticket 43)
        fog = {int(k): int(v) for k, v in chapters.get("fog", {}).items()}
        if fog:
            self._load_chapter_events()
            for index, level in fog.items():
                self.chapter_settings["chapters"][index]["initialFogLevel"] = max(0, min(level, 15))
        # Cracked walls' HP (chapter settings' mapCrackedWallHeath, ticket 111)
        wall_hp = {int(k): int(v) for k, v in chapters.get("wallHp", {}).items()}
        if wall_hp:
            self._load_chapter_events()
            for index, hp in wall_hp.items():
                self.chapter_settings["chapters"][index]["mapCrackedWallHeath"] = max(1, min(hp, 127))
        if chapters.get("levelBonus"):
            self._load_chapter_events()
            _set_level_bonus(self.chapter_settings["chapters"], chapters["levelBonus"])
        # Titles of the chapters the project adds (newchapter.py): a text of their own, the slot's may be shared
        titles = {int(k): str(v) for k, v in chapters.get("titles", {}).items()}
        if titles:
            self._load_chapter_events()
            settings = self.chapter_settings["chapters"]
            for index, title in titles.items():
                text = name_message(title)
                for key in ("chapTitleTextId", "chapTitleTextIdInHectorStory"):
                    current = settings[index].get(key, 0)
                    if current and sum(1 for c in settings if key in c and c[key] == current) == 1:
                        self.texts.set_raw(current, text)
                    else:
                        settings[index][key] = self.texts.add(text)
            self._add_title_images(titles)
        # Chapters with or without convoy, when that differs from the game's rule (tickets 29, 106)
        edited = {int(k): bool(v) for k, v in chapters.get("convoy", {}).items()}
        if chapters.get("blank") or chapters.get("added") or any(convoy.has_convoy(k) != v for k, v in edited.items()):
            indexes = range(len(maps.chapter_settings(self.decomp_dir)))
            without = [i for i in indexes if not edited.get(i, convoy.has_convoy(i, chapters))]
            if without != [i for i in indexes if not convoy.has_convoy(i)]:
                self.no_convoy = without

    def _add_title_images(self, titles: dict[int, str]) -> None:
        """The title strip of each chapter the project adds, drawn from its text (chaptitle.py), after the game's."""
        if not (self.decomp_dir / chaptitle.TABLE_FILE).is_file():
            return
        table, data = self._read(chaptitle.TABLE_FILE), self._read(chaptitle.DATA_FILE)
        pointers = self._read(chaptitle.POINTERS_FILE)
        template = self.decomp_dir / chaptitle.TITLE_FILE.format(n=0)
        game_titles = {}
        for chapter in self.chapter_settings["chapters"]:
            text = chapter.get("chapTitleTextId", 0)
            if text in self.texts.messages:
                game_titles.setdefault(chapter.get("chapTitleId", 0), self.texts.get_name(text))
        rows = ""
        for number, (index, title) in enumerate(sorted(titles.items()), chaptitle.FIRST_NEW_ID):
            if number > chaptitle.LAST_NEW_ID:
                raise GameDataError("Too many chapter titles")
            name = f"chap_title_fem_{number}"
            picture = chaptitle.strip(self.decomp_dir, title, template, game_titles)
            self.asset_files[f"graphics/chap_title/{name}.png"] = picture
            rows += f"\t{{{name}, 0, 0}}, // {number}\n"
            data = (data.rstrip("\n") + f"\n\t.global {name}\n{name}:\n"
                    f"\t.incbin \"graphics/chap_title/{name}.4bpp.lz\"\n\t.align 2, 0\n")
            pointers = pointers.rstrip("\n") + f"\nextern char {name}[];\n"
            for key in ("chapTitleId", "chapTitleIdInHectorStory"):
                self.chapter_settings["chapters"][index][key] = number
        close = table.rindex("};")
        self.asset_files[chaptitle.TABLE_FILE] = table[:close] + rows + table[close:]
        self.asset_files[chaptitle.DATA_FILE] = data
        self.asset_files[chaptitle.POINTERS_FILE] = pointers

    # ---------- maps ----------

    @staticmethod
    def export_maps() -> dict:
        """Project map data: layouts, map change sets and object settings (by layout id) are stored
        only once edited. Objects: "x,y" of the object's first cell -> what a chest holds, what a
        village or house says (see mapobjects.py)."""
        return {"layouts": {}, "changes": {}, "objects": {}}

    def apply_maps(self, maps_data: dict) -> None:
        """Painted layouts, edited change sets, and what new objects need: a change putting them in
        their used state (open chest, closed village...) and their location event."""
        painted = maps_data.get("layouts", {})
        changes = maps_data.get("changes", {})
        settings = maps_data.get("objects", {})
        tilesets = maps_data.get("tilesets", {})
        palettes = maps_data.get("palettes", {})
        bases = maps_data.get("bases", {})
        offsets = maps_data.get("offsets", {})
        colors = maps_data.get("paletteColors", {})
        if not painted and not changes and not settings and not tilesets and not palettes and not bases and not colors:
            return
        # Retouched colors of the game's map palettes, for every chapter using them.
        for symbol, edited in colors.items():
            path = maps.asset_files(self.decomp_dir).get(symbol)
            if path and edited:
                self.map_files[path.relative_to(self.decomp_dir).as_posix()] = maps.edited_palette(path, edited)
        known = maps.layouts(self.decomp_dir)
        # The game's entry paths may not exist on another map: its units appear at their places (ticket 108).
        for layout_id in (set(painted) | set(bases)) & set(known):
            for chapter in known[layout_id]["chapters"]:
                for group in self._chapter_groups(chapter):
                    if any(f"{group}[]" in source for source in self.unit_defs.values()):
                        self.unit_defs = units.place_at_destination(self.unit_defs, group)
        # Another tile sheet of the game, for every chapter on the layout (ticket 21).
        for layout_id, symbol in bases.items():
            base = maps.base_of(self.decomp_dir, symbol)
            if layout_id not in known or base is None:
                continue
            self._load_chapter_events()
            for chapter in known[layout_id]["chapters"]:
                self.chapter_settings["chapters"][chapter]["map"].update(base["map"])
        # Another palette of the tileset, for every chapter on the layout (ticket 16).
        for layout_id, symbol in palettes.items():
            if layout_id not in known or not symbol:
                continue
            assets = maps.with_base(self.decomp_dir, known[layout_id]["assets"], bases.get(layout_id))
            if symbol not in {p["id"] for p in maps.palette_choices(self.decomp_dir, assets)}:
                raise GameDataError(f"{layout_id}: palette {symbol} does not go with its tileset")
            self._load_chapter_events()
            index = maps.asset_table(self.decomp_dir).index(symbol)
            for chapter in known[layout_id]["chapters"]:
                self.chapter_settings["chapters"][chapter]["map"]["paletteId"] = index
        # Mirrored and turned tiles added to tilesets: their terrains count for the objects below.
        terrains: dict[str, bytes] = {}
        for config_name, edits in tilesets.items():
            layout_id = tileedit.layout_for(self.decomp_dir, config_name)
            if layout_id and edits:
                tileset = tileedit.Tileset(self.decomp_dir, layout_id, edits)
                self.map_files.update(tileset.files())
                terrains[config_name] = bytes(tileset.terrain)
        map_change_source = original_source = None  # read when a change set is written
        for layout_id in sorted(set(painted) | set(changes) | set(settings) | set(bases)):
            if layout_id not in known:
                continue
            json_rel = known[layout_id]["changes"]
            rows = painted[layout_id]["rows"] if layout_id in painted else self._original_rows(layout_id)
            change_list = changes.get(layout_id)
            explicit = change_list if change_list is not None else (
                maps.read_changes(self.decomp_dir, json_rel) if json_rel else [])
            assets = maps.with_base(self.decomp_dir, known[layout_id]["assets"], bases.get(layout_id))
            terrain = terrains.get(assets.config.stem)
            if terrain is None and assets.config != known[layout_id]["assets"].config:
                terrain = maps.read_config(assets.config)[1]
            offset = tuple(offsets.get(layout_id, (0, 0)))
            objects = mapobjects.map_objects(self.decomp_dir, layout_id, rows, explicit, settings.get(layout_id),
                                             terrain, assets, offset)
            autos = [o["auto"] for o in objects if o["auto"]]
            # Ruined villages first: the engine takes the last change holding a cell, and a gate's
            # last one must stay its closed village (mapobjects.ruin_change).
            ruins = [o["ruin"] for o in objects if o.get("ruin")]
            written = ruins + list(explicit) + autos
            if written or (json_rel and change_list is not None):
                if map_change_source is None:
                    map_change_source = original_source = self._read(maps.MAP_CHANGE_FILE)
                if not json_rel:
                    json_rel, map_change_source = maps.add_change_set(layout_id, map_change_source)
                    table = self.map_files.get(maps.ASSET_TABLE_FILE) or self._read(maps.ASSET_TABLE_FILE)
                    index, self.map_files[maps.ASSET_TABLE_FILE] = maps.add_asset(table, Path(json_rel).stem)
                    self._load_chapter_events()
                    for chapter in known[layout_id]["chapters"]:
                        self.chapter_settings["chapters"][chapter]["map"]["changeLayerId"] = index
                files, map_change_source = maps.write_changes(self.decomp_dir, json_rel, written, map_change_source)
                self.map_files.update(files)
            self._apply_map_events(layout_id, rows, objects, settings.get(layout_id, {}), terrain, offset)
        if map_change_source != original_source:
            self.map_files[maps.MAP_CHANGE_FILE] = map_change_source
        for layout_id, layout in painted.items():
            if layout_id not in known:
                continue
            rows = layout["rows"]
            mar, info = maps.encode_layout(layout_id, len(rows[0]), len(rows), [c for row in rows for c in row])
            rel = known[layout_id]["mar"]
            if mar != (self.decomp_dir / rel).read_bytes():
                self.map_files[rel] = mar
            rel_info = rel[: -len(".mar")] + ".json"
            if info != self._read(rel_info):
                self.map_files[rel_info] = info

    def _original_rows(self, layout_id: str) -> list[list[int]]:
        width, height, cells = maps.read_layout(maps.layouts(self.decomp_dir)[layout_id]["assets"].layout)
        return [cells[y * width: (y + 1) * width] for y in range(height)]

    def map_object_events(self, layout_id: str) -> dict[tuple[int, int], dict]:
        """Original location events (chest, door, village, house) of the first chapter using a layout,
        by position."""
        self._load_chapter_events()
        for index in maps.layouts(self.decomp_dir)[layout_id]["chapters"]:
            found = self._location_list(index)
            if found:
                rel, start, end = found
                events = mapobjects.read_location_events(self.event_sources[rel][start:end])
                shops = self._shop_lists()
                for e in events:
                    if e.get("shop") in shops:
                        e["items"] = shops[e["shop"]]
                return {(e["x"], e["y"]): e for e in events}
        return {}

    def _shop_lists(self) -> dict[str, list[str]]:
        path = self.decomp_dir / mapobjects.SHOP_LIST_FILE
        return mapobjects.read_shop_lists(self._read(mapobjects.SHOP_LIST_FILE)) if path.is_file() else {}

    def _location_list(self, chapter_index: int) -> tuple[str, int, int] | None:
        symbol = self._chapter_event_symbol(self.chapter_settings["chapters"][chapter_index])
        if not symbol:
            return None
        try:
            group = objectives.event_group(self.event_sources, symbol)
        except objectives.ObjectiveError:
            return None
        name = group.get("locationBasedEvents", "")
        return objectives._list(self.event_sources, name) if re.fullmatch(r"\w+", name) else None

    def _apply_map_events(self, layout_id: str, rows: list[list[int]], objects: list[dict], settings: dict,
                          edited_terrain: bytes | None = None, offset: tuple[int, int] = (0, 0)) -> None:
        """Location events of the chapters using a layout: events added for new villages, houses,
        chests and doors (or set in the project), removed where the painting erased the object; the
        original ones follow a map moved by `offset`."""
        layout = maps.layouts(self.decomp_dir)[layout_id]
        _metatiles, original_terrain = maps.read_config(layout["assets"].config)
        original = maps.moved_rows(self._original_rows(layout_id), offset, len(rows[0]), len(rows))

        def kind_at(grid, x, y):
            terrain = original_terrain if grid is original else (edited_terrain or original_terrain)
            if 0 <= y < len(grid) and 0 <= x < len(grid[0]) and 0 <= grid[y][x] < len(terrain):
                return mapobjects.KINDS.get(terrain[grid[y][x]])
            return None

        erased = any(kind_at(original, x, y) in mapobjects.EVENT_KINDS and kind_at(rows, x, y) != kind_at(original, x, y)
                     for y in range(len(original)) for x in range(len(original[0])))
        added = any(o["new"] and o["kind"] in mapobjects.EVENT_KINDS for o in objects)
        if not (erased or added or settings or any(offset)):
            return
        self._load_chapter_events()

        done = set()
        for index in layout["chapters"]:
            found = self._location_list(index)
            if not found or found[:2] in done:
                continue
            done.add(found[:2])
            rel, start, end = found
            source = self.event_sources[rel]
            body = source[start:end]
            if any(offset):
                body = mapobjects.move_location_events(body, *offset, len(rows[0]), len(rows))
                self.event_sources[rel] = source = source[:start] + body + source[end:]
                end = start + len(body)
            events = mapobjects.read_location_events(body)
            prefix = rel.rsplit("-", 1)[0]
            flags = mapobjects.used_flags([s for r, s in self.event_sources.items() if r.startswith(prefix)])
            remove: set[tuple[int, int]] = set()
            lines: list[str] = []
            scripts = ""
            for e in events:
                # The painting erased the object: its event would point at nothing.
                before, after = kind_at(original, e["x"], e["y"]), kind_at(rows, e["x"], e["y"])
                if mapobjects.event_matches(e["kind"], before) and not mapobjects.event_matches(e["kind"], after):
                    remove.add(e["span"])

            def flag() -> str:
                n = next(n for n in range(mapobjects.FIRST_FLAG, mapobjects.LAST_FLAG + 1) if n not in flags)
                flags.add(n)
                return f"EVFLAG_TMP({n})"

            for obj in objects:
                kind = obj["kind"]
                if kind not in mapobjects.EVENT_KINDS:
                    continue
                cells = {tuple(c) for c in obj["cells"]}
                mine = [e for e in events if (e["x"], e["y"]) in cells and mapobjects.event_matches(e["kind"], kind)]
                own = settings.get(f"{obj['x']},{obj['y']}")
                if own is None and (mine or not obj["new"]):
                    continue  # original behavior (an original object without event is decoration)
                remove.update(e["span"] for e in mine)
                if own and own.get("off"):
                    continue
                s = {**mapobjects.DEFAULTS[kind], **(own or {})}
                x, y = obj["x"], obj["y"]
                if kind == "chest":
                    lines.append(f"ChestMoney({int(s['gold'])}, {x}, {y})" if s.get("gold")
                                 else f"Chest({s.get('item') or 'ITEM_VULNERARY'}, {x}, {y})")
                elif kind in mapobjects.SHOP_KINDS:
                    name = f"ShopList_FEM_{layout_id}_{x}_{y}"
                    scripts += mapobjects.shop_list(name, s.get("items") or mapobjects.DEFAULTS[kind]["items"])
                    macro = "SecretShop" if s.get("secret") else kind.capitalize()
                    lines.append(f"{macro}({name}, {x}, {y})")
                elif kind == "door":
                    door_flag = flag()
                    lines += [f"Door({cx}, {cy}, {door_flag})" for cx, cy in obj["cells"]]
                else:
                    name = f"EventScr_FEM_{layout_id}_{x}_{y}"
                    message = self.texts.add(mapobjects.dialogue_message(
                        s.get("face") or mapobjects.DEFAULTS[kind]["face"], s.get("text") or "...",
                        fonts.widths(self.decomp_dir)))
                    house = kind == "house"
                    scripts += mapobjects.village_script(name, message, None if house else s.get("item"),
                                                         None if house else s.get("gold"), house)
                    lines.append(f"House(0, {name}, {x}, {y})" if house else f"Village({flag()}, {name}, {x}, {y})")
            if not remove and not lines:
                continue
            for s0, e0 in sorted(remove, reverse=True):
                body = body[:s0] + body[e0:]
            if lines:
                m = objectives._END_RE.search(body)
                indent = m.group(1) if m else "    "
                block = "".join(f"{indent}{line}\n" for line in lines)
                body = body[: m.start()] + block + body[m.start():] if m else body + block
            declaration = source.rfind("\n", 0, start) + 1
            self.event_sources[rel] = source[:declaration] + scripts + source[declaration:start] + body + source[end:]

    # ---------- dialogues ----------

    @staticmethod
    def export_animations() -> dict:
        """Project battle animations (ticket 44): "animations" {key: imported animation, its files in the
        project's assets/animations/<key>/}, "classes" {class id: {weapon type: game animation number or
        "new:<key>"}} (the class's animation for that weapon, replaced or added)."""
        return {"animations": {}, "classes": {}}

    def apply_character_palettes(self, characters: list[dict]) -> None:
        """Characters' own colours in battle, before the animations, which must know about them (charpalettes.py)."""
        known = {e.fields["number"] for e in self.classes.entries}
        edits = {ch["id"]: {k: v for k, v in ch["battleColors"].items() if k in known}
                 for ch in characters if ch.get("battleColors")}
        if not any(edits.values()):
            return
        names = (charpalettes.CONFIG_FILE, charpalettes.TABLE_FILE, charpalettes.DATA_FILE)
        try:
            files, self.first_new_palette = charpalettes.apply({n: self._read(n) for n in names}, edits)
        except charpalettes.PaletteError as e:
            raise GameDataError(str(e)) from e
        self.asset_files.update(files)

    def apply_animations(self, data: dict, assets_dir: Path) -> None:
        """Imported animations added after the game's (table, sheets, scripts), and the classes' changed
        animations written as new settings arrays (banim_import.py)."""
        imported = data.get("animations", {})
        overrides = {k: v for k, v in data.get("classes", {}).items() if v}
        if not imported and not overrides:
            return
        keys = sorted(imported, key=lambda k: int(k))
        first = len(banim.table(self.decomp_dir)) + 1
        numbers = {f"new:{k}": first + i for i, k in enumerate(keys)}
        added = []
        for key in keys:
            symbol = banim_import.symbol_of(key)
            folder = assets_dir / "animations" / key
            files = [f for f in folder.rglob("*") if f.is_file()]
            if not files:
                raise GameDataError(f"Animation {key}: its files are missing from the project")
            for f in files:
                rel = f.relative_to(folder).as_posix()
                self.asset_files[rel] = f.read_text(encoding="utf-8") if rel.endswith(".s") else f.read_bytes()
            added.append((symbol, sum(1 for f in files if "_sheet_" in f.name)))
        if added:
            names = (banim_import.TABLE_FILE, banim_import.POINTERS_FILE, banim_import.SHEETS_INCLUDE,
                     banim_import.LINKER_SCRIPT)
            try:
                self.asset_files.update(banim_import.register({n: self._read(n) for n in names}, added, first))
                self.asset_files[banim_import.MAIN_FILE] = banim_import.without_unique_palettes(
                    self._read(banim_import.MAIN_FILE), first - 1, self.first_new_palette)
            except banim_import.ImportError_ as e:
                raise GameDataError(f"Battle animations: {e.args[0]}") from e
        if not overrides:
            return
        confs = banim.configs(self.decomp_dir)
        entries = {e.fields["number"]: e for e in self.classes.entries}
        defs_by_class = {}
        for class_id, weapons in overrides.items():
            entry = entries.get(class_id)
            if entry is None:
                raise GameDataError(f"Unknown class {class_id}")
            defs = [dict(d) for d in confs.get(entry.fields.get("pBattleAnimDef", "").lstrip("&").strip(), [])]
            for wtype, anim in banim_import.with_groups(weapons).items():
                number = numbers.get(anim) if isinstance(anim, str) else int(anim)
                # a weapon type, or an item of a group (throwing axes)
                weapon = WEAPON_TYPES_REV.get(wtype) or (wtype if wtype in banim_import.GROUP_ITEMS else None)
                if number is None or weapon is None:
                    raise GameDataError(f"{class_id}: unknown animation {anim} for {wtype}")
                same = [d for d in defs if d["weapon"] == weapon]
                for d in same:
                    d["number"] = number
                if not same:
                    defs.append({"weapon": weapon, "number": number})
            defs_by_class[class_id] = defs
        source, arrays = banim_import.class_configs(self._read(banim_import.CONF_FILE), defs_by_class)
        self.asset_files[banim_import.CONF_FILE] = source
        for class_id, name in arrays.items():
            entries[class_id].fields["pBattleAnimDef"] = name
        self.new_anim_confs = sorted(arrays.values())

    @staticmethod
    def export_portraits() -> dict:
        """Project portraits: portrait id -> imported sheet (see portraits.py); empty for the game."""
        return {}

    def apply_portraits(self, data: dict, assets_dir: Path) -> None:
        """Sheets imported in the project replace the game's portraits (files and mouth / eye positions)."""
        from PIL import Image

        if not data:
            return
        table = self._read(portraits.PORTRAIT_TABLE)
        source = table
        first = portraits.first_new_id(self.decomp_dir)
        added: dict[int, dict] = {}
        for key, entry in sorted(data.items(), key=lambda kv: int(kv[0])):
            pid = int(key)
            new = portraits.is_new(self.decomp_dir, pid)
            name = portraits.new_name(pid) if new else portraits.portrait_name(self.decomp_dir, pid)
            path = assets_dir / entry["file"]
            if not path.is_file():
                raise GameDataError(f"Portrait {key}: {entry['file']} not found")
            with Image.open(path) as img:
                sheet, _colors = portraits.indexed(img)
            self.asset_files.update(portraits.overlay_files(self.decomp_dir, name, portraits.from_sheet(sheet)))
            positions = {"mouth": entry.get("mouth", [2, 6]), "eyes": entry.get("eyes", [3, 4])}
            if new:
                added[pid] = positions
            else:
                source = portraits.write_positions(source, name, positions["mouth"], positions["eyes"])
        if added:
            data_s, header, source = portraits.add_to_sources(
                self._read(portraits.DATA_FILE), self._read(portraits.HEADER_FILE), source, first, added)
            self.asset_files[portraits.DATA_FILE] = data_s
            self.asset_files[portraits.HEADER_FILE] = header
            self.new_faces = sorted(added)
        if source != table:
            self.asset_files[portraits.PORTRAIT_TABLE] = source

    @staticmethod
    def export_dialogues() -> dict:
        """Project dialogues: edited messages only, as steps (see dialogues.py), by message id; and
        new battle and death quotes: {"kind": "battle" | "death", "chapter": index (255: any),
        "a": character, "b": opponent ("" = anyone), "steps": [...]} (see quotes.py)."""
        return {"messages": {}, "quotes": []}

    def apply_dialogues(self, data: dict) -> None:
        in_battle = self._quote_messages() if data.get("messages") else set()
        for key, steps in data.get("messages", {}).items():
            index = int(key, 0) if isinstance(key, str) else int(key)
            if index not in self.texts.messages:
                raise GameDataError(f"Unknown message {key}")
            body = self._message(steps, index in in_battle)
            if not dialogues.same_message(self.texts.raw(index), body):
                self.texts.set_raw(index, body)
        new_quotes = [q for q in data.get("quotes", []) if q.get("a") and q.get("kind") not in ("talk", "scene")]
        # Messages made for event scripts: their ids replace "new:<key>" in the scripts
        def scene_message(q: dict) -> str:
            body = self._message(q.get("steps") or [])
            return dialogues.as_question(body) if q.get("question") else body

        scene_ids = {q["key"]: self.texts.add(scene_message(q))
                     for q in data.get("quotes", []) if q.get("kind") == "scene" and q.get("key")}
        talks = [q for q in data.get("quotes", []) if q.get("kind") == "talk" and q.get("a") and q.get("b")]
        for n, talk in enumerate(talks):
            self._add_talk(n, talk)
        turns = [q for q in data.get("quotes", []) if q.get("kind") == "turn"]
        for n, scene in enumerate(turns):
            self._add_turn_scene(n, scene)
        if data.get("scripts"):
            self._apply_scripts(data["scripts"], scene_ids)
        if data.get("triggers"):
            self._load_event_sources()
            for script, change in data["triggers"].items():
                self.event_sources = {rel: dialogues.with_trigger(source, script, change)
                                      for rel, source in self.event_sources.items()}
        if data.get("removedScenes"):
            self._load_event_sources()
            for script in data["removedScenes"]:
                self.event_sources = {rel: dialogues.without_scene(source, script) for rel, source in self.event_sources.items()}
        conversations = [q for q in data.get("quotes", []) if q.get("kind") == "support"]
        if data.get("supports") is not None:
            self._apply_supports(data["supports"], conversations)
        new_quotes = [q for q in new_quotes if q.get("kind") not in ("turn", "support")]
        if not new_quotes:
            return
        self._load_chapter_events()
        if not self.defeat_talks:
            raise GameDataError(f"{quotes.FILE} not found")
        used = self._quote_flags()
        for q in new_quotes:
            msg = self.texts.add(self._message(q.get("steps") or [], battle=True))
            chapter = int(q.get("chapter", quotes.ANY_CHAPTER))
            if q.get("kind") == "battle":
                flag = next(n for n in range(quotes.FIRST_FLAG, chapterflags.LAST_FLAG + 1) if (chapter, n) not in used)
                self._new_quote_flags = True
                used.add((chapter, flag))
                self.defeat_talks = quotes.add_battle_quote(self.defeat_talks, self._chapter_constants, chapter,
                                                            q["a"], q.get("b", ""), msg, flag)
            else:
                self.defeat_talks = quotes.add_death_quote(self.defeat_talks, self._chapter_constants, chapter, q["a"], msg)

    def _message(self, steps: list[dict], battle: bool = False) -> str:
        """Message body of dialogue steps, laid out for the box (battle quotes have a narrower one)."""
        width = dialogues.BATTLE_WIDTH if battle else dialogues.TALK_WIDTH
        return dialogues.render(dialogues.layout_steps(steps, fonts.widths(self.decomp_dir), width))

    def _quote_messages(self) -> set[int]:
        """Messages of the battle quotes and last words (shown in the battle screen's box)."""
        if not (self.decomp_dir / maps.CHAPTER_SETTINGS_FILE).is_file():
            return set()
        self._load_chapter_events()
        found = quotes.read_quotes(self.defeat_talks, self._chapter_constants)
        return {q["msg"] for q in found["battle"] + found["death"]}

    def _event_list(self, index: int, field: str) -> tuple[str, int, int]:
        """(file, body start, body end) of one of a chapter's event lists (turnBasedEvents...)."""
        self._load_chapter_events()
        symbol = self._chapter_event_symbol(self.chapter_settings["chapters"][index])
        try:
            group = objectives.event_group(self.event_sources, symbol or "")
        except objectives.ObjectiveError as e:
            raise GameDataError(f"Chapter {index} has no events") from e
        found = objectives._list(self.event_sources, group.get(field, ""))
        if found is None:
            raise GameDataError(f"Chapter {index} has no {field} list")
        return found

    def _add_to_list(self, found: tuple[str, int, int], script: str, lines: list[str]) -> None:
        """A script (written just before the list) and entries (at the end of the list)."""
        rel, start, end = found
        source = self.event_sources[rel]
        body = source[start:end]
        m = objectives._END_RE.search(body)
        indent = m.group(1) if m else "    "
        block = "".join(f"{indent}{line}\n" for line in lines)
        body = body[: m.start()] + block + body[m.start():] if m else body + block
        declaration = source.rfind("\n", 0, start) + 1
        self.event_sources[rel] = source[:declaration] + script + source[declaration:start] + body + source[end:]

    def _free_flag(self, rel: str, first: int) -> int:
        prefix = rel.rsplit("-", 1)[0] + "-"
        used = mapobjects.used_flags([s for r, s in self.event_sources.items() if r.startswith(prefix)])
        return next(f for f in range(first, 100) if f not in used)

    def _add_turn_scene(self, n: int, scene: dict) -> None:
        """A message at the start of turn N of a side (once)."""
        index = int(scene.get("chapter", 0))
        found = self._event_list(index, "turnBasedEvents")
        turn = max(1, int(scene.get("turn", 1)))
        faction = dialogues.FACTIONS.get(scene.get("phase", "player"), "FACTION_BLUE")
        flag = self._free_flag(found[0], dialogues.TALK_FIRST_FLAG)
        message = self.texts.add(self._message(scene.get("steps") or []))
        name = f"EventScr_FEM_Turn_{index}_{n}"
        self._add_to_list(found, dialogues.scene_script(name, message),
                          [f"TURN(EVFLAG_TMP({flag}), {name}, {turn}, 0, {faction})"])

    def _add_reinforcements(self, name: str, meta: dict, group_units: list[dict]) -> None:
        """A group made in the project: its units arrive at the start of turn N of a side, with the
        game's reinforcement routine (EventScr_LoadReinforce: camera on them, then they appear)."""
        if not re.fullmatch(r"UnitDef_FEM_\w+", name):
            raise GameDataError(f"Bad name for a new unit group: {name}")
        self.unit_defs[units.NEW_GROUPS_FILE] = self.unit_defs[units.NEW_GROUPS_FILE].rstrip("\n") + "\n" + \
            units.render_new_group(name, group_units, units.ai_macros(self.decomp_dir))
        self._add_turn_event(name, meta)

    def _apply_group_turns(self, chapters: dict) -> None:
        """The game's reinforcement groups (ticket 109): "groupTurns" {group: {chapter, turn, phase}} moves their turn;
        in a chapter the project cleared their events are gone, so the groups it filled get new ones."""
        turns = chapters.get("groupTurns", {})
        cleared = chapters.get("cleared", [])
        for index in cleared:
            symbol = self._chapter_event_symbol(maps.chapter_settings(self.decomp_dir)[index])
            for group in units.chapter_unit_groups(self.decomp_dir, symbol) if symbol else []:
                filled = chapters.get("unitGroups", {}).get(group["name"])
                if group["origin"] == "turn" and filled:
                    allies = all(u.get("side") == "ally" for u in filled)
                    self._add_turn_event(group["name"], {"chapter": index, "turn": group["turn"],
                                                         "phase": "ally" if allies else "enemy", **turns.get(group["name"], {})})
        for name, meta in turns.items():
            if meta.get("chapter") not in cleared:
                self._move_turn_event(name, meta)

    def _move_turn_event(self, name: str, meta: dict) -> None:
        rel, start, end = self._event_list(int(meta.get("chapter", 0)), "turnBasedEvents")
        source = self.event_sources[rel]

        def moved(m: re.Match) -> str:
            loaded = [group for group, _ in units._script_loads(self.decomp_dir, m.group(2))]
            return f"{m.group(1)}{max(1, int(meta['turn']))}{m.group(4)}" if name in loaded else m.group(0)

        body = re.sub(r"(\bTURN\s*\(\s*[^,]+,\s*(\w+)\s*,\s*)(\d+)(\s*,)", moved, source[start:end])
        self.event_sources[rel] = source[:start] + body + source[end:]

    def _add_turn_event(self, name: str, meta: dict) -> None:
        index = int(meta.get("chapter", 0))
        found = self._event_list(index, "turnBasedEvents")
        turn = max(1, int(meta.get("turn", 1)))
        faction = dialogues.FACTIONS.get(meta.get("phase", "enemy"), "FACTION_RED")
        flag = self._free_flag(found[0], dialogues.TALK_FIRST_FLAG)
        script_name = f"EventScr_FEM_Load_{name.removeprefix('UnitDef_').removeprefix('FEM_')}"
        script = (f"extern CONST_DATA struct UnitDefinition {name}[];\n\n"
                  f"CONST_DATA EventListScr {script_name}[] = {{\n"
                  f"    SVAL(EVT_SLOT_2, {name})\n    CALL(EventScr_LoadReinforce)\n    NoFade\n    ENDA\n}};\n\n")
        self._add_to_list(found, script, [f"TURN(EVFLAG_TMP({flag}), {script_name}, {turn}, 0, {faction})"])

    def _add_talk(self, n: int, talk: dict) -> None:
        """A new conversation: "Talk" from a to b (and b to a with "both") shows its message; with
        "recruit", b joins the player's army."""
        index = int(talk.get("chapter", 0))
        found = self._event_list(index, "characterBasedEvents")
        flag = self._free_flag(found[0], dialogues.TALK_FIRST_FLAG)
        message = self.texts.add(self._message(talk.get("steps") or []))
        name = f"EventScr_FEM_Talk_{index}_{n}"
        lines = [f"CHAR(EVFLAG_TMP({flag}), {name}, {talk['a']}, {talk['b']})"]
        if talk.get("both"):
            lines.append(f"CHAR(EVFLAG_TMP({flag}), {name}, {talk['b']}, {talk['a']})")
        self._add_to_list(found, dialogues.talk_script(name, message, talk["b"] if talk.get("recruit") else None), lines)

    # ---------- event scripts (visual editor) ----------

    def find_script(self, name: str) -> tuple[str, int, int] | None:
        """(file, body start, body end) of an event script."""
        self._load_event_sources()
        for rel, source in self.event_sources.items():
            if name in source:
                found = events.find_scripts(source).get(name)
                if found:
                    return rel, *found
        return None

    def script_names(self) -> list[str]:
        """The chapters' event scripts, for CALL."""
        self._load_event_sources()
        return sorted({name for source in self._original_event_sources.values() for name in events.find_scripts(source)})

    def script_commands(self, name: str) -> list[dict]:
        found = self.find_script(name)
        if found is None:
            raise GameDataError(f"Unknown event script {name}")
        rel, start, end = found
        return events.parse_script(self.event_sources[rel][start:end])

    def _apply_scripts(self, scripts: dict[str, list[dict]], scene_ids: dict[str, int] | None = None) -> None:
        """Scripts edited in the visual editor replace the original ones (only when they differ).
        `scene_ids`: ids of the messages made for scripts, by key (arguments "new:<key>")."""
        def message(value):
            if isinstance(value, str) and value.startswith(dialogues.SCENE_MESSAGE):
                key = value[len(dialogues.SCENE_MESSAGE):]
                if key not in (scene_ids or {}):
                    raise GameDataError(f"Unknown new message {key}")
                return f"0x{scene_ids[key]:X}"
            return value

        for name, commands in sorted(scripts.items()):
            commands = [{**c, "args": [message(a) for a in c["args"]]} if c.get("args") else c for c in commands]
            found = self.find_script(name)
            if found is None:
                raise GameDataError(f"Unknown event script {name}")
            rel, start, end = found
            source = self.event_sources[rel]
            if events.same_commands(events.parse_script(source[start:end]), commands):
                continue
            bad = next((c for c in commands if events.validate_command(c)), None)
            if bad is not None:
                raise GameDataError(f"{name}: bad command {bad.get('op')}")
            self.event_sources[rel] = source[:start] + events.render_script(commands) + source[end:]

    # ---------- supports ----------

    def _support_owners(self) -> dict[str, str]:
        """SupportData name -> character."""
        out = {}
        for e in self.characters.entries:
            m = re.fullmatch(r"&\s*(\w+)", e.fields.get("pSupportData", "").strip())
            if m:
                out[m.group(1)] = e.fields["number"]
        return out

    def original_supports(self) -> list[dict]:
        """The game's support pairs {a, b, base, growth, messages: [C, B, A]} (none without the files)."""
        if not (self.decomp_dir / supports.SUPPORTS_FILE).is_file():
            return []
        blocks = supports.read_blocks(self._read(supports.SUPPORTS_FILE))
        talks = supports.read_talks(self._read(supports.TALKS_FILE))
        return [{**p, "messages": talks.get(tuple(sorted((p["a"], p["b"]))))}
                for p in supports.pairs_of(blocks, self._support_owners())]

    def _apply_supports(self, pairs: list[dict], conversations: list[dict]) -> None:
        """Support pairs of the project: each character's list rewritten when it changed (a new
        SupportData for a character who had none), new pairs added to gSupportTalkList with their
        conversations (new quotes of kind "support")."""
        source = self._read(supports.SUPPORTS_FILE)
        blocks = supports.read_blocks(source)
        owners = self._support_owners()
        block_of = {char: name for name, char in owners.items()}
        original = {owners[name]: partners for name, partners in blocks.items() if name in owners}
        wanted = supports.partners_by_character(pairs, original)
        changed = {}
        entries = {e.fields["number"]: e for e in self.characters.entries}
        for char, partners in sorted(wanted.items()):
            if partners == original.get(char, []):
                continue
            if len(partners) > supports.MAX_PARTNERS:
                raise GameDataError(f"{char}: more than {supports.MAX_PARTNERS} support partners")
            name = block_of.get(char)
            if name is None:
                if char not in entries:
                    raise GameDataError(f"Unknown character {char}")
                name = f"SupportData_FEM_{char.removeprefix('CHARACTER_')}"
                entries[char].fields["pSupportData"] = f"&{name}"
                self.new_support_blocks.append(name)
            changed[name] = partners
        if changed:
            self.support_source = supports.write_blocks(source, changed)
        talks = supports.read_talks(self._read(supports.TALKS_FILE))
        new_talks = []
        for p in pairs:
            key = tuple(sorted((p["a"], p["b"])))
            if key in talks:
                continue
            msgs = []
            for rank in (1, 2, 3):
                steps = next((q.get("steps") for q in conversations if tuple(sorted((q.get("a"), q.get("b")))) == key
                              and int(q.get("rank", 0)) == rank), None)
                msgs.append(self.texts.add(self._message(steps)) if steps else 0)
            new_talks.append((p["a"], p["b"], msgs))
        if new_talks:
            self.support_talks = supports.add_talks(self._read(supports.TALKS_FILE), new_talks)

    def _quote_flags(self) -> set[tuple[int, int]]:
        """(chapter, flag) of temporary flags already used by battle quotes and chapter events."""
        used = set()
        for q in quotes.read_quotes(self.defeat_talks, self._chapter_constants)["battle"]:
            try:
                used.add((q["chapter"], int(q["flag"], 0)))
            except ValueError:
                pass
        for i, chapter in enumerate(self.chapter_settings["chapters"]):
            symbol = self._chapter_event_symbol(chapter)
            rel = self._event_group_file(symbol)
            if rel:
                prefix = rel.rsplit("-", 1)[0] + "-"
                flags = mapobjects.used_flags([s for r, s in self.event_sources.items() if r.startswith(prefix)])
                used.update((i, n) for n in flags)
        return used

    def _event_group_file(self, symbol: str | None) -> str | None:
        """File defining a chapter event group (its scripts are in the files with the same prefix)."""
        if not symbol:
            return None
        return next((r for r, s in self.event_sources.items() if re.search(rf"ChapterEventGroup\s+{symbol}\b", s)), None)

    def quote_scenes(self, chapter: int) -> list[dict]:
        """Battle and death quotes of a chapter (quotes.ANY_CHAPTER: of every chapter) as dialogue scenes."""
        self._load_chapter_events()
        if not self.defeat_talks:
            return []
        found = quotes.read_quotes(self.defeat_talks, self._chapter_constants)
        scenes, seen = [], set()
        for q in found["battle"]:
            if q["chapter"] == chapter and q["msg"] and q["msg"] not in seen:
                seen.add(q["msg"])
                # The game writes a boss quote twice ({0, boss} and {boss, 0}): show the boss first.
                a, b = (q["b"], q["a"]) if not q["a"] else (q["a"], q["b"])
                scenes.append({"script": f"battle:{q['msg']}", "messages": [q["msg"]], "file": quotes.FILE,
                               "trigger": {"kind": "battle", "a": a, "b": b}})
        for q in found["death"]:
            if q["chapter"] == chapter and q["msg"] and q["msg"] not in seen:
                seen.add(q["msg"])
                scenes.append({"script": f"death:{q['msg']}", "messages": [q["msg"]], "file": quotes.FILE,
                               "trigger": {"kind": "death", "a": q["a"]}})
        return scenes

    def chapter_event_files(self, index: int) -> list[str]:
        """Event files of a chapter: the one with its event group and those with the same prefix."""
        self._load_chapter_events()
        rel = self._event_group_file(self._chapter_event_symbol(self.chapter_settings["chapters"][index]))
        if rel is None:
            return []
        prefix = rel.rsplit("-", 1)[0] + "-"
        return sorted(r for r in self.event_sources if r.startswith(prefix))

    def chapter_openings(self) -> list[str | None]:
        """Each chapter's opening scene."""
        self._load_chapter_events()
        out = []
        for chapter in self.chapter_settings["chapters"]:
            symbol = self._chapter_event_symbol(chapter)
            try:
                out.append(objectives.event_group(self.event_sources, symbol or "").get("beginningSceneEvents"))
            except objectives.ObjectiveError:
                out.append(None)
        return out

    def chapter_endings(self) -> list[str | None]:
        """Each chapter's ending scene: where the Campaign page links a chapter that leads nowhere (ticket 55)."""
        self._load_chapter_events()
        out = []
        for chapter in self.chapter_settings["chapters"]:
            try:
                group = objectives.event_group(self.event_sources, self._chapter_event_symbol(chapter) or "")
                out.append(group.get("endingSceneEvents"))
            except objectives.ObjectiveError:
                out.append(None)
        return out

    def ending_scripts(self) -> set[str]:
        """The chapters' ending scenes."""
        if not (self.decomp_dir / maps.CHAPTER_SETTINGS_FILE).is_file():
            return set()
        self._load_chapter_events()
        out = set()
        for chapter in self.chapter_settings["chapters"]:
            try:
                group = objectives.event_group(self.event_sources, self._chapter_event_symbol(chapter) or "")
            except objectives.ObjectiveError:
                continue
            out.add(group.get("endingSceneEvents"))
        return out - {None}

    def chapter_links(self, edited: dict[str, list[dict]] | None = None) -> list[list[dict]]:
        """For each chapter, the commands of its scripts that start another chapter (story.links), with the
        script's name and whether it is the chapter's ending scene; `edited`: the project's edited scripts,
        read instead of the game's."""
        self._load_chapter_events()
        out = []
        for index, chapter in enumerate(self.chapter_settings["chapters"]):
            try:
                group = objectives.event_group(self.event_sources, self._chapter_event_symbol(chapter) or "")
                ending = group.get("endingSceneEvents")
            except objectives.ObjectiveError:
                ending = None
            found = []
            for rel in self.chapter_event_files(index):
                source = self._original_event_sources.get(rel, self.event_sources[rel])
                for name, (start, end) in events.find_scripts(source).items():
                    commands = (edited or {}).get(name)
                    if commands is None:
                        body = source[start:end]
                        if not any(op in body for op in story.CHANGE_OPS):
                            continue
                        commands = events.parse_script(body)
                    found += [{"script": name, "ending": name == ending, **link} for link in story.links(commands)]
            # An ending scene the project wrote in a file with another prefix (the tower's floors: tower1-eventinfo.h,
            # tower-eventscript.h), for a chapter it adds (ticket 55).
            if ending in (edited or {}) and not any(link["script"] == ending for link in found):
                found += [{"script": ending, "ending": True, **link} for link in story.links(edited[ending])]
            out.append(found)
        return out

    def chapter_dialogues(self, index: int) -> list[dict]:
        """Event scripts of a chapter that show messages, with what starts them and their messages."""
        self._load_chapter_events()
        symbol = self._chapter_event_symbol(self.chapter_settings["chapters"][index])
        if not symbol:
            return []
        try:
            group = objectives.event_group(self.event_sources, symbol)
        except objectives.ObjectiveError:
            return []
        rel = self._event_group_file(symbol)
        if rel is None:
            return []
        prefix = rel.rsplit("-", 1)[0] + "-"
        files = {r: s for r, s in self.event_sources.items() if r.startswith(prefix)}
        scenes = []
        for r in sorted(files):
            scenes += [{"script": name, "messages": ids, "file": r} for name, ids in dialogues.script_messages(files[r])]
        lists = {}
        for source in files.values():
            for name, body in re.findall(r"EventListScr\s+(\w+)\s*\[\s*\]\s*=\s*\{(.*?)\n\};", source, re.S):
                lists[name] = body
        triggers = dialogues.scene_triggers(group, lists, set(lists))
        tutorials = set(re.findall(r"\w+", lists.get(group.get("tutorialEvents", ""), "")))

        def trigger(script: str, seen: frozenset = frozenset()) -> dict:
            """What starts a script; a script started by another one gets its caller's trigger."""
            if script in triggers:
                return triggers[script]
            if script in tutorials or "Tut" in script:
                return {"kind": "tutorial"}
            caller = next((name for name, body in lists.items()
                           if name != script and name not in seen and re.search(rf"\b{script}\b", body)), None)
            if caller is None:
                return {"kind": "other"}
            return {**trigger(caller, seen | {script}), "via": caller}

        # Scripts started by the chapter's events that show no message (reinforcements, map changes...):
        # listed too, for the event editor.
        shown = {s["script"] for s in scenes}
        script_file = {name: r for r, source in files.items() for name in events.find_scripts(source)}
        for name in triggers:
            if name not in shown and name in script_file and not name.startswith("EventListScr"):
                scenes.append({"script": name, "messages": [], "file": script_file[name]})
        for scene in scenes:
            scene["trigger"] = trigger(scene["script"])
        scenes += self.quote_scenes(index)
        order = {k: i for i, k in enumerate(dialogues.SCENE_ORDER)}
        scenes.sort(key=lambda s: (order.get(s["trigger"]["kind"], 99),
                                   int(s["trigger"].get("turn", "0"), 0) if str(s["trigger"].get("turn", "0")).isdigit() else 0))
        return scenes

    # ---------- chapter objectives ----------

    def _load_event_sources(self) -> None:
        """The chapters' event files (src/events/*.h), once."""
        if self._original_event_sources:
            return
        self.event_sources = {}
        for pattern in EVENT_INFO_FILES:
            for path in sorted(self.decomp_dir.glob(pattern)):
                rel = path.relative_to(self.decomp_dir).as_posix()
                if rel not in self.unit_defs:
                    self.event_sources[rel] = self._read(rel)
        self._original_event_sources = dict(self.event_sources)

    def _load_chapter_events(self) -> None:
        if self.chapter_settings is not None:
            return
        self._settings_raw = self._read(maps.CHAPTER_SETTINGS_FILE)
        self.chapter_settings = json.loads(self._settings_raw)
        self._load_event_sources()
        # Death quotes: the one flagged EVFLAG_DEFEAT_BOSS names the chapter's boss.
        self._chapter_constants = {}
        if (self.decomp_dir / objectives.CHAPTERS_HEADER).is_file():
            self._chapter_constants = objectives.chapter_constants(self._read(objectives.CHAPTERS_HEADER))
        talks = self.decomp_dir / objectives.DEFEAT_TALK_FILE
        self.defeat_talks = self._read(objectives.DEFEAT_TALK_FILE) if talks.is_file() else ""
        self._original_defeat_talks = self.defeat_talks

    def apply_prep(self, chapters: dict) -> None:
        """The preparations screen of the chapters the project changed or added (prep.py), after the edited scripts."""
        edited = {int(k): bool(v) for k, v in chapters.get("prep", {}).items()}
        for index in sorted(set(edited) | {int(k) for k in chapters.get("added", {})}):
            symbol = self._chapter_event_symbol(maps.chapter_settings(self.decomp_dir)[index])
            scene = units.beginning_scene(self.decomp_dir, symbol) if symbol else None
            if scene:
                self._load_chapter_events()
                self._apply_scripts({scene: prep.with_prep(self.script_commands(scene), edited.get(index, True))})

    def _chapter_groups(self, index: int) -> list[str]:
        symbol = self._chapter_event_symbol(maps.chapter_settings(self.decomp_dir)[index])
        return [g["name"] for g in units.chapter_unit_groups(self.decomp_dir, symbol)] if symbol else []

    def _chapter_event_symbol(self, chapter: dict) -> str | None:
        table = maps.asset_table(self.decomp_dir)
        index = chapter.get("mapEventDataId", 0)
        return table[index] if 0 < index < len(table) else None

    def read_objective(self, index: int) -> dict:
        """Objective of chapter `index` as currently written (original game + applied edits)."""
        self._load_chapter_events()
        chapters = self.chapter_settings["chapters"]
        chapter = chapters[index]
        objective = objectives.read_objective(
            chapter["goal"], self.event_sources, self._chapter_event_symbol(chapter), self.texts)
        status_id = chapter["goal"].get("statusObjectiveTextId", 0)
        # Several chapters may share a status text or an event group: editing one changes the others.
        objective["hasStatusText"] = bool(status_id)
        sharing = sum(1 for c in chapters if status_id and c["goal"].get("statusObjectiveTextId") == status_id)
        objective["statusShared"] = max(0, sharing - 1)
        symbol = self._chapter_event_symbol(chapter)
        objective["eventsShared"] = max(0, sum(1 for c in chapters if symbol and self._chapter_event_symbol(c) == symbol) - 1)
        bosses = objectives.read_bosses(self.defeat_talks, self._chapter_constants).get(index, [])
        objective["boss"] = bosses[0] if bosses else None
        objective["bossEditable"] = len(bosses) <= 1 and bool(self.defeat_talks)
        protect = chapter["goal"].get("protectCharacterIndex", 0)
        names = {v: k for k, v in self._character_constants().items()}
        objective["protect"] = names.get(protect, f"0x{protect:02X}") if protect else None
        return objective

    def _character_constants(self) -> dict[str, int]:
        header = self.decomp_dir / "include/constants/characters.h"
        if not header.is_file():
            return dict(self.new_characters)
        return {**{name: int(value, 0) for name, value in
                   re.findall(r"\b(CHARACTER_\w+)\s*=\s*(0x[0-9A-Fa-f]+|\d+)", self._read(CHARACTER_CONSTANTS_FILE))},
                **self.new_characters}

    def apply_objective(self, index: int, new: dict) -> None:
        current = self.read_objective(index)
        chapter = self.chapter_settings["chapters"][index]
        keys = ("type", "seize", "seizeLabel", "turns", "area", "areaWho", "orBoss")
        if any(new.get(k, current[k]) != current[k] for k in keys):
            self.event_sources = objectives.apply_objective(
                chapter["goal"], self.event_sources, self._chapter_event_symbol(chapter), current,
                {k: new.get(k, current[k]) for k in keys})
            if new.get("type") == "area":
                chapter["goal"]["windowTextId"] = self.texts.add("Reach the goal[X]")
        protect = new.get("protect", current["protect"])
        if protect != current["protect"]:
            # The protected character: an icon on the map, and the game is lost if they die.
            chapter["goal"]["protectCharacterIndex"] = self._character_constants().get(protect, 0) if protect else 0
            if protect:
                self.defeat_talks = quotes.set_death_flag(self.defeat_talks, self._chapter_constants, index, protect,
                                                          "EVFLAG_GAMEOVER")
                self.event_sources = objectives.ensure_game_over(self.event_sources, self._chapter_event_symbol(chapter))
        boss = new.get("boss")
        by_boss = new.get("type", current["type"]) == "defeat_boss" or (
            new.get("type", current["type"]) == "defense" and new.get("orBoss", current["orBoss"]))
        if boss and boss != current["boss"] and by_boss:
            self.defeat_talks = objectives.set_boss(self.defeat_talks, self._chapter_constants, index, boss)
        text = new.get("statusText")
        status_id = chapter["goal"].get("statusObjectiveTextId", 0)
        if text is not None and status_id and text.strip() != current["statusText"]:
            self.texts.set_raw(status_id, objectives.status_message(text))

    def apply_combat(self, combat_data: dict) -> None:
        if self.triangle is not None and "triangle" in combat_data:
            rules = [
                {"attacker": WEAPON_TYPES_REV[r["attacker"]], "defender": WEAPON_TYPES_REV[r["defender"]],
                 "hit": int(r["hit"]), "damage": int(r["damage"])}
                for r in combat_data["triangle"]
            ]
            if rules != self.triangle:
                self.triangle = rules
        if self.effectiveness is not None:
            for name, classes in combat_data.get("effectiveness", {}).items():
                if name not in self.effectiveness:
                    raise GameDataError(f"Unknown effectiveness list {name}")
                if list(classes) != self.effectiveness[name]:
                    self.effectiveness[name] = list(classes)

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
        """Editable class data (project JSON). Read-only facts are in class_facts()."""
        result = []
        for e in self.classes.entries:
            f = e.fields
            ranks = parse_designated_list(f.get("baseRanks", "{ }"))
            result.append({
                "id": f["number"],
                "name": self._text_name(f),
                "bases": {s: _int_field(f, "base" + STAT_SUFFIX[s], signed=True) for s in CLASS_STATS},
                "mov": _int_field(f, "baseMov", signed=True),
                "maxes": {s: _int_field(f, "max" + STAT_SUFFIX[s], signed=True) for s in CLASS_STATS},
                "growths": {s: _int_field(f, "growth" + STAT_SUFFIX[s], signed=True) for s in GROWTHS},
                "promotionGains": {s: _int_field(f, "promotion" + PROMO_SUFFIX[s]) for s in PROMO_STATS},
                "relativePower": _int_field(f, "classRelativePower", signed=True),
                "genericPortrait": _int_field(f, "defaultPortraitId"),
                "weaponRanks": {WEAPON_TYPES[k]: _rank_to_json(v) for k, v in ranks.items()},
                "abilities": _abilities(f.get("attributes", "0")),
                "promotions": list(self.promotions.get(f["number"], [])) if self.promotions is not None else [],
                "movement": _movement_group(f.get("pMovCostTable", "")),
                "terrainBonus": _terrain_group(f.get("pTerrainAvoidLookup", "")),
            })
        return result

    def class_facts(self) -> dict[str, dict]:
        """Read-only facts about each class, derived from the decomp (not editable)."""
        used = self.classes_used_in_game()
        genders = self.class_genders()
        return {
            e.fields["number"]: {
                "animatedWeapons": self.animated_weapons.get(e.fields["number"], []),
                "usedInGame": e.fields["number"] in used,
                "gender": genders.get(e.fields["number"]),
            }
            for e in self.classes.entries
        }

    def movement_types(self) -> list[str]:
        """Movement cost table families used by classes (HorseT2, Fly, Armor...)."""
        return sorted({_movement_group(e.fields.get("pMovCostTable", "")) for e in self.classes.entries} - {None})

    def new_class(self, model: str, taken: set[str]) -> dict:
        """Sheet of a class to add, copying `model`; `taken` are the ids already in the project."""
        record = next((r for r in self.export_classes() if r["id"] == model), None)
        if record is None:
            raise GameDataError("unknownClass")
        for n in range(FIRST_NEW_CLASS, LAST_NEW_CLASS + 1):
            new_id = f"{NEW_CLASS_PREFIX}{n:02X}"
            if new_id not in taken:
                return {**record, "id": new_id, "name": "", "model": model}
        raise GameDataError("noFreeClass")

    def _add_class(self, new_id: str, model: str | None) -> Entry:
        """A class the project adds: an entry after the game's ones, with the fields of its model."""
        n = int(new_id.removeprefix(NEW_CLASS_PREFIX), 16)
        if not FIRST_NEW_CLASS <= n <= LAST_NEW_CLASS:
            raise GameDataError(f"{new_id}: not after the game's classes")
        source = next((e for e in self.classes.entries if e.original_fields and e.fields["number"] == model), None)
        if source is None:
            raise GameDataError(f"{new_id}: unknown model class {model}")
        fields = dict(source.original_fields)
        fields["number"] = new_id
        fields["nameTextId"] = hex(self.texts.add(name_message("")))
        if "descTextId" in fields:   # its own help text, starting as the model's
            fields["descTextId"] = hex(self.texts.add(self.texts.raw(_int_field(source.original_fields, "descTextId"))))
        close = self.classes.source.rindex("};")
        start = self.classes.source.rfind("\n", 0, close) + 1
        key = re.sub(rf"\b{re.escape(model)}\b", new_id, source.key)   # "CLASS_X - 1" in the class table
        entry = Entry(key=key, fields=fields, start=start, end=start, indent=source.indent)
        self.classes.entries.append(entry)
        self.new_classes[new_id] = (n, model)
        self.animated_weapons[new_id] = self.animated_weapons.get(model, [])
        return entry

    def _with_new_class_files(self, out: dict[str, str | bytes]) -> None:
        """Constants of the classes the project adds."""
        if (self.decomp_dir / CLASS_CONSTANTS_FILE).is_file():
            out[CLASS_CONSTANTS_FILE] = self._enum_with(CLASS_CONSTANTS_FILE, "CLASS_",
                                                        {c: n for c, (n, _m) in self.new_classes.items()})

    def _class_numbers(self) -> dict[str, int]:
        """Class id -> number (the game's from classes.h, else their order in the table; the project's own)."""
        numbers = {e.fields["number"]: i + 1 for i, e in enumerate(e for e in self.classes.entries if e.original_fields)}
        if (self.decomp_dir / CLASS_CONSTANTS_FILE).is_file():
            numbers.update({name: int(value, 0) for name, value in
                            re.findall(r"\b(CLASS_\w+)\s*=\s*(0x[0-9A-Fa-f]+|\d+)", self._read(CLASS_CONSTANTS_FILE))})
        numbers.update({c: n for c, (n, _m) in self.new_classes.items()})
        return numbers

    def _with_moving_sprites(self, out: dict[str, str | bytes]) -> None:
        """unit_icon_move_table, one row per class in order: rows for the classes the project adds (their models'),
        and the moving sheets imported for classes, with the walking motion of the class's row."""
        if not (self.decomp_dir / MOVING_SPRITES_FILE).is_file():
            return
        source = self._read(MOVING_SPRITES_FILE)
        rows = re.findall(r"^[ \t]*\{[^{}\n]*\},[^\n]*$", source, re.MULTILINE)
        numbers = self._class_numbers()
        models = {n: model for n, model in self.new_classes.values()}
        table = list(rows)
        for n in range(len(rows) + 1, max(models, default=0) + 1):   # a gap left by a removed class: the first row
            table.append(re.sub(r"//.*$", f"// {n - 1}", rows[numbers.get(models.get(n, ""), 1) - 1]))
        for class_id, sprite in self.map_sprites.items():
            n = numbers.get(class_id, 0)
            if sprite["move"] and 0 < n <= len(table):
                table[n - 1] = re.sub(r"\{\s*\w+", "{" + mapsprites.sheet_name("move", sprite["key"]), table[n - 1], count=1)
        if table != rows:
            start, end = source.index(rows[0]), source.index(rows[-1]) + len(rows[-1])
            out[MOVING_SPRITES_FILE] = source[:start] + "\n".join(table) + source[end:]

    @staticmethod
    def export_music() -> dict:
        """Music imported by the project (music.py): none in the original game."""
        return {"songs": {}, "chapters": {}}

    def apply_music(self, data: dict, assets_dir: Path) -> None:
        """Imported songs in free rows of the song table, and their numbers in the chapters' music settings."""
        files, numbers = music.build_files(self.decomp_dir, data, assets_dir)
        if not numbers:
            return
        self.asset_files.update(files)
        self._load_chapter_events()
        settings = self.chapter_settings["chapters"]
        for index, phases in data.get("chapters", {}).items():
            for phase, key in phases.items():
                if key in numbers and phase in music.PHASES:
                    for field in (phase, phase + "InHectorStory"):
                        if field in settings[int(index)]["bgm"]:
                            settings[int(index)]["bgm"][field] = numbers[key]

    @staticmethod
    def export_map_sprites() -> dict:
        """Map sprites imported for classes: none in the original game."""
        return {"classes": {}, "sprites": {}}

    def apply_map_sprites(self, data: dict, assets_dir: Path) -> None:
        """Map sprites imported for classes (mapsprites.py): their sheets, a standing sprite number for each
        (after the game's), given to the classes as their SMSId."""
        if not data.get("classes") or not (self.decomp_dir / mapsprites.WAIT_TABLE_FILE).is_file():
            return
        game_rows = mapsprites.wait_rows(self._read(mapsprites.WAIT_TABLE_FILE))
        entries = {e.fields["number"]: e for e in self.classes.entries}
        for class_id, key in sorted(data["classes"].items()):
            info, entry, folder = data.get("sprites", {}).get(key), entries.get(class_id), assets_dir / "mapsprites" / key
            if info is None or entry is None or not (folder / "stand.png").is_file():
                continue
            if key not in self.map_sprite_ids:
                number = len(game_rows) + len(self.map_sprite_ids)
                if number >= mapsprites.MAX_WAIT_SPRITES:
                    raise GameDataError(f"At most {mapsprites.MAX_WAIT_SPRITES - len(game_rows)} imported map sprites")
                pattern = re.match(r"\{\s*(\d+)", game_rows[min(_int_field(entry.original_fields, "SMSId"),
                                                                 len(game_rows) - 1)]).group(1)
                self.map_sprite_ids[key] = (number, f"{{{pattern}, {info['size']}, {mapsprites.sheet_name('wait', key)}}}")
                self.asset_files[f"graphics/unit_icon/wait/{mapsprites.sheet_name('wait', key)}.png"] = \
                    (folder / "stand.png").read_bytes()
                if (folder / "walk.png").is_file():
                    self.asset_files[f"graphics/unit_icon/move/{mapsprites.sheet_name('move', key)}.png"] = \
                        (folder / "walk.png").read_bytes()
            entry.fields["SMSId"] = hex(self.map_sprite_ids[key][0])
            self.map_sprites[class_id] = {"key": key, "move": (folder / "walk.png").is_file()}

    def _with_map_sprite_files(self, out: dict[str, str | bytes]) -> None:
        """The imported sheets' rows of unit_icon_wait_table, their incbins and their declarations."""
        keys = sorted(self.map_sprite_ids, key=lambda k: self.map_sprite_ids[k][0])
        moves = {s["key"] for s in self.map_sprites.values() if s["move"]}
        out[mapsprites.WAIT_TABLE_FILE] = mapsprites.with_wait_rows(self._read(mapsprites.WAIT_TABLE_FILE),
                                                                    [self.map_sprite_ids[k][1] for k in keys])
        names = [(mapsprites.sheet_name("wait", k), "wait") for k in keys]
        names += [(mapsprites.sheet_name("move", k), "move") for k in keys if k in moves]
        for rel, kind in ((mapsprites.WAIT_DATA_FILE, "wait"), (mapsprites.MOVE_DATA_FILE, "move")):
            blocks = "".join(mapsprites.incbin_block(n, k) for n, k in names if k == kind)
            if blocks and (self.decomp_dir / rel).is_file():
                out[rel] = self._read(rel).rstrip("\n") + "\n" + blocks
        if (self.decomp_dir / mapsprites.POINTERS_FILE).is_file():
            out[mapsprites.POINTERS_FILE] = self._read(mapsprites.POINTERS_FILE).rstrip("\n") + "\n" + \
                "".join(f"extern char {n}[];\n" for n, _k in names)

    def _new_class_promotions(self) -> None:
        """New classes promote like their models unless the project says otherwise; the last one gets a row even
        without promotions, so the engine's gPromoJidLut[class] lookup stays inside the table."""
        if self.promotions is None or not self.new_classes:
            return
        last = max(self.new_classes, key=lambda c: self.new_classes[c][0])
        if not self.promotions.get(last):
            self.promotions[last] = ["0"]

    def apply_classes(self, classes: list[dict]) -> None:
        self.other_dancers |= any(danceanim.ABILITIES & set(cl.get("abilities", []))
                                  and cl["id"] not in danceanim.DANCER_CLASSES for cl in classes)
        entries = {e.fields["number"]: e for e in self.classes.entries}
        for cl in classes:
            entry = entries.get(cl["id"])
            if entry is None and cl["id"].startswith(NEW_CLASS_PREFIX):
                entry = entries[cl["id"]] = self._add_class(cl["id"], cl.get("model"))
            if entry is None:
                raise GameDataError(f"Unknown class {cl['id']}")
            f = entry.fields
            self.texts.set_name(_int_field(f, "nameTextId"), cl["name"])
            self._set_description(f, cl)
            for s in CLASS_STATS:
                _set_int(f, "base" + STAT_SUFFIX[s], cl["bases"][s], signed=True)
                _set_int(f, "max" + STAT_SUFFIX[s], cl["maxes"][s], signed=True)
            _set_int(f, "baseMov", cl["mov"], signed=True)
            if "genericPortrait" in cl:
                _set_int(f, "defaultPortraitId", cl["genericPortrait"])
            for s in GROWTHS:
                _set_int(f, "growth" + STAT_SUFFIX[s], cl["growths"][s], signed=True)
            for s in PROMO_STATS:
                _set_int(f, "promotion" + PROMO_SUFFIX[s], cl["promotionGains"][s])
            _set_int(f, "classRelativePower", cl["relativePower"], signed=True)
            self._apply_ranks(f, cl["weaponRanks"])
            self._apply_abilities(f, cl["abilities"])
            if cl["movement"] != _movement_group(f.get("pMovCostTable", "")):
                f["pMovCostTable"] = _movement_tables(cl["movement"])
            if cl["terrainBonus"] != _terrain_group(f.get("pTerrainAvoidLookup", "")):
                for kind, field in (("Avo", "pTerrainAvoidLookup"), ("Def", "pTerrainDefenseLookup"),
                                    ("Res", "pTerrainResistanceLookup")):
                    f[field] = f"TerrainTable_{kind}_{cl['terrainBonus']}"
            if self.promotions is not None and cl["promotions"] != self.promotions.get(cl["id"], []):
                if len(cl["promotions"]) > 2:
                    raise GameDataError(f"{cl['id']}: at most two promotions")
                self.promotions[cl["id"]] = list(cl["promotions"])

    def _apply_ranks(self, f: dict[str, str], ranks: dict) -> None:
        old = parse_designated_list(f.get("baseRanks", "{ }"))
        new = {WEAPON_TYPES_REV[t]: r for t, r in ranks.items() if r not in (0, "", None)}
        old_values = {k: _rank_value(_rank_to_json(v)) for k, v in old.items()}
        new_values = {k: _rank_value(v) for k, v in new.items()}
        if old_values != new_values:
            f["baseRanks"] = render_designated_list({k: _rank_to_c(v) for k, v in new.items()})

    def _description(self, fields: dict, key: str = "descTextId") -> str | None:
        """The help text of a character, class or item, as the editors show it (lines, no text codes)."""
        index = _int_field(fields, key)
        if not index or index not in self.texts.messages:
            return None
        return re.sub(r"\[[^\]]*\]", "", self.texts.raw(index).replace("[LF]\n", "\n").replace("[LF]", "\n")).strip()

    def descriptions(self) -> dict[str, dict[str, str]]:
        """The game's help texts: the project keeps only those it changes ("description" in its records)."""
        tables = {"characters": self.characters, "classes": self.classes, "items": self.items}
        return {kind: {e.fields["number"]: text for e in table.entries
                       if (text := self._description(e.original_fields)) is not None}
                for kind, table in tables.items()} | {
            "itemUses": {e.fields["number"]: text for e in self.items.entries
                         if (text := self._description(e.original_fields, "useDescTextId")) is not None}}

    def _set_description(self, fields: dict, record: dict) -> None:
        text = record.get("description")
        if text is None:
            return
        index = _int_field(fields, "descTextId")
        if index and text != self._description(fields):
            self.texts.set_raw(index, name_message(text.strip().replace("\n", "[LF]\n")))

    def add_texts(self, *bodies: str) -> tuple[int, ...]:
        """New short messages; their numbers."""
        return tuple(self.texts.add(name_message(body)) for body in bodies)

    def export_characters(self) -> list[dict]:
        return [self._character_record(entry) for entry in self.characters.entries]

    def free_character_numbers(self) -> list[int]:
        """Entries of the table the game never uses (no constant, loaded by no unit): a new character takes one."""
        used = set()
        for source in self._original_unit_defs.values():
            used |= {parse_int(n) for n in re.findall(r"\.charIndex\s*=\s*(0x[0-9A-Fa-f]+|\d+)", source)}
        numbers = (e.original_fields["number"] for e in self.characters.entries)
        return sorted(n for n in (parse_int(k) for k in numbers if not k.startswith("CHARACTER_"))
                      if 0 < n < 0xFF and n not in used)

    def reusable_characters(self) -> dict[str, int]:
        """The game's named characters a blank project takes out of its list, with their numbers (newchapter.py): all
        but the first lord, the summons and the citizens and arena opponents the engine asks for."""
        constants = self._character_constants()
        return {name: n for name, n in constants.items()
                if 1 < n < GENERIC_CHARACTER_START and "SUMMON" not in name}

    def blank_dropped_characters(self) -> set[str]:
        """The named characters out of a blank project's list, all but the first lord and the generic ones. The game keeps
        its entries: the engine asks for the summons and the arena opponents, but the user has nothing to do with them."""
        return {name for name, n in self._character_constants().items() if n > 1 and name not in NAMED_GENERICS}

    def new_character(self, ally: bool, taken: set[str], reuse: bool = False) -> dict:
        """Sheet of a character to add: the first free entry for an ally (below ALLY_CHARACTER_END) or an enemy
        (from it); `taken` are the ids already in the project; `reuse`: then a game character a blank project dropped."""
        for n in self.free_character_numbers():
            new_id = f"{NEW_CHARACTER_PREFIX}{n:02X}"
            if (n < ALLY_CHARACTER_END) == ally and new_id not in taken:
                entry = next(e for e in self.characters.entries if e.original_fields["number"] != "0"
                             and not e.original_fields["number"].startswith("CHARACTER_")
                             and parse_int(e.original_fields["number"]) == n)
                record = self._character_record(entry)
                record.update(id=new_id, name="", level=1, portraitId=0, weaponRanks={},
                              bases={s: 0 for s in STATS}, affinity=None, abilities=[])
                return record
        if reuse:
            for name, n in sorted(self.reusable_characters().items(), key=lambda kv: kv[1]):
                if (n < ALLY_CHARACTER_END) == ally and name not in taken:
                    entry = next(e for e in self.characters.entries if e.original_fields["number"] == name)
                    record = self._character_record(entry)
                    record.update(name="", description="", level=1, portraitId=0, weaponRanks={}, bases={s: 0 for s in STATS},
                                  affinity=None, abilities=[], convoyAccess=False, canSeize=False)
                    return record
        raise GameDataError("noFreeCharacter")

    def _activate_character(self, new_id: str) -> Entry:
        """Give a free entry the constant of a character the project adds, with its own name and help texts."""
        n = int(new_id.removeprefix(NEW_CHARACTER_PREFIX), 16)
        if n not in self.free_character_numbers():
            raise GameDataError(f"{new_id}: entry 0x{n:02X} is used by the game")
        entry = next(e for e in self.characters.entries if e.fields["number"] != "0"
                     and not e.fields["number"].startswith("CHARACTER_") and parse_int(e.fields["number"]) == n)
        entry.key = f"{new_id} - 1"
        f = entry.fields
        f["number"] = new_id
        f["nameTextId"] = hex(self.texts.add(name_message("")))
        f["descTextId"] = hex(self.texts.add(name_message("")))
        f["sort_order"] = hex(n)   # place in the unit lists; the game's characters use their own number too
        self.new_characters[new_id] = n
        return entry

    def _enum_with(self, rel: str, prefix: str, constants: dict[str, int]) -> str:
        """A constants header with `constants` added at the end of the first enum of `prefix` constants."""
        source = self._read(rel)
        m = re.search(rf"\b{prefix}\w+\s*=", source)
        if m is None:
            raise GameDataError(f"No {prefix} constants in {rel}")
        close = source.index("\n};", m.start())
        lines = "".join(f"\n    {name} = 0x{n:02X}," for name, n in sorted(constants.items(), key=lambda kv: kv[1]))
        return source[:close] + lines + source[close:]

    def _character_record(self, entry: Entry) -> dict:
        f = entry.fields
        ranks = parse_designated_list(f.get("baseRanks", "{ }"))
        return {
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
            # opens the convoy, with the units next to them (ticket 29, see convoy.py)
            "convoyAccess": f["number"] in convoy.DEFAULT_OPENERS,
            # can seize (the route's lord in the game, ticket 37, see seize.py)
            "canSeize": f["number"] in seize.DEFAULT_SEIZERS,
        }

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
                "effectiveness": _effectiveness_name(f.get("pEffectiveness", "")),
                "reservedFor": self._reserved_for(f),
                "monsterWeapon": "IA_LOCK_3" in _split_flags(f.get("attributes", "0")),
                "properties": [key for flag, key in ITEM_PROPERTIES.items() if flag in _split_flags(f.get("attributes", "0"))],
                "weaponEffect": WEAPON_EFFECTS.get(f.get("weaponEffectId", "")),
                "weaponExp": _int_field(f, "weaponExp"),
                "statBonuses": self._item_bonus(f),
            })
        return result

    def _item_bonus(self, fields: dict[str, str]) -> dict[str, int] | None:
        return self.item_bonuses.get(fields.get("pStatBonuses", "").strip().lstrip("&"))

    def spell_items(self) -> list[str]:
        """Items with a spell or projectile of their own, in the game's table."""
        path = self.decomp_dir / SPELL_ASSOC_FILE
        source = path.read_text(encoding="utf-8") if path.is_file() else ""
        return re.findall(r"^[ \t]*SPELL_ASSOC_DATA(?:_WPN|_WPN_MAGIC)?\(\s*(ITEM_\w+)", source, re.MULTILINE)

    # ---------- export (project JSON -> decomp files) ----------

    def apply_characters(self, characters: list[dict]) -> None:
        entries = {e.fields["number"]: e for e in self.characters.entries}
        self.other_dancers |= any(danceanim.ABILITIES & set(ch.get("abilities", []))
                                  and ch.get("class") not in danceanim.DANCER_CLASSES for ch in characters)
        openers = [ch["id"] for ch in characters if ch.get("convoyAccess", ch["id"] in convoy.DEFAULT_OPENERS)]
        if set(openers) != {k for k in entries if k in convoy.DEFAULT_OPENERS}:
            self.convoy_openers = openers
        seizers = [ch["id"] for ch in characters if ch.get("canSeize", ch["id"] in seize.DEFAULT_SEIZERS)]
        if set(seizers) != {k for k in entries if k in seize.DEFAULT_SEIZERS}:
            self.seizers = seizers
        # A free entry a new character takes is no longer edited under its raw number.
        taken = {int(ch["id"].removeprefix(NEW_CHARACTER_PREFIX), 16) for ch in characters
                 if ch["id"].startswith(NEW_CHARACTER_PREFIX)}
        characters = [ch for ch in characters if ch["id"].startswith("CHARACTER_") or parse_int(ch["id"]) not in taken]
        for ch in characters:
            entry = entries.get(ch["id"])
            if entry is None and ch["id"].startswith(NEW_CHARACTER_PREFIX):
                entry = entries[ch["id"]] = self._activate_character(ch["id"])
            if entry is None:
                raise GameDataError(f"Unknown character {ch['id']}")
            f = entry.fields
            self.texts.set_name(_int_field(f, "nameTextId"), ch["name"])
            self._set_description(f, ch)
            if f["defaultClass"] != ch["class"]:
                original_class = entry.original_fields["defaultClass"]
                # In game, chapters load units with an explicit class: defaultClass alone
                # only matters when a chapter leaves it out. Retarget the chapters too.
                self._retarget_unit_class(ch["id"], original_class, ch["class"])
                f["defaultClass"] = ch["class"]
            _set_int(f, "baseLevel", ch["level"])
            old_portrait = _int_field(entry.original_fields, "portraitId")
            if ch["portraitId"] != old_portrait and old_portrait:
                self.portrait_moves[old_portrait] = ch["portraitId"]
            self.character_portraits[ch["id"]] = ch["portraitId"]
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
        # Generic weapon locks are not abilities: FE Maker assigns them from the weapons'
        # "reserved for" lists (_apply_reservations). Older projects may still list them.
        abilities = [a for a in abilities if a not in GENERIC_LOCK_KEYS]
        current = f.get("attributes", "0")
        if set(_abilities(current)) == set(abilities):
            return
        unknown = [a for a in abilities if a not in ABILITIES_REV]
        if unknown:
            raise GameDataError(f"Unknown abilities {unknown}")
        # Keep tokens FE Maker does not know (raw numbers...) and the current generic locks,
        # then known flags in bit order.
        kept = [t for t in _split_flags(current) if t not in ABILITIES or ABILITIES[t] in GENERIC_LOCK_KEYS]
        flags = kept + [flag for flag, key in ABILITIES.items() if key in abilities]
        f["attributes"] = " | ".join(flags) if flags else "0"

    # ---------- weapon reservations ----------

    def _lock_members(self, n: str, original: bool = True) -> frozenset[tuple[str, str]]:
        """Classes and characters having CA_LOCK_n, as ("class"|"character", id) pairs."""
        members = set()
        for kind, parsed in (("class", self.classes), ("character", self.characters)):
            for e in parsed.entries:
                attrs = e.original_fields if original else e.fields
                if f"CA_LOCK_{n}" in _split_flags(attrs.get("attributes", "0")):
                    members.add((kind, e.fields["number"]))
        return frozenset(members)

    def _reserved_for(self, fields: dict[str, str]) -> dict | None:
        """Who may wield an item, from its generic locks; None when unrestricted."""
        needed = [n for n in GENERIC_LOCKS if f"IA_LOCK_{n}" in _split_flags(fields.get("attributes", "0"))]
        if not needed:
            return None
        members = set.intersection(*(set(self._lock_members(n)) for n in needed))
        return {
            "characters": [e.fields["number"] for e in self.characters.entries if ("character", e.fields["number"]) in members],
            "classes": [e.fields["number"] for e in self.classes.entries if ("class", e.fields["number"]) in members],
        }

    def _apply_reservations(self, items: list[dict]) -> None:
        """Give each "reserved for" group a generic lock bit, then set the item flags and the
        CA_LOCK flags of the classes and characters of the group.

        Groups identical to an original lock keep its bit, so an unmodified project is
        unchanged. The engine checks a lock against the character's AND the class's flags.
        """
        if not any("reservedFor" in it for it in items):
            return  # project from before reservations existed: keep the original locks
        entries = {e.fields["number"]: e for e in self.items.entries}
        original_sets = {n: self._lock_members(n) for n in GENERIC_LOCKS}
        changed: dict[str, frozenset] = {}  # item id -> new group (frozenset() = nobody)
        unrestricted: list[str] = []
        for it in items:
            if "reservedFor" not in it:
                continue
            f = entries[it["id"]].fields
            reserved = it["reservedFor"]
            if reserved == self._reserved_for(f):
                continue  # as in the original game (the Mani Katti is reserved for nobody there)
            if reserved is not None and not reserved.get("characters") and not reserved.get("classes"):
                # Reserved for nobody would make the weapon unusable: an empty list means no restriction.
                reserved = None
            if reserved == self._reserved_for(f):
                continue
            if reserved is None:
                unrestricted.append(it["id"])
                continue
            changed[it["id"]] = frozenset(
                [("character", c) for c in it["reservedFor"].get("characters", [])]
                + [("class", c) for c in it["reservedFor"].get("classes", [])]
            )
        if not changed and not unrestricted:
            return

        # Bits still used by unchanged reserved items keep their meaning.
        kept_bits = set()
        for it in items:
            if it["id"] not in changed and it["id"] not in unrestricted:
                attrs = _split_flags(entries[it["id"]].fields.get("attributes", "0"))
                kept_bits |= {n for n in GENERIC_LOCKS if f"IA_LOCK_{n}" in attrs}
        bit_of: dict[frozenset, str] = {}
        for group in dict.fromkeys(changed.values()):
            same = [n for n in GENERIC_LOCKS if original_sets[n] == group]
            if same:
                bit_of[group] = same[0]
                continue
            free = [n for n in LOCK_PREFERENCE if n not in kept_bits and n not in bit_of.values()]
            if not free:
                raise GameDataError("Too many different weapon reservations: the engine has 6 weapon locks")
            bit_of[group] = free[0]

        # Items: replace their generic lock flags.
        for item_id in list(changed) + unrestricted:
            f = entries[item_id].fields
            tokens = [t for t in _split_flags(f.get("attributes", "0")) if not re.fullmatch(r"IA_LOCK_[124567]", t)]
            if item_id in changed:
                tokens.append(f"IA_LOCK_{bit_of[changed[item_id]]}")
            f["attributes"] = " | ".join(tokens) if tokens else "0"

        # Classes and characters: membership of each (re)assigned bit.
        for group, n in bit_of.items():
            if original_sets[n] == group:
                continue
            for kind, parsed in (("class", self.classes), ("character", self.characters)):
                for e in parsed.entries:
                    flag = f"CA_LOCK_{n}"
                    tokens = _split_flags(e.fields.get("attributes", "0"))
                    member = (kind, e.fields["number"]) in group
                    if member and flag not in tokens:
                        tokens.append(flag)
                    elif not member and flag in tokens:
                        tokens.remove(flag)
                    else:
                        continue
                    # Rewrite in bit order (known flags), unknown tokens first.
                    known = {t for t in tokens if t in ABILITIES}
                    ordered = [t for t in tokens if t not in ABILITIES] + [t for t in ABILITIES if t in known]
                    e.fields["attributes"] = " | ".join(ordered) if ordered else "0"

    def last_item_number(self) -> int:
        """Number of the game's last item (its table goes up to it)."""
        if not (self.decomp_dir / ITEM_CONSTANTS_FILE).is_file():
            return len(self.items.entries) - 1
        return max(int(v, 0) for v in re.findall(r"\bITEM_\w+\s*=\s*(0x[0-9A-Fa-f]+|\d+)", self._read(ITEM_CONSTANTS_FILE)))

    def new_item(self, model: str, taken: set[str]) -> dict:
        """Sheet of a weapon to add, copying `model`; `taken` are the ids already in the project."""
        record = next((r for r in self.export_items() if r["id"] == model), None)
        if record is None or record["weaponType"] not in set(RANKABLE_TYPES) - {"staff"}:
            raise GameDataError("notAWeapon")
        for n in range(self.last_item_number() + 1, LAST_ITEM_NUMBER + 1):
            new_id = f"{NEW_ITEM_PREFIX}{n:02X}"
            if new_id not in taken:
                return {**record, "id": new_id, "name": "", "model": model}
        raise GameDataError("noFreeItem")

    def _add_item(self, new_id: str, model: str | None) -> Entry:
        """A weapon the project adds: an entry after the game's ones, with the fields of its model."""
        n = int(new_id.removeprefix(NEW_ITEM_PREFIX), 16)
        if not self.last_item_number() < n <= LAST_ITEM_NUMBER:
            raise GameDataError(f"{new_id}: not after the game's items")
        source = next((e for e in self.items.entries if e.original_fields and e.fields["number"] == model), None)
        if source is None:
            raise GameDataError(f"{new_id}: unknown model weapon {model}")
        fields = dict(source.original_fields)
        fields["number"] = new_id
        fields["nameTextId"] = hex(self.texts.add(name_message("")))
        if "descTextId" in fields:   # its own help text, starting as the model's
            fields["descTextId"] = hex(self.texts.add(self.texts.raw(_int_field(source.original_fields, "descTextId"))))
        close = self.items.source.rindex("};")
        start = self.items.source.rfind("\n", 0, close) + 1
        key = re.sub(rf"\b{re.escape(model)}\b", new_id, source.key)   # "CLASS_X - 1" in the class table
        entry = Entry(key=key, fields=fields, start=start, end=start, indent=source.indent)
        self.items.entries.append(entry)
        self.new_items[new_id] = (n, model)
        return entry

    def _with_new_item_copies(self, out: dict[str, str | bytes]) -> None:
        """Constants of the weapons the project adds, and the copies of their models' spells and own animations."""
        news = sorted(self.new_items.items(), key=lambda kv: kv[1][0])
        if (self.decomp_dir / ITEM_CONSTANTS_FILE).is_file():
            out[ITEM_CONSTANTS_FILE] = self._enum_with(ITEM_CONSTANTS_FILE, "ITEM_", {i: n for i, (n, _m) in news})
        for rel, pattern in ((SPELL_ASSOC_FILE, r"^[ \t]*SPELL_ASSOC_DATA\w*\(\s*{model}\s*,.*\n"),
                             (BATTLE_ANIM_CONF_FILE, r"^[ \t]*\{{\s*\.wtype\s*=\s*{model}\s*,\s*\.index\s*=\s*\w+\s*,\s*\}},\n")):
            if not (self.decomp_dir / rel).is_file():
                continue
            text = out.get(rel) or self._read(rel)
            if isinstance(text, bytes):
                continue
            for new_id, (_n, model) in news:
                text = re.sub(pattern.format(model=re.escape(model)),
                              lambda m, i=new_id, mo=model: m.group(0) + re.sub(rf"\b{re.escape(mo)}\b", i, m.group(0)),
                              text, flags=re.MULTILINE)
            if text != self._read(rel):
                out[rel] = text

    def apply_items(self, items: list[dict]) -> None:
        entries = {e.fields["number"]: e for e in self.items.entries}
        use_texts = Counter(e.original_fields.get("useDescTextId") for e in self.items.entries if e.original_fields)
        for it in items:
            entry = entries.get(it["id"])
            if entry is None and it["id"].startswith(NEW_ITEM_PREFIX):
                entry = entries[it["id"]] = self._add_item(it["id"], it.get("model"))
            if entry is None:
                raise GameDataError(f"Unknown item {it['id']}")
            f = entry.fields
            self.texts.set_name(_int_field(f, "nameTextId"), it["name"])
            self._set_description(f, it)
            self._set_use_text(f, it, use_texts)
            wtype = WEAPON_TYPES_REV.get(it["weaponType"], it["weaponType"])
            if f.get("weaponType") != wtype:
                f["weaponType"] = wtype
                _set_flags(f, _type_flags(it["weaponType"]), ("IA_WEAPON", "IA_STAFF"))
            for key, field in (("might", "might"), ("hit", "hit"), ("crit", "crit"), ("weight", "weight"),
                               ("uses", "maxUses"), ("pricePerUse", "costPerUse"), ("iconId", "iconId")):
                _set_int(f, field, it[key])
            encoded = (it["range"]["min"] << 4) | it["range"]["max"]
            if encoded != _int_field(f, "encodedRange"):
                self.other_ranges = self.other_ranges or encoded not in weaponrange.GAME_RANGES
            _set_int(f, "encodedRange", encoded)
            if "effectiveness" in it and it["effectiveness"] != _effectiveness_name(f.get("pEffectiveness", "")):
                if it["effectiveness"] is None:
                    f["pEffectiveness"] = "NULL"
                elif self.effectiveness is not None and it["effectiveness"] not in self.effectiveness:
                    raise GameDataError(f"Unknown effectiveness list {it['effectiveness']}")
                else:
                    f["pEffectiveness"] = it["effectiveness"]
            rank = it["weaponRank"]
            current = f.get("weaponRank", "0")
            if _rank_value(rank if isinstance(rank, (str, int)) else 0) != _rank_value(
                _rank_to_json(current) if current in WEAPON_RANKS else parse_int(current)
            ):
                f["weaponRank"] = _rank_to_c(rank)
            if "monsterWeapon" in it:
                _set_flags(f, ["IA_LOCK_3"] if it["monsterWeapon"] else [], ("IA_LOCK_3",))
            if "properties" in it:
                _set_flags(f, [flag for flag, key in ITEM_PROPERTIES.items() if key in it["properties"]], tuple(ITEM_PROPERTIES))
            if "weaponEffect" in it and it["weaponEffect"] != WEAPON_EFFECTS.get(f.get("weaponEffectId", "")):
                f["weaponEffectId"] = WEAPON_EFFECTS_REV.get(it["weaponEffect"], "WPN_EFFECT_NONE")
            if "weaponExp" in it:
                _set_int(f, "weaponExp", it["weaponExp"])
            if "statBonuses" in it:
                self._set_item_bonus(f, it["statBonuses"])
            if it.get("spellFrom"):
                self.spell_choices[it["id"]] = it["spellFrom"]
        self._apply_reservations(items)

    def _set_use_text(self, fields: dict, record: dict, use_texts: Counter) -> None:
        """The text of the Use screen; items sharing a message of the game get one of their own."""
        text = record.get("useDescription")
        if text is None or text == self._description(fields, "useDescTextId"):
            return
        message = name_message(text.strip().replace("\n", "[LF]\n"))
        index = _int_field(fields, "useDescTextId")
        if index and use_texts[fields["useDescTextId"]] == 1:
            self.texts.set_raw(index, message)
        elif index or text.strip():
            fields["useDescTextId"] = hex(self.texts.add(message))

    def _set_item_bonus(self, fields: dict[str, str], bonuses: dict[str, int] | None) -> None:
        wanted = {stat: value for stat, value in (bonuses or {}).items() if value}
        if wanted == (self._item_bonus(fields) or {}):
            return
        if not wanted:
            fields["pStatBonuses"] = "NULL"
            return
        name = f"{NEW_BONUS_PREFIX}{fields['number']}"
        self.item_bonuses[name] = wanted
        fields["pStatBonuses"] = f"&{name}"

    def _with_item_bonuses(self, out: dict[str, str | bytes]) -> None:
        """The stat bonuses the project sets, written above the item table that points to them."""
        table = "CONST_DATA struct ItemData gItemData[]"
        rows = "".join(f"CONST_DATA struct ItemStatBonuses {name} = {{\n"
                       + "".join(f"\t.{stat}Bonus = {bonus[stat]},\n" for stat in ITEM_BONUS_STATS if stat in bonus) + "};\n\n"
                       for name, bonus in self.item_bonuses.items() if name.startswith(NEW_BONUS_PREFIX))
        if rows:
            out[ITEMS_FILE] = out[ITEMS_FILE].replace(table, rows + table, 1)

    def casts_at_range(self, class_id: str, model: str | None, item: dict, animations: dict | None,
                       assets_dir: Path | None) -> bool:
        """The class's battle animation for this weapon strikes from afar, as `GetBattleAnimationId` picks it:
        the item's own line first, then its type's. A class the project adds has its model's animations."""
        changed = banim_import.with_groups(((animations or {}).get("classes") or {}).get(class_id, {}))
        anim = changed.get(item["id"], changed.get(item["weaponType"]))
        if isinstance(anim, str):
            key = anim.removeprefix("new:")
            return assets_dir is None or banim.casts_at_range(assets_dir / "animations" / key, banim_import.symbol_of(key))
        entry = next((e for e in self.classes.entries if e.fields["number"] == (model or class_id)), None)
        conf = banim.configs(self.decomp_dir).get(entry.fields.get("pBattleAnimDef", "").lstrip("&").strip()) if entry else None
        if anim is None:
            wtype = WEAPON_TYPES_REV.get(item["weaponType"])
            lines = {d["weapon"]: d["number"] for d in conf or []}
            anim = lines.get(item["id"], lines.get(wtype))
        table = banim.table(self.decomp_dir)
        return not anim or anim > len(table) or banim.casts_at_range(self.decomp_dir, table[anim - 1].symbol)

    def _with_animation_sounds(self, out: dict[str, str | bytes]) -> None:
        if any(rel.endswith(".s") and banim_import.has_sounds(text) for rel, text in self.asset_files.items()):
            out.update(banim_import.sound_files(self.decomp_dir))

    def _with_spell_choices(self, out: dict[str, str | bytes]) -> None:
        """Items taking another item's spell: their row of the spell table becomes a copy of its row."""
        if not self.spell_choices or not (self.decomp_dir / SPELL_ASSOC_FILE).is_file():
            return
        text = out.get(SPELL_ASSOC_FILE) or self._read(SPELL_ASSOC_FILE)

        def row(item: str) -> re.Match | None:
            return re.search(rf"^[ \t]*SPELL_ASSOC_DATA\w*\(\s*{re.escape(item)}\s*[,)].*\n", text, re.MULTILINE)

        for item, source in self.spell_choices.items():
            model = row(source)
            if model is None or item == source:
                continue
            copy = re.sub(rf"\b{re.escape(source)}\b", item, model.group(0))
            own = row(item)
            at = (own.start(), own.end()) if own else (model.end(), model.end())
            text = text[:at[0]] + copy + text[at[1]:]
        if text != self._read(SPELL_ASSOC_FILE):
            out[SPELL_ASSOC_FILE] = text

    def _follow_portraits(self) -> None:
        """A character given another portrait keeps it in the dialogues: the messages showing their
        original portrait ([LoadFace][FID_Gilliam]) show the new one, unless another character
        still has the original portrait (ticket 36)."""
        if not self.portrait_moves:
            return
        defs = self.decomp_dir / dialogues.TEXT_DEFS_FILE
        faces = dialogues.read_faces(defs.read_text(encoding="utf-8")) if defs.is_file() else {}
        replace: dict[str, str] = {}
        for old, new in self.portrait_moves.items():
            if old in self.character_portraits.values():
                continue
            if portraits.is_new(self.decomp_dir, new):
                target = portraits.face_code(new)
            else:
                target = next((fid for fid, pid in faces.items() if pid == new), None)
            if target is None:
                continue
            for fid, pid in faces.items():
                if pid == old:
                    replace[f"[LoadFace][{fid}]"] = f"[LoadFace][{target}]"
        self.portrait_moves = {}
        if not replace:
            return
        pattern = re.compile("|".join(re.escape(k) for k in replace))
        for index in [*self.texts.messages, *self.texts.added]:
            body = self.texts.raw(index)
            new_body = pattern.sub(lambda m: replace[m.group(0)], body)
            if new_body == body:
                continue
            if index in self.texts.added:
                self.texts.added[index] = new_body
            else:
                self.texts.set_raw(index, new_body)

    def changed_files(self) -> dict[str, str | bytes]:
        """Decomp-relative path -> new content (text, or bytes for binary files), for files that
        differ from the decomp."""
        self._follow_portraits()
        out: dict[str, str | bytes] = {**self.map_files, **self.asset_files}
        for rel, parsed in ((CHARACTERS_FILE, self.characters), (ITEMS_FILE, self.items), (CLASSES_FILE, self.classes)):
            if any(e.fields != e.original_fields for e in parsed.entries):
                out[rel] = render_array(parsed)
        if self.new_support_blocks:   # SupportData FE Maker adds are not declared in bmreliance.h
            externs = "".join(f"extern CONST_DATA struct SupportData {n};\n" for n in self.new_support_blocks)
            include = '#include "bmreliance.h"\n'
            out[CHARACTERS_FILE] = out[CHARACTERS_FILE].replace(include, include + externs, 1)
        if self.new_anim_confs:   # AnimConf arrays FE Maker adds are not declared in ekrbattle.h
            externs = "".join(f"extern CONST_DATA struct BattleAnimDef {n}[];\n" for n in self.new_anim_confs)
            include = '#include "ekrbattle.h"\n'
            out[CLASSES_FILE] = out[CLASSES_FILE].replace(include, include + externs, 1)
        if self.new_characters:
            out[CHARACTER_CONSTANTS_FILE] = self._enum_with(CHARACTER_CONSTANTS_FILE, "CHARACTER_", self.new_characters)
        if self.support_source is not None:
            out[supports.SUPPORTS_FILE] = self.support_source
        if self.support_talks is not None:
            out[supports.TALKS_FILE] = self.support_talks
        chars: set[str] = set()
        if self.texts.edits or self.texts.added:
            out[TEXTS_FILE] = self.texts.render()
            chars = self.texts.special_chars()
        if chars or self.new_faces:
            defs = self._read(dialogues.TEXT_DEFS_FILE)
            if chars:
                defs = textdefs_with(defs, chars)
            if self.new_faces:
                defs = portraits.textdefs_with_faces(defs, self.new_faces)
            out[dialogues.TEXT_DEFS_FILE] = defs
        for rel, source in self.unit_defs.items():
            if source != self._original_unit_defs[rel]:
                out[rel] = source
        if self.convoy_openers is not None:
            out[convoy.MENU_FILE] = convoy.with_openers(self._read(convoy.MENU_FILE), self.convoy_openers)
        if self.seizers is not None:
            out[seize.FILE] = seize.with_seizers(self._read(seize.FILE), self.seizers)
        if chapterflags.uses_late_flags(list(self.event_sources.values())) or self._new_quote_flags:
            out[chapterflags.FILE] = chapterflags.with_late_flags(self._read(chapterflags.FILE))
        if unitstats.uses(list(self.event_sources.values())):
            out[unitstats.FILE] = unitstats.with_function(self._read(unitstats.FILE))
            out[unitstats.HEADER] = unitstats.with_declaration(self._read(unitstats.HEADER))
        if self.other_dancers:
            out[danceanim.FILE] = danceanim.with_guard(self._read(danceanim.FILE))
        if self.other_ranges:
            out[weaponrange.ITEM_FILE] = weaponrange.with_item_ranges(self._read(weaponrange.ITEM_FILE))
            out[weaponrange.RANGE_MAP_FILE] = weaponrange.with_range_map(self._read(weaponrange.RANGE_MAP_FILE))
        if self.no_convoy is not None:
            out[convoy.CONTAINER_FILE] = convoy.with_chapters(self._read(convoy.CONTAINER_FILE), self.no_convoy)
        if self.new_classes:
            self._with_new_class_files(out)
            self._new_class_promotions()
        if self.new_classes or self.map_sprites:
            self._with_moving_sprites(out)
        if self.map_sprite_ids:
            self._with_map_sprite_files(out)
        if self.promotions is not None and self.promotions != self._original_promotions:
            out[combat.PROMOTIONS_FILE] = combat.render_promotions(self._sources[combat.PROMOTIONS_FILE], self.promotions)
        if self.effectiveness is not None and self.effectiveness != self._original_effectiveness:
            out[combat.EFFECTIVENESS_FILE] = combat.render_effectiveness(
                self._sources[combat.EFFECTIVENESS_FILE], self.effectiveness)
        if self.triangle is not None and self.triangle != self._original_triangle:
            out[combat.TRIANGLE_FILE] = combat.render_triangle(self._sources[combat.TRIANGLE_FILE], self.triangle)
        for rel, source in self.event_sources.items():
            if source != self._original_event_sources[rel]:
                out[rel] = source
        if self.chapter_settings is not None:
            settings = json.dumps(self.chapter_settings, indent=2)  # same layout as the decomp's file
            if settings != self._settings_raw:
                out[maps.CHAPTER_SETTINGS_FILE] = settings
            if self.defeat_talks != self._original_defeat_talks:
                out[objectives.DEFEAT_TALK_FILE] = self.defeat_talks
        if self.new_items:
            self._with_new_item_copies(out)
        self._with_item_bonuses(out)
        self._with_spell_choices(out)
        self._with_animation_sounds(out)
        return out

    # ---------- assets ----------

    def item_icon_files(self) -> list[str]:
        """Icon PNG paths (decomp-relative), indexed by iconId."""
        source = self._read(ITEM_ICONS_FILE)
        return [m.replace(".4bpp", ".png") for m in re.findall(r'\.incbin\s+"([^"]+\.4bpp)"', source)]
