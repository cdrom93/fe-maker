"""Small engine tweaks applied to the decomp sources at build time, on the user's machine.

FE Maker stores only the instruction (anchor + inserted lines, our own code); the
modified decomp file is generated locally in the build overlay and never
distributed. If an anchor is not found (the decomp changed), the build stops
with a clear error instead of producing a broken game.
"""

from __future__ import annotations

import re
from pathlib import Path

from . import units

GAME_CONTROL_FILE = "src/gamecontrol.c"
PROLOGUE_SCRIPT_FILE = "src/events/prologue-eventscript.h"
PROLOGUE_UNITS_FILE = "src/events/prologue-eventudefs.h"
PROLOGUE_GROUPS = ("UnitDef_Event_PrologueAlly", "UnitDef_Event_PrologueEnemy")
EVENT_MACROS_FILE = "include/EAstdlib.h"
# With MNCH (and MoveToChapter), the game goes to the chapter of the world map node where the lord
# stands (SaveMenu_SetLcdChapterIdx, src/savemenu.c), set by the story's world map scenes. A test
# build started on the map skips them: the next chapter would be the prologue again (ticket 38).
# There, MNCH goes straight to the chapter it names, like MNC2.
_MNCH_DEFINE = "#define MNCH EvtChangeChapterWM\n"
_MNCH_DIRECT = "/* FE Maker: no world map, straight to the next chapter */\n#define MNCH EvtChangeChapterBM\n"

# Simplified prologue for test builds: no cutscene, the units are simply on the map.
_SIMPLE_PROLOGUE_SCENE = """
    /* FE Maker: simplified prologue for test builds (no cutscene, no walk-in) */
    LOAD1(1, UnitDef_Event_PrologueAlly)
    ENUN
    LOAD1(1, UnitDef_Event_PrologueEnemy)
    ENUN
    NoFade
    ENDA
"""

# Test start modes: "normal" (full intro), "menu" (straight to the save menu),
# "map" (new game created automatically, straight onto the first chapter's map).
START_MODES = ("normal", "menu", "map")

_GAME_CONTROL_RE = re.compile(
    r"(struct\s+ProcCmd\s+CONST_DATA\s+gProcScr_GameControl\s*\[\s*\]\s*=\s*\{.*?"
    r"PROC_REPEAT\(\s*GameControl_8009A60_Null\s*\),[ \t]*\n)",
    re.DOTALL,
)

_QUICK_START_DECL = (
    "/* FE Maker: quick start for test builds */\n"
    "void WriteNewGameSave(int index, int isDifficult, int mode, int isTutorial);\n"
    "void FEMaker_QuickStartOnMap(ProcPtr proc);\n\n"
)

# Same steps as choosing "New Game" then "Normal" in the save menu (see
# SaveMenuWriteNewGame: despite its name, isTutorial = 1 means no tutorial),
# then the battle map of the first chapter, skipping the opening monologue and
# the world map.
_QUICK_START_DEF = """
/* FE Maker: quick start for test builds */
void FEMaker_QuickStartOnMap(ProcPtr proc)
{
    WriteNewGameSave(0, 0, 1, 1);
    GameControl_EnableSoundEffects(proc);
    Proc_Goto(proc, LGAMECTRL_EXEC_BM_EXT);
}
"""


class TweakError(Exception):
    pass


def _anchor(source: str) -> re.Match:
    m = _GAME_CONTROL_RE.search(source)
    if not m:
        raise TweakError(f"The quick start option does not match this version of the decomp ({GAME_CONTROL_FILE})")
    return m


def skip_intro(source: str) -> str:
    """Boot straight to the save menu, skipping the health warning, logos,
    opening cutscene and title screen."""
    m = _anchor(source)
    insert = "    PROC_GOTO(LGAMECTRL_EXEC_SAVEMENU), /* FE Maker: skip intro */\n"
    return source[: m.end(1)] + insert + source[m.end(1):]


def start_on_map(source: str) -> str:
    """Boot straight onto the first chapter's map with a fresh normal-mode game
    (the chapter's opening scene still plays: press Start to skip it)."""
    m = _anchor(source)
    insert = "    PROC_CALL(FEMaker_QuickStartOnMap), /* FE Maker: start on map */\n"
    out = source[: m.start(1)] + _QUICK_START_DECL + source[m.start(1): m.end(1)] + insert + source[m.end(1):]
    return out.rstrip("\n") + "\n" + _QUICK_START_DEF


def simplify_prologue(script: str) -> str:
    """Replace the prologue's opening scene (throne room, escape, Seth giving the Rapier...)
    with one that only puts the player's units and the enemies on the map."""
    m = re.search(r"EventListScr\s+EventScr_Prologue_BeginningScene\s*\[\s*\]\s*=\s*\{", script)
    if not m:
        raise TweakError(f"The simplified prologue does not match this version of the decomp ({PROLOGUE_SCRIPT_FILE})")
    end = script.index("};", m.end())
    return script[: m.end()] + _SIMPLE_PROLOGUE_SCENE + script[end:]


def without_world_map(decomp_dir: Path, files: dict[str, str]) -> dict[str, str]:
    """MNCH (and MoveToChapter) go straight to the chapter they name, like MNC2: no world map between
    chapters (the project option "no world map", like FEBuilder's, and test builds started on the map)."""
    macros = files.get(EVENT_MACROS_FILE) or (decomp_dir / EVENT_MACROS_FILE).read_text(encoding="utf-8")
    if _MNCH_DIRECT in macros:
        return files
    if _MNCH_DEFINE not in macros:
        raise TweakError(f"{EVENT_MACROS_FILE}: MNCH not found")
    files[EVENT_MACROS_FILE] = macros.replace(_MNCH_DEFINE, _MNCH_DIRECT, 1)
    return files


def apply_test_tweaks(decomp_dir: Path, options: dict, files: dict[str, str]) -> dict[str, str]:
    """Add the tweaks enabled for test builds to `files` (decomp-relative path -> content)."""
    start = options.get("start", "normal")
    if start not in START_MODES:
        raise TweakError(f"Unknown start mode: {start}")
    if start != "normal":
        source = files.get(GAME_CONTROL_FILE)
        if source is None:
            source = (decomp_dir / GAME_CONTROL_FILE).read_text(encoding="utf-8")
        files[GAME_CONTROL_FILE] = skip_intro(source) if start == "menu" else start_on_map(source)
    if start == "map":
        files = without_world_map(decomp_dir, files)
    if options.get("simplePrologue"):
        def current(rel: str) -> str:
            return files[rel] if rel in files else (decomp_dir / rel).read_text(encoding="utf-8")

        files[PROLOGUE_SCRIPT_FILE] = simplify_prologue(current(PROLOGUE_SCRIPT_FILE))
        unit_files = {PROLOGUE_UNITS_FILE: current(PROLOGUE_UNITS_FILE)}
        for group in PROLOGUE_GROUPS:
            unit_files = units.place_at_destination(unit_files, group)
        files.update(unit_files)
    return files
