import struct
import wave
from io import BytesIO

import pytest

from fe_maker.decomp import instruments, midi, music


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
    assert music.safe_key("Mon thème") == "mon_theme"
    assert music.song_name(87, "theme") == "song087_fem_theme"


# --- MIDI reading (fictional files) ---

def _track(events: bytes) -> bytes:
    return b"MTrk" + struct.pack(">I", len(events)) + events


def _midi(*tracks: bytes, division: int = 24) -> bytes:
    return b"MThd" + struct.pack(">IHHH", 6, 1, len(tracks), division) + b"".join(tracks)


def test_midi_notes_controls_tempo_and_loop():
    conductor = _track(
        b"\x18\xff\x58\x04\x04\x02\x18\x08"            # time signature at tick 24
        b"\xff\xff\xff\xff\x68\xff\x51\x03\x07\xa1\x20"  # delta -24 (as mid2agb reads it): tempo back to tick 0
        b"\x00\xff\x06\x01["                             # loop start
        b"\x30\xff\x06\x01]"                             # loop end at tick 48
        b"\x00\xff\x2f\x00")
    notes = _track(
        b"\x00\xc1\x05"                    # program 5, channel 1
        b"\x00\xb1\x07\x64"                # volume 100
        b"\x00\xb1\x0b\x50"                # expression: not kept (mid2agb ignores it)
        b"\x00\x91\x3c\x50"                # note 60 on
        b"\x0c\x3e\x50"                    # running status: note 62 on
        b"\x0c\x3c\x00"                    # note 60 off (velocity 0)
        b"\x00\xe1\x00\x50"                # pitch bend up
        b"\x0c\x81\x3e\x00"                # note 62 off
        b"\x00\xff\x2f\x00")
    song = midi.read(_midi(conductor, notes))
    assert song["tempos"] == [[0, 500000]]
    assert song["loop"] == [0, 48]
    events = song["channels"][1]
    assert [0, "p", 5] in events and [0, "c", 7, 100] in events
    assert not any(e[1] == "c" and e[2] == 11 for e in events)
    assert [0, "n", 60, 80, 24] in events and [12, "n", 62, 80, 24] in events
    assert [24, "b", (0x50 << 7) - 8192] in events


def test_not_a_midi():
    with pytest.raises(midi.MidiError, match="notAMidi"):
        midi.read(b"RIFF....")


# --- The game's instruments (fictional files in the decomp's shapes) ---

def _extended(value: float) -> bytes:
    exponent = 0
    while value >= 2:
        value, exponent = value / 2, exponent + 1
    return struct.pack(">HQ", 16383 + exponent, int(value * (1 << 63)))


def _aif(pcm: bytes, rate: float = 13379.0, loop: int | None = None) -> bytes:
    def chunk(name: bytes, body: bytes) -> bytes:
        return name + struct.pack(">I", len(body)) + body + (b"\0" if len(body) % 2 else b"")
    chunks = chunk(b"COMM", struct.pack(">HIH", 1, len(pcm), 8) + _extended(rate))
    if loop is not None:
        chunks += chunk(b"MARK", struct.pack(">H", 2) + struct.pack(">HIB", 1, loop, 5) + b"START"
                        + struct.pack(">HIB", 2, len(pcm), 3) + b"END")
        chunks += chunk(b"INST", bytes([60, 0, 0, 127, 1, 127]) + struct.pack(">hHHHHHH", 0, 1, 1, 2, 0, 0, 0))
    chunks += chunk(b"SSND", struct.pack(">II", 0, 0) + pcm)
    return b"FORM" + struct.pack(">I", 4 + len(chunks)) + b"AIFF" + chunks


def test_aif_samples_with_their_loop_become_wav():
    info = instruments.read_aif(_aif(bytes([0, 10, 20, 0xF6]), loop=2))
    assert round(info["rate"]) == 13379 and info["loop"] == 2 and info["pcm"] == bytes([0, 10, 20, 0xF6])
    with wave.open(BytesIO(instruments.to_wav(info))) as w:
        assert w.getframerate() == 13379 and w.readframes(4) == bytes([128, 138, 148, 118])
    assert instruments.read_aif(_aif(b"\0\0"))["loop"] is None


