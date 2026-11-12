import copy

import pytest

from fe_maker.decomp.cparse import parse_array, render_array
from fe_maker.decomp.gamedata import DecompData, GameDataError
from fe_maker.decomp.texts import TextFile


def test_unmodified_round_trip_changes_nothing(decomp_dir):
    d = DecompData(decomp_dir)
    d.apply_characters(copy.deepcopy(d.export_characters()))
    d.apply_items(copy.deepcopy(d.export_items()))
    assert d.changed_files() == {}


def test_render_unmodified_array_is_identical(decomp_dir):
    source = (decomp_dir / "src" / "data_characters.c").read_text(encoding="utf-8")
    assert render_array(parse_array(source, "gCharacterData")) == source


def test_export_characters(decomp_dir):
    hero = DecompData(decomp_dir).export_characters()[0]
    assert hero["id"] == "CHARACTER_TESTHERO"
    assert hero["name"] == "Testhero"
    assert hero["class"] == "CLASS_TESTLORD"
    assert hero["bases"] == {"hp": 3, "pow": 1, "skl": 0, "spd": 0, "def": 0, "res": 0, "lck": 4, "con": 0}
    assert hero["growths"]["hp"] == 50
    assert hero["weaponRanks"] == {"sword": "E"}


def test_edit_character_only_touches_that_entry(decomp_dir):
    d = DecompData(decomp_dir)
    chars = d.export_characters()
    chars[0]["bases"]["hp"] = 9
    chars[0]["weaponRanks"]["lance"] = "B"
    d.apply_characters(chars)
    out = d.changed_files()["src/data_characters.c"]
    assert ".baseHP = 9," in out
    assert "[ITYPE_LANCE] = WPN_EXP_B" in out
    assert ".pSupportData = &SupportData_TestHero," in out
    # The other entry is copied byte for byte.
    original = (decomp_dir / "src" / "data_characters.c").read_text(encoding="utf-8")
    rival = original[original.index("[CHARACTER_TESTRIVAL - 1]"):]
    assert rival in out


def test_rename_writes_texts(decomp_dir):
    d = DecompData(decomp_dir)
    chars = d.export_characters()
    chars[1]["name"] = "Nemesis"
    d.apply_characters(chars)
    files = d.changed_files()
    assert set(files) == {"texts/texts.txt"}
    reparsed = TextFile(files["texts/texts.txt"])
    assert reparsed.get_name(3) == "Nemesis"
    assert reparsed.get_name(2) == "Testhero"
    assert reparsed.get_name(4) == "Test Blade"


def test_class_change_applies_to_chapters(decomp_dir):
    d = DecompData(decomp_dir)
    chars = d.export_characters()
    chars[0]["class"] = "CLASS_TESTKNIGHT"
    d.apply_characters(chars)
    files = d.changed_files()
    assert ".defaultClass = CLASS_TESTKNIGHT," in files["src/data_characters.c"]
    udefs = files["src/events_udefs.c"]
    # The hero's own appearances move to the new class...
    assert udefs.count(".charIndex = CHARACTER_TESTHERO,\n        .classIndex = CLASS_TESTKNIGHT,") == 2
    # ...other characters are untouched.
    assert ".charIndex = CHARACTER_TESTRIVAL,\n        .classIndex = CLASS_TESTLORD," in udefs


def test_item_locks(decomp_dir):
    d = DecompData(decomp_dir)
    # TESTBLADE is locked to CA_LOCK_4: only the lord class has it, no character does.
    assert d.item_locks() == {"ITEM_TESTBLADE": {"classes": ["CLASS_TESTLORD"], "characters": []}}


def test_abilities_and_affinity(decomp_dir):
    d = DecompData(decomp_dir)
    chars = d.export_characters()
    assert chars[0]["abilities"] == ["female"]
    assert chars[0]["affinity"] is None
    chars[0]["abilities"] = ["female", "lock4", "canto"]
    chars[0]["affinity"] = "light"
    d.apply_characters(chars)
    out = d.changed_files()["src/data_characters.c"]
    # bit order; lock4 is ignored: weapon locks come from the items' "reserved for" lists
    assert ".attributes = CA_CANTO | CA_FEMALE," in out
    assert ".affinity = UNIT_AFFIN_LIGHT," in out


def test_missing_new_fields_are_left_untouched(decomp_dir):
    d = DecompData(decomp_dir)
    chars = d.export_characters()
    for c in chars:  # a project created before abilities/affinity existed
        del c["abilities"], c["affinity"]
    d.apply_characters(chars)
    assert d.changed_files() == {}


