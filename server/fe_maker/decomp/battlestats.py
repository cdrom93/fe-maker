"""Battle stats with animations off (game option `mapBattleStats`).

FEBuilderGBA's patch "FE8-Battle Stats with Anims Off ver2" (Tequila; weapon line by Vesly), written into the decomp
in C: in a map battle between two units, each box under its HP shows Hit, Dmg, Crt and AS, then the weapon's icon and
name and the weapon triangle's arrow. The patch's images (box, numbers with "-" for "?", stat names, arrows, the two
taller boxes' TSA) are downloaded once from laqieer's mirror of FEBuilderGBA's patches, never kept in this repository.
The stat names use the item icons' palette (the patch's own palette is the same colors). The box is placed as the
patch does (lower on screen, taller), kept whole on screen.
"""

from __future__ import annotations

import urllib.error
import urllib.request
from pathlib import Path

from ..config import config_dir
from .tweaks import TweakError

REPO = "laqieer/FEBuilderGBA-patch2"
COMMIT = "6b0105c242041bb56e1d599709f5606569eb92ed"
FOLDER = "FE8U/FE8-Battle%20Stats%20with%20Anims%20Offv2"
# FE Maker's name -> (the patch's file, its size when decompressed; 0: not compressed)
ASSETS = {"box": ("Anims_Off_Battle_Graphic-New.dmp", 1024), "numbers": ("new_numbers.dmp", 576),
          "names": ("New_Stat_Names.dmp", 320), "right": ("src/RightBox.dmp", 218), "left": ("src/LeftBox.dmp", 200),
          "arrows": ("src/ArrowIcons.dmp", 0)}
GRAPHICS_DIR = "graphics/fem_battle_stats"
DATA_FILE = "data/data_9A31F8.s"
BOX_FILE = "src/mapanim_infobox.c"
PLACE_FILE = "src/mapanim.c"


def _download(name: str) -> bytes:
    file, size = ASSETS[name]
    path = config_dir() / "febuilder-patch2" / COMMIT[:12] / "battle-stats" / Path(file).name
    if not path.is_file():
        from ..ferepo import _ssl_context
        url = f"https://raw.githubusercontent.com/{REPO}/{COMMIT}/{FOLDER}/{file}"
        request = urllib.request.Request(url, headers={"User-Agent": "FE-Maker"})
        try:
            with urllib.request.urlopen(request, timeout=30, context=_ssl_context()) as response:
                data = response.read(4096)
        except (urllib.error.URLError, OSError) as e:
            raise TweakError("Battle stats with animations off: the patch's images could not be downloaded") from e
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
    data = path.read_bytes()
    ok = (data[0] == 0x10 and int.from_bytes(data[1:4], "little") == size) if size else len(data) == 256
    if not ok:
        path.unlink()
        raise TweakError(f"Battle stats with animations off: unexpected file {file}")
    return data


def _replace(text: str, old: str, new: str, rel: str) -> str:
    if text.count(old) != 1:
        raise TweakError(f"Battle stats with animations off: {rel} does not match this version of the decomp")
    return text.replace(old, new, 1)


_LABELS = {"box": "Img_MapBattleInfoBoxFem", "numbers": "Img_MapBattleInfoNumFem", "names": "Img_MapBattleStatNamesFem",
           "right": "Tsa_MapBattleBoxRightFem", "left": "Tsa_MapBattleBoxLeftFem", "arrows": "Img_MapBattleArrowsFem"}

