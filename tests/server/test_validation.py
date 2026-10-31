from fe_maker.decomp.gamedata import DecompData
from fe_maker.validation import validate


def _codes(problems):
    return {(p.id, p.field, p.code) for p in problems}


def test_original_data_is_valid(decomp_dir):
    d = DecompData(decomp_dir)
    assert [p for p in validate(d.export_characters(), d.export_items(), d) if p.severity == "error"] == []


def test_detects_problems(decomp_dir):
    d = DecompData(decomp_dir)
    chars, items = d.export_characters(), d.export_items()
    chars[0]["bases"]["hp"] = 200
    chars[0]["class"] = "CLASS_NOPE"
    chars[1]["name"] = ""
    chars.append(dict(chars[0]))
    items[0]["range"] = {"min": 3, "max": 1}
    items[0]["iconId"] = 99
    codes = _codes(validate(chars, items, d))
    assert ("CHARACTER_TESTHERO", "bases.hp", "outOfRange") in codes
    assert ("CHARACTER_TESTHERO", "class", "unknownClass") in codes
    assert ("CHARACTER_TESTRIVAL", "name", "nameEmpty") in codes
    assert ("CHARACTER_TESTHERO", "id", "duplicateId") in codes
    assert ("ITEM_TESTBLADE", "range", "rangeInverted") in codes
    assert ("ITEM_TESTBLADE", "iconId", "outOfRange") in codes


def test_weapon_rank_without_battle_animation(decomp_dir):
    d = DecompData(decomp_dir)
    chars = d.export_characters()
    chars[0]["weaponRanks"]["lance"] = "C"  # the lord class only animates swords
    codes = _codes(validate(chars, d.export_items(), d))
    assert ("CHARACTER_TESTHERO", "weaponRanks.lance", "noBattleAnimation") in codes
    lord = chars[0]["class"]
    # a lance animation the project gave the lord class (ticket 50), without changing the game's data
    codes = _codes(validate(chars, d.export_items(), d, animations={"classes": {lord: {"lance": "new:1"}}}))
    assert not any(c[2] == "noBattleAnimation" for c in codes)
    assert "lance" not in d.animated_weapons.get(lord, [])
    assert ("CHARACTER_TESTHERO", "weaponRanks.lance", "noBattleAnimation") in _codes(validate(chars, d.export_items(), d))
    chars[0]["class"] = "CLASS_TESTKNIGHT"  # the knight animates lances
    codes = _codes(validate(chars, d.export_items(), d))
    assert not any(c[2] == "noBattleAnimation" for c in codes)


def test_characters_the_font_lacks_are_an_error(decomp_dir):
    d = DecompData(decomp_dir)
    chars = d.export_characters()
    chars[0]["name"] = "Héro"  # the test font has é
    assert not [p for p in validate(chars, d.export_items(), d) if p.code == "unsupportedChars"]
    chars[0]["name"] = "Hèro☃"
    problems = [p for p in validate(chars, d.export_items(), d) if p.code == "unsupportedChars"]
    assert problems and problems[0].severity == "error" and problems[0].params["chars"] == "è ☃"


def test_unused_class_is_a_warning(decomp_dir):
    d = DecompData(decomp_dir)
    chars = d.export_characters()
    chars[0]["class"] = "CLASS_TESTUNUSED"
    chars[0]["weaponRanks"] = {}
    problems = [p for p in validate(chars, d.export_items(), d) if p.code == "unusedClass"]
    assert problems and problems[0].severity == "warning"


def test_chapter_unit_problems(decomp_dir):
    from fe_maker.decomp import units

    d = DecompData(decomp_dir)
    group = [dict(u) for u in units.read_unit_groups(decomp_dir)["UnitDef_TestChapter"].units]
    group[1]["endX"], group[1]["endY"] = group[0]["endX"], group[0]["endY"]
    group[2]["character"] = "0"
    group += [dict(group[0], slot=None, copyOf=0, side="ally", endX=n, endY=9) for n in range(21)]
    codes = _codes(validate(d.export_characters(), d.export_items(), d, chapters={"unitGroups": {"UnitDef_TestChapter": group}}))
    assert ("UnitDef_TestChapter#1", "position", "sameTile") in codes
    assert ("UnitDef_TestChapter#2", "character", "noCharacter") in codes
    assert ("UnitDef_TestChapter#", "side", "tooManyUnits") in codes


