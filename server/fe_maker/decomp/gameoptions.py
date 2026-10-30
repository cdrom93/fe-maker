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
RANGE_DISPLAY_FILE = "src/playerphase.c"
EXP_BAR_FILE = "src/mapanim_expbar.c"
LEVEL_UP_FILE = "src/mapanim_lvup.c"
BATTLE_FILE = "src/bmbattle.c"

# Option -> (field of gPlaySt.config, the game's default, allowed values), in the order and with the choices of the
# game's Configuration menu (gGameOptionsUiOrder, gGameOptions in src/uiconfig.c). Animation: 0 "1" without
# backgrounds, 3 "2" with backgrounds, 1 off, 2 solo (PLAY_ANIMCONF_x); unit window: 0 panel, 1 burst, 2 off; combat
# window: 0 strategic, 1 detailed, 2 off; window color: the four colors; the others 0 on, 1 off (text speed 0 slow,
# 1 normal, 2 fast, 3 max; game speed 0 normal, 1 fast).
DEFAULTS: dict[str, tuple[str, int, tuple[int, ...]]] = {
    "animation": ("animationType", 0, (0, 3, 1, 2)),
    "gameSpeed": ("gameSpeed", 0, (0, 1)),
    "textSpeed": ("textSpeed", 1, (0, 1, 2, 3)),
    "terrainWindow": ("disableTerrainDisplay", 0, (0, 1)),
    "unitWindow": ("unitDisplayType", 0, (0, 1, 2)),
    "battleForecast": ("battleForecastType", 0, (0, 1, 2)),
    "objective": ("disableGoalDisplay", 0, (0, 1)),
    "subtitleHelp": ("noSubtitleHelp", 0, (0, 1)),
    "autoCursor": ("autoCursor", 0, (0, 1)),
    "autoEndTurn": ("disableAutoEndTurns", 0, (0, 1)),
    "music": ("disableBgm", 0, (0, 1)),
    "soundEffects": ("disableSoundEffects", 0, (0, 1)),
    "windowColor": ("windowColor", 0, (0, 1, 2, 3)),
}
SWITCHES = ("stationaryRange", "skipOpening", "quickChapterTitle", "holdAToSpeedUp", "quickExpBar", "quickLevelUp",
            "noSupportAnimations")

_INIT_RE = re.compile(r"void InitPlayConfig\(int isDifficult, s8 unk\)\s*\{.*?\n\}", re.DOTALL)
# FEBuilder "Omission of 1-second wait when displaying chapter titles": the title can be skipped at once.
_TITLE_WAIT = "    PROC_CALL(ChapterIntro_Init),\n\n    PROC_SLEEP(60),\n"
_TITLE_QUICK = "    PROC_CALL(ChapterIntro_Init),\n\n    PROC_SLEEP(1), /* FE Maker: quick chapter title */\n"
# FEBuilder "Hold A to speed up movement": the game only allows it once it has been played through.
_HOLD_A = "if (!IsFirstPlaythrough() && (gKeyStatusPtr->heldKeys & A_BUTTON))"
_HOLD_A_ALWAYS = "if (gKeyStatusPtr->heldKeys & A_BUTTON) /* FE Maker: hold A from the first playthrough */"
# FEBuilder "Null Move Display": a unit that never moves (movement AI 3, "stays") shows no movement range, only
# what it can attack from where it stands. In DisplayUnitEffectRange (selecting a unit to see its range).
_RANGE = "    GenerateUnitMovementMapExt(gActiveUnit, UNIT_MOV(gActiveUnit) - gActionData.moveCount);\n"
_RANGE_STATIONARY = ("    /* FE Maker: a unit that never moves (movement AI 3) shows no movement range */\n"
                     "    GenerateUnitMovementMapExt(gActiveUnit,\n"
                     "        (UNIT_FACTION(gActiveUnit) != FACTION_BLUE && gActiveUnit->ai2 == 3)\n"
                     "        ? 0 : UNIT_MOV(gActiveUnit) - gActionData.moveCount);\n")

