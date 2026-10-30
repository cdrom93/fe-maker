"""Options of the built game (the "Game options" page, project fe-maker.json "gameOptions").

- Defaults of a new save's options (InitPlayConfig, src/bmio.c): the player can still change them in the game's
  Options menu.
- Comfort changes (docs/patchs-qol.md, priority 1), each the C version of a FEBuilderGBA "SYSTEM" patch: an anchored
  rewrite of the decomp source, like the test modes (tweaks.py); the build stops if an anchor is missing.

Only the options the project changes are written: an unmodified project rebuilds the original game.
"""

from __future__ import annotations

import re
from pathlib import Path

from .tweaks import GAME_CONTROL_FILE, TweakError, skip_intro

CONFIG_FILE = "src/bmio.c"
CHAPTER_INTRO_FILE = "src/chapterintrofx.c"
MOVE_SPEED_FILE = "src/mu.c"

# Option -> (field of gPlaySt.config, the game's default, allowed values). Values, from the Options menu
# (src/uiconfig.c): animation 0 on, 1 off, 2 solo (PLAY_ANIMCONF_x); textSpeed 0 slow, 1 normal, 2 fast, 3 max
# (GetTextDisplaySpeed); gameSpeed 0 normal, 1 fast; autoCursor 0 on, 1 off; autoEndTurn 0 on, 1 off;
# terrainWindow 0 on, 1 off; unitWindow 0 detailed, 1 simple, 2 off; battleForecast 0 detailed, 1 simple, 2 off.
DEFAULTS: dict[str, tuple[str, int, tuple[int, ...]]] = {
    "animation": ("animationType", 0, (0, 1, 2)),
    "textSpeed": ("textSpeed", 1, (0, 1, 2, 3)),
    "gameSpeed": ("gameSpeed", 0, (0, 1)),
    "autoCursor": ("autoCursor", 0, (0, 1)),
    "autoEndTurn": ("disableAutoEndTurns", 0, (0, 1)),
    "terrainWindow": ("disableTerrainDisplay", 0, (0, 1)),
    "unitWindow": ("unitDisplayType", 0, (0, 1, 2)),
    "battleForecast": ("battleForecastType", 0, (0, 1, 2)),
}
SWITCHES = ("skipOpening", "quickChapterTitle", "holdAToSpeedUp")

_INIT_RE = re.compile(r"void InitPlayConfig\(int isDifficult, s8 unk\)\s*\{.*?\n\}", re.DOTALL)
# FEBuilder "Omission of 1-second wait when displaying chapter titles": the title can be skipped at once.
_TITLE_WAIT = "    PROC_CALL(ChapterIntro_Init),\n\n    PROC_SLEEP(60),\n"
_TITLE_QUICK = "    PROC_CALL(ChapterIntro_Init),\n\n    PROC_SLEEP(1), /* FE Maker: quick chapter title */\n"
# FEBuilder "Hold A to speed up movement": the game only allows it once it has been played through.
_HOLD_A = "if (!IsFirstPlaythrough() && (gKeyStatusPtr->heldKeys & A_BUTTON))"
_HOLD_A_ALWAYS = "if (gKeyStatusPtr->heldKeys & A_BUTTON) /* FE Maker: hold A from the first playthrough */"


def validate(options: dict) -> str | None:
    """Problem code for the options, else None."""
    for key, value in options.items():
        if key in DEFAULTS:
            if value not in DEFAULTS[key][2]:
                return "badGameOption"
        elif key in SWITCHES:
            if not isinstance(value, bool):
                return "badGameOption"
        else:
            return "unknownGameOption"
    return None


def with_defaults(source: str, options: dict) -> str:
    """InitPlayConfig with the project's defaults."""
    m = _INIT_RE.search(source)
    if m is None:
        raise TweakError(f"The new game options do not match this version of the decomp ({CONFIG_FILE})")
    body = m.group(0)
    for key, (field, _game, _allowed) in DEFAULTS.items():
        if key in options:
            body, n = re.subn(rf"(gPlaySt\.config\.{field} = )\d+;", rf"\g<1>{int(options[key])};", body)
            if n != 1:
                raise TweakError(f"Option {field} not found in InitPlayConfig ({CONFIG_FILE})")
    return source[:m.start()] + body + source[m.end():]


def _replace(source: str, old: str, new: str, rel: str) -> str:
    if old not in source:
        raise TweakError(f"A game option does not match this version of the decomp ({rel})")
    return source.replace(old, new, 1)


def apply(decomp_dir: Path, options: dict, files: dict) -> dict:
    """Add the project's game options to `files` (decomp-relative path -> content)."""
    def current(rel: str) -> str:
        return files[rel] if rel in files else (decomp_dir / rel).read_text(encoding="utf-8")

    if any(key in options and options[key] != DEFAULTS[key][1] for key in DEFAULTS):
        files[CONFIG_FILE] = with_defaults(current(CONFIG_FILE), {k: v for k, v in options.items() if k in DEFAULTS})
    if options.get("skipOpening"):
        files[GAME_CONTROL_FILE] = skip_intro(current(GAME_CONTROL_FILE))
    if options.get("quickChapterTitle"):
        files[CHAPTER_INTRO_FILE] = _replace(current(CHAPTER_INTRO_FILE), _TITLE_WAIT, _TITLE_QUICK, CHAPTER_INTRO_FILE)
    if options.get("holdAToSpeedUp"):
        files[MOVE_SPEED_FILE] = _replace(current(MOVE_SPEED_FILE), _HOLD_A, _HOLD_A_ALWAYS, MOVE_SPEED_FILE)
    return files
