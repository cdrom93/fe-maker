"""Music the project imports (first demo, 30/10/2026): a MIDI file from the user's PC, played with one of the game's
instrument sets, as the player phase music of chapters.

The decomp converts each song of sound/songs/midi/ with mid2agb, with its own rule in songs.mk (instrument set -G,
reverb -R, priority -P, volume -V), links it through linker_script_sound.txt, and gSongTable (sound/song_table.s)
gives it its number: an imported song takes a free row of that table (dummy_song), its number goes to the
chapters' "bgm" settings. Files are named song<number>_fem_<key> (docker/entrypoint.sh removes such leftovers from
the working copy: the Makefile builds every .mid it finds, and one without its rule would stop the build).

Project data: data/music.json {"songs": {key: {"name", "voicegroup", "volume"}}, "chapters": {index: {slot: song}},
"victory": {index: enemies}, "battle": {slot: song}, "bosses": {character id: song}}, a song being an imported key
(str) or a game song number (int, NO_SONG for none);
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

from . import midi, nimap

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
    constants = {n: c for c, n in reversed(list(song_constants(decomp_dir).items()))}
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
        out.append({"number": number, "name": label, "file": name, "voicegroup": voicegroup, "volume": volume,
                    "constant": constants.get(number, "")})
    return out


def midi_path(decomp_dir: Path, file: str) -> Path:
    return decomp_dir / MIDI_DIR / f"{file}.mid"


def apply_choices(settings: list[dict], data: dict, numbers: dict[str, int]) -> None:
    """The chapters' song choices into the chapter settings (imported songs by the numbers build_files gave them)."""
    for index, slots in data.get("chapters", {}).items():
        if int(index) >= len(settings):
            continue
        for slot, song in slots.items():
            number = numbers.get(song) if isinstance(song, str) else numbers.get(MAP_ROW + str(song), song)
            if number is None or slot not in SLOTS:
                continue
            for field in (slot, slot + "InHectorStory") if slot in PHASES else (slot,):
                if field in settings[int(index)].get("bgm", {}):
                    settings[int(index)]["bgm"][field] = int(number)
    for index, enemies in data.get("victory", {}).items():
        if int(index) < len(settings):
            settings[int(index)]["victorySongEnemyThreshold"] = max(0, min(int(enemies), 127))   # an s8


# Battle music (src/banim-efxsound.c, EkrPlayMainBGM): the song the battle screen plays, by situation, and the
# boss themes (gBanimBossBGMs: character, song pairs ended by -1; only for a unit not of the player's side, on the
# left of the battle screen). A slot is the SONG_ constant written at that spot of the source; the project's choice
# replaces it there with a number. FE8's Healing / Curing names are crossed: healing staves play SONG_CURING.
BATTLE_FILE = "src/banim-efxsound.c"
BATTLE_SLOTS = {
    "playerAttacks": ("SONG_ATTACK", r"\? SONG_ATTACK :"),
    "enemyAttacks": ("SONG_DEFENSE", r": SONG_DEFENSE;"),
    "healStaff": ("SONG_CURING", r"songid = SONG_CURING;"),
    "statusStaff": ("SONG_HEALING", r"songid = SONG_HEALING;"),
    "dance": ("SONG_TETHYS", r"EfxOverrideBgm\(SONG_TETHYS,"),
    "promotion": ("SONG_TO_A_HIGHER_PLACE", r"EfxOverrideBgm\(SONG_TO_A_HIGHER_PLACE,"),
    "arena": ("SONG_IN_THE_COLOSSEUM", r"EfxOverrideBgm\(SONG_IN_THE_COLOSSEUM,"),
}
_BOSS_TABLE = re.compile(r"(CONST_DATA int gBanimBossBGMs\[)[^\]]*(\] = \{\n)(.*?)(\n\};)", re.DOTALL)


# Scenes: an event command's song argument is a SONG_ constant, or SCENE_PREFIX + an imported song's key, defined at
# build time in the event macros (include/EAstdlib.h) with the song's number (0, no music, for a song since removed).
SCENE_PREFIX = "FEM_SONG_"


def scene_songs(sources) -> set[str]:
    """Keys of the imported songs event scripts name."""
    return {m for text in sources for m in re.findall(rf"\b{SCENE_PREFIX}(\w+)", text)}


