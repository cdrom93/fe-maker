"""Music the project imports (first demo, 30/10/2026): a MIDI file from the user's PC, played with one of the game's
instrument sets, as the player phase music of chapters.

The decomp converts each song of sound/songs/midi/ with mid2agb, with its own rule in songs.mk (instrument set -G,
reverb -R, priority -P, volume -V), links it through linker_script_sound.txt, and gSongTable (sound/song_table.s)
gives it its number: an imported song takes a free row of that table (dummy_song), its number goes to the
chapters' "bgm" settings. Files are named song<number>_fem_<key> (docker/entrypoint.sh removes such leftovers from
the working copy: the Makefile builds every .mid it finds, and one without its rule would stop the build).

Project data: data/music.json {"songs": {key: {"name", "voicegroup", "volume"}}, "chapters": {index: {slot: song}},
"victory": {index: enemies}}, a song being an imported key (str) or a game song number (int, NO_SONG for none);
files in the project's assets/music/<key>.mid. FE-Repo-Music songs mostly need the community instrument set NIMAP2,
not in the game: later.

Chapter slots (mapBgmIds in the chapter settings, chosen by GetCurrentMapMusicIndex in bm.c): the three phases, their
variants once EVFLAG_BGM_CHANGE is set (one shared by the player and allied phases, one for the enemy phase), and the
opening (MAP_BGM_PROLOGUE, played by the chapter intro, none = 0xFFFF). The Hector story copies follow the phases.
victorySongEnemyThreshold: the player phase plays SONG_GRASP_AT_VICTORY once that few enemies are left (0: never).
"""

from __future__ import annotations

import re
import unicodedata
from pathlib import Path

SONG_TABLE_FILE = "sound/song_table.s"
RULES_FILE = "songs.mk"
LINKER_FILE = "linker_script_sound.txt"
MIDI_DIR = "sound/songs/midi"
# Instruments and volume of the game's player phase music (song009_agbfe3_bgm_map_pl2 in songs.mk)
DEFAULT_VOICEGROUP, DEFAULT_VOLUME = 40, 53
PHASES = ("bluePhase", "redPhase", "greenPhase")
SLOTS = (*PHASES, "blueGreenPhaseAlt", "redPhaseAlt", "prologue")
OPTIONAL_SLOTS = ("blueGreenPhaseAlt", "redPhaseAlt", "prologue")   # may be "none"
NO_SONG = 0xFFFF
SONGS_HEADER = "include/constants/songs.h"
FIRST_SOUND_EFFECT = 0x60   # rows from there on are sound effects


class MusicError(Exception):
    pass


def check_midi(data: bytes) -> None:
    if not data.startswith(b"MThd"):
        raise MusicError("notAMidi")


def song_name(number: int, key: str) -> str:
    return f"song{number:03d}_fem_{key}"


def safe_key(text: str) -> str:
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()   # accents dropped, letters kept
    return re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")[:30] or "song"


def free_numbers(table: str) -> list[int]:
    """Rows of gSongTable holding dummy_song (row 0 excepted)."""
    rows = re.findall(r"^\s*song\s+(\w+)", table, re.MULTILINE)
    return [n for n, name in enumerate(rows) if name == "dummy_song" and n > 0]


def song_rules(rules: str) -> dict[str, tuple[int, int]]:
    """Each song's instrument set and volume (mid2agb's -G and -V in songs.mk), by file name."""
    return {m.group(1): (int(m.group(2)), int(m.group(3))) for m in re.finditer(
        r"^\$\(MID_SUBDIR\)/(\w+)\.s:[^\n]*\n\t[^\n]*?-G(\d+)[^\n]*?-V(\d+)", rules, re.MULTILINE)}


def _title(constant: str) -> str:
    words = constant.removeprefix("SONG_").replace("_", " ").lower()
    return words[:1].upper() + words[1:]


