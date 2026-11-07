"""Damage and heal numbers in battle animations (game option `battleNumbers`, ticket 169).

C-SkillSys's AnimNumber (Kernel/Wizardry/Common/BanimHack/AnimNumber, MIT, Mokha and contributors), at skills.COMMIT,
written into the decomp: a red "-n" over the unit hit when its HP bar flashes, a green "+n" over the unit healed (staff,
or the drain of Nosferatu, Sol and Aether). Its image (Data/Anims/Source/Img_EfxAnimNumber.png) is downloaded once,
never in this repository. Tiles: those of the game's MISS / NO DAMAGE text (OBJ 0x6012000), never shown with a number;
palette: OBJ 15, as C-SkillSys.
"""

from __future__ import annotations

import io
from pathlib import Path

from PIL import Image

from ..config import config_dir
from .skills import COMMIT, REPO, _download

IMAGE_URL = f"https://raw.githubusercontent.com/{REPO}/{COMMIT}/Data/Anims/Source/Img_EfxAnimNumber.png"
IMAGE = "graphics/banim/anim_number_fem.png"
DATA_FILE = "data/banim-efxhitfx.s"
HPBAR_FILE = "src/banim-efxhpbar.c"
FLASH_FILE = "src/banim-efxflashunit.c"
HEADER = "include/efxbattle.h"


class BattleNumbersError(Exception):
    pass


def image_png() -> bytes:
    """The numbers' image as a 4-bit PNG (gbagfx makes the tiles and the palette from it)."""
    path = _download(IMAGE_URL, config_dir() / "cskillsys" / COMMIT[:12] / "Img_EfxAnimNumber.png")
    image = Image.open(path)
    if image.mode != "P" or image.size != (176, 32):
        raise BattleNumbersError("Img_EfxAnimNumber.png: unexpected image")
    out = io.BytesIO()
    image.save(out, "PNG", bits=4)
    return out.getvalue()


def _replace(text: str, old: str, new: str, rel: str) -> str:
    if text.count(old) != 1:
        raise BattleNumbersError(f"Battle numbers: {rel} does not match this version of the decomp ({old.strip()[:60]})")
    return text.replace(old, new, 1)


def _sprites() -> str:
    """AnimSprite_AnimNumber1 to 15 of C-SkillSys's animscr_num.s: up to 4 squares of 16 x 16 (the sign and 3 digits),
    each its own y while the number bounces in."""
    rows = [(-8,), (-7,), (-6,), (-4, -8), (-3, -7), (-1, -6), (1, -4), (3, -3), (1, -1, -8), (0, 3, -5), (0, 1, -3),
            (0, -1, 0, -8), (0, 1, 3, -5), (0, 0, -1, -3), (0, 0, 0, 0)]
    out = []
    for n, ys in enumerate(rows, 1):
        squares = "".join(f"    {{ .header = 0x40000000, .as = {{ .object = {{ .oam2 = {2 * k}, .x = {0x10 * k}, "
                          f".y = {y} }} }} }},\n" for k, y in enumerate(ys))
        out.append(f"CONST_DATA struct AnimSpriteData AnimSprite_AnimNumberFem{n}[] = {{\n{squares}    ANIM_SPRITE_END\n}};\n")
    return "\n".join(out)


def _script() -> str:
    up = [(n, 1 if n <= 10 else 2) for n in range(1, 16)]
    down = [(n, 1) for n in range(15, 0, -1)]
    lines = [f"    ANIMSCR_FORCE_SPRITE(AnimSprite_AnimNumberFem{n}, {t}),\n" for n, t in up]
    lines.append("    ANFMT_NOT_FORCESPRITE + ANFMT_INST_TYPE(ANIM_INS_TYPE_WAIT) + 0x1A,\n")
    lines += [f"    ANIMSCR_FORCE_SPRITE(AnimSprite_AnimNumberFem{n}, {t}),\n" for n, t in down]
    lines.append("    ANFMT_NOT_FORCESPRITE + ANFMT_INST_TYPE(ANIM_INS_TYPE_END),\n")
    return "CONST_DATA AnimScr AnimScr_AnimNumberFem[] = {\n" + "".join(lines) + "};\n"