def test_class_genders(decomp_dir):
    # Lord's first animation is index 1 -> "tstf_sw1" (female), Knight's is 2 -> "tstm_sp1" (male).
    genders = DecompData(decomp_dir).class_genders()
    assert genders["CLASS_TESTLORD"] == "female"
    assert genders["CLASS_TESTKNIGHT"] == "male"


def test_odd_length_names_are_padded(decomp_dir):
    d = DecompData(decomp_dir)
    items = d.export_items()
    items[0]["name"] = "Bladeo"  # even: no padding
    d.apply_items(items)
    assert "\nBladeo[X]\n" in d.changed_files()["texts/texts.txt"]
    d = DecompData(decomp_dir)
    items[0]["name"] = "Blade"  # odd: padded like the original game ("Gilliam[.][X]")
    d.apply_items(items)
    assert "\nBlade[.][X]\n" in d.changed_files()["texts/texts.txt"]


def test_animated_weapons(decomp_dir):
    d = DecompData(decomp_dir)
    assert d.animated_weapons == {
        "CLASS_TESTLORD": ["sword"],
        "CLASS_TESTKNIGHT": ["lance", "sword", "axe"],
        "CLASS_TESTUNUSED": ["lance", "sword", "axe"],
    }


def test_name_control_codes_are_hidden_and_recomputed():
    texts = TextFile("#0x0\n[X]\n\n## MSG_001\nHerox[.][X]\n")
    assert texts.get_name(1) == "Herox"
    texts.set_name(1, "Champion")
    assert "\nChampion[X]\n" in texts.render()
    texts.set_name(1, "Champ")
    assert "\nChamp[.][X]\n" in texts.render()


def test_items(decomp_dir):
    d = DecompData(decomp_dir)
    items = d.export_items()
    assert [i["id"] for i in items] == ["ITEM_TESTBLADE"]
    blade = items[0]
    assert blade["range"] == {"min": 1, "max": 2}
    assert blade["weaponRank"] == "D"
    blade["range"]["max"] = 3
    blade["might"] = 6
    d.apply_items(items)
    out = d.changed_files()["src/data_items.c"]
    assert ".encodedRange = 19," in out
    assert ".might = 6," in out


def test_item_icons(decomp_dir):
    assert DecompData(decomp_dir).item_icon_files() == [
        "graphics/item_icon/item_icon_test_a.png",
        "graphics/item_icon/item_icon_test_b.png",
    ]


def test_free_character_entries(decomp_dir):
    # Raw-numbered entries no unit loads: 0x03 below ALLY_CHARACTER_END (playable), 0x50 after it.
    assert DecompData(decomp_dir).free_character_numbers() == [0x3, 0x50]


def test_new_character_takes_a_free_entry(decomp_dir):
    d = DecompData(decomp_dir)
    ally = d.new_character(True, set())
    assert ally["id"] == "CHARACTER_NEW_03"
    assert ally["level"] == 1 and ally["portraitId"] == 0 and ally["weaponRanks"] == {}
    assert d.new_character(False, set())["id"] == "CHARACTER_NEW_50"
    with pytest.raises(GameDataError, match="noFreeCharacter"):
        d.new_character(True, {"CHARACTER_NEW_03"})


def test_new_character_gets_a_constant_and_its_own_name(decomp_dir):
    d = DecompData(decomp_dir)
    chars = d.export_characters()
    new = d.new_character(True, set())
    new.update(name="Aline", portraitId=2, level=4)
    chars.append(new)
    d.apply_characters(chars)   # the raw record of entry 0x03 is still in the list: it is left out
    files = d.changed_files()
    header = files["include/constants/characters.h"]
    assert "    CHARACTER_NEW_03 = 0x03,\n};\n\nenum event_autoload_pid_idx" in header
    source = files["src/data_characters.c"]
    entry = source[source.index("[CHARACTER_NEW_03 - 1]"):]
    entry = entry[:entry.index("},")]
    assert ".number = CHARACTER_NEW_03," in entry and ".baseLevel = 4," in entry and ".portraitId = 2," in entry
    name_id = int(entry.split(".nameTextId = ")[1].split(",")[0], 16)
    texts = TextFile(files["texts/texts.txt"])
    assert texts.get_name(name_id) == "Aline"
    assert texts.get_name(7) == "Enemy"   # the name the free entries share is untouched
    assert source.count("[0x50 - 1]") == 1   # the other free entry too
    assert d._character_constants()["CHARACTER_NEW_03"] == 3


