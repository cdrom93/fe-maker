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
MAP_UI_FILE = "src/bm.c"
UNIT_FILE = "src/bmunit.c"
MAP_SPRITES_FILE = "src/bmudisp.c"

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
SWITCHES = ("stationaryRange", "skipOpening", "skipStoryIntro", "talkBubbles",
            "quickChapterTitle", "holdAToSpeedUp", "quickExpBar", "quickLevelUp",
            "noSupportAnimations", "hpBars", "casualMode", "dangerZone")

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
# Select shows the enemies' range: the game has this display, only its map menu command was left out
# (MapMenu_DangerZone_UnusedEffect). It has no active unit, which the display idle reads for B and R.
_DANGER_LABEL = "PROC_LABEL(12),\n    PROC_CALL(PlayerPhase_DisplayDangerZone),\n"
_DANGER_LABEL_WAIT = ("PROC_LABEL(12),\n    PROC_CALL(EndPlayerPhaseSideWindows),\n\n    PROC_WHILE(DoesBMXFADEExist),\n\n"
                      "    PROC_CALL(PlayerPhase_DisplayDangerZone),\n")
_DANGER_AFTER = ("                StartMinimapPlayerPhase();\n\n                Proc_Goto(proc, 9);\n\n"
                 "                return;\n            }\n")
_DANGER_SELECT = _DANGER_AFTER + (
    "\n            /* FE Maker: Select shows the enemies' range */\n"
    "            if (gKeyStatusPtr->newKeys & SELECT_BUTTON)\n"
    "            {\n"
    "                struct Unit * unit = GetUnit(gBmMapUnit[gBmSt.playerCursor.y][gBmSt.playerCursor.x]);\n\n"
    "                if (unit)\n"
    "                {\n"
    "                    EndAllMus();\n"
    "                    ShowUnitSprite(unit);\n"
    "                }\n\n"
    "                gActiveUnit = NULL;\n"
    "                gBmSt.swapActionRangeCount = 0;\n\n"
    "                Proc_Goto(proc, 12);\n\n"
    "                return;\n"
    "            }\n")
_DANGER_B = ("        if (gKeyStatusPtr->newKeys & B_BUTTON)\n        {\n            if (gActiveUnit->state & US_HAS_MOVED)\n")
_DANGER_B_SAFE = ("        if (gKeyStatusPtr->newKeys & (gActiveUnit ? B_BUTTON : B_BUTTON | SELECT_BUTTON))\n"
                  "        {\n            if (gActiveUnit && (gActiveUnit->state & US_HAS_MOVED))\n")
_DANGER_R = "        else if (gKeyStatusPtr->newKeys & R_BUTTON)\n        {\n            action = ACT_INFOSCREEN;\n"
_DANGER_R_SAFE = ("        else if (gActiveUnit && (gKeyStatusPtr->newKeys & R_BUTTON))\n"
                  "        {\n            action = ACT_INFOSCREEN;\n")

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
# FEBuilder "ForceBattleOffWithDanceAndStaff" (7743), which reuses the Subtitle Help line: here a line of its own in the
# game's Configuration menu, on a free bit of the options, ON (battle screen) or OFF, starting OFF: staves and dances
# stay on the map, even with animations on.
_ANIM_TYPE = "int GetBattleAnimPreconfType(void) {\n"
_ANIM_TYPE_NO_SUPPORT = (_ANIM_TYPE + "    /* FE Maker: the player can leave staves and dances on the map */\n"
                         "    if (gPlaySt.config.unk41_6 && (GetItemType(gBattleActor.weapon) == ITYPE_STAFF\n"
                         "        || gActionData.unitActionType == UNIT_ACTION_DANCE))\n"
                         "        return PLAY_ANIMCONF_OFF;\n\n")
