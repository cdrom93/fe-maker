import pytest

from fe_maker.decomp import objectives

# Fictional test data written for FE Maker. Not taken from the game.
EVENTS = """CONST_DATA EventListScr EventListScr_Test_Turn[] = {
    TURN(0x0, EventScr_TestTurn1, 1, 0, FACTION_RED)
    END_MAIN
};

CONST_DATA EventListScr EventListScr_Test_Location[] = {
    Seize(4, 2)
    END_MAIN
};

CONST_DATA EventListScr EventListScr_Test_Misc[] = {
    AFEV(EVFLAG_TMP(7), EventScr_TestBossTalk, EVFLAG_DEFEAT_BOSS)
    CauseGameOverIfLordDies
    END_MAIN
};

CONST_DATA struct ChapterEventGroup TestEvents = {
    .turnBasedEvents      = EventListScr_Test_Turn,
    .locationBasedEvents  = EventListScr_Test_Location,
    .miscBasedEvents      = EventListScr_Test_Misc,
    .endingSceneEvents    = EventScr_TestEnding,
};
"""


class Texts:
    def __init__(self):
        self.messages = {100: "Seize the[LF]\nthrone[X]"}

    def raw(self, index):
        return self.messages[index]


def _goal(kind="seize", window=417, turn=0):
    return {"statusObjectiveTextId": 100, "windowTextId": window, "windowDataType": kind,
            "windowEndTurnNumber": turn, "protectCharacterIndex": 0, "destPosX": 255, "destPosY": 0}


def test_status_message_pads_each_line():
    assert objectives.status_message("Guard Mansel for 13\nturns") == "Guard Mansel for 13[.][LF]\nturns[.][X]"
    assert objectives.status_text("Guard Mansel for 13[.][LF]\nturns[.][X]") == "Guard Mansel for 13\nturns"


def test_read_seize_objective():
    o = objectives.read_objective(_goal(), {"ev.h": EVENTS}, "TestEvents", Texts())
    assert o["type"] == "seize" and o["editable"] and o["seize"] == [{"x": 4, "y": 2}]
    assert o["statusText"] == "Seize the\nthrone" and o["seizeLabel"] == "throne"


def test_change_objective_type_and_back():
    sources, goal = {"ev.h": EVENTS}, _goal()
    current = objectives.read_objective(goal, sources, "TestEvents", Texts())
    out = objectives.apply_objective(goal, sources, "TestEvents", current, {"type": "defeat_all"})
    assert "Seize(" not in out["ev.h"]
    assert out["ev.h"].index("DefeatAll(EventScr_TestEnding)") < out["ev.h"].index("AFEV(EVFLAG_TMP(7)")
    assert goal["windowDataType"] == "defeat_all" and goal["windowTextId"] == 414
    o = objectives.read_objective(goal, out, "TestEvents", Texts())
    assert o["type"] == "defeat_all" and o["editable"]

    out = objectives.apply_objective(goal, out, "TestEvents", o, {"type": "defense", "turns": 8})
    assert "TURN(EVFLAG_WIN, EventScr_TestEnding, 9, 0, FACTION_BLUE)" in out["ev.h"]
    assert "DefeatAll" not in out["ev.h"] and goal["windowEndTurnNumber"] == 9
    o = objectives.read_objective(goal, out, "TestEvents", Texts())
    assert o["type"] == "defense" and o["turns"] == 8 and o["editable"]

    seize = {"type": "seize", "seize": [{"x": 4, "y": 2}], "seizeLabel": "throne"}
    out = objectives.apply_objective(goal, out, "TestEvents", o, seize)
    assert out["ev.h"] == EVENTS
    assert goal == _goal()


