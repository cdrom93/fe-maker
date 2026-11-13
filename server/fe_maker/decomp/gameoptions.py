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

from . import battlenumbers
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
    # only with noSupportAnimations (ticket 43): written by apply(), the game has no such line; 1 = staves on the map
    "staffDance": ("unk41_6", 1, (0, 1)),
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
OWN_LINE_DEFAULTS = ("staffDance",)   # defaults of a menu line FE Maker adds, set by apply()
SWITCH_GROUPS = {"start": ("skipOpening", "skipStoryIntro", "quickChapterTitle"),
                 "speed": ("holdAToSpeedUp", "holdLBattleSpeed", "quickExpBar", "quickLevelUp", "noSupportAnimations"),
                 "map": ("hpBars", "talkBubbles", "dangerZone", "stationaryRange", "healPreview"),
                 "battle": ("battleNumbers",),
                 "screens": ("statusGrowths",),
                 "rules": ("actAfterTalk", "casualMode", "strMagSplit", "skills"),
                 "items": ("tempBonusRule", "deadItemsToConvoy"),
                 "sound": ("musicTracks",)}
# Options with several choices, the first one the default (in SWITCH_GROUPS for their category). tempBonusRule: how
# the temporary bonuses of Pure Water copies meet (ticket 164; TEMP_BONUS_RULE_FEM, gamedata.TEMP_BONUS_MACROS).
CHOICES: dict[str, tuple[str, ...]] = {"tempBonusRule": ("strongest", "add", "replace")}
SWITCHES = tuple(key for keys in SWITCH_GROUPS.values() for key in keys if key not in CHOICES)
_TEMP_RULE = "#define TEMP_BONUS_RULE_FEM 0\n"
TEMP_RULE_FILE = "include/bmunit.h"

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
_OBJ_UI_LOAD_BARS = """#include "face.h"

int IsBattleDeamonActive(void);

/* FE Maker: the HP bars' tiles */
void FemLoadHpBars(void) {
    int length, x;

    if (IsBattleDeamonActive())
        return; /* a battle animation's fighter sheet sits on these tiles (ticket 161) */
    for (x = 0; x < FACE_SLOT_COUNT; ++x)
        if (gFaces[x])
            return; /* a portrait's tiles sit on these (slot 0 at 0x300, ticket 51): reloaded once it is gone */

    for (length = 1; length <= 11; ++length) {
        u32 fill[2] = { 0, 0 };
        int color = length >= 9 ? 0xB : length >= 7 ? 0x1 : length >= 5 ? 0x3 : length >= 3 ? 0x4 : 0xC;
        int tile = 0x340 + length * 2;
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
_ICONS_BARS = """#include "face.h"

void FemLoadHpBars(void);

/* FE Maker: a bar under a wounded unit */
static void FemPutHpBar(struct Unit * unit)
{
    int x = unit->xPos * 16 - gBmSt.camera.x;
    int y = unit->yPos * 16 - gBmSt.camera.y;
    int i;

    for (i = 0; i < FACE_SLOT_COUNT; ++i)
        if (gFaces[i])
            return; /* a portrait is shown: the bar would cover it (ticket 161) */
    if (((u32*) (0x06010000 + 0x342 * 0x20))[4] != 0xFFFFFFF0)
        FemLoadHpBars(); /* a portrait took the bars' tiles (ticket 51): the first bar's top border is gone */

    if (x < -16 || x > DISPLAY_WIDTH || y < -16 || y > DISPLAY_HEIGHT)
        return;
    if (gBmMapFog[unit->yPos][unit->xPos] == 0)
        return;

    if (unit->curHP < unit->maxHP && unit->maxHP != 0) {
        int length = unit->curHP * 12 / unit->maxHP;

        if (length < 1)
            length = 1;
        CallARM_PushToSecondaryOAM(OAM1_X(0x200 + x), OAM0_Y(0x100 + y + 10), gObject_16x8,
            OAM2_CHR(0x340 + length * 2) + OAM2_LAYER(2));
    }
}