def scene_defines(keys: set[str], numbers: dict[str, int]) -> str:
    return "".join(f"#define {SCENE_PREFIX}{key} 0x{numbers.get(key, 0):X}\n" for key in sorted(keys))


def song_constants(decomp_dir: Path) -> dict[str, int]:
    header = decomp_dir / SONGS_HEADER
    if not header.is_file():
        return {}
    return {m.group(1): int(m.group(2), 0) for m in re.finditer(
        r"^\s*(SONG_\w+)\s*=\s*(0x[0-9A-Fa-f]+|\d+)", header.read_text(encoding="utf-8"), re.MULTILINE)}


def game_battle_songs(decomp_dir: Path) -> dict[str, int]:
    """The game's song for each battle slot found in the source."""
    path = decomp_dir / BATTLE_FILE
    if not path.is_file():
        return {}
    source, numbers = path.read_text(encoding="utf-8"), song_constants(decomp_dir)
    return {slot: numbers[name] for slot, (name, spot) in BATTLE_SLOTS.items()
            if name in numbers and re.search(spot, source)}


def game_boss_songs(decomp_dir: Path) -> dict[str, int]:
    """The game's boss themes: character constant (or number) -> song number."""
    path = decomp_dir / BATTLE_FILE
    m = _BOSS_TABLE.search(path.read_text(encoding="utf-8")) if path.is_file() else None
    if not m:
        return {}
    numbers = song_constants(decomp_dir)
    pairs = re.findall(r"(\w+)\s*,\s*(\w+)\s*,", m.group(3))
    return {who: numbers.get(song, int(song, 0) if song[:1].isdigit() else NO_SONG)
            for who, song in pairs if who != "-1"}


# The game plays a character's theme only for the battle's left unit, and never for the player's units; with themes
# chosen in FE Maker, a theme plays in either camp, the left unit's first (ticket 77; FEBuilderGBA's battle BGM of
# player units does the like, CREDITS.md).
BOSS_CAMP = """    songid2 = GetBanimBossBGM(&bul->unit);

    if (UNIT_FACTION(GetUnitFromCharId(UNIT_CHAR_ID(&bul->unit))) == FACTION_BLUE)
        songid2 = -1;

    if (gBanimValid[POS_L] == false)
        songid2 = -1;
"""
BOTH_CAMPS = """    songid2 = GetBanimBossBGM(&bul->unit);

    if (gBanimValid[POS_L] == false)
        songid2 = -1;

    if (songid2 == -1 && gBanimValid[POS_R] != false)
        songid2 = GetBanimBossBGM(&bur->unit);
"""


def with_battle_songs(source: str, slots: dict[str, int], bosses: dict[int, int] | None) -> str:
    """The battle source with the chosen songs: slots by number, and, when bosses is given, the whole boss table
    (character number -> song; NO_SONG: no theme) rewritten with numbers, as large as needed."""
    for slot, number in slots.items():
        name, spot = BATTLE_SLOTS[slot]
        source = re.sub(spot, lambda m, n=name, v=number: m.group(0).replace(n, f"0x{v:X}"), source)
    if bosses is not None:
        source = source.replace(BOSS_CAMP, BOTH_CAMPS)
        m = _BOSS_TABLE.search(source)
        if m:
            rows = [f"    0x{who:X}, 0x{song:X}," for who, song in sorted(bosses.items()) if song != NO_SONG]
            body = "\n".join([*rows, "    -1, -1"])
            source = source[:m.start()] + f"{m.group(1)}{len(rows) + 1} * 2{m.group(2)}{body}{m.group(4)}" + source[m.end():]
    return source


def battle_choices(decomp_dir: Path, data: dict, numbers: dict[str, int], character_number) -> tuple[dict, dict | None]:
    """The project's battle slots (song numbers) and, if any boss theme changed, the whole boss table."""
    def number(ref):
        return numbers.get(ref) if isinstance(ref, str) else ref

    slots = {s: n for s, ref in data.get("battle", {}).items() if s in BATTLE_SLOTS and (n := number(ref)) is not None}
    chosen = data.get("bosses", {})
    if not chosen:
        return slots, None
    table = {character_number(who): song for who, song in game_boss_songs(decomp_dir).items()}
    for who, ref in chosen.items():
        n, pid = number(ref), character_number(who)
        if n is not None and pid:
            table[pid] = n
    return slots, table


