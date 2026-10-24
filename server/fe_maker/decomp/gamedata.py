"""Convert characters, items and classes between the decomp and FE Maker's JSON.

Project JSON exposes player-facing fields with readable names. Every other
field of the C struct is kept untouched under "engine" so it can be written
back exactly.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from . import combat, dialogues, events, fonts, mapobjects, maps, objectives, portraits, quotes, supports, tileedit, units
from .cparse import (
    parse_array,
    parse_designated_list,
    parse_int,
    render_array,
    render_designated_list,
)
from .texts import TextFile, textdefs_with

CHARACTERS_FILE = "src/data_characters.c"
CLASSES_FILE = "src/data_classes.c"
ITEMS_FILE = "src/data_items.c"
TEXTS_FILE = "texts/texts.txt"
ITEM_ICONS_FILE = "data/data_item_icon.s"
BATTLE_ANIM_CONF_FILE = "src/data_banimconf.c"
BATTLE_ANIM_TABLE_FILE = "src/banim_data.c"
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
        self.texts = TextFile(self._read(TEXTS_FILE))
        self.unit_defs: dict[str, str] = {}
        for pattern in UNIT_DEF_FILES:
            for path in sorted(decomp_dir.glob(pattern)):
                rel = path.relative_to(decomp_dir).as_posix()
                self.unit_defs[rel] = self._read(rel)
        self._original_unit_defs = dict(self.unit_defs)
        # Imported graphics (decomp-relative path -> content), see apply_portraits
        self.asset_files: dict[str, bytes | str] = {}
        # Ids of the portraits the project adds (their text codes go to textdefs.txt)
        self.new_faces: list[int] = []
        # Supports edited in the project (see _apply_supports)
        self.support_source: str | None = None
        self.support_talks: str | None = None
        self.new_support_blocks: list[str] = []
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
        "newGroups" {name: {"chapter", "turn", "phase"}}, their units in "unitGroups"."""
        return {"unitGroups": {}, "objectives": {}}

    def apply_chapters(self, chapters: dict) -> None:
        new_groups = chapters.get("newGroups", {})
        edits = {k: v for k, v in chapters.get("unitGroups", {}).items() if k not in new_groups}
        if edits:
            self.unit_defs = units.apply_unit_groups(self.unit_defs, edits, units.ai_macros(self.decomp_dir))
        for name, meta in new_groups.items():
            group_units = chapters.get("unitGroups", {}).get(name, [])
            if group_units:
                self._add_reinforcements(name, meta, group_units)
        for index, objective in chapters.get("objectives", {}).items():
            self.apply_objective(int(index), objective)

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
        if not painted and not changes and not settings and not tilesets and not palettes and not bases:
            return
        known = maps.layouts(self.decomp_dir)
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
            objects = mapobjects.map_objects(self.decomp_dir, layout_id, rows, explicit, settings.get(layout_id),
                                             terrain, assets)
            autos = [o["auto"] for o in objects if o["auto"]]
            if json_rel and (change_list is not None or autos):
                if map_change_source is None:
                    map_change_source = original_source = self._read(maps.MAP_CHANGE_FILE)
                files, map_change_source = maps.write_changes(
                    self.decomp_dir, json_rel, list(explicit) + autos, map_change_source)
                self.map_files.update(files)
            self._apply_map_events(layout_id, rows, objects, settings.get(layout_id, {}), terrain)
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
                          edited_terrain: bytes | None = None) -> None:
        """Location events of the chapters using a layout: events added for new villages, houses,
        chests and doors (or set in the project), removed where the painting erased the object."""
        layout = maps.layouts(self.decomp_dir)[layout_id]
        _metatiles, original_terrain = maps.read_config(layout["assets"].config)
        original = self._original_rows(layout_id)

        def kind_at(grid, x, y):
            terrain = original_terrain if grid is original else (edited_terrain or original_terrain)
            if 0 <= y < len(grid) and 0 <= x < len(grid[0]) and grid[y][x] < len(terrain):
                return mapobjects.KINDS.get(terrain[grid[y][x]])
            return None

        erased = any(kind_at(original, x, y) in mapobjects.EVENT_KINDS and kind_at(rows, x, y) != kind_at(original, x, y)
                     for y in range(len(original)) for x in range(len(original[0])))
        added = any(o["new"] and o["kind"] in mapobjects.EVENT_KINDS for o in objects)
        if not (erased or added or settings):
            return
        self._load_chapter_events()

        done = set()
        for index in layout["chapters"]:
            found = self._location_list(index)
            if not found or found in done:
                continue
            done.add(found)
            rel, start, end = found
            source = self.event_sources[rel]
            body = source[start:end]
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
                        s.get("face") if s.get("face") in mapobjects.FACES else "FID_VillagerOldMan", s.get("text") or "...",
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
        new_quotes = [q for q in data.get("quotes", []) if q.get("a") and q.get("kind") != "talk"]
        talks = [q for q in data.get("quotes", []) if q.get("kind") == "talk" and q.get("a") and q.get("b")]
        for n, talk in enumerate(talks):
            self._add_talk(n, talk)
        turns = [q for q in data.get("quotes", []) if q.get("kind") == "turn"]
        for n, scene in enumerate(turns):
            self._add_turn_scene(n, scene)
        if data.get("scripts"):
            self._apply_scripts(data["scripts"])
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
                flag = next(n for n in range(quotes.FIRST_FLAG, 70) if (chapter, n) not in used)
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
        index = int(meta.get("chapter", 0))
        found = self._event_list(index, "turnBasedEvents")
        turn = max(1, int(meta.get("turn", 1)))
        faction = dialogues.FACTIONS.get(meta.get("phase", "enemy"), "FACTION_RED")
        flag = self._free_flag(found[0], dialogues.TALK_FIRST_FLAG)
        script_name = f"EventScr_FEM_Load_{name[len('UnitDef_FEM_'):]}"
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

    def script_commands(self, name: str) -> list[dict]:
        found = self.find_script(name)
        if found is None:
            raise GameDataError(f"Unknown event script {name}")
        rel, start, end = found
        return events.parse_script(self.event_sources[rel][start:end])

    def _apply_scripts(self, scripts: dict[str, list[dict]]) -> None:
        """Scripts edited in the visual editor replace the original ones (only when they differ)."""
        for name, commands in sorted(scripts.items()):
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
            return {}
        return {name: int(value, 0) for name, value in
                re.findall(r"\b(CHARACTER_\w+)\s*=\s*(0x[0-9A-Fa-f]+|\d+)", self._read("include/constants/characters.h"))}

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

    def apply_classes(self, classes: list[dict]) -> None:
        entries = {e.fields["number"]: e for e in self.classes.entries}
        for cl in classes:
            entry = entries.get(cl["id"])
            if entry is None:
                raise GameDataError(f"Unknown class {cl['id']}")
            f = entry.fields
            self.texts.set_name(_int_field(f, "nameTextId"), cl["name"])
            for s in CLASS_STATS:
                _set_int(f, "base" + STAT_SUFFIX[s], cl["bases"][s], signed=True)
                _set_int(f, "max" + STAT_SUFFIX[s], cl["maxes"][s], signed=True)
            _set_int(f, "baseMov", cl["mov"], signed=True)
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
                "effectiveness": _effectiveness_name(f.get("pEffectiveness", "")),
                "reservedFor": self._reserved_for(f),
                "monsterWeapon": "IA_LOCK_3" in _split_flags(f.get("attributes", "0")),
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
                tokens = _split_flags(f.get("attributes", "0"))
                if it["monsterWeapon"] and "IA_LOCK_3" not in tokens:
                    f["attributes"] = " | ".join(tokens + ["IA_LOCK_3"])
                elif not it["monsterWeapon"] and "IA_LOCK_3" in tokens:
                    tokens.remove("IA_LOCK_3")
                    f["attributes"] = " | ".join(tokens) if tokens else "0"
        self._apply_reservations(items)

    def changed_files(self) -> dict[str, str | bytes]:
        """Decomp-relative path -> new content (text, or bytes for binary files), for files that
        differ from the decomp."""
        out: dict[str, str | bytes] = {**self.map_files, **self.asset_files}
        for rel, parsed in ((CHARACTERS_FILE, self.characters), (ITEMS_FILE, self.items), (CLASSES_FILE, self.classes)):
            if any(e.fields != e.original_fields for e in parsed.entries):
                out[rel] = render_array(parsed)
        if self.new_support_blocks:   # SupportData FE Maker adds are not declared in bmreliance.h
            externs = "".join(f"extern CONST_DATA struct SupportData {n};\n" for n in self.new_support_blocks)
            include = '#include "bmreliance.h"\n'
            out[CHARACTERS_FILE] = out[CHARACTERS_FILE].replace(include, include + externs, 1)
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
        return out

    # ---------- assets ----------

    def item_icon_files(self) -> list[str]:
        """Icon PNG paths (decomp-relative), indexed by iconId."""
        source = self._read(ITEM_ICONS_FILE)
        return [m.replace(".4bpp", ".png") for m in re.findall(r'\.incbin\s+"([^"]+\.4bpp)"', source)]