def test_new_character_on_a_used_entry_is_refused(decomp_dir):
    d = DecompData(decomp_dir)
    chars = d.export_characters()
    new = d.new_character(True, set())
    new.update(id="CHARACTER_NEW_01", name="Aline")
    with pytest.raises(GameDataError, match="used by the game"):
        d.apply_characters([*chars, new])


def test_new_weapon_copies_its_model_after_the_game_items(decomp_dir):
    d = DecompData(decomp_dir)
    items = d.export_items()
    new = d.new_item("ITEM_TESTBLADE", set())
    assert new["id"] == "ITEM_NEW_02" and new["model"] == "ITEM_TESTBLADE" and new["might"] == 3
    assert d.new_item("ITEM_TESTBLADE", {"ITEM_NEW_02"})["id"] == "ITEM_NEW_03"
    new.update(name="Lame", might=8)
    d.apply_items([*items, new])
    source = d.changed_files()["src/data_items.c"]
    original = (decomp_dir / "src" / "data_items.c").read_text(encoding="utf-8")
    assert source.startswith(original[:original.rindex("};")])   # the game's entries are untouched
    added = source[source.index("\t[ITEM_NEW_02] = {"):]
    assert ".number = ITEM_NEW_02," in added and ".might = 8," in added and added.endswith("\t},\n};\n")
    assert "IA_LOCK_4" in added   # reserved like its model


def test_only_items_can_be_copied(decomp_dir):
    with pytest.raises(GameDataError, match="notAnItem"):
        DecompData(decomp_dir).new_item("ITEM_NONE", set())


def test_new_class_copies_its_model_after_the_game_classes(decomp_dir):
    d = DecompData(decomp_dir)
    classes = d.export_classes()
    new = d.new_class("CLASS_TESTKNIGHT", set())
    assert new["id"] == "CLASS_NEW_80" and new["model"] == "CLASS_TESTKNIGHT"
    assert new["promotions"] == ["CLASS_TESTLORD"]   # promotes like its model
    other = d.new_class("CLASS_TESTLORD", {"CLASS_NEW_80"})
    other.update(name="Duc", promotions=[])
    new["name"] = "Garde"
    d.apply_classes([*classes, new, other])
    files = d.changed_files()
    source = files["src/data_classes.c"]
    assert "[CLASS_NEW_80 - 1] = {" in source and "[CLASS_NEW_81 - 1] = {" in source   # keyed like the game's
    assert ".number = CLASS_NEW_80," in source
    promotions = files["src/classchg-data.c"]
    assert "{CLASS_TESTLORD}" in promotions.split("[CLASS_NEW_80]")[1].split("\n")[0]
    # the last new class has a row even without promotions: the engine reads gPromoJidLut[class]
    assert "{0}" in promotions.split("[CLASS_NEW_81]")[1].split("\n")[0]
    assert "gSomethingElse" in promotions


def test_a_description_is_written_only_when_it_changes(decomp_dir):
    d = DecompData(decomp_dir)
    characters = d.export_characters()
    d.apply_characters(characters)
    assert not d.texts.edits
    index = _description_index(d)
    if index:
        characters[0]["description"] = "Un jeune héros\nvenu du nord"
        d.apply_characters(characters)
        assert "[LF]\nvenu du nord" in d.texts.raw(index)
        assert d._description(d.characters.entries[0].fields) == "Un jeune héros\nvenu du nord"


def test_a_class_description_is_written(decomp_dir, monkeypatch):
    d = DecompData(decomp_dir)
    written = []
    monkeypatch.setattr(d, "_set_description", lambda fields, record: written.append(record["id"]))
    classes = d.export_classes()
    d.apply_classes(classes)
    assert written == [c["id"] for c in classes]


def _description_index(d):
    from fe_maker.decomp.gamedata import _int_field

    return _int_field(d.characters.entries[0].fields, "descTextId")


def test_a_copied_item_acts_like_its_model_in_the_engine(decomp_dir):
    """Ticket 144: staves and items act by their number, so the copy joins each test of its model's number."""
    d = DecompData(decomp_dir)
    new = d.new_item("ITEM_TESTBLADE", set())
    d.apply_items([*d.export_items(), new])
    code = d.changed_files()["src/cp_testitems.c"]
    assert "case ITEM_TESTBLADE: case ITEM_NEW_02:" in code
    assert ("(GetItemIndex(gUnits[2]->items[0]) == ITEM_TESTBLADE || GetItemIndex(gUnits[2]->items[0]) == ITEM_NEW_02)"
            in code)
    assert "(bu->weaponBefore != ITEM_TESTBLADE && bu->weaponBefore != ITEM_NEW_02)" in code
    assert "{ ITEM_TESTBLADE, AiTestBlade },\n    { ITEM_NEW_02, AiTestBlade },\n    { ITEM_NONE, NULL }," in code