CODE = """
/* FE Maker (ticket 169): damage and heal numbers (C-SkillSys's AnimNumber, MIT, Mokha and contributors) */
#include "ctc.h"

#define ANIMNUM_CHR_FEM 0x100   /* the MISS / NO DAMAGE text's tiles (0x6012000), never shown with a number */
#define ANIMNUM_PAL_FEM 0xF
#define ANIMNUM_LEN_FEM 11      /* 0 to 9 and the sign, 2 tiles each; the red ones 2 rows lower */

extern const u8 Img_EfxAnimNumberFem[];
extern const u16 Pal_EfxAnimNumberFem[];

struct ProcEfxAnimNumberFem {
    PROC_HEADER;
    struct Anim * anim;
    struct Anim * anim_num;
    int number;
    int slot;
};

%(sprites)s
%(script)s
static void CopyAnimNumberFem(const u8 * src, u8 * dst)
{
    CpuFastCopy(src, dst, 0x40);
    CpuFastCopy(src + 0x20 * ANIMNUM_LEN_FEM * 2, dst + 0x400, 0x40);
}

static void SetupEfxAnimNumberGfxFem(int number, int slot)
{
    u8 * vram = (u8 *) OBJ_VRAM0 + (ANIMNUM_CHR_FEM + slot * 8) * 0x20;
    int i, value = number > 0 ? number : -number;
    int base = number > 0 ? 0 : 2 * 2 * ANIMNUM_LEN_FEM;

    CpuFastFill(0, vram, 0x20 * 8);
    CpuFastFill(0, vram + 0x400, 0x20 * 8);
    if (value > 999)
        value = 999;
    for (i = 3; i > 0;)
    {
        CopyAnimNumberFem(Img_EfxAnimNumberFem + (base + (value %% 10) * 2) * 0x20, vram + i * 2 * 0x20);
        value /= 10;
        i--;
        if (value <= 0)
            break;
    }
    CopyAnimNumberFem(Img_EfxAnimNumberFem + (base + 10 * 2) * 0x20, vram + i * 2 * 0x20);
    ApplyPalette(Pal_EfxAnimNumberFem, 0x10 + ANIMNUM_PAL_FEM);
}

static void EfxAnimNumberStartFem(struct ProcEfxAnimNumberFem * proc)
{
    struct Anim * anim;
    int x = OAM1_X(proc->anim->xPosition) - 0x34;

    if (x < 0)
        x = 0;
    proc->anim_num = anim = AnimCreate(AnimScr_AnimNumberFem, 0x95);
    anim->xPosition = OAM1_X(x);
    anim->yPosition = OAM0_Y(0x25);
    anim->oam2Base = OAM2_PAL(ANIMNUM_PAL_FEM) + OAM2_LAYER(1) + OAM2_CHR(ANIMNUM_CHR_FEM + proc->slot * 8);
}

static void EfxAnimNumberLoopFem(struct ProcEfxAnimNumberFem * proc)
{
    if (proc->anim_num->state == 0)
        Proc_Break(proc);
}

CONST_DATA struct ProcCmd ProcScr_EfxAnimNumberFem[] = {
    PROC_YIELD,
    PROC_CALL(EfxAnimNumberStartFem),
    PROC_REPEAT(EfxAnimNumberLoopFem),
    PROC_END,
};

void NewEfxAnimNumberFem(struct Anim * anim, int number)
{
    struct ProcEfxAnimNumberFem * proc;
    struct ProcEfxAnimNumberFem * other = Proc_Find(ProcScr_EfxAnimNumberFem);

    if (number == 0)
        return;
    proc = Proc_Start(ProcScr_EfxAnimNumberFem, PROC_TREE_3);
    proc->anim = anim;
    proc->number = number;
    proc->slot = other ? !other->slot : 0;   /* the damage and the drain show at once: two slots */
    SetupEfxAnimNumberGfxFem(number, proc->slot);
}

/* heal (efxHPBarLive) and drain (efxHPBarResire, once the drainer's HP is known) */
static void EfxHpBarLiveNumberFem(struct ProcEfxHpBar * proc)
{
    NewEfxAnimNumberFem(proc->anim_this, proc->next - proc->this);
}

static void EfxHpBarResireNumberFem(struct ProcEfxHpBar * proc)
{
    if (++proc->timer < 4)
        return;
    NewEfxAnimNumberFem(proc->anim_main_other, proc->next - proc->this);
    proc->timer = 0;
    Proc_Break(proc);
}

"""