OPTION_MENU_FILE = "src/uiconfig.c"
OPTION_MENU_HEADER = "include/uiconfig.h"
_MENU_ENUM = "    GAME_OPTION_RANK_DISPLAY   = 16,\n"
_MENU_ORDER = ("    [ 1] = GAME_OPTION_GAME_SPEED,\n    [ 2] = GAME_OPTION_TEXT_SPEED,\n    [ 3] = GAME_OPTION_TERRAIN,\n"
               "    [ 4] = GAME_OPTION_UNIT,\n    [ 5] = GAME_OPTION_COMBAT,\n    [ 6] = GAME_OPTION_OBJECTIVE,\n"
               "    [ 7] = GAME_OPTION_SUBTITLE_HELP,\n    [ 8] = GAME_OPTION_AUTOCURSOR,\n"
               "    [ 9] = GAME_OPTION_AUTOEND_TURNS,\n    [10] = GAME_OPTION_MUSIC,\n"
               "    [11] = GAME_OPTION_SOUND_EFFECTS,\n    [12] = GAME_OPTION_WINDOW_COLOR,\n")
_MENU_TABLE_END = "        .icon = 0x20,\n        .func = GenericOptionChangeHandler,\n    }\n};\n"
_MENU_GET = "    case GAME_OPTION_RANK_DISPLAY:\n        value = gPlaySt.config.rankDisplay;\n\n        break;\n"
_MENU_SET = "    case GAME_OPTION_RANK_DISPLAY:\n        gPlaySt.config.rankDisplay = newValue;\n\n        break;\n"
MENU_TEXTS = {"label": "Staff & Dance", "help": "Animate staves and dances"}
# The menu's rows start on tile row 5, two rows each: a 14th row would end past the 32 rows of its tilemap, its lower half
# lost. They start one row higher and the layer is shifted down by as much (ticket 77).
_MENU_ROW_BASE = (("        int y = (i * 2) + 5;\n\n        DrawGameOptionIcon(i, 5);\n",
                   "        int y = (i * 2) + 4;\n\n        DrawGameOptionIcon(i, 4);\n"),
                  ("selectedIdx % 7, selectedIdx * 2 + 5);", "selectedIdx % 7, selectedIdx * 2 + 4);"),
                  ("    int y = ((selectedIdx * 2) + 5) & 0x1f;\n", "    int y = ((selectedIdx * 2) + 4) & 0x1f;\n"),
                  ("    DrawGameOptionIcon(selectedIdx, 5);\n", "    DrawGameOptionIcon(selectedIdx, 4);\n"))
_MENU_LAYER = "BG_SetPosition(BG_1, 0, gConfigUiState->bg1YOffset);"


def _menu_order() -> str:
    """The game's order with the added line second, under Animation."""
    lines = _MENU_ORDER.splitlines(keepends=True)
    moved = [re.sub(r"\[ *(\d+)\]", lambda m: f"[{int(m[1]) + 1:2}]", line) for line in lines]
    return "    [ 1] = GAME_OPTION_FEM_SUPPORT_ANIM,\n" + "".join(moved)


def _menu_line(label: int, on_help: int) -> str:
    selector = ("            {{\n                0x{help:X},\n                {text},\n                {x},\n                2\n"
                "            }},\n")
    empty = ("            {\n                MSG_000,\n                MSG_000,\n                190,\n"
             "                0\n            },\n")
    return (f"    [GAME_OPTION_FEM_SUPPORT_ANIM] =\n    {{\n        .msgId = 0x{label:X},\n        .selectors =\n        {{\n"
            + selector.format(help=on_help, text="MSG_0BD", x=112) + selector.format(help=on_help, text="MSG_0BE", x=135)
            + empty + empty + "        },\n        .icon = 0x0,\n        .func = GenericOptionChangeHandler,\n    },\n")