# Fixed screens: the songs the game starts by name outside chapters and battles. Each screen: the constants it starts
# (a call of the sound functions naming one) and the files where it does; a choice replaces them there by a number.
# Left alone: the link arena (sio_*), the sound room's list, the world map (gWMSongTable, by location).
_SONG_CALL = r"\b(?:StartBgm|StartBgmExt|StartBgmCore|StartBgmFadeIn|ChangeBgm|OverrideBgm)\(\s*"
SCREEN_SLOTS: dict[str, tuple[tuple[str, ...], tuple[str, ...]]] = {
    "intro": (("0x1",), ("src/opanim-main.c",)),
    "title": (("SONG_MAIN_THEME", "SONG_MAIN_THEME_EXT"),
              ("src/titlescreen.c", "src/soundroom.c", "src/uisupport.c", "src/gamecontrol.c")),
    "storyIntro": (("SONG_PROLOGUE",), ("src/opsubtitle.c",)),
    "preparations": (("SONG_COMBAT_PREPARATION",), ("src/prep_menuproc.c", "src/prep_sallycursor.c",
                                                     "src/prep_itemuse.c", "src/classchg-main.c", "src/uiconfig.c",
                                                     "src/uisupport.c")),
    "prepSupports": (("SONG_BONDS",), ("src/prepscreen.c", "src/prep_atmenu.c")),
    "supportViewer": (("SONG_DISTANT_ROADS",), ("src/savemenu.c", "src/uisupport.c")),
    "shop": (("SONG_SHOPS",), ("src/bmshop.c",)),
    "armory": (("SONG_ARMORIES",), ("src/bmshop.c",)),
    "arenaMenu": (("SONG_COLOSSEUM_ENTRANCE",), ("src/uiarena.c", "src/prep_itemuse.c")),
    "arenaVictory": (("SONG_COLOSSEUM_VICTORY",), ("src/uiarena.c",)),
    "allyDeath": (("SONG_IN_SORROWS_SHROUD",), ("src/eventinfo.c",)),
    "gameOver": (("SONG_GAME_OVER",), ("src/gameoverbgfx.c", "src/eventinfo.c")),
    "epilogue": (("SONG_EPILOGUE",), ("src/ending_details.c",)),
    "credits": (("SONG_BGM_ED_STAFF_2",), ("src/ending_details.c",)),
    "dungeonRecord": (("SONG_RECORDS",), ("src/bmdifficulty.c",)),
}


def _screen_call(constant: str) -> str:
    return _SONG_CALL + re.escape(constant) + r"\b"


def game_screen_songs(decomp_dir: Path) -> dict[str, int]:
    """The song each fixed screen plays in the game (its first constant), for the screens this decomp has."""
    numbers = song_constants(decomp_dir)
    out = {}
    for slot, (constants, files) in SCREEN_SLOTS.items():
        first = constants[0]
        number = int(first, 0) if first[:1].isdigit() else numbers.get(first)
        sources = [p.read_text(encoding="utf-8") for rel in files if (p := decomp_dir / rel).is_file()]
        if number is not None and any(re.search(_screen_call(c), s) for c in constants for s in sources):
            out[slot] = number
    return out


def with_screen_songs(read, slots: dict[str, int]) -> dict[str, str]:
    """The files of the fixed screens given another song (read(rel) -> current text): changed files only."""
    out: dict[str, str] = {}
    for slot, number in slots.items():
        constants, files = SCREEN_SLOTS[slot]
        for rel in files:
            before = out.get(rel) or read(rel)
            if before is None:
                continue
            source = before
            for constant in constants:
                source = re.sub(_screen_call(constant), lambda m, c=constant, n=number: m.group(0).replace(c, f"0x{n:X}"),
                                source)
            if source != before:
                out[rel] = source
    return out


def screen_choices(data: dict, numbers: dict[str, int]) -> dict[str, int]:
    return {s: n for s, ref in data.get("screens", {}).items()
            if s in SCREEN_SLOTS and (n := numbers.get(ref) if isinstance(ref, str) else ref) is not None}


GAME_TRACKS = 8   # tracks of the game's music players (sound/music_player_table.s); 16 with the option musicTracks


def track_count(data: bytes) -> int:
    """Tracks the game makes of a MIDI file: mid2agb gives each MIDI channel playing notes a track."""
    try:
        song = midi.read(data)
    except (midi.MidiError, IndexError):
        return 0
    return sum(1 for events in song["channels"].values() if any(e[1] == "n" for e in events))


