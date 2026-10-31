from fe_maker.decomp import dialogues

SOURCE = """EventListScr Turns[] = {
    TURN(0x0, EventScr_One, 2, 2, FACTION_BLUE)
    TURN(EVFLAG_TMP(11), EventScr_Range, 1, 255, FACTION_BLUE)
    TURN(0x0, EventScr_Once, 3, 0, FACTION_RED)
    CharacterEventBothWays(0x8, EventScr_Talk, CHARACTER_SETH, CHARACTER_FRANZ)
    CHAR(0x9, EventScr_Single, CHARACTER_EIRIKA, CHARACTER_SETH)
};
"""


def test_a_turn_moves_with_its_end():
    out = dialogues.with_trigger(SOURCE, "EventScr_One", {"turn": "5", "faction": "FACTION_RED"})
    assert "TURN(0x0, EventScr_One, 5, 5, FACTION_RED)" in out


def test_a_range_keeps_its_end_and_no_end_stays_no_end():
    out = dialogues.with_trigger(SOURCE, "EventScr_Range", {"turn": "4"})
    assert "TURN(EVFLAG_TMP(11), EventScr_Range, 4, 255, FACTION_BLUE)" in out
    assert "TURN(0x0, EventScr_Once, 6, 0, FACTION_RED)" in dialogues.with_trigger(SOURCE, "EventScr_Once", {"turn": "6"})


def test_who_talks_changes():
    out = dialogues.with_trigger(SOURCE, "EventScr_Talk", {"b": "CHARACTER_GILLIAM"})
    assert "CharacterEventBothWays(0x8, EventScr_Talk, CHARACTER_SETH, CHARACTER_GILLIAM)" in out
    out = dialogues.with_trigger(SOURCE, "EventScr_Single", {"a": "CHARACTER_FRANZ"})
    assert "CHAR(0x9, EventScr_Single, CHARACTER_FRANZ, CHARACTER_SETH)" in out


def test_other_lines_stay_and_an_unknown_scene_changes_nothing():
    assert dialogues.with_trigger(SOURCE, "EventScr_None", {"turn": "2"}) == SOURCE
    assert "EventScr_Range, 1, 255" in dialogues.with_trigger(SOURCE, "EventScr_One", {"turn": "2"})


def test_a_talk_written_both_ways_is_read_as_a_talk():
    group = {"characterBasedEvents": "Talks"}
    lists = {"Talks": "    CharacterEventBothWays(0x8, EventScr_Talk, CHARACTER_SETH, CHARACTER_FRANZ)\n"}
    found = dialogues.scene_triggers(group, lists, {"EventScr_Talk"})
    assert found["EventScr_Talk"] == {"kind": "talk", "a": "CHARACTER_SETH", "b": "CHARACTER_FRANZ"}


def test_a_removed_scene_leaves_the_lists_and_its_callers():
    source = SOURCE + "EventScr Caller[] = {\n    CALL(EventScr_One)\n    ENDA\n};\n"
    out = dialogues.without_scene(source, "EventScr_One")
    assert "EventScr_One" not in out
    assert "EventScr_Once" in out and "ENDA" in out
    assert "EventScr_Talk" not in dialogues.without_scene(SOURCE, "EventScr_Talk")