def test_custom_objectives_are_read_only():
    custom = EVENTS.replace("    Seize(4, 2)\n", "    LOCA(EVFLAG_WIN, EventScr_TestSpecial, 4, 2, TILE_COMMAND_SEIZE)\n")
    o = objectives.read_objective(_goal(), {"ev.h": custom}, "TestEvents", Texts())
    assert not o["editable"] and o["reason"] == "custom"
    with pytest.raises(objectives.ObjectiveError):
        objectives.apply_objective(_goal(), {"ev.h": custom}, "TestEvents", o, {"type": "defeat_all"})
    # A protected character does not make the objective read-only: it combines with any objective.
    escort = dict(_goal(), protectCharacterIndex=29)
    assert objectives.read_objective(escort, {"ev.h": EVENTS}, "TestEvents", Texts())["editable"]


def test_reach_an_area():
    sources, goal = {"ev.h": EVENTS}, _goal()
    current = objectives.read_objective(goal, sources, "TestEvents", Texts())
    area = {"type": "area", "area": {"x1": 1, "y1": 2, "x2": 3, "y2": 4}, "areaWho": "CHARACTER_TESTHERO"}
    out = objectives.apply_objective(goal, sources, "TestEvents", current, area)
    assert "Seize(" not in out["ev.h"]
    assert "AREA(EVFLAG_WIN, EventScr_FEM_ReachArea_TestEvents, 1, 2, 3, 4)" in out["ev.h"]
    script = out["ev.h"].index("CONST_DATA EventListScr EventScr_FEM_ReachArea_TestEvents[]")
    assert script < out["ev.h"].index("EventListScr_Test_Misc[]")
    assert "SVAL(EVT_SLOT_2, CHARACTER_TESTHERO)" in out["ev.h"] and "EventScr_UnTriggerIfNotUnit" in out["ev.h"]
    assert goal["windowDataType"] == "seize"
    with pytest.raises(objectives.ObjectiveError):
        objectives.apply_objective(_goal(), sources, "TestEvents", current, {"type": "area"})


def test_game_over_when_protected_character_dies():
    assert objectives.ensure_game_over({"ev.h": EVENTS}, "TestEvents") == {"ev.h": EVENTS}
    without = EVENTS.replace("    CauseGameOverIfLordDies\n", "")
    out = objectives.ensure_game_over({"ev.h": without}, "TestEvents")
    assert "    CauseGameOverIfLordDies\n    END_MAIN" in out["ev.h"]


TALKS = """CONST_DATA struct DefeatTalkEnt gDefeatTalkList[] = {
    {
        .pid     = CHARACTER_TESTRIVAL,
        .route   = CHAPTER_MODE_ANY,
        .chapter = CHAPTER_TEST_0,
        .flag    = EVFLAG_DEFEAT_BOSS,
        .msg     = 0x0917,
    },
    {
        .pid = -1
    }
};
"""
CHAPTERS = {"CHAPTER_TEST_0": 0, "CHAPTER_TEST_1": 1}


def test_chapter_constants():
    assert objectives.chapter_constants("enum {\n    CHAPTER_TEST_0 = 0x00, // a\n    CHAPTER_TEST_1 = 0x01,\n};") == CHAPTERS


def test_boss_is_read_from_death_quotes_and_can_change():
    assert objectives.read_bosses(TALKS, CHAPTERS) == {0: ["CHARACTER_TESTRIVAL"]}
    changed = objectives.set_boss(TALKS, CHAPTERS, 0, "CHARACTER_TESTHERO")
    assert objectives.read_bosses(changed, CHAPTERS) == {0: ["CHARACTER_TESTHERO"]}
    assert "0x0917" not in changed  # the previous boss's last words are not kept
    added = objectives.set_boss(TALKS, CHAPTERS, 1, "CHARACTER_TESTHERO")
    assert objectives.read_bosses(added, CHAPTERS) == {0: ["CHARACTER_TESTRIVAL"], 1: ["CHARACTER_TESTHERO"]}
    assert added.rstrip().endswith("{\n        .pid = -1\n    }\n};")
    assert objectives.set_boss(TALKS, CHAPTERS, 0, "CHARACTER_TESTRIVAL") == TALKS
