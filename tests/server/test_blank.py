from fe_maker import newchapter
from fe_maker.decomp import objectives

# Fictional excerpt in the shape of a chapter's event file.
SOURCES = {"src/events/a-eventinfo.h": """CONST_DATA EventListScr Turn[] = {
    TURN(0x0, EventScr_Turn1, 1, 0, FACTION_RED)
    TURN(EVFLAG_WIN, EventScr_End, 6, 0, FACTION_BLUE)
    END_MAIN
};

CONST_DATA EventListScr Misc[] = {
    DefeatBoss(EventScr_End)
    AFEV(EVFLAG_TMP(7), EventScr_OneLeft, 0)
    CauseGameOverIfLordDies
    END_MAIN
};

CONST_DATA EventListScr * Tutorial[] = {
    EventScr_Tutorial0,
    NULL
};

CONST_DATA struct ChapterEventGroup Group = {
    .turnBasedEvents = Turn,
    .miscBasedEvents = Misc,
    .tutorialEvents = Tutorial,
};
"""}


def test_clearing_keeps_the_objective_and_the_game_over_check():
    out = objectives.clear_events(SOURCES, "Group")["src/events/a-eventinfo.h"]
    assert "EventScr_Turn1" not in out and "EventScr_OneLeft" not in out and "EventScr_Tutorial0" not in out
    assert "TURN(EVFLAG_WIN, EventScr_End, 6, 0, FACTION_BLUE)" in out
    assert "DefeatBoss(EventScr_End)" in out and "CauseGameOverIfLordDies" in out and out.count("END_MAIN") == 2


def test_reached_chapters_follow_the_links_from_the_first():
    links = [[{"to": 2}], [{"to": 0}], [{"to": None}], []]
    assert newchapter.reached_chapters(links) == {0, 2}


def test_the_story_order_follows_the_links():
    links = [[{"to": 2, "ending": True}], [], [{"to": 1, "ending": False}, {"to": 3, "ending": True}], []]
    assert newchapter.story_order(links) == [0, 2, 3, 1]


def test_an_emptied_group_does_not_need_the_game_s_units(monkeypatch):
    from types import SimpleNamespace

    from fe_maker import scope
    from fe_maker.decomp import units

    game = {"Emptied": SimpleNamespace(units=[{"character": "CHARACTER_SETH"}]),
            "Kept": SimpleNamespace(units=[{"character": "CHARACTER_FRANZ"}])}
    monkeypatch.setattr(units, "read_unit_groups", lambda decomp: game)
    monkeypatch.setattr(units, "chapter_unit_groups", lambda decomp, symbol: [{"name": "Emptied"}, {"name": "Kept"}])
    project = SimpleNamespace(decomp_dir=None, load=lambda name: {"unitGroups": {"Emptied": []}})
    data = SimpleNamespace(chapter_settings={"chapters": [{}]}, _chapter_event_symbol=lambda settings: "Group")
    assert scope._used(project, {0}, data)[0] == {"CHARACTER_FRANZ"}
