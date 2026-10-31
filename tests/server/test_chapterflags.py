from pathlib import Path

import pytest

from fe_maker.decomp import chapterflags

SOURCE = """void ResetChapterFlags(void) {
    int i;

    for (i = 0; i < (32 + 8) / 8; i++) {
        gChapterFlagBits[i] = 0;
    }
}

int GetChapterFlagBitsSize(void) {
    return 5;
}
"""


def test_only_flags_past_the_games_count():
    assert not chapterflags.uses_late_flags(["Door(8, 3, EVFLAG_TMP(40))", "EVFLAG_TMP(100)"])
    assert chapterflags.uses_late_flags(["Door(8, 3, EVFLAG_TMP(41))"])


def test_chapters_clear_every_flag_and_a_suspend_keeps_seven_bytes():
    out = chapterflags.with_late_flags(SOURCE.replace("\n", "\r\n"))
    assert "i < 16;" in out and "return 7;" in out


def test_another_decomp_is_refused():
    with pytest.raises(chapterflags.ChapterFlagsError):
        chapterflags.with_late_flags("")


def test_the_real_file_matches():
    path = Path(__file__).parents[2] / "decomp" / chapterflags.FILE
    if path.is_file():
        assert "return 7;" in chapterflags.with_late_flags(path.read_text(encoding="utf-8", errors="replace"))
