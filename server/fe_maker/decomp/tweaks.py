"""Small engine tweaks applied to the decomp sources at build time, on the user's machine.

FE Maker stores only the instruction (anchor + inserted line, our own code); the
modified decomp file is generated locally in the build overlay and never
distributed. If the anchor is not found (the decomp changed), the build stops
with a clear error instead of producing a broken game.
"""

from __future__ import annotations

import re
from pathlib import Path

GAME_CONTROL_FILE = "src/gamecontrol.c"


class TweakError(Exception):
    pass


def skip_intro(source: str) -> str:
    """Boot straight to the save menu, skipping the health warning, logos,
    opening cutscene and title screen (handy when testing)."""
    m = re.search(
        r"gProcScr_GameControl\s*\[\s*\]\s*=\s*\{.*?(PROC_REPEAT\(\s*GameControl_8009A60_Null\s*\),[ \t]*\n)",
        source,
        re.DOTALL,
    )
    if not m:
        raise TweakError(f"'Skip intro' does not match this version of the decomp ({GAME_CONTROL_FILE})")
    insert = "    PROC_GOTO(LGAMECTRL_EXEC_SAVEMENU), /* FE Maker: skip intro */\n"
    return source[: m.end(1)] + insert + source[m.end(1):]


def apply_test_tweaks(decomp_dir: Path, options: dict, files: dict[str, str]) -> dict[str, str]:
    """Add the tweaks enabled for test builds to `files` (decomp-relative path -> content)."""
    if options.get("skipIntro"):
        source = files.get(GAME_CONTROL_FILE)
        if source is None:
            source = (decomp_dir / GAME_CONTROL_FILE).read_text(encoding="utf-8")
        files[GAME_CONTROL_FILE] = skip_intro(source)
    return files
