import pytest

from fe_maker.decomp import convoy
from fe_maker.decomp.gamedata import DecompData

# Fictional C sources in the decomp's layout (not taken from the game).
MENU = """u8 OtherUsability(void)
{
    return 0;
}

u8 SupplyUsability(const struct MenuItemDef * def, int number)
{
    switch (x)
    {
        default:
            break;
    }
    return MENU_NOTSHOWN;
}

u8 SupplyCommandEffect(void)
{
    return 0;
}
"""
CONTAINER = """bool8 HasConvoyAccess(void)
{
    if (gPlaySt.chapterIndex <= CHAPTER_L_1)
        return false;
    return true;
}

bool8 sub_8031660(void)
{
    return true;
}
"""


def test_openers_and_chapters_are_rewritten():
    menu = convoy.with_openers(MENU, ["CHARACTER_EIRIKA", "CHARACTER_SETH"])
    assert "number == CHARACTER_SETH || IsAdjacentForSupply(CHARACTER_SETH))" in menu and "static" not in menu
    assert menu.startswith("u8 OtherUsability(void)") and menu.endswith("u8 SupplyCommandEffect(void)\n{\n    return 0;\n}\n")
    assert menu.count("u8 SupplyUsability(") == 1 and "switch (x)" not in menu
    container = convoy.with_chapters(CONTAINER, [5, 0])
    assert "if (chapterId == 0x00)\n        return false;" in container and "chapterId == 0x05" in container
    assert container.endswith("bool8 sub_8031660(void)\n{\n    return true;\n}\n") and "CHAPTER_L_1" not in container
    with pytest.raises(convoy.ConvoyError):
        convoy.with_openers("int main(void)\n{\n}\n", [])


def test_game_rules():
    assert not convoy.has_convoy(0) and not convoy.has_convoy(0x38) and convoy.has_convoy(2)


def test_blank_projects_and_added_chapters_have_the_convoy(decomp_dir, monkeypatch):
    monkeypatch.setattr("fe_maker.decomp.gamedata.maps.chapter_settings", lambda _: [{}] * 3)
    assert convoy.has_convoy(0, {"blank": True}) and convoy.has_convoy(1, {"added": {"1": {"after": 0}}})
    assert not convoy.has_convoy(1, {"added": {"2": {"after": 1}}})
    d = DecompData(decomp_dir)
    d.apply_chapters({"unitGroups": {}, "blank": True})
    assert d.no_convoy == []
    d = DecompData(decomp_dir)
    d.apply_chapters({"unitGroups": {}, "blank": True, "convoy": {"2": False}})
    assert d.no_convoy == [2]


def test_only_changes_are_written(decomp_dir):
    d = DecompData(decomp_dir)
    chars = d.export_characters()
    d.apply_characters(chars)
    d.apply_chapters({"unitGroups": {}, "convoy": {"2": True}})       # same as the game
    assert d.convoy_openers is None and d.no_convoy is None
    chars[0]["convoyAccess"] = True
    d.apply_characters(chars)
    assert d.convoy_openers == [chars[0]["id"]]


def test_preparations_screen():
    from fe_maker.decomp import prep
    scene = [{"op": "LOAD1", "args": ["1", "U"]}, {"op": "ENUN"}, {"op": "NoFade"}, {"op": "ENDA"}]
    added = prep.with_prep(scene, True)
    assert added[2] == {"op": "CALL", "args": [prep.SCRIPT]} and added[3:] == scene[2:]
    assert prep.with_prep(added, True) == added and prep.with_prep(added, False) == scene
    assert prep.default(1, {"added": {"1": {}}}, False) and not prep.default(0, {"added": {"1": {}}}, False)
    assert prep.default(0, {}, True)


def test_who_can_seize():
    from fe_maker.decomp import seize
    source = "x\ns8 CanUnitSeize(struct Unit* unit) {\n    int leaderId;\n    return 0;\n}\n"
    out = seize.with_seizers(source, ["CHARACTER_EIRIKA", "CHARACTER_SETH"])
    assert "== CHARACTER_SETH)\n        return 1;" in out and "== CHARACTER_EPHRAIM)\n        return 0;" in out
    assert "CHARACTER_EIRIKA" not in out
