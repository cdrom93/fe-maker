"""Songs in the game's music assembly (FE-Repo-Music's .s files) turned into MIDI files (decomp/songasm.py), and
FE-Repo-Music's list (ferepo_music.py). The songs here are written for the test."""

import pytest

from fe_maker import ferepo_music
from fe_maker.decomp import midi, songasm

SONG = """\t.include "MPlayDef.s"

\t.equ\tmy-song_grp, voicegroup000
\t.equ\tmy-song_pri, 0
\t.equ\tmy-song_mvl, 100
\t.equ\tmy-song_key, 0
\t.equ\tmy-song_tbs, 1

\t.section .rodata
\t.global\tmy-song
\t.align\t2

my-song_1:
\t.byte\tKEYSH , my-song_key+0
\t.byte\tTEMPO , 120*my-song_tbs/2
\t.byte\t\tVOICE , 48
\t.byte\t\tVOL   , 90*my-song_mvl/mxv
\t.byte\t\tPAN   , c_v-10
\t.byte\t\tN12   , Cn3 , v100
\t.byte\tW12
my-song_1_loop:
\t.byte\tTEMPO , 150*my-song_tbs/2
\t.byte\t\t        Dn3
\t.byte\tW12
\t.byte\tPATT
\t .word\tmy-song_1_pattern
\t.byte\t\tTIE   , En3 , v080
\t.byte\tW24
\t.byte\t\tEOT
\t.byte\tGOTO
\t .word\tmy-song_1_loop
\t.byte\tFINE

my-song_1_pattern:
\t.byte\t\tN06   , Gn3 , v090, gtp1
\t.byte\tW06
\t.byte\tPEND

my-song_2:
\t.byte\t\tVOICE , 0
\t.byte\t\tMOD 2
\t.byte\t\tN24   , CnM1 , v127
\t.byte\tW24
\t.byte\tFINE

\t.align\t2
my-song:
\t.byte\t2\t@ NumTrks
\t.byte\t0\t@ NumBlks
\t.byte\tmy-song_pri\t@ Priority
\t.byte\tmy-song_rev\t@ Reverb.
\t.word\tmy-song_grp
\t.word\tmy-song_1
\t.word\tmy-song_2
\t.end
"""


def test_a_song_becomes_a_midi_file():
    song = midi.read(songasm.to_midi(SONG))
    assert song["division"] == 24
    assert song["tempos"] == [[0, 500000], [12, 400000]]
    assert song["loop"] == [12, 54]
    notes = [e for e in song["channels"][0] if e[1] == "n"]
    # running status over TEMPO (D3 plays as the N12 before it), the pattern's note with its added gate time, the tie
    assert notes == [[0, "n", 60, 100, 12], [12, "n", 62, 100, 12], [24, "n", 67, 90, 7], [30, "n", 64, 80, 24]]
    assert [0, "p", 48] in song["channels"][0]
    assert [0, "c", 7, 90] in song["channels"][0] and [0, "c", 10, 54] in song["channels"][0]
    assert [e for e in song["channels"][1] if e[1] == "n"] == [[0, "n", 12, 127, 24]]
    assert songasm.song_volume(SONG) == 100


def test_not_a_song():
    with pytest.raises(songasm.SongAsmError):
        songasm.to_midi("\t.include \"MPlayDef.s\"\n")


def test_ferepo_music_lists_songs_with_their_recordings():
    paths = ["Game OSTs/Some Series/Song A {Ann, Bob}.s", "Game OSTs/Some Series/Song A {Ann, Bob}.ogg",
             "OC Artist Songs/Cid/Cid - Song B.s", "GBA Soundfonts/x.s", "[AA] Direct Play .S Files {7743}/y.s",
             "README.md"]
    songs = ferepo_music.songs(paths)
    assert [s["name"] for s in songs] == ["Song A", "Cid - Song B"]
    assert songs[0]["authors"] == ["Ann", "Bob"] and songs[0]["preview"].endswith(".ogg")
    assert songs[1]["authors"] == ["Cid"] and songs[1]["preview"] is None
    found, total = ferepo_music.search(songs, "cid")
    assert total == 1 and found[0]["folder"] == "OC Artist Songs/Cid"
    assert ferepo_music.search(songs, folder="Game OSTs")[1] == 1
    source = ferepo_music.source(paths[0])
    assert source["license"] == "Unlicense" and source["url"].startswith(ferepo_music.PAGE_PREFIX)


def test_ferepo_music_refuses_other_paths():
    with pytest.raises(ferepo_music.FeRepoMusicError):
        ferepo_music.fetch_song("../secret.s")
    with pytest.raises(ferepo_music.FeRepoMusicError):
        ferepo_music.fetch_preview("Game OSTs/song.exe")
