import copy

from fe_maker.decomp.cparse import parse_array, render_array
from fe_maker.decomp.gamedata import DecompData
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
        "CLASS_TESTKNIGHT": ["lance", "sword"],
        "CLASS_TESTUNUSED": ["lance", "sword"],
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
