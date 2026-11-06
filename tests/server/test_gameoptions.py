from pathlib import Path

import pytest

from fe_maker.decomp import gameoptions
from fe_maker.decomp.tweaks import TweakError

# Fictional excerpt in the shape of the decomp's InitPlayConfig (src/bmio.c).
SOURCE = """void InitPlayConfig(int isDifficult, s8 unk) {
    gPlaySt.config.animationType = 0;
    gPlaySt.config.autoCursor = 0;
    gPlaySt.config.textSpeed = 1; // a comment
    gPlaySt.config.gameSpeed = 0;
}

void Other(void) {
    gPlaySt.config.textSpeed = 1;
}
"""


def test_new_game_defaults_only_in_init_play_config():
    out = gameoptions.with_defaults(SOURCE, {"textSpeed": 2, "autoCursor": 1})
    assert "gPlaySt.config.textSpeed = 2; // a comment" in out and "gPlaySt.config.autoCursor = 1;" in out
    assert out.endswith("void Other(void) {\n    gPlaySt.config.textSpeed = 1;\n}\n")   # other functions untouched
    with pytest.raises(TweakError):
        gameoptions.with_defaults("void Something(void) {}", {"textSpeed": 2})


def test_options_are_checked():
    assert gameoptions.validate({"textSpeed": 3, "skipOpening": True}) is None
    assert gameoptions.validate({"textSpeed": 9}) == "badGameOption"
    assert gameoptions.validate({"skipOpening": 1}) == "badGameOption"
    assert gameoptions.validate({"somethingElse": True}) == "unknownGameOption"


def test_no_option_no_file(tmp_path):
    assert gameoptions.apply(tmp_path, {}, {}) == {}
    assert gameoptions.apply(tmp_path, {"textSpeed": 1}, {}) == {}   # the game's own default


def test_the_goal_display_is_added_to_init_play_config():
    # InitPlayConfig does not set it: the cleared state leaves it at 0
    out = gameoptions.with_defaults(SOURCE, {"objective": 1})
    assert "    gPlaySt.config.gameSpeed = 0;\n    gPlaySt.config.disableGoalDisplay = 1;\n}\n\nvoid Other" in out


def test_new_switches_are_known_and_stop_on_a_changed_decomp(tmp_path):
    assert gameoptions.validate({"quickExpBar": True, "quickLevelUp": True, "noSupportAnimations": True}) is None
    (tmp_path / "src").mkdir()
    (tmp_path / gameoptions.EXP_BAR_FILE).write_text("nothing here")
    with pytest.raises(TweakError):
        gameoptions.apply(tmp_path, {"quickExpBar": True}, {})


def test_the_story_intro_goes_with_the_world_map_tale_but_not_the_lord():
    root = Path(__file__).parents[2] / "decomp"
    if not (root / gameoptions.WORLD_MAP_INTRO_FILE).is_file():
        pytest.skip("no decomp")
    text = gameoptions.apply(root, {"skipStoryIntro": True}, {})[gameoptions.WORLD_MAP_INTRO_FILE]
    assert "WM_TEXT(0x08DB, 0)" not in text and "WM_SPAWNLORD(WM_MU_0, CHARACTER_EIRIKA" in text
    assert "EventScrWM_Prologue_ChapterIntro" in text


def test_every_switch_has_one_group():
    assert len(gameoptions.SWITCHES) == len(set(gameoptions.SWITCHES)) == 16


def test_a_unit_acts_after_a_talk():
    source = Path(__file__).parents[2] / "decomp" / gameoptions.RANGE_DISPLAY_FILE
    if not source.is_file():
        pytest.skip("no decomp")
    text = gameoptions.apply(source.parents[1], {"actAfterTalk": True}, {})[gameoptions.RANGE_DISPLAY_FILE]
    assert "PROC_CALL_2(FemAfterTalk)" in text and "gBmSt.taken_action |= 16;" in text


def test_the_danger_zone_is_written_with_the_other_range_option():
    source = (Path(__file__).parents[2] / "decomp" / gameoptions.RANGE_DISPLAY_FILE)
    if not source.exists():
        pytest.skip("no decomp")
    files = gameoptions.apply(source.parents[1], {"dangerZone": True, "stationaryRange": True}, {})
    text = files[gameoptions.RANGE_DISPLAY_FILE]
    assert "Select shows the enemies' range" in text and "movement AI 3" in text
    assert "if (gActiveUnit && (gActiveUnit->state & US_HAS_MOVED))" in text


def test_bars_and_bubble_tiles_wait_for_the_end_of_a_battle_animation():
    """Ticket 161: a battle quote's talk reloads the object UI graphics while the right fighter's sheet sits on the
    bars' and bubble's tiles."""
    source = Path(__file__).parents[2] / "decomp" / gameoptions.MAP_UI_FILE
    if not source.is_file():
        pytest.skip("no decomp")
    text = gameoptions.apply(source.parents[1], {"hpBars": True, "talkBubbles": True}, {})[gameoptions.MAP_UI_FILE]
    assert text.count("if (IsBattleDeamonActive())\n        return;") == 2


def test_growths_on_the_status_screen_colour_the_stat_names():
    """Ticket 166: Select shows the growths; each name takes its growth's colour (two palettes loaded with the screen)."""
    root = Path(__file__).parents[2] / "decomp"
    if not (root / gameoptions.STATUS_FILE).is_file():
        pytest.skip("no decomp")
    text = gameoptions.apply(root, {"statusGrowths": True}, {})[gameoptions.STATUS_FILE]
    assert "ApplyPalettes(sGrowthColorsFem[0], STATSCREEN_BGPAL_GROWTHS_FEM, 2);" in text
    assert text.index("ColorStatLabelsFem();") < text.index("// displaying mov stat value")
    assert "PutGrowthLabelFem(STATSCREEN_TEXT_BWL, y, MSG_4E9, 9);" in text