# Two units: the patch's images, its stats and weapon line under each HP.
_DRAW_OLD = """    Decompress(
        Img_MapBattleInfoBox,
        (void*)(VRAM) + GetBackgroundTileDataOffset(1) + BM_BGCHR_BANIM_IFBACK * 0x20); //< TODO: put in macro?

    PrepareMapBattleBoxNumGfx(Img_MapBattleInfoHpBar);
"""
_DRAW_NEW = """    Decompress(
        gManimSt.actorCount == 2 ? Img_MapBattleInfoBoxFem : Img_MapBattleInfoBox, /* FE Maker: battle stats */
        (void*)(VRAM) + GetBackgroundTileDataOffset(1) + BM_BGCHR_BANIM_IFBACK * 0x20); //< TODO: put in macro?

    PrepareMapBattleBoxNumGfx(Img_MapBattleInfoHpBar);

    if (gManimSt.actorCount == 2) {
        Decompress(Img_MapBattleInfoNumFem, (u8*)(VRAM) + GetBackgroundTileDataOffset(0) + 0x20 * 0x20);
        Decompress(Img_MapBattleInfoHpBar, (u8*)(VRAM + 0x20 * 43));
        Decompress(Img_MapBattleStatNamesFem, (u8*)(VRAM) + GetBackgroundTileDataOffset(0) + 0x20 * FEM_STAT_NAMES);
        CpuFastCopy(Img_MapBattleArrowsFem, (u8*)(VRAM) + GetBackgroundTileDataOffset(0) + 0x20 * FEM_STAT_ARROWS, 0x100);
        LoadIconPalette(0, FEM_STAT_PAL);
    }
"""
_TWO_OLD = """        DisplayBattleInfoBox(proc, 0, -1);
        DisplayBattleInfoBox(proc, 1, -11);
        break;
"""
_TWO_NEW = """        DisplayBattleInfoBox(proc, 0, -1);
        DisplayBattleInfoBox(proc, 1, -11);
        FemPutBattleStats(0);
        FemPutBattleStats(1);
        break;
"""
_TSA_OLD = "    {Tsa_MapBattleBoxGfx3, Tsa_MapBattleBoxGfx2},\n"
_TSA_NEW = "    {Tsa_MapBattleBoxRightFem, Tsa_MapBattleBoxLeftFem}, /* FE Maker: battle stats */\n"
_CODE_ANCHOR = "void EndMapAnimInfoWindow(void)\n"
_CODE = """/* FE Maker: battle stats with animations off, as FEBuilderGBA's "FE8-Battle Stats with Anims Off ver2"
 * (Tequila; the weapon line by Vesly) */
extern u8 Img_MapBattleInfoBoxFem[];
extern u8 Img_MapBattleInfoNumFem[];
extern u8 Img_MapBattleStatNamesFem[];
extern u8 Img_MapBattleArrowsFem[];
extern CONST_DATA u8 Tsa_MapBattleBoxRightFem[];
extern CONST_DATA u8 Tsa_MapBattleBoxLeftFem[];

#define FEM_STAT_NAMES 0x40  /* Hit (2 tiles), Dmg (3), Crt (2), AS (3) */
#define FEM_STAT_ARROWS 0x4A /* 4 x 2 tiles: up, down */
#define FEM_STAT_PAL 3       /* the item icons' palette */

static void FemPutStatNumber(u16 * tile, int number)
{
    int i;

    for (i = 0; i < 3; ++i)
        tile[-i] = 0;

    if (number < 0 || number == 0xFF) {
        /* "--", the patch's numbers draw it in place of the game's "??" */
        tile[0] = tile[-1] = TILEREF(0x20 + 10, BM_BGPAL_BANIM_UNK5);
        return;
    }

    i = 0;
    do {
        tile[-i++] = TILEREF(0x20 + number % 10, BM_BGPAL_BANIM_UNK5);
        number /= 10;
    } while (number != 0 && i < 3);
}

static void FemPutStatName(u16 * tile, int first, int count)
{
    int i;

    for (i = 0; i < count; ++i)
        tile[i] = TILEREF(FEM_STAT_NAMES + first + i, FEM_STAT_PAL);
}

void FemPutBattleStats(int index)
{
    struct BattleUnit * bu = gManimSt.actor[index].bu;
    struct BattleUnit * other = gManimSt.actor[1 - index].bu;
    int x = gManimSt.actor[index].hp_info_x;
    int y = gManimSt.actor[index].hp_info_y;
    int damage = bu->battleAttack;

    if (damage != 0xFF) {
        damage -= other->battleDefense;
        if (damage < 0)
            damage = 0;
    }

    /* the numbers first: a number clears its 3 tiles, the names' third tile is one of them (as the patch) */
    FemPutStatNumber(gBG0TilemapBuffer + TILEMAP_INDEX(x + 5, y + 4), bu->battleEffectiveHitRate);
    FemPutStatNumber(gBG0TilemapBuffer + TILEMAP_INDEX(x + 10, y + 4), damage);
    FemPutStatNumber(gBG0TilemapBuffer + TILEMAP_INDEX(x + 5, y + 5), bu->battleEffectiveCritRate);
    FemPutStatNumber(gBG0TilemapBuffer + TILEMAP_INDEX(x + 10, y + 5),
        gActionData.unitActionType == UNIT_ACTION_STAFF ? -1 : bu->battleSpeed);
    FemPutStatName(gBG0TilemapBuffer + TILEMAP_INDEX(x + 1, y + 4), 0, 2);
    FemPutStatName(gBG0TilemapBuffer + TILEMAP_INDEX(x + 6, y + 4), 2, 3);
    FemPutStatName(gBG0TilemapBuffer + TILEMAP_INDEX(x + 1, y + 5), 5, 2);
    FemPutStatName(gBG0TilemapBuffer + TILEMAP_INDEX(x + 6, y + 5), 7, 3);

    if (bu->weaponBefore) {
        struct Text text;
        const char * name = GetItemName(bu->weaponBefore);
        int arrow = 0;

        DrawIcon(gBG0TilemapBuffer + TILEMAP_INDEX(x + 1, y + 6), GetItemIconId(bu->weaponBefore),
            TILEREF(0, FEM_STAT_PAL));

        InitText(&text, 7);
        Text_SetParams(&text, GetStringTextCenteredPos(7 * 8, name), TEXT_COLOR_SYSTEM_WHITE);
        Text_DrawString(&text, name);
        PutText(&text, gBG0TilemapBuffer + TILEMAP_INDEX(x + 3, y + 6));

        /* the weapon triangle: up when it is on this unit's side */
        if (bu->wTriangleDmgBonus != other->wTriangleDmgBonus)
            arrow = bu->wTriangleDmgBonus > other->wTriangleDmgBonus ? 1 : 3;
        else if (bu->wTriangleHitBonus != other->wTriangleHitBonus)
            arrow = bu->wTriangleHitBonus > other->wTriangleHitBonus ? 1 : 3;

        if (arrow) {
            gBG0TilemapBuffer[TILEMAP_INDEX(x + 10, y + 6)] = FEM_STAT_ARROWS + arrow;
            gBG0TilemapBuffer[TILEMAP_INDEX(x + 10, y + 7)] = FEM_STAT_ARROWS + arrow + 4;
        }
    }

    BG_EnableSyncByMask(BG0_SYNC_BIT);
}

"""
# Two units: the box is 9 tiles high (4 in the game); it goes under the lower unit, above the upper one, between them,
# else at the bottom of the screen (or the top when the upper unit is there). The patch moves it the same way, on screen.
_PLACE_OLD = """            if (ABS(array[0] - array[1]) >= 80)
            {
                y = 64;
            }
"""
_PLACE_NEW = """            if (TRUE) /* FE Maker: battle stats, a taller box */
            {
                int top = array[0] < array[1] ? array[0] : array[1];
                int bottom = array[0] + array[1] - top;

                if ((bottom + 24) / 8 <= 11)
                    y = bottom + 24;
                else if (top >= 80)
                    y = top - 80;
                else if (((top + 23) / 8) * 8 + 72 <= bottom)
                    y = top + 23;
                else
                    y = top >= 72 || bottom > 72 ? 0 : 88;
            }
            else if (ABS(array[0] - array[1]) >= 80)
            {
                y = 64;
            }
"""