""" + _ICONS
_ICONS_LOOP = "        switch (unit->statusIndex) {\n        case UNIT_STATUS_POISON:\n"
_ICONS_LOOP_BARS = "        FemPutHpBar(unit);\n\n" + _ICONS_LOOP

# A yellow bubble over the units the selected one can talk to, to recruit them or not, or support with (ticket 113, as
# in Vision Quest): one 16 x 8 picture in free object tiles, after the HP bars'. HP bars and bubble sit in object tiles
# 0x340-0x37F, which nothing uses on the map (ticket 142: the weathers' particles take 0x12-0x7F of the first rows).
# A battle animation puts its right fighter's sheet on 0x300-0x3FF, and its talks (battle quotes) reload the object UI
# graphics: the tiles are not written while one runs (ticket 161). A portrait (face slot 0, 0x300-0x3FF) too: not
# written under one, reloaded at the first frame without one (ticket 51).
# Vision Quest's bubble, redrawn pixel for pixel from a screenshot (ticket 69 of 10/11): a round one, its tail toward the
# unit, at the upper left of its square. Colors of the first object palette (the same as Vision Quest's): o orange, y
# yellow, l lilac.
_BUBBLE = ("..ooooo.........", ".oyyyyyo........", "oyylllyyo.......", "oylllllyo.......",
           "oylllllyo.......", "oyylllyyyo......", ".oyyyyyyoo......", "..oooooo........")
_BUBBLE_TILE = 0x360


def _bubble_tiles() -> str:
    """The bubble as tiles: left, right; 4 bits a pixel, 8 rows of 32 bits."""
    color = {".": 0, "y": 0x1, "l": 0x8, "o": 0xC}
    tiles = []
    for left in (0, 8):
        rows = [sum(color[_BUBBLE[y][left + x]] << (x * 4) for x in range(8)) for y in range(8)]
        tiles.append("    { " + ", ".join(f"0x{row:08X}" for row in rows) + " },\n")
    return "".join(tiles)



_BUBBLE_ROW = _bubble_tiles().split(", ")[1]   # its first tile's row 1: written by FemLoadBubble

_OBJ_UI_LOAD_BUBBLE = """/* FE Maker: the talk bubble's tiles */
static const u32 sFemBubble[2][8] = {
""" + _bubble_tiles() + """};

#include "face.h"

int IsBattleDeamonActive(void);

void FemLoadBubble(void) {
    int tile, y;

    if (IsBattleDeamonActive())
        return; /* a battle animation's fighter sheet sits on these tiles (ticket 161) */
    for (y = 0; y < FACE_SLOT_COUNT; ++y)
        if (gFaces[y])
            return; /* a portrait's tiles sit on these (ticket 51): reloaded once it is gone */

    for (tile = 0; tile < 2; ++tile)
        for (y = 0; y < 8; ++y)
            ((u32*) (0x06010000 + (""" + str(_BUBBLE_TILE) + """ + tile) * 0x20))[y] = sFemBubble[tile][y];
}

""" + _OBJ_UI_LOAD + "    FemLoadBubble();\n"
_ICONS_BUBBLE = """#include "eventinfo.h"
#include "face.h"
#include "bmreliance.h"

void FemLoadBubble(void);

/* FE Maker: a bubble on a unit the selected one can talk to, or support with */
static void FemPutBubble(struct Unit * unit)
{
    int x = unit->xPos * 16 - gBmSt.camera.x;
    int y = unit->yPos * 16 - gBmSt.camera.y;
    int i, show;

    for (i = 0; i < FACE_SLOT_COUNT; ++i)
        if (gFaces[i])
            return; /* a portrait is shown: the bubble would cover it (ticket 161) */
    if (((u32*) (0x06010000 + """ + str(_BUBBLE_TILE) + """ * 0x20))[1] != """ + _BUBBLE_ROW + """)
        FemLoadBubble(); /* a portrait took the bubble's tiles (ticket 51) */
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
        CallARM_PushToSecondaryOAM(OAM1_X(0x200 + x - 5), OAM0_Y(0x100 + y - 2), gObject_16x8,
            OAM2_CHR(""" + str(_BUBBLE_TILE) + """) + OAM2_LAYER(2));
    }
}

