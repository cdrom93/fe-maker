"""The sound room's list (gSoundRoomTable, src/soundroom_data.c): the project's imported songs join it (ticket 76).

A row is {bgmId, songLength (frames: the time bar and the move to the next song), displayCondFunc, nameTextId}, the
list ending with bgmId -1. The game shows a row once the song was heard (PlaySong unlocks the songs numbered below
128, a bit each in the save's sound room flags); a row with a display condition is a secret one, left out of the
completion percentage and shown when heard or when its condition holds. Imported songs take the song table's free
rows (music.build_files), the first ones below 128: those are unlocked when heard like the game's songs; the others
could never be, so they are secret rows always shown (the game's IsExtraSoundRoomEnabled returns TRUE). The menu's
flags hold 128 rows.
FEBuilderGBA edits the same table in its sound room editor (CREDITS.md).
"""

from __future__ import annotations

import re

from . import midi

DATA_FILE = "src/soundroom_data.c"
UNLOCKED_BELOW = 128   # PlaySong: songs numbered from there on are never unlocked
MAX_ROWS = 128          # SoundRoomProc.flags: 0x10 bytes
SHOWN = "(void *)IsExtraSoundRoomEnabled"   # a game function that returns TRUE
_END = re.compile(r"(\n[ \t]*\{\s*\.bgmId = -1,\s*\},\s*\};)")


def frames(data: bytes) -> int:
    """How long a MIDI file plays, in frames (60 a second): to its loop's end when it loops."""
    try:
        song = midi.read(data)
    except (midi.MidiError, IndexError):
        return 0
    end = song["loop"][1] if song["loop"] else song["end"]
    seconds, tick, tempo = 0.0, 0, 500000
    for at, value in song["tempos"]:
        if at >= end:
            break
        seconds += (at - tick) / song["division"] * tempo / 1e6
        tick, tempo = max(at, tick), value
    seconds += (end - tick) / song["division"] * tempo / 1e6
    return max(round(seconds * 60), 60)


def row_count(source: str) -> int:
    return len(re.findall(r"\.bgmId\s*=\s*[^-\s]", source))


def with_songs(source: str, songs: list[tuple[int, int, int]]) -> str:
    """The table with a row per (song number, length in frames, name message) before its end mark."""
    if not songs:
        return source
    match = _END.search(source)
    if not match or row_count(source) + len(songs) > MAX_ROWS:
        return source
    rows = "".join(
        f"\n    {{\n        .bgmId = {n},\n        .songLength = {length},\n"
        f"        .displayCondFunc = {'NULL' if n < UNLOCKED_BELOW else SHOWN},\n        .nameTextId = {msg},\n    }},"
        for n, length, msg in songs)
    source = source[:match.start()] + rows + source[match.start():]
    if any(n >= UNLOCKED_BELOW for n, _, _ in songs):
        head = source.index("struct SoundRoomEnt CONST_DATA gSoundRoomTable[]")
        source = source[:head] + "bool IsExtraSoundRoomEnabled(void);\n\n" + source[head:]
    return source