def apply(decomp_dir: Path, files: dict) -> dict:
    def current(rel: str) -> str:
        return files[rel] if rel in files else (decomp_dir / rel).read_text(encoding="utf-8")

    files[IMAGE] = image_png()
    data = current(DATA_FILE)
    files[DATA_FILE] = data.rstrip("\n") + (
        "\n\n@ FE Maker (ticket 169): damage and heal numbers (C-SkillSys's Img_EfxAnimNumber)\n"
        "\t.align 2\n\t.global Img_EfxAnimNumberFem\nImg_EfxAnimNumberFem:\n"
        f"\t.incbin \"{IMAGE[:-4]}.4bpp\"\n"
        "\t.align 2\n\t.global Pal_EfxAnimNumberFem\nPal_EfxAnimNumberFem:\n"
        f"\t.incbin \"{IMAGE[:-4]}.gbapal\"\n")
    header = current(HEADER)
    files[HEADER] = _replace(header, "struct ProcEfxHpBar {\n",
                             "void NewEfxAnimNumberFem(struct Anim * anim, int number); /* FE Maker (ticket 169) */\n\n"
                             "struct ProcEfxHpBar {\n", HEADER)
    bar = current(HPBAR_FILE)
    bar = _replace(bar, "CONST_DATA struct ProcCmd ProcScr_efxHPBar[] = {\n",
                   CODE % {"sprites": _sprites(), "script": _script()} + "CONST_DATA struct ProcCmd ProcScr_efxHPBar[] = {\n",
                   HPBAR_FILE)
    bar = _replace(bar, "    PROC_REPEAT(EfxHpBarResire_SetAnotherSide),\n",
                   "    PROC_REPEAT(EfxHpBarResire_SetAnotherSide),\n    PROC_REPEAT(EfxHpBarResireNumberFem),\n", HPBAR_FILE)
    files[HPBAR_FILE] = _replace(bar, "    PROC_NAME(\"efxHPBarLive\"),\n",
                                 "    PROC_NAME(\"efxHPBarLive\"),\n    PROC_YIELD,\n    PROC_CALL(EfxHpBarLiveNumberFem),\n",
                                 HPBAR_FILE)
    flash = _replace(current(FLASH_FILE), '#include "bmlib.h"\n', '#include "bmlib.h"\n#include "bmbattle.h"\n', FLASH_FILE)
    files[FLASH_FILE] = _replace(flash,"    /* ? */\n    if (_duartion == 0)\n        Proc_Break(proc);\n}\n", (
        "    /* FE Maker (ticket 169): the damage, as C-SkillSys (the HP bar flashes on every hit with damage) */\n"
        "    if (anim->nextRoundId > 0)\n"
        "        NewEfxAnimNumberFem(anim, -gBattleHitArray[anim->nextRoundId - 1].hpChange);\n\n"
        "    /* ? */\n    if (_duartion == 0)\n        Proc_Break(proc);\n}\n"), FLASH_FILE)
    return files