""" + _ICONS
_ICONS_LOOP_BUBBLE = "        FemPutBubble(unit);\n\n" + _ICONS_LOOP

# A unit acts on after Talk or Support, as after a trade (FEBuilder's "Contemporary FE style talk and support", redone
# in C): one more step of the player phase, right after the action, goes back to the unit's menu; the game's taken_action
# then turns B into Wait. Its 16 is a free bit of that byte.
_TALK_HEAD = "struct ProcCmd CONST_DATA gProcScr_PlayerPhase[] =\n"
_TALK_HEAD_NEW = "static s8 FemAfterTalk(ProcPtr proc);\n\n" + _TALK_HEAD
_TALK_STEP = "    PROC_CALL_2(ApplyUnitAction),\n"
_TALK_STEP_NEW = _TALK_STEP + "    PROC_CALL_2(FemAfterTalk),\n"
_TALK_CANCEL = "//! FE8U = 0x0801D008\nvoid PlayerPhase_BackToMove(ProcPtr proc)\n"
_TALK_CANCEL_NEW = """/* FE Maker: back to the unit's menu after Talk or Support, unless the unit left or the map is won */
static s8 FemAfterTalk(ProcPtr proc)
{
    if (gActionData.unitActionType != UNIT_ACTION_TALK && gActionData.unitActionType != UNIT_ACTION_SUPPORT)
        return 1;

    gActiveUnit = GetUnit(gActionData.subjectIndex);
    if (gActiveUnit->state & (US_DEAD | US_NOT_DEPLOYED | US_BIT16) || ShouldCallEndEvent())
        return 1;

    gBmSt.taken_action |= 16;
    HideUnitSprite(gActiveUnit);
    EndAllMus();
    StartMu(gActiveUnit);
    PlayerPhase_CancelAction(proc);
    return 1;
}

""" + _TALK_CANCEL

_STORY_INTRO = "    StartIntroMonologue(proc);\n"
_STORY_INTRO_NONE = "    /* FE Maker: no story intro */\n"
# The tale of Magvel itself is the prologue's world map event (ticket 115): only its first commands stay, which put the
# lord on the world map.
WORLD_MAP_INTRO_FILE = "src/events/prologue-wm.h"
_WORLD_MAP_TALE = re.compile(r"(EventScrWM_Prologue_Beginning\[\] = \{\n(?:.*\n)*?    WM_CENTERCAMONLORD\(WM_MU_0\)\n)"
                             r"(?:.*\n)*?(    ENDA\n\};)")

# Casual mode, after FEBuilder's "CasualMode" (its behavior, written in C, always on rather than a choice in the game):
# a fallen player unit leaves the map, keeps its supports and comes back for the next chapter.
_DEATH_CLEANUP = ("            if (UNIT_CATTRIBUTES(unit) & CA_SUPPLY)\n"
                  "                unit->state = unit->state &~ US_DEAD;\n")
_DEATH_CLEANUP_CASUAL = "            unit->state = unit->state &~ US_DEAD; /* FE Maker: casual mode */\n"
_DEATH_SUPPORTS = "            unit->state |= US_DEAD | US_HIDDEN;\n            InitUnitsupports(unit);\n"
_DEATH_SUPPORTS_CASUAL = "            unit->state |= US_DEAD | US_HIDDEN; /* FE Maker: casual mode, supports stay */\n"

# Ticket 8: a fallen player unit's items go to the convoy, as far as it has room (FE Maker's own code). Not with casual
# mode, where the unit comes back with its items.
_UNIT_INCLUDES = '#include "bmmind.h"\n'
_UNIT_INCLUDES_CONVOY = _UNIT_INCLUDES + '#include "bmcontainer.h"\n'
_DEATH_ELSE = "        if (UNIT_IS_PHANTOM(unit))\n            unit->pCharacterData = NULL;\n        else {\n"
_DEATH_ELSE_CONVOY = _DEATH_ELSE + """            /* FE Maker: the fallen unit's items go to the convoy (ticket 8) */
            int i;

            for (i = 0; i < UNIT_ITEM_COUNT && unit->items[i]; i++)
                if (GetConvoyItemCount() < CONVOY_ITEM_COUNT)
                    AddItemToConvoy(unit->items[i]);
            for (i = 0; i < UNIT_ITEM_COUNT; i++)
                unit->items[i] = 0;

"""

# Ticket 7: holding L plays battle animations twice as fast, like FEBuilder's "SpeedUpAnims" (Circles) and
# "FastBattleAnimation" (7743): the battle's frame update runs twice per frame.
BATTLE_ANIM_FILE = "src/banim-ekrbattle.c"
_BATTLE_FRAME = "    if (gEkrDebugUnk1 == 0)\n        MainUpdateEkrBattle();\n"
_BATTLE_FRAME_FAST = """    if (gEkrDebugUnk1 == 0) {
        MainUpdateEkrBattle();
        /* FE Maker: holding L plays the battle twice as fast (ticket 7), not the level up, promotion and popup
           screens, whose drawing goes wrong at double speed (ticket 21) */
        if ((gKeyStatusPtr->heldKeys & L_BUTTON) && gEkrBattleEndFlag == 0 && !Proc_Find(ProcScr_EkrLevelup)
            && !Proc_Find(ProcScr_ekrClasschg) && !Proc_Find(ProcScr_ekrPopup) && !Proc_Find(ProcScr_ekrPopup2))
            MainUpdateEkrBattle();
    }