def test_a_copied_item_can_have_another_items_effect(decomp_dir):
    """Ticket 144: a copy can take the effect of another item than its model."""
    d = DecompData(decomp_dir)
    new = d.new_item("ITEM_TESTBLADE", set())
    new["actsLike"] = "ITEM_TESTSTAFF"
    d.apply_items([*d.export_items(), new])
    code = d.changed_files()["src/cp_testitems.c"]
    assert "case ITEM_TESTSTAFF: case ITEM_NEW_02:" in code and "case ITEM_TESTBLADE:\n" in code


def test_a_copied_vulnerary_heals_its_own_amount(decomp_dir):
    """Ticket 144: a copy healing more or less gets its own case where the engine writes the model's amount."""
    d = DecompData(decomp_dir)
    out = {
        "src/bmitem.c": "int GetUnitItemHealAmount(struct Unit* unit, int item) {\n    int result = 0;\n\n"
                        "    switch (GetItemIndex(item)) {\n\n    case ITEM_VULNERARY: case ITEM_NEW_CE:\n        result = 10;\n"
                        "        break;\n    }\n    return result;\n}\n",
        "src/bmusemind.c": "void ActionStaffDoorChestUseItem(ProcPtr proc) {\n    switch (itemId) {\n"
                           "        case ITEM_VULNERARY: case ITEM_NEW_CE:\n            ExecVulneraryItem(proc, 10);\n"
                           "            break;\n    }\n}\n",
    }
    d._own_item_amount(out, "ITEM_NEW_CE", "ITEM_VULNERARY", 3)
    assert "case ITEM_NEW_CE:\n        result = 3;\n        break;\n" in out["src/bmitem.c"]
    assert "case ITEM_VULNERARY:\n" in out["src/bmitem.c"]
    assert "case ITEM_NEW_CE:\n            ExecVulneraryItem(proc, 3);" in out["src/bmusemind.c"]
    assert "case ITEM_VULNERARY:\n            ExecVulneraryItem(proc, 10);" in out["src/bmusemind.c"]