def apply(decomp_dir: Path, files: dict) -> dict:
    def current(rel: str) -> str:
        return files[rel] if rel in files else (decomp_dir / rel).read_text(encoding="utf-8")

    data = current(DATA_FILE).rstrip("\n") + "\n\n@ FE Maker: battle stats with animations off (FEBuilderGBA's patch)\n"
    for name, label in _LABELS.items():
        rel = f"{GRAPHICS_DIR}/{name}.dmp"
        files[rel] = _download(name)
        data += f"\t.align 2\n\t.global {label}\n{label}:\n\t.incbin \"{rel}\"\n"
    files[DATA_FILE] = data
    box = current(BOX_FILE)
    box = _replace(box, '#include "constants/songs.h"\n',
                   '#include "constants/songs.h"\n#include "icon.h"\n#include "fontgrp.h"\n#include "bmitem.h"\n'
                   '#include "bmbattle.h"\n#include "bmmind.h"\n', BOX_FILE)
    box = _replace(box, _CODE_ANCHOR, _CODE + _CODE_ANCHOR, BOX_FILE)
    box = _replace(box, _DRAW_OLD, _DRAW_NEW, BOX_FILE)
    box = _replace(box, _TWO_OLD, _TWO_NEW, BOX_FILE)
    files[BOX_FILE] = _replace(box, _TSA_OLD, _TSA_NEW, BOX_FILE)
    files[PLACE_FILE] = _replace(current(PLACE_FILE), _PLACE_OLD, _PLACE_NEW, PLACE_FILE)
    return files