"""

# Ticket 6: choosing a staff's target shows "HP now -> HP after" in the target's window, the second number green when
# it reaches max HP, after FEBuilder's "Show Heal Amount" (Tequila); here with the staff chosen (not the first item)
# and through GetUnitItemHealAmount, so FE Maker's healing rules count.
INFO_WINDOW_FILE = "src/unitinfowindow.c"
HEAL_SELECT_FILE = "src/bmmenu.c"
_HP_WINDOW = "//! FE8U = 0x08034FFC\nvoid StartUnitHpStatusInfoWindow(ProcPtr parent) {\n"
_HP_WINDOW_HEAL = """#include "bmmind.h"

/* FE Maker (ticket 6): the target's HP before and after the staff's healing */
void RefreshUnitHealPreviewWindowFem(struct Unit* unit) {
    int x = GetUnitInfoWindowX(unit, 10);
    struct UnitInfoWindowProc* proc = UnitInfoWindow_DrawBase(0, unit, x, 0, 10, 1);
    struct Text* text = proc->lines + 0;
    int hp = GetUnitCurrentHp(unit);
    int max = GetUnitMaxHp(unit);
    int healed = hp + GetUnitItemHealAmount(gActiveUnit, gActiveUnit->items[gActionData.itemSlotIndex]);

    ClearText(text);
    Text_InsertDrawString(text, 0, 3, GetStringFromIndex(0x4E9)); // HP
    Text_InsertDrawNumberOrBlank(text, 28, 2, hp);
    Text_InsertDrawString(text, 36, 3, "->");
    Text_InsertDrawNumberOrBlank(text, 56, healed >= max ? 4 : 2, healed >= max ? max : healed);
    PutText(text, gBG0TilemapBuffer + TILEMAP_INDEX(x + 1, 3));
}

""" + _HP_WINDOW
_HEAL_SWITCH = ("u8 HealMapSelect_SwitchIn(ProcPtr proc, struct SelectTarget* target) {\n\n"
                "    ChangeActiveUnitFacing(target->x, target->y);\n\n"
                "    RefreshUnitHpInfoWindow(GetUnit(target->uid));\n")
_HEAL_SWITCH_PREVIEW = ("void RefreshUnitHealPreviewWindowFem(struct Unit* unit);\n\n"
                        + _HEAL_SWITCH.replace("RefreshUnitHpInfoWindow", "RefreshUnitHealPreviewWindowFem"))


def validate(options: dict) -> str | None:
    """Problem code for the options, else None."""
    for key, value in options.items():
        if key in DEFAULTS:
            if value not in DEFAULTS[key][2]:
                return "badGameOption"
        elif key in SWITCHES:
            if not isinstance(value, bool):
                return "badGameOption"
        elif key in CHOICES:
            if value not in CHOICES[key]:
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
        if key in options and key not in OWN_LINE_DEFAULTS:
            body, n = re.subn(rf"(gPlaySt\.config\.{field} = )\d+;", rf"\g<1>{int(options[key])};", body)
            if n != 1 and field != "disableGoalDisplay":   # the only one the game leaves at the 0 of the cleared state
                raise TweakError(f"Option {field} not found in InitPlayConfig ({CONFIG_FILE})")
            if n != 1:
                body = f"{body[:-1]}    gPlaySt.config.{field} = {int(options[key])};\n}}"
    return source[:m.start()] + body + source[m.end():]


# Ticket 166: on page 1 of the status screen, Select shows the character's growth rates in place of the stats (with the
# Metis Tome's +5, as CheckBattleUnitLevelUp uses them), a bar up to 100 %, and an HP line in place of the battles /
# wins / losses one; Mov and Con, which do not grow, stay. Magic's growth with the Strength/Magic split (strmag.py).
STATUS_FILE = "src/statscreen.c"
STATUS_HEADER = "include/statscreen.h"
_STATUS_FIELD = "    /* 08 */ s8 inTransition;\n"
_STATUS_FIELD_GROWTHS = _STATUS_FIELD + "    /* 09 */ u8 growthsFem; /* FE Maker: growth rates shown (Select, ticket 166) */\n"
_STATUS_OPEN = "    gStatScreen.help = NULL;\n"   # StartStatScreen (inTransition = FALSE is first in PageSlide_OnEnd)
_STATUS_OPEN_GROWTHS = _STATUS_OPEN + "    gStatScreen.growthsFem = FALSE;\n"
_STATUS_BAR = ("void DrawStatWithBar(int num, int x, int y, int base, int total, int max)\n{\n"
               "    int diff = total - base;\n")
_STATUS_BAR_GROWTHS = """/* FE Maker (ticket 166): a stat's growth rate by its bar number (0 Str, 1 Skl, 2 Spd, 3 Lck, 4 Def,
   5 Res, 8 Mag with the Strength/Magic split, 9 HP), -1 for Mov and Con */
