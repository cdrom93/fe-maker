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
