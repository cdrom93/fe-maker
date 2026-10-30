import pytest

from fe_maker.decomp import music


def test_midi_files_only():
    music.check_midi(b"MThd\x00\x00\x00\x06")
    with pytest.raises(music.MusicError, match="notAMidi"):
        music.check_midi(b"RIFF....")


def test_free_rows_of_the_song_table():
    # Fictional table in the shape of sound/song_table.s
    table = "gSongTable:\n\tsong dummy_song, 0, 0\n\tsong song001_x, 1, 1\n\tsong dummy_song, 0, 0\n"
    assert music.free_numbers(table) == [2]   # row 0 stays


def test_song_names():
    assert music.safe_key("Ma Chanson (v2)!") == "ma_chanson_v2"
    assert music.song_name(87, "theme") == "song087_fem_theme"