def game_songs(decomp_dir: Path) -> list[dict]:
    """The game's music (sound effects left out): {"number", "name", "file", "voicegroup", "volume"}."""
    if not (decomp_dir / SONG_TABLE_FILE).is_file() or not (decomp_dir / RULES_FILE).is_file():
        return []   # a decomp without its sound files (the interface tests' fictional one)
    table =(decomp_dir / SONG_TABLE_FILE).read_text(encoding="utf-8")
    rules = song_rules((decomp_dir / RULES_FILE).read_text(encoding="utf-8"))
    names: dict[int, str] = {}
    header = decomp_dir / SONGS_HEADER
    if header.is_file():
        text = header.read_text(encoding="utf-8")
        for m in re.finditer(r"^\s*(SONG_\w+)\s*=\s*(0x[0-9A-Fa-f]+|\d+)", text, re.MULTILINE):
            if not re.fullmatch(r"SONG_[0-9A-F]{2}", m.group(1)):
                names.setdefault(int(m.group(2), 0), _title(m.group(1)))
    out = []
    for number, name in enumerate(re.findall(r"^\s*song\s+(\w+)", table, re.MULTILINE)):
        if number >= FIRST_SOUND_EFFECT or name not in rules or "_se_" in name:
            continue
        voicegroup, volume = rules[name]
        label = names.get(number) or re.sub(r"^song\d+_(agbfe3_)?(bgm_)?", "", name).replace("_", " ")
        out.append({"number": number, "name": label, "file": name, "voicegroup": voicegroup, "volume": volume})
    return out


def midi_path(decomp_dir: Path, file: str) -> Path:
    return decomp_dir / MIDI_DIR / f"{file}.mid"


def apply_choices(settings: list[dict], data: dict, numbers: dict[str, int]) -> None:
    """The chapters' song choices into the chapter settings (imported songs by the numbers build_files gave them)."""
    for index, slots in data.get("chapters", {}).items():
        if int(index) >= len(settings):
            continue
        for slot, song in slots.items():
            number = numbers.get(song) if isinstance(song, str) else song
            if number is None or slot not in SLOTS:
                continue
            for field in (slot, slot + "InHectorStory") if slot in PHASES else (slot,):
                if field in settings[int(index)].get("bgm", {}):
                    settings[int(index)]["bgm"][field] = int(number)
    for index, enemies in data.get("victory", {}).items():
        if int(index) < len(settings):
            settings[int(index)]["victorySongEnemyThreshold"] = max(0, min(int(enemies), 127))   # an s8


def build_files(decomp_dir: Path, data: dict, assets_dir: Path) -> tuple[dict[str, str | bytes], dict[str, int]]:
    """Files of the songs the chapters use (decomp-relative path -> content) and each song's number."""
    songs = data.get("songs", {})
    used = sorted({key for slots in data.get("chapters", {}).values() for key in slots.values()
                   if isinstance(key, str) and key in songs and (assets_dir / "music" / f"{key}.mid").is_file()})
    if not used:
        return {}, {}
    table = (decomp_dir / SONG_TABLE_FILE).read_text(encoding="utf-8")
    rules = (decomp_dir / RULES_FILE).read_text(encoding="utf-8")
    linker = (decomp_dir / LINKER_FILE).read_text(encoding="utf-8")
    free = free_numbers(table)
    if len(used) > len(free):
        raise MusicError("noFreeSong")
    rows = list(re.finditer(r"^\s*song\s+(\w+)\s*,[^\n]*$", table, re.MULTILINE))
    files: dict[str, str | bytes] = {}
    numbers: dict[str, int] = {}
    links = ""
    for key, n in zip(used, free):
        info, name = songs[key], song_name(n, key)
        numbers[key] = n
        row = rows[n]
        table = table[:row.start()] + f"\tsong {name}, 1, 1" + table[row.end():]
        rows = list(re.finditer(r"^\s*song\s+(\w+)\s*,[^\n]*$", table, re.MULTILINE))
        files[f"{MIDI_DIR}/{name}.mid"] = (assets_dir / "music" / f"{key}.mid").read_bytes()
        voicegroup, volume = int(info.get("voicegroup", DEFAULT_VOICEGROUP)), int(info.get("volume", DEFAULT_VOLUME))
        rules += f"\n$(MID_SUBDIR)/{name}.s: %.s: %.mid\n\t$(MID2AGB) $< $@ -E -G{voicegroup:03d} -R020 -P010 -V{volume:03d}\n"
        links += f"{MIDI_DIR}/{name}.o(.rodata);\n"
    last = list(re.finditer(rf"^{re.escape(MIDI_DIR)}/\w+\.o\(\.rodata\);\n", linker, re.MULTILINE))[-1]
    files[SONG_TABLE_FILE] = table
    files[RULES_FILE] = rules
    files[LINKER_FILE] = linker[:last.end()] + links + linker[last.end():]
    return files, numbers