# FEBuilder "Display bar quickly when getting exp in map anime" and "Acceleration of growth status display of level
# up": shorter waits in the map animations' scripts, by what the wait comes after.
_EXP_WAIT = "    PROC_REPEAT(ProcMAExpBar_FrameAdvance),\n    PROC_SLEEP(0x14),\n"
_EXP_WAIT_QUICK = "    PROC_REPEAT(ProcMAExpBar_FrameAdvance),\n    PROC_SLEEP(0x2),\n"
_EXP_END = "    PROC_REPEAT(ProcMAExpBar_OnIncrement),\n    PROC_SLEEP(0x14),\n"
_EXP_END_QUICK = "    PROC_REPEAT(ProcMAExpBar_OnIncrement),\n    PROC_SLEEP(0x4),\n"
_LEVEL_TEXT = "    PROC_CALL(ManimLevelUp_StartLevelUpText),\n    PROC_SLEEP(70),\n"
_LEVEL_TEXT_QUICK = "    PROC_CALL(ManimLevelUp_StartLevelUpText),\n    PROC_SLEEP(24),\n"
_LEVEL_IN = "    PROC_REPEAT(ManimLevelUp_ScrollIn),\n    PROC_SLEEP(30),\n"
_LEVEL_IN_QUICK = "    PROC_REPEAT(ManimLevelUp_ScrollIn),\n    PROC_SLEEP(8),\n"
_LEVEL_GAINS = "    PROC_REPEAT(ManimLevelUp_PutStatGainLabels),\n    PROC_SLEEP(60),\n"
_LEVEL_GAINS_QUICK = "    PROC_REPEAT(ManimLevelUp_PutStatGainLabels),\n    PROC_SLEEP(30),\n"
# FEBuilder "ForceBattleOffWithDanceAndStaff": staves and dances stay on the map, even with animations on.
_ANIM_TYPE = "int GetBattleAnimPreconfType(void) {\n"
_ANIM_TYPE_NO_SUPPORT = (_ANIM_TYPE + "    /* FE Maker: no battle screen for staves and dances */\n"
                         "    if (GetItemType(gBattleActor.weapon) == ITYPE_STAFF\n"
                         "        || gActionData.unitActionType == UNIT_ACTION_DANCE)\n"
                         "        return PLAY_ANIMCONF_OFF;\n\n")


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
            if n != 1 and field != "disableGoalDisplay":   # the only one the game leaves at the 0 of the cleared state
                raise TweakError(f"Option {field} not found in InitPlayConfig ({CONFIG_FILE})")
            if n != 1:
                body = f"{body[:-1]}    gPlaySt.config.{field} = {int(options[key])};\n}}"
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
    if options.get("stationaryRange"):
        files[RANGE_DISPLAY_FILE] = _replace(current(RANGE_DISPLAY_FILE), _RANGE, _RANGE_STATIONARY, RANGE_DISPLAY_FILE)
    if options.get("skipOpening"):
        files[GAME_CONTROL_FILE] = skip_intro(current(GAME_CONTROL_FILE))
    if options.get("quickChapterTitle"):
        files[CHAPTER_INTRO_FILE] = _replace(current(CHAPTER_INTRO_FILE), _TITLE_WAIT, _TITLE_QUICK, CHAPTER_INTRO_FILE)
    if options.get("holdAToSpeedUp"):
        files[MOVE_SPEED_FILE] = _replace(current(MOVE_SPEED_FILE), _HOLD_A, _HOLD_A_ALWAYS, MOVE_SPEED_FILE)
    if options.get("quickExpBar"):
        source = _replace(current(EXP_BAR_FILE), _EXP_WAIT, _EXP_WAIT_QUICK, EXP_BAR_FILE)
        files[EXP_BAR_FILE] = _replace(source, _EXP_END, _EXP_END_QUICK, EXP_BAR_FILE)
    if options.get("quickLevelUp"):
        source = _replace(current(LEVEL_UP_FILE), _LEVEL_TEXT, _LEVEL_TEXT_QUICK, LEVEL_UP_FILE)
        source = _replace(source, _LEVEL_IN, _LEVEL_IN_QUICK, LEVEL_UP_FILE)
        files[LEVEL_UP_FILE] = _replace(source, _LEVEL_GAINS, _LEVEL_GAINS_QUICK, LEVEL_UP_FILE)
    if options.get("noSupportAnimations"):
        files[BATTLE_FILE] = _replace(current(BATTLE_FILE), _ANIM_TYPE, _ANIM_TYPE_NO_SUPPORT, BATTLE_FILE)
    return files