def test_ai_outside_engine_tables(decomp_dir):
    from fe_maker.decomp import units

    d = DecompData(decomp_dir)
    group = [dict(u) for u in units.read_unit_groups(decomp_dir)["UnitDef_TestChapter"].units]
    group[0]["ai"] = [0x15, 0x0, 0x0, 0x0]
    group[1]["ai"] = [0x0, 0x3, 0x5, 0x0]  # recovery setting 5: past the 5-entry threshold table
    group[2]["ai"] = [0x14, 0x12, 0xfc, 0x20]
    codes = _codes(validate(d.export_characters(), d.export_items(), d, chapters={"unitGroups": {"UnitDef_TestChapter": group}}))
    assert ("UnitDef_TestChapter#0", "ai", "badAi") in codes
    assert ("UnitDef_TestChapter#1", "ai", "badAi") in codes
    assert ("UnitDef_TestChapter#2", "ai", "badAi") not in codes


def test_objective_problems(decomp_dir):
    d = DecompData(decomp_dir)
    objectives = {
        "0": {"type": "seize", "seize": [], "statusText": "Prendre le château ☃"},
        "1": {"type": "defense", "turns": 0, "statusText": "Survive for 12 turns and more\nand more\nand more"},
        "2": {"type": "defeat_all", "statusText": "Defeat all enemies"},
    }
    codes = _codes(validate(d.export_characters(), d.export_items(), d, chapters={"unitGroups": {}, "objectives": objectives}))
    assert ("objective#0", "seize", "noSeizeTile") in codes
    assert ("objective#0", "statusText", "unsupportedChars") in codes
    assert ("objective#1", "turns", "outOfRange") in codes
    assert ("objective#1", "statusText", "objectiveTextTooLong") in codes
    assert not [c for c in codes if c[0] == "objective#2"]


def test_painted_maps_are_checked(decomp_dir):
    from fe_maker.validation import _validate_maps, map_size_problem

    good = [[5] * 15 for _ in range(10)]
    problems = []
    _validate_maps(problems, {"layouts": {
        "A": {"rows": [[0, 1], [2]]},
        "B": {"rows": [[0] * 14 + [1024]] + good[1:]},
        "C": {"rows": good},
        "D": {"rows": [[5] * 15 for _ in range(9)]},
    }})
    assert [(p.id, p.code) for p in problems] == [("A", "badLayout"), ("B", "badTile"), ("D", "mapTooSmall")]
    # Engine buffers (src/bmmap.c): the largest original map is 30 x 31.
    assert map_size_problem(30, 31) is None and map_size_problem(40, 30)["code"] == "mapTooBig"


def test_map_changes_are_checked(decomp_dir):
    from fe_maker.validation import _validate_maps

    good = [[5] * 15 for _ in range(10)]
    change = {"id": 0, "x": 14, "y": 9, "w": 1, "h": 1, "rows": [[3]]}
    problems = []
    _validate_maps(problems, {"layouts": {"M": {"rows": good}}, "changes": {"M": [
        change, dict(change, x=14, w=2, rows=[[3, 3]]), dict(change, id=1, rows=[[3], [3]])]}})
    assert [p.code for p in problems] == ["badChangeId", "changeOutOfMap", "badLayout"]


def test_weapon_a_unit_cannot_use():
    from fe_maker.validation import weapon_problem

    blade = {"weaponType": "sword", "weaponRank": "D", "reservedFor": {"characters": [], "classes": ["CLASS_LORD"]}}
    lord = {"id": "CLASS_LORD", "weaponRanks": {"sword": "E"}, "abilities": []}
    hero = {"id": "CHARACTER_HERO", "weaponRanks": {"sword": "D"}, "abilities": []}
    assert weapon_problem(blade, hero, lord) is None
    assert weapon_problem(blade, hero, {"id": "CLASS_KNIGHT", "weaponRanks": {"sword": "A"}}) == ("weaponReserved", {})
    assert weapon_problem(blade, None, lord) == ("weaponRank", {"rank": "D", "wtype": "sword"})   # class rank only
    assert weapon_problem({"weaponType": "item", "weaponRank": 0}, None, None) is None
    claw = {"weaponType": "monster", "weaponRank": 0, "monsterWeapon": True}
    assert weapon_problem(claw, None, {"id": "CLASS_MOGALL", "abilities": ["lock3"]}) is None
    assert weapon_problem(claw, hero, lord) == ("weaponReserved", {})