# HP bars under wounded units, drawn like FEBuilder's "HPbars_simple" (Circles and Zane; its behavior and look, written
# in C): a bar 14 pixels wide, its 12 inner pixels green, then yellow, orange, red as they empty, on dark blue. Eleven
# 16 x 8 pictures in free object tiles (rows 0 and 1, from column 0x12), drawn at each load of the map's object
# graphics; colors of the first object palette. Under the windows (object layer 2, as the units), ticket 114.
_OBJ_UI_LOAD = "void LoadObjUIGfx(void) {\n"
_OBJ_UI_LOAD_BARS = """/* FE Maker: the HP bars' tiles */
static void FemLoadHpBars(void) {
    int length, x;

    for (length = 1; length <= 11; ++length) {
        u32 fill[2] = { 0, 0 };
        int color = length >= 9 ? 0xB : length >= 7 ? 0x1 : length >= 5 ? 0x3 : length >= 3 ? 0x4 : 0xC;
        int tile = length <= 7 ? 0x10 + length * 2 : 0x30 + (length - 7) * 2;
        u32* left = (u32*) (0x06010000 + tile * 0x20);
        u32* right = left + 8;

        for (x = 1; x < 15; ++x)
            fill[x / 8] |= (u32) ((x >= 2 && x <= 13) ? (x - 1 <= length ? color : 0xD) : 0xF) << ((x % 8) * 4);
        for (x = 0; x < 8; ++x)
            left[x] = right[x] = 0;
        left[4] = left[6] = 0xFFFFFFF0;
        right[4] = right[6] = 0x0FFFFFFF;
        left[5] = fill[0];
        right[5] = fill[1];
    }
}

void LoadObjUIGfx(void) {
    FemLoadHpBars();
"""
_ICONS = "void PutUnitSpriteIconsOam(void)\n{\n"
_ICONS_BARS = """/* FE Maker: a bar under a wounded unit */
static void FemPutHpBar(struct Unit * unit)
{
    int x = unit->xPos * 16 - gBmSt.camera.x;
    int y = unit->yPos * 16 - gBmSt.camera.y;

    if (x < -16 || x > DISPLAY_WIDTH || y < -16 || y > DISPLAY_HEIGHT)
        return;
    if (gBmMapFog[unit->yPos][unit->xPos] == 0)
        return;

    if (unit->curHP < unit->maxHP && unit->maxHP != 0) {
        int length = unit->curHP * 12 / unit->maxHP;

        if (length < 1)
            length = 1;
        CallARM_PushToSecondaryOAM(OAM1_X(0x200 + x), OAM0_Y(0x100 + y + 10), gObject_16x8,
            OAM2_CHR(length <= 7 ? 0x10 + length * 2 : 0x30 + (length - 7) * 2) + OAM2_LAYER(2));
    }
}

""" + _ICONS
_ICONS_LOOP = "        switch (unit->statusIndex) {\n        case UNIT_STATUS_POISON:\n"
_ICONS_LOOP_BARS = "        FemPutHpBar(unit);\n\n" + _ICONS_LOOP

# A yellow bubble over the units the selected one can talk to, to recruit them or not, or support with (ticket 113, as
# in Vision Quest): two 16 x 8 pictures in free object tiles, after the HP bars'. Colors of the first object palette:
# # border, y yellow, d dark.
_BUBBLE = ("...########.....", "..#yyyyyyyy#....", ".#yyyyyyyyyy#...", ".#yydyydyydy#...",
           ".#yyyyyyyyyy#...", "..#yyyyyyyy#....", "...####yy###....", ".....#yy#.......",
           "......##........", "................", "................", "................",
           "................", "................", "................", "................")
_BUBBLE_TILE = 0x3A


def _bubble_tiles() -> str:
    """The bubble as tiles: top left, top right, bottom left, bottom right; 4 bits a pixel, 8 rows of 32 bits."""
    color = {".": 0, "y": 0x1, "#": 0xF, "d": 0xD}
    tiles = []
    for top in (0, 8):
        for left in (0, 8):
            rows = [sum(color[_BUBBLE[top + y][left + x]] << (x * 4) for x in range(8)) for y in range(8)]
            tiles.append("    { " + ", ".join(f"0x{row:08X}" for row in rows) + " },\n")
    return "".join(tiles)


