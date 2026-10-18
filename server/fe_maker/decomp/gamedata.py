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
        return [
            {
                "id": f["number"],
                "name": self._text_name(f),
                "bases": {s: _int_field(f, "base" + STAT_SUFFIX[s]) for s in STATS if s != "lck"} | {"lck": 0},
                "mov": _int_field(f, "baseMov"),
                "animatedWeapons": self.animated_weapons.get(f["number"], []),
                "usedInGame": f["number"] in used,
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