static int GetStatGrowthFem(struct Unit* unit, int num)
{
    const struct CharacterData* character = unit->pCharacterData;
    int bonus = (unit->state & US_GROWTH_BOOST) ? 5 : 0;

    switch (num) {
    case 0: return character->growthPow + bonus;
    case 1: return character->growthSkl + bonus;
    case 2: return character->growthSpd + bonus;
    case 3: return character->growthLck + bonus;
    case 4: return character->growthDef + bonus;
    case 5: return character->growthRes + bonus;
#ifdef UNIT_MAG_FEM
    case 8: return gCharacterMagFem[character->number][1] + bonus;
#endif
    case 9: return character->growthHP + bonus;
    }
    return -1;
}

/* FE Maker (ticket 166): a stat's name coloured by its growth rate, for player units, with the colours and steps of the
   MSS Display Growths options (Skill System, through FEBuilderGBA): 2 palettes of 5 colours, green to red */
#define STATSCREEN_BGPAL_GROWTHS_FEM 8 /* 8 and 9, free on this screen */
static const u16 sGrowthColorsFem[2][16] = {
    { 0x0000, 0x266A, 0x0B27, 0x0D63, 0x266A, 0x3710, 0x0D63, 0x266A, 0x3355, 0x0D63, 0x266A, 0x47B9, 0x0D63,
      0x266A, 0x3BFD, 0x0CE8 },
    { 0x0000, 0x4196, 0x4B9F, 0x106A, 0x3133, 0x2EBF, 0x106A, 0x3133, 0x321F, 0x106A, 0x3133, 0x317F, 0x106A,
      0x3133, 0x211F, 0x106A },
};
static const u8 sGrowthStepsFem[] = { 20, 30, 40, 45, 50, 60, 70, 80, 90, 100 };

static void PutGrowthLabelFem(int textId, int y, int msg, int num)
{
    struct Text* text = &gStatScreen.text[textId];
    u16* tm = gUiTmScratchA + TILEMAP_INDEX(1, y);
    int growth = GetStatGrowthFem(gStatScreen.unit, num);
    int step = 0, color, i;

    ClearText(text); /* drawn in gold already: a glyph drawn over another mixes their pixels */
    if (UNIT_FACTION(gStatScreen.unit) != FACTION_BLUE || growth < 0) {
        PutDrawText(text, tm, TEXT_COLOR_SYSTEM_GOLD, 0, 0, GetStringFromIndex(msg));
        return;
    }
    while (step < 10 && growth >= sGrowthStepsFem[step])
        step++;
    if (step == 10) { /* 100 % and more: the game's own green */
        PutDrawText(text, tm, TEXT_COLOR_SYSTEM_GREEN, 0, 0, GetStringFromIndex(msg));
        return;
    }
    color = 9 - step; /* 0 green (90 %) to 9 red (under 20 %): palette 8 + color / 5, its color % 5-th group */
    PutDrawText(text, tm, color % 5, 0, 0, GetStringFromIndex(msg));
    for (i = 0; i < text->tile_width; i++) {
        tm[i] = (tm[i] & 0xFFF) | ((STATSCREEN_BGPAL_GROWTHS_FEM + color / 5) << 12);
        tm[i + 0x20] = (tm[i + 0x20] & 0xFFF) | ((STATSCREEN_BGPAL_GROWTHS_FEM + color / 5) << 12);
    }
}