def test_unusable_weapons_of_units(decomp_dir):
    d = DecompData(decomp_dir)
    chars, items = d.export_characters(), d.export_items()
    groups = {"UnitDef_TestChapter": [
        {"character": "CHARACTER_TESTHERO", "class": "CLASS_TESTLORD", "items": ["ITEM_TESTBLADE"], "endX": 1, "endY": 1},
        {"character": "CHARACTER_TESTRIVAL", "class": "CLASS_TESTKNIGHT", "items": ["ITEM_TESTBLADE"], "endX": 2, "endY": 1}]}
    chapters = {"unitGroups": groups, "objectives": {}}
    found = {(p.id, p.code) for p in validate(chars, items, d, chapters=chapters)}
    assert ("UnitDef_TestChapter#1", "weaponReserved") in found and ("UnitDef_TestChapter#0", "weaponReserved") not in found
    # The class of a named character comes from its sheet: a class change there makes the blade unusable.
    next(c for c in chars if c["id"] == "CHARACTER_TESTHERO")["class"] = "CLASS_TESTKNIGHT"
    found = {(p.id, p.code) for p in validate(chars, items, d, chapters=chapters)}
    assert ("UnitDef_TestChapter#0", "weaponReserved") in found


def test_units_of_chapters_nobody_plays_are_not_checked(decomp_dir):
    d = DecompData(decomp_dir)
    chars, items = d.export_characters(), d.export_items()
    groups = {"UnitDef_TestChapter": [
        {"character": "CHARACTER_TESTRIVAL", "class": "CLASS_TESTKNIGHT", "items": ["ITEM_TESTBLADE"], "endX": 2, "endY": 1}]}
    chapters = {"unitGroups": groups, "objectives": {}}
    assert any(p.code == "weaponReserved" for p in validate(chars, items, d, chapters=chapters))
    found = validate(chars, items, d, chapters=chapters, unplayed={"UnitDef_TestChapter"})
    assert not any(p.code == "weaponReserved" for p in found)


def test_manual_change_must_hold_its_object(monkeypatch):
    from fe_maker.decomp import mapobjects
    from fe_maker.validation import _validate_map_objects

    snag = {"kind": "snag", "x": 6, "y": 4, "cells": [(6, 4)], "new": True, "change": 0, "auto": None, "ruin": None,
            "noAfter": False}
    monkeypatch.setattr(mapobjects, "map_objects", lambda *args, **kwargs: [snag])
    passage = {"x": 6, "y": 4, "w": 3, "h": 1, "rows": [[1, 2, 2]], "manual": True}
    changes = [dict(passage, id=0), dict(passage, id=1, x=7, w=2, rows=[[2, 2]]), dict(passage, id=2, x=7, w=2, manual=False)]
    problems = []
    _validate_map_objects(problems, {"layouts": {"M": {"rows": []}}, "changes": {"M": changes}},
                          {"M": {"changes": None}}, None, {"M": (15, 10)})
    assert [(p.code, p.params) for p in problems] == [("manualChangeOffObject", {"id": 1})]


def test_only_filler_slots_count_as_removed_tiles():
    from types import SimpleNamespace

    from fe_maker.validation import _filler_slots

    # slot 2 copies the real tile 0 (a tile of the game a map may use); slots 3-5 hold the filler
    metatiles = [[1, 2, 3, 4], [0, 0, 0, 0], [1, 2, 3, 4], [0, 0, 0, 0], [0, 0, 0, 0], [0, 0, 0, 0]]
    tileset = SimpleNamespace(metatiles=metatiles, terrain=bytes(6), duplicates=[False, False, True, True, True, True])
    assert _filler_slots(tileset) == {3, 4, 5}


def test_new_character_on_an_entry_the_game_uses(decomp_dir):
    d = DecompData(decomp_dir)
    chars = d.export_characters()
    free, taken = d.new_character(True, set()), d.new_character(True, set())
    free["name"], taken["name"] = "Aline", "Bea"
    taken["id"] = "CHARACTER_NEW_02"   # entry of CHARACTER_TESTRIVAL
    codes = _codes(validate([*chars, free, taken], d.export_items(), d))
    assert ("CHARACTER_NEW_02", "id", "characterEntryTaken") in codes
    assert not any(c[0] == "CHARACTER_NEW_03" and c[2] == "characterEntryTaken" for c in codes)
