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


def test_accents_are_a_warning(decomp_dir):
    d = DecompData(decomp_dir)
    chars = d.export_characters()
    chars[0]["name"] = "Héro"
    problems = [p for p in validate(chars, d.export_items(), d) if p.code == "nameNonAscii"]
    assert problems and problems[0].severity == "warning"