static void ColorStatLabelsFem(void)
{
    int y = 3;

#ifdef UNIT_MAG_FEM
    PutGrowthLabelFem(STATSCREEN_TEXT_POWLABEL, 1, MSG_4FE, 0);
    PutGrowthLabelFem(STATSCREEN_TEXT_UNUSUED, 3, MSG_4FF, 8);
    y = 5;
#else
    PutGrowthLabelFem(STATSCREEN_TEXT_POWLABEL, 1, UnitHasMagicRank(gStatScreen.unit) ? MSG_4FF : MSG_4FE, 0);
#endif
    PutGrowthLabelFem(STATSCREEN_TEXT_SKLLABEL, y, gMid_Skl, 1);
    PutGrowthLabelFem(STATSCREEN_TEXT_SPDLABEL, y + 2, gMid_Spd, 2);
    PutGrowthLabelFem(STATSCREEN_TEXT_LCKLABEL, y + 4, gMid_Lck, 3);
    PutGrowthLabelFem(STATSCREEN_TEXT_DEFLABEL, y + 6, gMid_Def, 4);
    PutGrowthLabelFem(STATSCREEN_TEXT_RESLABEL, y + 8, gMid_Res, 5);
}

""" + _STATUS_BAR + """    int growth = gStatScreen.growthsFem ? GetStatGrowthFem(gStatScreen.unit, num) : -1;

    if (growth >= 0) { /* FE Maker: the growth rate (one tile right, where the bonus goes: 100 % fits), its bar up to 100 % */
        PutNumberOrBlank(gUiTmScratchA + TILEMAP_INDEX(x + 1, y), TEXT_COLOR_SYSTEM_BLUE, growth);
        DrawStatBarGfx(0x401 + num*6, 6,
            gUiTmScratchC + TILEMAP_INDEX(x - 2, y + 1),
            TILEREF(0, STATSCREEN_BGPAL_6), 41, (growth > 100 ? 100 : growth) * 41 / 100, 0);
        return;
    }

"""
_STATUS_BWL = ("void DisplayBwl(void)\n{\n"
               "    struct UnitUsageStats* stats = GetPidStats(gStatScreen.unit->pCharacterData->number);\n")
_STATUS_BWL_GROWTHS = "static void PutGrowthLabelFem(int textId, int y, int msg, int num);\n\n" + _STATUS_BWL + """
    if (gStatScreen.growthsFem) { /* FE Maker (ticket 166): HP's growth in place of this line, below Res */
#ifdef UNIT_MAG_FEM
        int y = 15;
#else
        int y = 13;
#endif
        ClearText(&gStatScreen.text[STATSCREEN_TEXT_BWL]);
        PutGrowthLabelFem(STATSCREEN_TEXT_BWL, y, MSG_4E9, 9); // HP
        DrawStatWithBar(9, 5, y, 0, 0, 0);
        return;
    }
"""
_STATUS_PALETTE = "    ApplyPalette(Pal_StatscreenEquipmentText, STATSCREEN_BGPAL_EQUIPMENT_LABEL);\n"
_STATUS_PALETTE_GROWTHS = _STATUS_PALETTE + "    ApplyPalettes(sGrowthColorsFem[0], STATSCREEN_BGPAL_GROWTHS_FEM, 2);\n"
_STATUS_LABELS = "    // displaying mov stat value\n"   # DisplayPage0, after the left column
_STATUS_LABELS_GROWTHS = "    ColorStatLabelsFem(); /* FE Maker (ticket 166) */\n\n" + _STATUS_LABELS
_STATUS_KEYS = "    else if (gKeyStatusPtr->newKeys & R_BUTTON)\n    {\n"
_STATUS_KEYS_GROWTHS = """    else if ((gKeyStatusPtr->newKeys & SELECT_BUTTON) && (gStatScreen.page == STATSCREEN_PAGE_0))
    {
        /* FE Maker (ticket 166): growth rates or stats */
        gStatScreen.growthsFem = !gStatScreen.growthsFem;
        DisplayPage(gStatScreen.page);
        TileMap_CopyRect(gUiTmScratchA, gBG0TilemapBuffer + TILEMAP_INDEX(12, 2), 18, 18);
        TileMap_CopyRect(gUiTmScratchC, gBG2TilemapBuffer + TILEMAP_INDEX(12, 2), 18, 18);
        BG_EnableSyncByMask(BG0_SYNC_BIT | BG2_SYNC_BIT);
        PlaySoundEffect(SONG_SE_SYS_CURSOR_LR1);
    }

