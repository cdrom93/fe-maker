"""Music the project imports (first demo, 30/10/2026): a MIDI file from the user's PC, played with one of the game's
instrument sets, as the player phase music of chapters.

The decomp converts each song of sound/songs/midi/ with mid2agb, with its own rule in songs.mk (instrument set -G,
reverb -R, priority -P, volume -V), links it through linker_script_sound.txt, and gSongTable (sound/song_table.s)
gives it its number: an imported song takes a free row of that table (dummy_song), its number goes to the
chapters' "bgm" settings. Files are named song<number>_fem_<key> (docker/entrypoint.sh removes such leftovers from
the working copy: the Makefile builds every .mid it finds, and one without its rule would stop the build).

Project data: data/music.json {"songs": {key: {"name", "voicegroup", "volume"}}, "chapters": {index: {phase: key}}};
files in the project's assets/music/<key>.mid. FE-Repo-Music songs mostly need the community instrument set NIMAP2,
not in the game: later.
"""

from __future__ import annotations

import re
from pathlib import Path

SONG_TABLE_FILE = "sound/song_table.s"
RULES_FILE = "songs.mk"
LINKER_FILE = "linker_script_sound.txt"
MIDI_DIR = "sound/songs/midi"
# Instruments and volume of the game's player phase music (song009_agbfe3_bgm_map_pl2 in songs.mk)
DEFAULT_VOICEGROUP, DEFAULT_VOLUME = 40, 53
PHASES = ("bluePhase", "redPhase", "greenPhase")


class MusicError(Exception):
    pass


def check_midi(data: bytes) -> None:
    if not data.startswith(b"MThd"):
        raise MusicError("notAMidi")


def song_name(number: int, key: str) -> str:
    return f"song{number:03d}_fem_{key}"


def safe_key(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")[:30] or "song"


def free_numbers(table: str) -> list[int]:
    """Rows of gSongTable holding dummy_song (row 0 excepted)."""
    rows = re.findall(r"^\s*song\s+(\w+)", table, re.MULTILINE)
    return [n for n, name in enumerate(rows) if name == "dummy_song" and n > 0]


def build_files(decomp_dir: Path, data: dict, assets_dir: Path) -> tuple[dict[str, str | bytes], dict[str, int]]:
    """Files of the songs the chapters use (decomp-relative path -> content) and each song's number."""
    songs = data.get("songs", {})
    used = sorted({key for phases in data.get("chapters", {}).values() for key in phases.values()
                   if key in songs and (assets_dir / "music" / f"{key}.mid").is_file()})
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