def _decomp(tmp_path):
    groups = tmp_path / "sound" / "voicegroups"
    groups.mkdir(parents=True)
    (groups / "voicegroup000.s").write_text(
        "\t.global voicegroup000\nvoicegroup000:\t@ 0x08200000\n"
        "\tvoice_directsound 60, 0, DirectSoundData_piano, 255, 0, 255, 165\t@08200000\n"
        "\tvoice_keysplit_all voicegroup001\t@0820000C\n"
        "\tvoice_square_1 0, 2, 0, 0, 15, 0\t@08200018\n"
        "\tvoice_noise 60, 0, 0, 1, 0, 0, 15, 2\t@08200024\n", encoding="utf-8")
    # a drum kit of one voice: its key 1 reads on into the next voicegroup, as in the ROM
    (groups / "voicegroup001.s").write_text(
        "\t.global voicegroup001\nvoicegroup001:\t@ 0x08200030\n"
        "\tvoice_directsound_no_resample 60, 70, DirectSoundData_kick, 255, 0, 255, 0\t@08200030\n", encoding="utf-8")
    (groups / "voicegroup002.s").write_text(
        "\t.global voicegroup002\nvoicegroup002:\t@ 0x0820003C\n"
        "\tvoice_programmable_wave wave000_sine, 0, 7, 15, 0\t@0820003C\n", encoding="utf-8")
    samples = tmp_path / "sound" / "direct_sound_samples"
    samples.mkdir()
    (samples / "piano.aif").write_bytes(_aif(b"\0\1"))
    (tmp_path / "sound" / "direct_sound_data.s").write_text(
        "\t.global DirectSoundData_piano\nDirectSoundData_piano:\n\t.incbin \"sound/direct_sound_samples/piano.bin\"\n",
        encoding="utf-8")
    return tmp_path


def test_voicegroups_read_by_address(tmp_path):
    decomp = _decomp(tmp_path)
    voices = instruments.voicegroup(decomp, 0)
    assert len(voices) == 128
    assert voices[0] == {"kind": "sample", "key": 60, "pan": 0, "sample": "piano", "env": [255, 0, 255, 165]}
    assert voices[2]["kind"] == "square" and voices[2]["duty"] == 2
    assert voices[3]["kind"] == "noise" and voices[3]["period"] == 1
    kit = voices[1]["voices"]
    assert kit[0]["kind"] == "fixed" and kit[0]["pan"] == 70
    assert kit[1]["kind"] == "wave"   # the next voicegroup's first voice
    assert voices[4]["kind"] == "fixed" and voices[6]["kind"] == "none"   # past the group: the next ones' voices
    assert instruments.voicegroup_numbers(decomp) == [0, 1, 2]
    assert instruments.sample_info(decomp, "piano")["pcm"] == b"\0\1"
    with pytest.raises(instruments.InstrumentError):
        instruments.voicegroup(decomp, 9)


def test_game_songs_named_from_songs_h(tmp_path):
    (tmp_path / "sound").mkdir()
    (tmp_path / "include" / "constants").mkdir(parents=True)
    (tmp_path / "sound" / "song_table.s").write_text(
        "gSongTable:\n\tsong dummy_song, 0, 0\n\tsong song001_agbfe3_bgm_theme, 1, 1\n"
        "\tsong song002_y_wind_3, 1, 1\n\tsong song003_se_sys_cursor, 2, 2\n", encoding="utf-8")
    (tmp_path / "songs.mk").write_text(
        "$(MID_SUBDIR)/song001_agbfe3_bgm_theme.s: %.s: %.mid\n\t$(MID2AGB) $< $@ -E -G007 -R020 -P010 -V090\n\n"
        "$(MID_SUBDIR)/song002_y_wind_3.s: %.s: %.mid\n\t$(MID2AGB) $< $@ -E -G008 -R020 -P010 -V100\n\n"
        "$(MID_SUBDIR)/song003_se_sys_cursor.s: %.s: %.mid\n\t$(MID2AGB) $< $@ -E -G009 -V100\n", encoding="utf-8")
    (tmp_path / "include" / "constants" / "songs.h").write_text(
        "enum {\n    SONG_NONE = 0x00,\n    SONG_THE_THEME = 0x01,\n    SONG_02 = 0x02,\n};\n", encoding="utf-8")
    assert music.game_songs(tmp_path) == [
        {"number": 1, "name": "The theme", "file": "song001_agbfe3_bgm_theme", "voicegroup": 7, "volume": 90,
         "constant": "SONG_THE_THEME"},
        {"number": 2, "name": "y wind 3", "file": "song002_y_wind_3", "voicegroup": 8, "volume": 100, "constant": "SONG_02"},
    ]