MAP_ROW = "#"   # numbers' key prefix: a game song's copy on the map's music player (build_files)


def _map_rows(table: str, data: dict) -> list[int]:
    """Game songs the chapters play on the map that the song table puts on music player 0, the battles' (the opening's
    and the title's songs): a battle there overwrites them, and after it the game takes up player 1's song again, which
    is none (ticket 74). They get a copy of their row on player 1."""
    rows = re.findall(r"^\s*song\s+\w+\s*,\s*(\d+)", table, re.MULTILINE)
    chosen = {song for slots in data.get("chapters", {}).values() for slot, song in slots.items() if slot in SLOTS}
    return sorted(n for n in chosen if isinstance(n, int) and 0 < n < len(rows) and rows[n] == "0")


def build_files(decomp_dir: Path, data: dict, assets_dir: Path) -> tuple[dict[str, str | bytes], dict[str, int]]:
    """Files of the songs the chapters and battles use (decomp-relative path -> content) and each song's number;
    a game song copied on the map's music player (_map_rows) under MAP_ROW + its number."""
    songs = data.get("songs", {})
    refs = [*(key for slots in data.get("chapters", {}).values() for key in slots.values()),
            *data.get("battle", {}).values(), *data.get("bosses", {}).values(), *data.get("scenes", []),
            *data.get("screens", {}).values()]
    used = sorted({key for key in refs
                   if isinstance(key, str) and key in songs and (assets_dir / "music" / f"{key}.mid").is_file()})
    path = decomp_dir / SONG_TABLE_FILE
    table = path.read_text(encoding="utf-8") if used or path.is_file() else ""
    copies = _map_rows(table, data)
    if not used and not copies:
        return {}, {}
    free = free_numbers(table)
    if len(used) + len(copies) > len(free):
        raise MusicError("noFreeSong")
    rows = list(re.finditer(r"^\s*song\s+(\w+)\s*,[^\n]*$", table, re.MULTILINE))
    files: dict[str, str | bytes] = {}
    numbers: dict[str, int] = {}
    for song, n in zip(copies, free[len(used):]):   # the same song, on the map's player
        numbers[MAP_ROW + str(song)] = n
        table = table[:rows[n].start()] + f"\tsong {rows[song].group(1)}, 1, 1" + table[rows[n].end():]
        rows = list(re.finditer(r"^\s*song\s+(\w+)\s*,[^\n]*$", table, re.MULTILINE))
    if not used:
        files[SONG_TABLE_FILE] = table
        return files, numbers
    rules = (decomp_dir / RULES_FILE).read_text(encoding="utf-8")
    linker = (decomp_dir / LINKER_FILE).read_text(encoding="utf-8")
    links = ""
    general_midi = None
    if any(songs[key].get("voicegroup") == nimap.KEY for key in used):   # NIMAP2, a voicegroup of its own
        nimap_files, linker = nimap.build_files(decomp_dir, linker)
        files.update(nimap_files)
        general_midi = nimap.number(decomp_dir)
    for key, n in zip(used, free):
        info, name = songs[key], song_name(n, key)
        numbers[key] = n
        row = rows[n]
        table = table[:row.start()] + f"\tsong {name}, 1, 1" + table[row.end():]
        rows = list(re.finditer(r"^\s*song\s+(\w+)\s*,[^\n]*$", table, re.MULTILINE))
        files[f"{MIDI_DIR}/{name}.mid"] = (assets_dir / "music" / f"{key}.mid").read_bytes()
        group = info.get("voicegroup", DEFAULT_VOICEGROUP)
        voicegroup = general_midi if group == nimap.KEY else int(group)
        volume = int(info.get("volume", DEFAULT_VOLUME))
        rules += f"\n$(MID_SUBDIR)/{name}.s: %.s: %.mid\n\t$(MID2AGB) $< $@ -E -G{voicegroup:03d} -R020 -P010 -V{volume:03d}\n"
        links += f"{MIDI_DIR}/{name}.o(.rodata);\n"
    last = list(re.finditer(rf"^{re.escape(MIDI_DIR)}/\w+\.o\(\.rodata\);\n", linker, re.MULTILINE))[-1]
    files[SONG_TABLE_FILE] = table
    files[RULES_FILE] = rules
    files[LINKER_FILE] = linker[:last.end()] + links + linker[last.end():]
    return files, numbers