_OBJ_UI_LOAD_BUBBLE = """/* FE Maker: the talk bubble's tiles */
static const u32 sFemBubble[4][8] = {
""" + _bubble_tiles() + """};

static void FemLoadBubble(void) {
    int tile, y;

    for (tile = 0; tile < 4; ++tile)
        for (y = 0; y < 8; ++y)
            ((u32*) (0x06010000 + (""" + str(_BUBBLE_TILE) + """ + tile) * 0x20))[y] = sFemBubble[tile][y];
}

""" + _OBJ_UI_LOAD + "    FemLoadBubble();\n"
_ICONS_BUBBLE = """#include "eventinfo.h"
#include "bmreliance.h"

/* FE Maker: a bubble on a unit the selected one can talk to, or support with */
static void FemPutBubble(struct Unit * unit)
{
    int x = unit->xPos * 16 - gBmSt.camera.x;
    int y = unit->yPos * 16 - gBmSt.camera.y;
    int i, show;

    if (!gActiveUnit || gActiveUnit == unit || !(gActiveUnit->state & US_HIDDEN)
        || UNIT_FACTION(gActiveUnit) != FACTION_BLUE || !gActiveUnit->pCharacterData)
        return;
    if (x < -16 || x > DISPLAY_WIDTH || y < 0 || y > DISPLAY_HEIGHT)
        return;
    if (gBmMapFog[unit->yPos][unit->xPos] == 0)
        return;

    show = CheckForCharacterEvents(gActiveUnit->pCharacterData->number, unit->pCharacterData->number);
    for (i = GetUnitSupporterCount(gActiveUnit) - 1; i >= 0 && !show; --i)
        show = GetUnitSupporterUnit(gActiveUnit, i) == unit && CanUnitSupportNow(gActiveUnit, i);

    if (show) {
        CallARM_PushToSecondaryOAM(OAM1_X(0x200 + x + 3), OAM0_Y(0x100 + y - 9), gObject_16x8,
            OAM2_CHR(""" + str(_BUBBLE_TILE) + """) + OAM2_LAYER(2));
        CallARM_PushToSecondaryOAM(OAM1_X(0x200 + x + 3), OAM0_Y(0x100 + y - 1), gObject_16x8,
            OAM2_CHR(""" + str(_BUBBLE_TILE + 2) + """) + OAM2_LAYER(2));
    }
}

""" + _ICONS
_ICONS_LOOP_BUBBLE = "        FemPutBubble(unit);\n\n" + _ICONS_LOOP

_STORY_INTRO = "    StartIntroMonologue(proc);\n"
_STORY_INTRO_NONE = "    /* FE Maker: no story intro */\n"

# Casual mode, after FEBuilder's "CasualMode" (its behavior, written in C, always on rather than a choice in the game):
# a fallen player unit leaves the map, keeps its supports and comes back for the next chapter.
_DEATH_CLEANUP = ("            if (UNIT_CATTRIBUTES(unit) & CA_SUPPLY)\n"
                  "                unit->state = unit->state &~ US_DEAD;\n")
_DEATH_CLEANUP_CASUAL = "            unit->state = unit->state &~ US_DEAD; /* FE Maker: casual mode */\n"
_DEATH_SUPPORTS = "            unit->state |= US_DEAD | US_HIDDEN;\n            InitUnitsupports(unit);\n"
_DEATH_SUPPORTS_CASUAL = "            unit->state |= US_DEAD | US_HIDDEN; /* FE Maker: casual mode, supports stay */\n"


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