def test_chapter_choices_go_to_the_chapter_settings():
    bgm = {"bluePhase": 9, "redPhase": 19, "greenPhase": 15, "bluePhaseInHectorStory": 9, "redPhaseInHectorStory": 19,
           "greenPhaseInHectorStory": 15, "blueGreenPhaseAlt": 0xFFFF, "redPhaseAlt": 0xFFFF, "prologue": 0xFFFF}
    settings = [{"bgm": dict(bgm), "victorySongEnemyThreshold": 0}]
    data = {"chapters": {"0": {"bluePhase": "theme", "redPhase": 20, "prologue": 3, "unknown": 4},
                         "5": {"bluePhase": 1}},
            "victory": {"0": 2}}
    music.apply_choices(settings, data, {"theme": 87})
    chosen = settings[0]["bgm"]
    assert chosen["bluePhase"] == chosen["bluePhaseInHectorStory"] == 87
    assert chosen["redPhase"] == chosen["redPhaseInHectorStory"] == 20
    assert chosen["prologue"] == 3 and chosen["greenPhase"] == 15
    assert settings[0]["victorySongEnemyThreshold"] == 2


def test_a_decomp_without_sound_files_has_no_game_songs(tmp_path):
    assert music.game_songs(tmp_path) == [] and instruments.voicegroup_numbers(tmp_path) == []


_BATTLE_SOURCE = """void EkrPlayMainBGM(void)
{
    songid = gBanimFactionPal[gEkrInitialHitSide] != 1 ? SONG_ATTACK : SONG_DEFENSE;
    if (GetBattleAnimArenaFlag() == 1)
        EfxOverrideBgm(SONG_IN_THE_COLOSSEUM, 0x100);
    if (GetBanimLinkArenaFlag() == 1)
        EfxOverrideBgm(SONG_IN_THE_COLOSSEUM, 0x100);
    case 2:
        songid = SONG_CURING;
}

CONST_DATA int gBanimBossBGMs[3 * 2] = {
    CHARACTER_KING,             SONG_THE_THEME,
    CHARACTER_QUEEN,            SONG_ATTACK,
    -1, -1
};
"""


def _battle_decomp(tmp_path):
    (tmp_path / "src").mkdir()
    (tmp_path / "include" / "constants").mkdir(parents=True)
    (tmp_path / "src" / "banim-efxsound.c").write_text(_BATTLE_SOURCE, encoding="utf-8")
    (tmp_path / "include" / "constants" / "songs.h").write_text(
        "    SONG_THE_THEME = 0x1B,\n    SONG_ATTACK = 0x19,\n    SONG_DEFENSE = 0x1A,\n    SONG_CURING = 0x22,\n"
        "    SONG_IN_THE_COLOSSEUM = 0x39,\n", encoding="utf-8")
    return tmp_path


def test_battle_songs_read_from_the_battle_source(tmp_path):
    decomp = _battle_decomp(tmp_path)
    assert music.game_battle_songs(decomp) == {"playerAttacks": 0x19, "enemyAttacks": 0x1A, "healStaff": 0x22,
                                               "arena": 0x39}
    assert music.game_boss_songs(decomp) == {"CHARACTER_KING": 0x1B, "CHARACTER_QUEEN": 0x19}


def test_battle_songs_and_boss_themes_written_back(tmp_path):
    decomp = _battle_decomp(tmp_path)
    numbers = {"CHARACTER_KING": 5, "CHARACTER_QUEEN": 6, "CHARACTER_HERO": 1}
    data = {"battle": {"playerAttacks": "theme", "arena": 9, "unknown": 3},
            "bosses": {"CHARACTER_KING": music.NO_SONG, "CHARACTER_HERO": "theme"}}
    slots, bosses = music.battle_choices(decomp, data, {"theme": 87}, lambda who: numbers.get(who, 0))
    assert slots == {"playerAttacks": 87, "arena": 9}
    assert bosses == {5: music.NO_SONG, 6: 0x19, 1: 87}
    out = music.with_battle_songs(_BATTLE_SOURCE, slots, bosses)
    assert "!= 1 ? 0x57 : SONG_DEFENSE;" in out
    assert out.count("EfxOverrideBgm(0x9, 0x100);") == 2   # the arena and the link arena
    assert "CONST_DATA int gBanimBossBGMs[3 * 2] = {\n    0x1, 0x57,\n    0x6, 0x19,\n    -1, -1\n};" in out
    assert music.battle_choices(decomp, {"battle": {"arena": 9}}, {}, numbers.get)[1] is None   # table kept as is


def test_scene_songs_defined_for_the_event_scripts():
    sources = ["MUSC(SONG_TENSION)\nMUSC(FEM_SONG_my_theme)\n", "MUSCSLOW(FEM_SONG_gone)\nFEM_SONG_my_themes"]
    keys = music.scene_songs(sources)
    assert keys == {"my_theme", "gone", "my_themes"}
    assert music.scene_defines({"my_theme", "gone"}, {"my_theme": 87}) == (
        "#define FEM_SONG_gone 0x0\n#define FEM_SONG_my_theme 0x57\n")   # a song since removed: no music