""" + _STATUS_KEYS


# FEBuilder "16_tracks_12_sounds": songs of 16 tracks (the game's music players have 8) and 12 notes at once (7, or 8
# for a few songs). The two music players' tracks move to free RAM (the unused debug print buffer of fontgrp.c, below
# the skills' data at 0x02028800): their IWRAM space stays where it is, so nothing else moves.
MUSIC_PLAYERS_FILE = "sound/music_player_table.s"
SOUND_FILE = "src/soundwrapper.c"
MUSIC_TRACKS = 16
MUSIC_NOTES = 12
_TRACKS_RAM = (0x02027000, 0x02027500)   # BGM1, BGM2: 16 tracks of 0x50 bytes each
_PLAYERS = tuple(f"\tmusic_player gMPlayInfo_BGM{n}, gMPlayTrack_BGM{n}, NUM_TRACKS_BGM{n}, 0\n" for n in (1, 2))
_PLAYERS_NEW = tuple(f"\tmusic_player gMPlayInfo_BGM{n}, 0x{a:08X}, {MUSIC_TRACKS}, 0 @ FE Maker: 16 tracks in free RAM\n"
                     for n, a in zip((1, 2), _TRACKS_RAM))
_NOTES_DEFAULT = "    Sound_SetMaxNumChannels(7);\n"
_NOTES_SONGS = "        if (gSoundSt.maxChannels != 8)\n            Sound_SetMaxNumChannels(8);\n"


def with_music_tracks(players: str, sound: str) -> tuple[str, str]:
    """The music players with 16 tracks and the sound driver with 12 notes at once (option musicTracks)."""
    for old, new in zip(_PLAYERS, _PLAYERS_NEW):
        players = _replace(players, old, new, MUSIC_PLAYERS_FILE)
    sound = _replace(sound, _NOTES_DEFAULT, f"    Sound_SetMaxNumChannels({MUSIC_NOTES}); /* FE Maker: 12 notes */\n",
                     SOUND_FILE)
    sound = _replace(sound, _NOTES_SONGS, f"        if (gSoundSt.maxChannels != {MUSIC_NOTES})\n"
                                          f"            Sound_SetMaxNumChannels({MUSIC_NOTES});\n", SOUND_FILE)
    return players, sound


def _replace(source: str, old: str, new: str, rel: str) -> str:
    if old not in source:
        raise TweakError(f"A game option does not match this version of the decomp ({rel})")
    return source.replace(old, new, 1)


def apply(decomp_dir: Path, options: dict, files: dict, menu_texts: tuple[int, int] = (0, 0)) -> dict:
    """Add the project's game options to `files` (decomp-relative path -> content); `menu_texts`: the messages of the
    Configuration menu's new line (MENU_TEXTS), added to the texts before they are written."""
    def current(rel: str) -> str:
        return files[rel] if rel in files else (decomp_dir / rel).read_text(encoding="utf-8")

    if any(key in options and options[key] != DEFAULTS[key][1] for key in DEFAULTS if key not in OWN_LINE_DEFAULTS):
        files[CONFIG_FILE] = with_defaults(current(CONFIG_FILE), {k: v for k, v in options.items() if k in DEFAULTS})
    rule = CHOICES["tempBonusRule"].index(options.get("tempBonusRule", "strongest"))
    if rule and _TEMP_RULE in files.get(TEMP_RULE_FILE, ""):   # only when a Pure Water copy uses the bonuses
        files[TEMP_RULE_FILE] = files[TEMP_RULE_FILE].replace(_TEMP_RULE, f"#define TEMP_BONUS_RULE_FEM {rule}\n", 1)
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
    if options.get("actAfterTalk"):
        source = _replace(current(RANGE_DISPLAY_FILE), _TALK_HEAD, _TALK_HEAD_NEW, RANGE_DISPLAY_FILE)
        source = _replace(source, _TALK_STEP, _TALK_STEP_NEW, RANGE_DISPLAY_FILE)
        files[RANGE_DISPLAY_FILE] = _replace(source, _TALK_CANCEL, _TALK_CANCEL_NEW, RANGE_DISPLAY_FILE)
    if options.get("skipStoryIntro"):
        files[GAME_CONTROL_FILE] = _replace(current(GAME_CONTROL_FILE), _STORY_INTRO, _STORY_INTRO_NONE, GAME_CONTROL_FILE)
        source, found = _WORLD_MAP_TALE.subn(r"\1\2", current(WORLD_MAP_INTRO_FILE))
        if not found:
            raise TweakError(f"A game option does not match this version of the decomp ({WORLD_MAP_INTRO_FILE})")
        files[WORLD_MAP_INTRO_FILE] = source
    if options.get("musicTracks"):
        files[MUSIC_PLAYERS_FILE], files[SOUND_FILE] = with_music_tracks(current(MUSIC_PLAYERS_FILE),
                                                                         current(SOUND_FILE))
    if options.get("quickChapterTitle"):
        files[CHAPTER_INTRO_FILE] = _replace(current(CHAPTER_INTRO_FILE), _TITLE_WAIT, _TITLE_QUICK, CHAPTER_INTRO_FILE)
    if options.get("holdAToSpeedUp"):
        files[MOVE_SPEED_FILE] = _replace(current(MOVE_SPEED_FILE), _HOLD_A, _HOLD_A_ALWAYS, MOVE_SPEED_FILE)
    if options.get("holdLBattleSpeed"):
        files[BATTLE_ANIM_FILE] = _replace(current(BATTLE_ANIM_FILE), _BATTLE_FRAME, _BATTLE_FRAME_FAST, BATTLE_ANIM_FILE)
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
    if options.get("deadItemsToConvoy") and not options.get("casualMode"):
        source = _replace(current(UNIT_FILE), _UNIT_INCLUDES, _UNIT_INCLUDES_CONVOY, UNIT_FILE)
        files[UNIT_FILE] = _replace(source, _DEATH_ELSE, _DEATH_ELSE_CONVOY, UNIT_FILE)
    if options.get("hpBars"):
        files[MAP_UI_FILE] = _replace(current(MAP_UI_FILE), _OBJ_UI_LOAD, _OBJ_UI_LOAD_BARS, MAP_UI_FILE)
        source = _replace(current(MAP_SPRITES_FILE), _ICONS, _ICONS_BARS, MAP_SPRITES_FILE)
        files[MAP_SPRITES_FILE] = _replace(source, _ICONS_LOOP, _ICONS_LOOP_BARS, MAP_SPRITES_FILE)
    if options.get("healPreview"):
        files[INFO_WINDOW_FILE] = _replace(current(INFO_WINDOW_FILE), _HP_WINDOW, _HP_WINDOW_HEAL, INFO_WINDOW_FILE)
        files[HEAL_SELECT_FILE] = _replace(current(HEAL_SELECT_FILE), _HEAL_SWITCH, _HEAL_SWITCH_PREVIEW, HEAL_SELECT_FILE)
    if options.get("battleNumbers"):
        files = battlenumbers.apply(decomp_dir, files)
    if options.get("talkBubbles"):
        files[MAP_UI_FILE] = _replace(current(MAP_UI_FILE), _OBJ_UI_LOAD, _OBJ_UI_LOAD_BUBBLE, MAP_UI_FILE)
        source = _replace(current(MAP_SPRITES_FILE), _ICONS, _ICONS_BUBBLE, MAP_SPRITES_FILE)
        files[MAP_SPRITES_FILE] = _replace(source, _ICONS_LOOP, _ICONS_LOOP_BUBBLE, MAP_SPRITES_FILE)
    if options.get("statusGrowths"):
        files[STATUS_HEADER] = _replace(current(STATUS_HEADER), _STATUS_FIELD, _STATUS_FIELD_GROWTHS, STATUS_HEADER)
        source = current(STATUS_FILE)
        for old, new in ((_STATUS_OPEN, _STATUS_OPEN_GROWTHS), (_STATUS_BAR, _STATUS_BAR_GROWTHS),
                         (_STATUS_BWL, _STATUS_BWL_GROWTHS), (_STATUS_KEYS, _STATUS_KEYS_GROWTHS),
                         (_STATUS_PALETTE, _STATUS_PALETTE_GROWTHS), (_STATUS_LABELS, _STATUS_LABELS_GROWTHS)):
            source = _replace(source, old, new, STATUS_FILE)
        files[STATUS_FILE] = source
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
                                      start + f"    gPlaySt.config.unk41_6 = {int(options.get('staffDance', 1))};"
                                      " /* FE Maker: 1 staves on the map (ticket 43) */\n", CONFIG_FILE)
    return files