def test_a_pure_water_copy_can_raise_another_stat_for_a_few_turns(decomp_dir):
    """Ticket 144: 4 bits per stat in the unit's spare bytes, read by the stat getters, lowered each turn, kept
    across a suspend in the save memory's unused bytes."""
    d = DecompData(decomp_dir)
    getters = "".join(f"inline int GetUnit{name}(struct Unit* unit) {{\n    return unit->{f};\n}}\n"
                      for name, f in (("Power", "pow"), ("Skill", "skl"), ("Speed", "spd"), ("Defense", "def"),
                                      ("Resistance", "res"), ("Luck", "lck")))
    out = {
        "include/bmunit.h": "struct Unit;\n#endif // GUARD_BM_UNIT_H\n",
        "src/bmunit.c": getters + "void Tick(struct Unit* unit) {\n        if (unit->barrierDuration != 0)\n"
                                  "            unit->barrierDuration--;\n}\n",
        "src/bmio.c": "void Reset(struct Unit* unit) {\n            unit->barrierDuration = 0;\n}\n",
        "src/fontgrp.c": "void PutNumberBonus(int number, u16 *tm)\n{\n    if (number == 0)\n        return;\n\n}\n",
        "src/statscreen.c": "void DrawStatWithBar(int num, int x, int y, int base, int total, int max)\n{\n"
                            "    DrawStatBarGfx(0x401 + num*6, 6,\n        0);\n}\n"
                            "    ApplyPalette(Pal_StatscreenEquipmentText, STATSCREEN_BGPAL_EQUIPMENT_LABEL);\n",
        "src/bmsave.c": "void WriteSuspendSave(int slot)\n{\n    chunk.kind = SAVEBLOCK_KIND_SUSPEND;\n}\n"
                        "void ReadSuspendSave(int slot)\n{\n"
                        "    SetBonusContentClaimFlags(LoadSavedBonusClaimFlags(gPlaySt.gameSaveSlot));\n}\n",
        "src/bmitemuse.c": "s8 CanUnitUseItem(struct Unit* unit, int item)\n{\n    switch (GetItemIndex(item))\n    {\n\n"
                           "    case ITEM_PUREWATER: case ITEM_NEW_CE:\n        return CanUnitUsePureWaterItem(unit);\n"
                           "    }\n}\n",
        "src/bmusemind.c": "void ActionStaffDoorChestUseItem(ProcPtr proc) {\n    switch (itemId) {\n"
                           "        case ITEM_PUREWATER: case ITEM_NEW_CE:\n            ExecPureWater(proc);\n"
                           "            break;\n    }\n}\n",
    }
    d.item_temp_bonuses["ITEM_NEW_CE"] = {"spd": 6, "def": -3}
    d._own_item_amount(out, "ITEM_NEW_CE", "ITEM_PUREWATER", 7)
    d._with_temporary_bonus(out)
    assert "SET_TEMP_BONUSES_FEM(drinker, TempBonusesAfterFem(drinker, 0xff00, 0xd600));" in out["src/bmusemind.c"]
    usable = "case ITEM_NEW_CE:\n        return TempBonusesAfterFem(unit, 0xff00, 0xd600) != TEMP_BONUSES_FEM(unit);"
    assert usable in out["src/bmitemuse.c"]
    assert "return TempStatFem(unit->spd + TEMP_BONUS_FEM(unit, 2));" in out["src/bmunit.c"]
    assert "return TempStatFem(unit->res + TEMP_BONUS_FEM(unit, 4));" in out["src/bmunit.c"]
    assert "#define TEMP_BONUS_FEM" in out["include/bmunit.h"] and "#define TEMP_BONUS_RULE_FEM 0" in out["include/bmunit.h"]
    assert "TEXT_SPECIAL_DASH" in out["src/fontgrp.c"] and "base = total;" in out["src/statscreen.c"]
    assert "SET_TEMP_BONUSES_FEM(unit, bonuses);" in out["src/bmunit.c"]
    assert "SET_TEMP_BONUSES_FEM(unit, 0);" in out["src/bmio.c"]
    assert "WriteTempBonusesFem(slot);" in out["src/bmsave.c"]
    assert "ReadTempBonusesFem(slot + gSuspendSaveIdOffset);" in out["src/bmsave.c"]


def test_a_usable_item_keeps_its_stat_bonuses_on_use(decomp_dir):
    """Ticket 162: a usable item (not a booster) given stat bonuses adds them for good when used."""
    d = DecompData(decomp_dir)
    out = {"src/bmusemind.c": "void ActionStaffDoorChestUseItem(ProcPtr proc) {\n    int itemId = 0;\n\n"
                              "    switch (itemId) {\n        case ITEM_VULNERARY:\n            break;\n    }\n}\n"}
    d.item_use_bonuses = ["ITEM_NEW_CE"]
    d._with_use_bonuses(out)
    code = out["src/bmusemind.c"]
    assert code.index("static void ApplyUseStatBonusesFem(") < code.index("void ActionStaffDoorChestUseItem(")
    assert "    switch (itemId) {\n        case ITEM_NEW_CE:\n            ApplyUseStatBonusesFem(" in code
    assert "case ITEM_VULNERARY:" in code


def test_temp_bonuses_of_a_pure_water_copy():
    """Ticket 164: several stats at once, maluses, clamped to -8..+7; the earlier one-stat fields still read."""
    from fe_maker.decomp.gamedata import temp_bonuses

    assert temp_bonuses({"tempBonuses": {"pow": 9, "spd": -12, "lck": 0, "hp": 3}}) == {"pow": 7, "spd": -8}
    assert temp_bonuses({"effectStat": "lck", "effectAmount": 12}) == {"lck": 7}
    assert temp_bonuses({"effectAmount": 3}) is None


def test_the_stacking_rule_of_temporary_bonuses_is_a_game_option(tmp_path):
    """Ticket 164: the strongest wins unless the project picks another rule (only written when the bonuses are)."""
    from fe_maker.decomp import gameoptions

    header = "#define TEMP_BONUS_RULE_FEM 0\n"
    assert gameoptions.validate({"tempBonusRule": "add"}) is None
    assert gameoptions.validate({"tempBonusRule": "max"}) == "badGameOption"
    files = gameoptions.apply(tmp_path, {"tempBonusRule": "replace"}, {"include/bmunit.h": header})
    assert files["include/bmunit.h"] == "#define TEMP_BONUS_RULE_FEM 2\n"
    assert "include/bmunit.h" not in gameoptions.apply(tmp_path, {"tempBonusRule": "add"}, {})