def apply(decomp_dir: Path, options: dict, files: dict, menu_texts: tuple[int, int] = (0, 0)) -> dict:
    """Add the project's game options to `files` (decomp-relative path -> content); `menu_texts`: the messages of the
    Configuration menu's new line (MENU_TEXTS), added to the texts before they are written."""
    def current(rel: str) -> str:
        return files[rel] if rel in files else (decomp_dir / rel).read_text(encoding="utf-8")

    if any(key in options and options[key] != DEFAULTS[key][1] for key in DEFAULTS):
        files[CONFIG_FILE] = with_defaults(current(CONFIG_FILE), {k: v for k, v in options.items() if k in DEFAULTS})
    if options.get("stationaryRange"):
        files[RANGE_DISPLAY_FILE] = _replace(current(RANGE_DISPLAY_FILE), _RANGE, _RANGE_STATIONARY, RANGE_DISPLAY_FILE)
    if options.get("dangerZone"):
        source = current(RANGE_DISPLAY_FILE)
        for old, new in ((_DANGER_LABEL, _DANGER_LABEL_WAIT), (_DANGER_AFTER, _DANGER_SELECT), (_DANGER_B, _DANGER_B_SAFE),
                         (_DANGER_R, _DANGER_R_SAFE)):
            source = _replace(source, old, new, RANGE_DISPLAY_FILE)
        files[RANGE_DISPLAY_FILE] = source
    if options.get("skipOpening"):
        files[GAME_CONTROL_FILE] = skip_intro(current(GAME_CONTROL_FILE))
    if options.get("skipStoryIntro"):
        files[GAME_CONTROL_FILE] = _replace(current(GAME_CONTROL_FILE), _STORY_INTRO, _STORY_INTRO_NONE, GAME_CONTROL_FILE)
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
    if options.get("casualMode"):
        files[CONFIG_FILE] = _replace(current(CONFIG_FILE), _DEATH_CLEANUP, _DEATH_CLEANUP_CASUAL, CONFIG_FILE)
        files[UNIT_FILE] = _replace(current(UNIT_FILE), _DEATH_SUPPORTS, _DEATH_SUPPORTS_CASUAL, UNIT_FILE)
    if options.get("hpBars"):
        files[MAP_UI_FILE] = _replace(current(MAP_UI_FILE), _OBJ_UI_LOAD, _OBJ_UI_LOAD_BARS, MAP_UI_FILE)
        source = _replace(current(MAP_SPRITES_FILE), _ICONS, _ICONS_BARS, MAP_SPRITES_FILE)
        files[MAP_SPRITES_FILE] = _replace(source, _ICONS_LOOP, _ICONS_LOOP_BARS, MAP_SPRITES_FILE)
    if options.get("talkBubbles"):
        files[MAP_UI_FILE] = _replace(current(MAP_UI_FILE), _OBJ_UI_LOAD, _OBJ_UI_LOAD_BUBBLE, MAP_UI_FILE)
        source = _replace(current(MAP_SPRITES_FILE), _ICONS, _ICONS_BUBBLE, MAP_SPRITES_FILE)
        files[MAP_SPRITES_FILE] = _replace(source, _ICONS_LOOP, _ICONS_LOOP_BUBBLE, MAP_SPRITES_FILE)
    if options.get("noSupportAnimations"):
        label, on_help = menu_texts
        files[BATTLE_FILE] = _replace(current(BATTLE_FILE), _ANIM_TYPE, _ANIM_TYPE_NO_SUPPORT, BATTLE_FILE)
        files[OPTION_MENU_HEADER] = _replace(current(OPTION_MENU_HEADER), _MENU_ENUM,
                                             _MENU_ENUM + "    GAME_OPTION_FEM_SUPPORT_ANIM = 17,\n", OPTION_MENU_HEADER)
        source = current(OPTION_MENU_FILE)
        source = _replace(source, _MENU_ORDER, _menu_order(), OPTION_MENU_FILE)
        for old, new in _MENU_ROW_BASE:
            source = _replace(source, old, new, OPTION_MENU_FILE)
        if source.count(_MENU_LAYER) != 2:
            raise TweakError(f"A game option does not match this version of the decomp ({OPTION_MENU_FILE})")
        source = source.replace(_MENU_LAYER, "BG_SetPosition(BG_1, 0, gConfigUiState->bg1YOffset - 8);")
        table_end = _MENU_TABLE_END.replace("    }\n};\n", "    },\n\n") + _menu_line(label, on_help) + "};\n"
        source = _replace(source, _MENU_TABLE_END, table_end, OPTION_MENU_FILE)
        source = _replace(source, _MENU_GET, _MENU_GET + "\n    case GAME_OPTION_FEM_SUPPORT_ANIM:\n"
                          "        value = gPlaySt.config.unk41_6;\n\n        break;\n", OPTION_MENU_FILE)
        files[OPTION_MENU_FILE] = _replace(source, _MENU_SET, _MENU_SET + "\n    case GAME_OPTION_FEM_SUPPORT_ANIM:\n"
                                           "        gPlaySt.config.unk41_6 = newValue;\n\n        break;\n", OPTION_MENU_FILE)
        start = "    gPlaySt.config.unk41_5 = 0;\n"
        files[CONFIG_FILE] = _replace(current(CONFIG_FILE), start,
                                      start + "    gPlaySt.config.unk41_6 = 1; /* FE Maker: staves on the map */\n", CONFIG_FILE)
    return files
