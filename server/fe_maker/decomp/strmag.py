"""Strength and Magic split (ticket 27, game option strMagSplit; docs/separation-force-magie.md).

The game has one stat, `pow`, for weapons and magic. With the option, a unit also has Magic, in its spare byte `_u3A`
(where FEBuilder's Skill System keeps it too): it follows the unit through every copy the game makes (battle units,
recruits, the prep screen's sort). Magic counts for tomes and for magic swords at range (`IA_MAGIC`,
`IA_MAGICDAMAGE`), for staves (heal amount, accuracy, range); Strength for the rest.

Data: a table per class (base, growth, maximum, promotion gain) and per character (base, growth), written from the
project's `bases`/`growths`/`maxes`/`promotionGains` "mag" values; without one, a class with a magic weapon rank (or a
character of such a class) takes its Strength figures, any other unit starts at 0 (MAGIC_DEFAULTS).

Ticket 164's temporary bonuses also lived in `_u3A`: with the split they move to a table by unit number, in IWRAM.
Saves: the game's packed units have no free bit; each save slot's Magic bytes go in the save memory's bonus-map zone
(SRAM_OFFSET_XMAP, read by the game only behind its own header), tied to the save by its time.
"""

from __future__ import annotations

import re
from pathlib import Path

MAGIC_RANKS = ("staff", "anima", "light", "dark")
NON_MAGIC_GROWTH = 5   # a generic's Magic growth in a class without magic


class StrMagError(Exception):
    pass


def is_magic_class(cls: dict) -> bool:
    return any(rank in MAGIC_RANKS for rank in (cls.get("weaponRanks") or {}))


def class_magic(cls: dict) -> tuple[int, int, int, int]:
    """(base, growth, maximum, promotion gain) of a class's Magic."""
    magic = is_magic_class(cls)
    bases, growths = cls.get("bases") or {}, cls.get("growths") or {}
    maxes, gains = cls.get("maxes") or {}, cls.get("promotionGains") or {}
    default = (bases.get("pow", 0), growths.get("pow", 0), maxes.get("pow", 20), gains.get("pow", 0)) if magic else \
        (0, NON_MAGIC_GROWTH, maxes.get("pow", 20), 0)
    return (int(bases.get("mag", default[0])), int(growths.get("mag", default[1])),
            int(maxes.get("mag", default[2])), int(gains.get("mag", default[3])))


def character_magic(character: dict, classes: dict[str, dict]) -> tuple[int, int]:
    """(base, growth) of a character's Magic (added to its class's base, as the other stats)."""
    bases, growths = character.get("bases") or {}, character.get("growths") or {}
    magic = is_magic_class(classes.get(character.get("class", ""), {}))
    default = (bases.get("pow", 0), growths.get("pow", 0)) if magic else (0, growths.get("pow", 0) // 4)
    return int(bases.get("mag", default[0])), int(growths.get("mag", default[1]))


def _byte(value: int) -> str:
    return str(value & 0xFF)


def _numbers(decomp_dir: Path, header: str) -> dict[str, int]:
    text = (decomp_dir / "include/constants" / header).read_text(encoding="utf-8")
    return {name: int(value, 0) for name, value in re.findall(r"\b([A-Z]\w+)\s*=\s*(0x[0-9A-Fa-f]+|\d+)", text)}


def _number(record_id: str, constants: dict[str, int], new_prefix: str) -> int | None:
    """Table entry of a class or character: its constant, a project's new entry, or a free entry's number."""
    if record_id.startswith(new_prefix):
        return int(record_id.removeprefix(new_prefix), 16)
    if record_id.lower().startswith("0x"):
        return int(record_id, 16)
    return constants.get(record_id)


def _rows(records: list[dict], numbers: dict[str, int], new_prefix: str, values) -> str:
    """One row per entry: a named record wins over a free entry's placeholder."""
    rows: dict[int, tuple[bool, str]] = {}
    for record in records:
        number = _number(record["id"], numbers, new_prefix)
        if number is None or not 0 <= number < 0x100:
            continue
        named = not record["id"].lower().startswith("0x")
        if number in rows and rows[number][0] and not named:
            continue
        rows[number] = (named, f"    [0x{number:02X}] = {{ {', '.join(_byte(v) for v in values(record))} }},\n")
    return "".join(row for _, (_, row) in sorted(rows.items()))


def _tables(decomp_dir: Path, characters: list[dict], classes: list[dict]) -> str:
    by_id = {c["id"]: c for c in classes}
    class_rows = _rows(classes, _numbers(decomp_dir, "classes.h"), "CLASS_NEW_", class_magic)
    char_rows = _rows(characters, _numbers(decomp_dir, "characters.h"), "CHARACTER_NEW_",
                      lambda c: character_magic(c, by_id))
    return ("/* FE Maker: Magic of each class (base, growth, maximum, promotion gain) and character (base, growth),\n"
            "   ticket 27 */\n"
            f"const u8 gClassMagFem[0x100][4] = {{\n{class_rows}}};\n\n"
            f"const u8 gCharacterMagFem[0x100][2] = {{\n{char_rows}}};\n\n")


HEADER = """
/* FE Maker: Magic, split from Strength (ticket 27), in the unit's spare byte _u3A */
#define UNIT_MAG_FEM(aUnit) (*(s8 *) &(aUnit)->_u3A)
#define UNIT_MAG_MAX_FEM(aUnit) (gClassMagFem[(aUnit)->pClassData->number][2])
extern const u8 gClassMagFem[0x100][4];     /* base, growth, maximum, promotion gain */
extern const u8 gCharacterMagFem[0x100][2]; /* base (signed), growth */
int GetUnitMagicFem(struct Unit* unit);
void ApplyPromotionMagicFem(struct Unit* unit, int classId);

"""
# ticket 164's counters leave _u3A for a table by unit number (IWRAM, sym_iwram.txt)
TEMP_TABLE = ("extern u32 gTempBonusesFem[0xC0];\n"
              "#define TEMP_BONUSES_FEM(aUnit) (gTempBonusesFem[(u8) (aUnit)->index])\n")
# 7 counters there: Magic's is the 7th (gamedata.TEMP_STATS)
TEMP_TABLE_SET = "#define SET_TEMP_BONUSES_FEM(aUnit, v) (gTempBonusesFem[(u8) (aUnit)->index] = (v) & 0xFFFFFFF)\n"
# the suspend save's 4th byte of each unit's counters (Magic), beside its 3 bytes (gamedata.TEMP_BONUS_SAVE)
TEMP_MAGIC_SAVE = ("#define TEMP_MAG_SAVE_FEM(slot) ((u8 *) CART_SRAM + SRAM_OFFSET_XMAP + 0x400"
                   " + ((slot) - SAVE_ID_SUSPEND) * 0x10)\n\n")

UNIT_FUNCTIONS = """int GetUnitMagicFem(struct Unit* unit) {
    int item = GetUnitEquippedWeapon(unit);
    const struct ItemStatBonuses* bonuses = item ? GetItemStatBonuses(item) : NULL;

    return UNIT_MAG_FEM(unit) + (bonuses ? bonuses->magBonus : 0);
}

/* FE Maker: Magic gained when the unit becomes class classId, up to that class's maximum */
void ApplyPromotionMagicFem(struct Unit* unit, int classId) {
    int mag = UNIT_MAG_FEM(unit) + gClassMagFem[classId][3];

    UNIT_MAG_FEM(unit) = mag > gClassMagFem[classId][2] ? gClassMagFem[classId][2] : mag;
}

"""

BATTLE_HELPER = """
/* FE Maker: Magic for magic weapons (tomes, magic swords at range), Strength otherwise (ticket 27) */
#define BATTLE_ATTACK_STAT_FEM(aBu) \\
    (((aBu)->weaponAttributes & (IA_MAGIC | IA_MAGICDAMAGE)) ? UNIT_MAG_FEM(&(aBu)->unit) : (aBu)->unit.pow)

"""

# Save memory: per slot (GAME0..2, SUSPEND, SUSPEND_ALT), the save time then the units' Magic in their save order
SAVE = """
/* FE Maker: the units' Magic, which the packed units have no room for, in the bonus-map zone of the save memory
   (after its header, which the game checks): per save slot, the save time then one byte per saved unit. */
#define MAG_SAVE_FEM(slot) ((u8 *) CART_SRAM + SRAM_OFFSET_XMAP + 0x100 + (slot) * 0x80)
#define MAG_SAVE_UNITS_FEM (UNIT_SAVE_AMOUNT_BLUE + UNIT_SAVE_AMOUNT_RED + UNIT_SAVE_AMOUNT_GREEN)

static struct Unit* MagSavedUnitFem(int i)
{
    if (i < UNIT_SAVE_AMOUNT_BLUE)
        return &gUnitArrayBlue[i];
    if (i < UNIT_SAVE_AMOUNT_BLUE + UNIT_SAVE_AMOUNT_RED)
        return &gUnitArrayRed[i - UNIT_SAVE_AMOUNT_BLUE];
    return &gUnitArrayGreen[i - UNIT_SAVE_AMOUNT_BLUE - UNIT_SAVE_AMOUNT_RED];
}

static void WriteMagicFem(int slot, int count)
{
    u8 buf[4 + MAG_SAVE_UNITS_FEM];
    u32 time = gPlaySt.time_saved;
    int i;

    buf[0] = time;
    buf[1] = time >> 8;
    buf[2] = time >> 16;
    buf[3] = time >> 24;
    for (i = 0; i < MAG_SAVE_UNITS_FEM; i++)
        buf[4 + i] = i < count ? MagSavedUnitFem(i)->_u3A : 0;
    WriteAndVerifySramFast(buf, MAG_SAVE_FEM(slot), sizeof(buf));
}

/* A save without its Magic bytes (made before the option): Magic estimated from the data, as an average level up */
static void EstimateMagicFem(struct Unit* unit)
{
    const struct CharacterData* character = unit->pCharacterData;
    int levels = unit->level - character->baseLevel;
    int mag = (s8) gCharacterMagFem[character->number][0] + gClassMagFem[character->defaultClass][0];

    if (unit->pClassData->number != character->defaultClass) {
        mag += gClassMagFem[unit->pClassData->number][3];
        levels = unit->level - 1 + 20 - character->baseLevel;
    }
    if (levels > 0)
        mag += levels * gCharacterMagFem[character->number][1] / 100;
    if (mag > UNIT_MAG_MAX_FEM(unit))
        mag = UNIT_MAG_MAX_FEM(unit);
    UNIT_MAG_FEM(unit) = mag < 0 ? 0 : mag;
}

static void ReadMagicFem(int slot, int count)
{
    u8 buf[4 + MAG_SAVE_UNITS_FEM];
    int i, known;

    ReadSramFast(MAG_SAVE_FEM(slot), buf, sizeof(buf));
    known = (buf[0] | buf[1] << 8 | buf[2] << 16 | (u32) buf[3] << 24) == gPlaySt.time_saved;
    for (i = 0; i < count; i++) {
        struct Unit* unit = MagSavedUnitFem(i);

        if (!unit->pCharacterData)
            continue;
        if (known)
            unit->_u3A = buf[4 + i];
        else
            EstimateMagicFem(unit);
    }
}

static void CopyMagicFem(int src, int dest)
{
    u8 buf[4 + MAG_SAVE_UNITS_FEM];

    ReadSramFast(MAG_SAVE_FEM(src), buf, sizeof(buf));
    WriteAndVerifySramFast(buf, MAG_SAVE_FEM(dest), sizeof(buf));
}

"""


def _patch(files: dict, decomp_dir: Path, rel: str, pairs: list[tuple[str, str]]) -> None:
    text = files[rel] if rel in files else (decomp_dir / rel).read_text(encoding="utf-8")
    for old, new in pairs:
        if old not in text:
            raise StrMagError(f"Strength/Magic split: {rel} does not match ({old.strip().splitlines()[0]})")
        text = text.replace(old, new, 1)
    files[rel] = text


def _getter_body(text: str, name: str) -> str:
    start = text.index(f"inline int GetUnit{name}(struct Unit* unit) {{")
    return text[start:text.index("\n}\n", start) + 3]


def _status_screen(files: dict, decomp_dir: Path) -> None:
    """Page 1 of the status screen: Str, then a new Mag line, Skl to Res one line lower (rows 1 to 13 of the left
    column, as the Skill System does); its own bar (number 8) and its R help between Str and Skl."""
    rel = "src/statscreen.c"
    text = files[rel] if rel in files else (decomp_dir / rel).read_text(encoding="utf-8")
    for row in (11, 9, 7, 5, 3):   # labels of Skl to Res, from the bottom
        old = f"gUiTmScratchA + TILEMAP_INDEX(1, {row}),"
        new = f"gUiTmScratchA + TILEMAP_INDEX(1, {row + 2}),"
        if old not in text:
            raise StrMagError("Strength/Magic split: src/statscreen.c does not match (labels)")
        text = text.replace(old, new, 1)
    for num, row in ((5, 11), (4, 9), (3, 7), (2, 5), (1, 3)):
        old = f"    DrawStatWithBar({num}, 5, {row},\n"
        if old not in text:
            raise StrMagError("Strength/Magic split: src/statscreen.c does not match (bars)")
        text = text.replace(old, f"    DrawStatWithBar({num}, 5, {row + 2},\n", 1)
    label_start = text.index("    // Displaying str/mag label\n")
    label_end = text.index("    // displaying str/mag stat value\n")
    text = text[:label_start] + (
        "    /* FE Maker: Str and Mag, each its own line (ticket 27) */\n"
        "    PutDrawText(\n        &gStatScreen.text[STATSCREEN_TEXT_POWLABEL],\n"
        "        gUiTmScratchA + TILEMAP_INDEX(1, 1),\n        TEXT_COLOR_SYSTEM_GOLD, 0, 0,\n"
        "        GetStringFromIndex(MSG_4FE)); // Str\n\n"
        "    PutDrawText(\n        &gStatScreen.text[STATSCREEN_TEXT_UNUSUED],\n"
        "        gUiTmScratchA + TILEMAP_INDEX(1, 3),\n        TEXT_COLOR_SYSTEM_GOLD, 0, 0,\n"
        "        GetStringFromIndex(MSG_4FF)); // Mag\n\n"
        "    DrawStatWithBar(8, 5, 3,\n        UNIT_MAG_FEM(gStatScreen.unit),\n"
        "        GetUnitMagicFem(gStatScreen.unit),\n        UNIT_MAG_MAX_FEM(gStatScreen.unit));\n\n"
    ) + text[label_end:]
    # R help: Str always Strength's text, Magic's below it, the rest one line lower
    pairs = [
        ("    102, 24, MSG_546, NULL, HbPopulate_SSPower,\n", "    102, 24, MSG_546, NULL, NULL,\n"),
        ("    NULL, &sHelpInfo_Ss0Skl, &sHelpInfo_Char, &sHelpInfo_Ss0Mov,\n",
         "    NULL, &sHelpInfo_Ss0MagFem, &sHelpInfo_Char, &sHelpInfo_Ss0Mov,\n"),
        ("DECL_INFO gHelpInfo_Ss0Pow =\n", "extern DECL_INFO sHelpInfo_Ss0MagFem;\n\nDECL_INFO gHelpInfo_Ss0Pow =\n"),
        ("DECL_INFO sHelpInfo_Ss0Skl =\n{\n    &gHelpInfo_Ss0Pow,",
         "/* FE Maker: Magic (ticket 27) */\nDECL_INFO sHelpInfo_Ss0MagFem =\n{\n"
         "    &gHelpInfo_Ss0Pow, &sHelpInfo_Ss0Skl, &sHelpInfo_Char, &sHelpInfo_Ss0Con,\n    102, 40, MSG_547,\n};\n\n"
         "DECL_INFO sHelpInfo_Ss0Skl =\n{\n    &sHelpInfo_Ss0MagFem,"),
        ("    105, 40, MSG_548,\n", "    105, 56, MSG_548,\n"),
        ("    102, 56, MSG_549,\n", "    102, 72, MSG_549,\n"),
        ("    102, 72, MSG_54A,\n", "    102, 88, MSG_54A,\n"),
        ("    102, 88, MSG_54B,\n", "    102, 104, MSG_54B,\n"),
        ("    102, 104, MSG_54C,\n", "    102, 120, MSG_54C,\n"),
    ]
    # the battles / wins / losses line (after a first playthrough) one row lower, below Res
    pairs += [("gUiTmScratchA + TILEMAP_INDEX(3, 14));", "gUiTmScratchA + TILEMAP_INDEX(3, 15));")] + [
        (f"TILEMAP_INDEX({x} + CountDigits(stats->{field}), 14)", f"TILEMAP_INDEX({x} + CountDigits(stats->{field}), 15)")
        for x, field in ((3, "battleAmt"), (7, "winAmt"), (11, "lossAmt"))]
    for old, new in pairs:
        if old not in text:
            raise StrMagError(f"Strength/Magic split: src/statscreen.c does not match ({old.strip()})")
        text = text.replace(old, new, 1)
    files[rel] = text


def _unit_list(files: dict, decomp_dir: Path) -> None:
    """Page 2 of the unit list: Str, Mag, Skl, Spd, Lck, Def, Res (Mag takes Affin's place, which the status screen
    still shows; the page has no room for 8 numbers); its sort by Magic in place of the sort by affinity."""
    rel = "src/unitlistscreen.c"
    text = files[rel] if rel in files else (decomp_dir / rel).read_text(encoding="utf-8")
    start = text.index("        case UNITLIST_PAGE_2:\n            PutNumberOrBlank(")
    end = text.index("            break;\n", start)
    columns = [("UNIT_POW_MAX(gSortedUnits[unitNum]->unit) == gSortedUnits[unitNum]->unit->pow", "GetUnitPower"),
               ("UNIT_MAG_MAX_FEM(gSortedUnits[unitNum]->unit) == UNIT_MAG_FEM(gSortedUnits[unitNum]->unit)",
                "GetUnitMagicFem"),
               ("UNIT_SKL_MAX(gSortedUnits[unitNum]->unit) == gSortedUnits[unitNum]->unit->skl", "GetUnitSkill"),
               ("UNIT_SPD_MAX(gSortedUnits[unitNum]->unit) == gSortedUnits[unitNum]->unit->spd", "GetUnitSpeed"),
               ("UNIT_LCK_MAX(gSortedUnits[unitNum]->unit) == gSortedUnits[unitNum]->unit->lck", "GetUnitLuck"),
               ("UNIT_DEF_MAX(gSortedUnits[unitNum]->unit) == gSortedUnits[unitNum]->unit->def", "GetUnitDefense"),
               ("UNIT_RES_MAX(gSortedUnits[unitNum]->unit) == gSortedUnits[unitNum]->unit->res", "GetUnitResistance")]
    body = "        case UNITLIST_PAGE_2: /* FE Maker: Mag after Str (ticket 27) */\n" + "".join(
        f"            PutNumberOrBlank(\n                tm + y * 0x20 + {9 + 3 * n},\n"
        f"                {at_max} ? 4 : 2,\n                {getter}(gSortedUnits[unitNum]->unit));\n"
        for n, (at_max, getter) in enumerate(columns)) + "\n"
    text = text[:start] + body + text[end:]
    affinity_sort = ("            #define KEY(i) (GetUnitAffinityIcon(gSortedUnits[(i)]->unit))\n"
                     "            SORT_MAIN(SORT_CORE_KEY(KEY, <, SWAP), SORT_CORE_KEY(KEY, >, SWAP))\n"
                     "            #undef KEY\n")
    if text.count(affinity_sort) != 1:
        raise StrMagError("Strength/Magic split: src/unitlistscreen.c does not match (sort)")
    text = text.replace(affinity_sort, "            SORT_BY_FUNC(GetUnitMagicFem) /* FE Maker: Magic (ticket 27) */\n"
                                       "            break;\n")
    # the column headers: Str (no longer S/M) and its help, Mag (sort key 13, Affin's) after it, the others one column
    # (24 pixels) further
    page = text.index("    [UNITLIST_PAGE_2] =\n")
    page_end = text.index("    [UNITLIST_PAGE_3] =\n")
    fields = text[page:page_end]
    entry = ("        {{\n            .sortKey = UNITLIST_SORTKEY_{key},\n            .labelString = 0x{label:08X},\n"
             "            .xColumn = {x},\n            .helpTextId = 0x{help:08X},\n        }},\n")
    old = [(7, 0x4EB, 64, 0x6EA), (8, 0x4EC, 91, 0x548), (9, 0x4ED, 113, 0x549), (10, 0x4EE, 136, 0x54A),
           (11, 0x4EF, 161, 0x54B), (12, 0x4F0, 184, 0x54C), (13, 0x4F1, 203, 0x551)]
    new = [(7, 0x4FE, 64, 0x546), (13, 0x4FF, 88, 0x547), (8, 0x4EC, 115, 0x548), (9, 0x4ED, 137, 0x549),
           (10, 0x4EE, 160, 0x54A), (11, 0x4EF, 185, 0x54B), (12, 0x4F0, 208, 0x54C)]
    old_text = "".join(entry.format(key=k, label=lab, x=x, help=h) for k, lab, x, h in old)
    if fields.count(old_text) != 1:
        raise StrMagError("Strength/Magic split: src/unitlistscreen.c does not match (columns)")
    fields = fields.replace(old_text, "".join(entry.format(key=k, label=lab, x=x, help=h) for k, lab, x, h in new))
    files[rel] = text[:page] + fields + text[page_end:]


def _level_up_screens(files: dict, decomp_dir: Path) -> None:
    """The level up boxes (battle, map, a booster used in the prep screen) have 8 lines: Con, which levels do not
    raise, gives its line to Mag (as in the Skill System); Str is always Str. Ticket 165: HP, Str, Mag, Skl on the
    left, Spd, Lck, Def, Res on the right (Con's slot, holding Magic, moves after Str)."""
    def patch(rel: str, pairs: list[tuple[str, str]], every: bool = False) -> None:
        text = files[rel] if rel in files else (decomp_dir / rel).read_text(encoding="utf-8")
        for old, new in pairs:
            if old not in text:
                raise StrMagError(f"Strength/Magic split: {rel} does not match ({old.strip()})")
            text = text.replace(old, new) if every else text.replace(old, new, 1)
        files[rel] = text

    patch("src/banim-ekrlvup.c", [
        # the labels: Hp, Str, Mag (Con's slot, ticket 165), then Skl to Res
        ("    &gMid_Res,\n    &gMid_Con\n", "    &gMid_Res\n"),
        ("    &gMid_Hp,\n    &gMid_Mag,\n", "    &gMid_Hp,\n    &gMid_Str,\n"),
        ("    &gMid_Str,\n    &gMid_Skl,\n", "    &gMid_Str,\n    &gMid_Mag,\n    &gMid_Skl,\n"),
        ("unit->pClassData->baseCon + unit->pCharacterData->baseCon + bunit2->changeCon;",
         "UNIT_MAG_FEM(unit) + bunit2->changeMagFem;"),
        ("bunit->unit.pClassData->baseCon + bunit->unit.pCharacterData->baseCon;", "UNIT_MAG_FEM(&bunit->unit);")],
        every=True)
    patch("src/banim-ekrlvup.c", [
        ("[EKRLVUP_STAT_CON] = unit->pClassData->baseCon + unit->pCharacterData->baseCon;",
         "[EKRLVUP_STAT_CON] = UNIT_MAG_FEM(unit);")], every=True)
    # the battle box draws its slots in order (sEfxLvupPartsPos: 4 on the left, then 4 on the right): Con's slot
    # (Magic) after Str's
    patch("include/ekrlevelup.h", [(
        "    EKRLVUP_STAT_POW,\n    EKRLVUP_STAT_SKL,\n    EKRLVUP_STAT_SPD,\n    EKRLVUP_STAT_LCK,\n"
        "    EKRLVUP_STAT_DEF,\n    EKRLVUP_STAT_RES,\n    EKRLVUP_STAT_CON,\n",
        "    EKRLVUP_STAT_POW,\n    EKRLVUP_STAT_CON, /* FE Maker: Magic (ticket 27) */\n    EKRLVUP_STAT_SKL,\n"
        "    EKRLVUP_STAT_SPD,\n    EKRLVUP_STAT_LCK,\n    EKRLVUP_STAT_DEF,\n    EKRLVUP_STAT_RES,\n")])
    # the map box places each line itself (x, y in tiles)
    places = [("Skl", (1, 8), (1, 10)), ("Spd", (1, 10), (9, 4)), ("Lck", (9, 4), (9, 6)), ("Def", (9, 6), (9, 8)),
              ("Res", (9, 8), (9, 10)), ("Con", (9, 10), (1, 8))]
    patch("src/mapanim_lvupfx.c", [
        (f"        .x = {x}, .y = {y},\n        .msg = {{ &gMid_{m}, &gMid_{m} }},\n",
         f"        .x = {nx}, .y = {ny},\n        .msg = {{ &gMid_{m}, &gMid_{m} }},\n")
        for m, (x, y), (nx, ny) in places])
    patch("src/mapanim_lvupfx.c", [
        ("        return gManimSt.actor[actor_id].bu->changeCon;\n",
         "        return gManimSt.actor[actor_id].bu->changeMagFem;\n"),
        ("            return UNIT_CON_BASE(unit);\n", "            return UNIT_MAG_FEM(unit);\n"),
        ("        .msg = { &gMid_Str, &gMid_Mag },\n", "        .msg = { &gMid_Str, &gMid_Str },\n"),
        ("        .msg = { &gMid_Con, &gMid_Con },\n", "        .msg = { &gMid_Mag, &gMid_Mag },\n")])
    patch("src/prep_itemusemind.c", [
        ("    proc->status_pre[EKRLVUP_STAT_CON] = UNIT_CON(parent->unit);\n",
         "    proc->status_pre[EKRLVUP_STAT_CON] = GetUnitMagicFem(parent->unit);\n"),
        ("    proc->status_pst[EKRLVUP_STAT_CON] = UNIT_CON(parent->unit);\n",
         "    proc->status_pst[EKRLVUP_STAT_CON] = GetUnitMagicFem(parent->unit);\n")])


def apply(decomp_dir: Path, files: dict, characters: list[dict], classes: list[dict]) -> dict:
    """Write the split into `files` (decomp-relative path -> content)."""
    files = dict(files)

    def patch(rel: str, pairs: list[tuple[str, str]]) -> None:
        _patch(files, decomp_dir, rel, pairs)

    def text(rel: str) -> str:
        return files[rel] if rel in files else (decomp_dir / rel).read_text(encoding="utf-8")

    # header: Magic, and ticket 164's counters out of _u3A
    patch("include/bmunit.h", [("\n#endif // GUARD_BM_UNIT_H", HEADER + "#endif // GUARD_BM_UNIT_H")])
    unit_h = text("include/bmunit.h")
    temp_table = "#define TEMP_BONUSES_FEM(aUnit) ((aUnit)->_u3A" in unit_h
    if temp_table:
        lines = unit_h.splitlines(keepends=True)
        get = next(line for line in lines if line.startswith("#define TEMP_BONUSES_FEM("))
        put = next(line for line in lines if line.startswith("#define SET_TEMP_BONUSES_FEM("))
        patch("include/bmunit.h", [(get, TEMP_TABLE), (put, TEMP_TABLE_SET)])
        patch("src/bmsave.c", [
            ("            entry[1] = unit->_u3A;\n            entry[2] = unit->_u3B;\n            entry[3] = unit->_u47;\n",
             "            entry[1] = TEMP_BONUSES_FEM(unit);\n            entry[2] = TEMP_BONUSES_FEM(unit) >> 8;\n"
             "            entry[3] = TEMP_BONUSES_FEM(unit) >> 16;\n"),
            ("            unit->_u3A = entry[1];\n            unit->_u3B = entry[2];\n            unit->_u47 = entry[3];\n",
             "            SET_TEMP_BONUSES_FEM(unit, entry[1] | entry[2] << 8 | entry[3] << 16 | (u32) top[i] << 24);\n"),
            # Magic's counter (the 4th byte) in the bonus-map zone, after the Magic bytes
            ("static void WriteTempBonusesFem(int slot)\n{\n    u8 buf[46];\n",
             TEMP_MAGIC_SAVE + "static void WriteTempBonusesFem(int slot)\n{\n    u8 buf[46];\n    u8 top[10];\n"),
            ("    for (i = 0; i < 46; i++)\n        buf[i] = 0;\n",
             "    for (i = 0; i < 46; i++)\n        buf[i] = 0;\n    for (i = 0; i < 10; i++)\n        top[i] = 0;\n"),
            ("            entry[0] = i;\n",
             "            top[count - 1] = TEMP_BONUSES_FEM(unit) >> 24;\n            entry[0] = i;\n"),
            ("    WriteAndVerifySramFast(buf, TEMP_BONUS_SAVE_FEM(slot), sizeof(buf));\n",
             "    WriteAndVerifySramFast(buf, TEMP_BONUS_SAVE_FEM(slot), sizeof(buf));\n"
             "    WriteAndVerifySramFast(top, TEMP_MAG_SAVE_FEM(slot), sizeof(top));\n"),
            ("static void ReadTempBonusesFem(int slot)\n{\n    u8 buf[46];\n",
             "static void ReadTempBonusesFem(int slot)\n{\n    u8 buf[46];\n    u8 top[10];\n"),
            ("    ReadSramFast(TEMP_BONUS_SAVE_FEM(slot), buf, sizeof(buf));\n",
             "    ReadSramFast(TEMP_BONUS_SAVE_FEM(slot), buf, sizeof(buf));\n"
             "    ReadSramFast(TEMP_MAG_SAVE_FEM(slot), top, sizeof(top));\n")])
        # Magic's counter, the 7th: lowered each turn, combined with a drink's (and read by GetUnitMagicFem)
        loop = "for (n = 0; n < 6; n++) {"
        for rel in ("include/bmunit.h", "src/bmunit.c"):
            if text(rel).count(loop) != 1:
                raise StrMagError(f"Strength/Magic split: {rel} does not match (temporary bonuses)")
            files[rel] = text(rel).replace(loop, "for (n = 0; n < 7; n++) {")
    patch("include/bmbattle.h", [
        ("    /* 7E */ s8 hasItemEffectTarget;\n    /* 7F */ /* pad */\n",
         "    /* 7E */ s8 hasItemEffectTarget;\n    /* 7F */ s8 changeMagFem; /* FE Maker: Magic gained (ticket 27) */\n"),
        ("\n#endif // GUARD_BMBATTLE_H", BATTLE_HELPER + "#endif // GUARD_BMBATTLE_H")])
    iwram = "sym_iwram.txt"
    iwram_end = ". = ALIGN(4); *libc.a:sbrkr.o(COMMON);"
    if temp_table:
        patch(iwram, [(iwram_end, iwram_end + "\n\n/* FE Maker: temporary bonuses by unit number, and by place in the"
                       " unit stack of the prep screen's sort (ticket 27) */\n"
                       ". = ALIGN(4); gTempBonusesFem = .;\n. = . + 0x300;\n"
                       ". = ALIGN(4); gTempStackFem = .;\n. = . + 0x100;")])
        # the prep screen sorts the army through a stack of copies: the bonuses follow each unit to its new number
        patch("src/bmusort.c", [
            ('#include "variables.h"\n', '#include "variables.h"\n\nextern u32 gTempStackFem[0x40];\n'),
            ("    CopyUnit(unit, sUnitStackTop);\n    sUnitStackTop->index = sUnitStackSize;\n",
             "    CopyUnit(unit, sUnitStackTop);\n    gTempStackFem[sUnitStackSize & 0x3F] = TEMP_BONUSES_FEM(unit);\n"
             "    sUnitStackTop->index = sUnitStackSize;\n")])
        stack_load = ("    CpuCopy16(sUnitStackBase, gUnitArrayBlue, (void*)sUnitStackTop - (void*)sUnitStackBase);\n")
        sort = text("src/bmusort.c")
        if sort.count(stack_load) != 2:
            raise StrMagError("Strength/Magic split: src/bmusort.c does not match (unit stack)")
        files["src/bmusort.c"] = sort.replace(stack_load, stack_load + (
            "    for (i = 1; i < sUnitStackSize; ++i)\n"
            "        SET_TEMP_BONUSES_FEM(&gUnitArrayBlue[i - 1], gTempStackFem[i & 0x3F]);\n"))

    # the unit: data, loading, automatic levels, caps, copies
    unit_functions = UNIT_FUNCTIONS if not temp_table else UNIT_FUNCTIONS.replace(
        "    return UNIT_MAG_FEM(unit) + (bonuses ? bonuses->magBonus : 0);",
        "    return TempStatFem(UNIT_MAG_FEM(unit) + (bonuses ? bonuses->magBonus : 0) + TEMP_BONUS_FEM(unit, 6));")
    bmunit = text("src/bmunit.c")
    power = _getter_body(bmunit, "Power")
    unit_pairs = [
        (power, _tables(decomp_dir, characters, classes) + unit_functions + power),
        ("    unit->lck   = character->baseLck;\n",
         "    unit->lck   = character->baseLck;\n"
         "    UNIT_MAG_FEM(unit) = (s8) gCharacterMagFem[character->number][0]\n"
         "        + gClassMagFem[unit->pClassData->number][0];\n"),
        ("        unit->lck   += GetAutoleveledStatIncrease(unit->pClassData->growthLck, levelCount);\n",
         "        unit->lck   += GetAutoleveledStatIncrease(unit->pClassData->growthLck, levelCount);\n"
         "        UNIT_MAG_FEM(unit) += GetAutoleveledStatIncrease(gClassMagFem[unit->pClassData->number][1],"
         " levelCount);\n"),
        ("        unit->lck   = unit->pCharacterData->baseLck;\n",
         "        unit->lck   = unit->pCharacterData->baseLck;\n"
         "        UNIT_MAG_FEM(unit) = (s8) gCharacterMagFem[unit->pCharacterData->number][0]\n"
         "            + gClassMagFem[unit->pClassData->number][0];\n"),
        ("    if (unit->pow > UNIT_POW_MAX(unit))\n        unit->pow = UNIT_POW_MAX(unit);\n",
         "    if (unit->pow > UNIT_POW_MAX(unit))\n        unit->pow = UNIT_POW_MAX(unit);\n\n"
         "    if (UNIT_MAG_FEM(unit) > UNIT_MAG_MAX_FEM(unit))\n        UNIT_MAG_FEM(unit) = UNIT_MAG_MAX_FEM(unit);\n"),
        ("        int result = GetUnitPower(unit) / 2;\n", "        int result = GetUnitMagicFem(unit) / 2;\n"),
    ]
    if temp_table:
        unit_pairs += [
            ("    u8 id = unit->index;\n    CpuFill16(0, unit, sizeof(struct Unit));\n",
             "    u8 id = unit->index;\n    if (GetUnit(id) == unit)\n        SET_TEMP_BONUSES_FEM(unit, 0);\n"
             "    CpuFill16(0, unit, sizeof(struct Unit));\n"),
            ("    u8 id = to->index;\n    memcpy(to, from, sizeof(struct Unit));\n",
             "    u8 id = to->index;\n    if (GetUnit(id) == to && GetUnit(from->index) == from)\n"
             "        SET_TEMP_BONUSES_FEM(to, TEMP_BONUSES_FEM(from));\n"
             "    memcpy(to, from, sizeof(struct Unit));\n")]
    patch("src/bmunit.c", unit_pairs)
    # the remaining part of the autolevel penalty's levels go through UnitAutolevelCore: nothing more to do there

    # battle: the stat of the attack, level ups, promotions, caps, the unit updated after the battle
    patch("src/bmbattle.c", [
        ("        gBattleActor.battleAttack -= gBattleActor.unit.pow / 2;\n",
         "        gBattleActor.battleAttack -= BATTLE_ATTACK_STAT_FEM(&gBattleActor) / 2;\n"),
        ("    bu->unit.pow = GetUnitPower(unit);\n",
         "    bu->unit.pow = GetUnitPower(unit);\n    UNIT_MAG_FEM(&bu->unit) = GetUnitMagicFem(unit);\n"),
        ("    bu->changePow = 0;\n", "    bu->changePow = 0;\n    bu->changeMagFem = 0;\n"),
        ("    bu->unit.pow = unit->pow;\n", "    bu->unit.pow = unit->pow;\n    UNIT_MAG_FEM(&bu->unit) = UNIT_MAG_FEM(unit);\n"),
        ("    attacker->battleAttack += attacker->unit.pow;\n",
         "    attacker->battleAttack += BATTLE_ATTACK_STAT_FEM(attacker);\n"),
        ("            attacker->battleAttack -= attacker->unit.pow / 2;\n",
         "            attacker->battleAttack -= BATTLE_ATTACK_STAT_FEM(attacker) / 2;\n"),
        ("        bu->changeLck = GetStatIncrease(bu->unit.pCharacterData->growthLck + growthBonus);\n"
         "        statGainTotal += bu->changeLck;\n",
         "        bu->changeLck = GetStatIncrease(bu->unit.pCharacterData->growthLck + growthBonus);\n"
         "        statGainTotal += bu->changeLck;\n\n"
         "        bu->changeMagFem = GetStatIncrease(gCharacterMagFem[bu->unit.pCharacterData->number][1] + growthBonus);\n"
         "        statGainTotal += bu->changeMagFem;\n"),
        ("    bu->changePow = bu->unit.pow   - unit->pow;\n",
         "    bu->changePow = bu->unit.pow   - unit->pow;\n"
         "    bu->changeMagFem = UNIT_MAG_FEM(&bu->unit) - UNIT_MAG_FEM(unit);\n"),
        ("    if ((unit->pow + bu->changePow) > UNIT_POW_MAX(unit))\n"
         "        bu->changePow = UNIT_POW_MAX(unit) - unit->pow;\n",
         "    if ((unit->pow + bu->changePow) > UNIT_POW_MAX(unit))\n"
         "        bu->changePow = UNIT_POW_MAX(unit) - unit->pow;\n\n"
         "    if ((UNIT_MAG_FEM(unit) + bu->changeMagFem) > UNIT_MAG_MAX_FEM(unit))\n"
         "        bu->changeMagFem = UNIT_MAG_MAX_FEM(unit) - UNIT_MAG_FEM(unit);\n"),
        ("    unit->pow   += bu->changePow;\n",
         "    unit->pow   += bu->changePow;\n    UNIT_MAG_FEM(unit) += bu->changeMagFem;\n"),
        ("    int baseAccuracy = (GetUnitPower(actor) - GetUnitResistance(target)) * 5;\n",
         "    int baseAccuracy = (GetUnitMagicFem(actor) - GetUnitResistance(target)) * 5;\n"),
        ("        unit->lck += lckGain;\n",
         "        unit->lck += lckGain;\n\n"
         "        {\n"
         "            int magGain = GetStatIncrease(growthBonus + gCharacterMagFem[unit->pCharacterData->number][1]);\n\n"
         "            if (UNIT_MAG_FEM(unit) + magGain > UNIT_MAG_MAX_FEM(unit))\n"
         "                magGain = UNIT_MAG_MAX_FEM(unit) - UNIT_MAG_FEM(unit);\n"
         "            UNIT_MAG_FEM(unit) += magGain;\n"
         "        }\n"),
    ])
    # promotions (two functions, the same lines)
    promoted = "    if (unit->pow > promotedClass->maxPow)\n        unit->pow = promotedClass->maxPow;\n"
    battle = text("src/bmbattle.c")
    if battle.count(promoted) != 2:
        raise StrMagError("Strength/Magic split: src/bmbattle.c does not match (promotions)")
    files["src/bmbattle.c"] = battle.replace(promoted, promoted + "\n    ApplyPromotionMagicFem(unit, promotedClass->number);\n")
    # staves heal with Magic
    patch("src/bmitem.c", [("    if (GetItemAttributes(item) & IA_STAFF) {\n        result += GetUnitPower(unit);\n",
                            "    if (GetItemAttributes(item) & IA_STAFF) {\n        result += GetUnitMagicFem(unit);\n")])
    # the AI's estimates: a tome's damage with Magic
    patch("src/cp_0803E2F4.c", [("    return GetUnitPower(unit) + GetItemMight(item);\n",
                                 "    return ((GetItemAttributes(item) & IA_MAGIC)\n"
                                 "        ? GetUnitMagicFem(unit) : GetUnitPower(unit)) + GetItemMight(item);\n")])
    patch("src/cp_staff.c", [("    score += GetUnitPower(unit);\n", "    score += GetUnitMagicFem(unit);\n")])

    _status_screen(files, decomp_dir)
    _level_up_screens(files, decomp_dir)
    _unit_list(files, decomp_dir)

    # items: a Magic bonus beside the others (weapons while equipped, boosters and usable items for good)
    patch("include/bmitem.h", [("    /* 08 */ s8 conBonus;\n};\n",
                                "    /* 08 */ s8 conBonus;\n    /* 09 */ s8 magBonus; /* FE Maker (ticket 27) */\n};\n")])
    patch("src/bmusemind.c", [("    unit->conBonus += statBonuses->conBonus;\n",
                               "    unit->conBonus += statBonuses->conBonus;\n"
                               "    UNIT_MAG_FEM(unit) += statBonuses->magBonus;\n")])
    if "    unit->conBonus += bonuses->conBonus;\n" in text("src/bmusemind.c"):   # ticket 162's usable items
        patch("src/bmusemind.c", [("    unit->conBonus += bonuses->conBonus;\n",
                                   "    unit->conBonus += bonuses->conBonus;\n    UNIT_MAG_FEM(unit) += bonuses->magBonus;\n")])
    # the arena: each side's attack with the stat of its weapon
    patch("src/bmarena.c", [
        ("    gBattleActor.battleAttack = GetUnitPower(gArenaState.playerUnit) + 5;\n",
         "    gBattleActor.battleAttack = (gArenaState.playerIsMagic\n"
         "        ? GetUnitMagicFem(gArenaState.playerUnit) : GetUnitPower(gArenaState.playerUnit)) + 5;\n"),
        ("    gBattleTarget.battleAttack = GetUnitPower(gArenaState.opponentUnit) + 5;\n",
         "    gBattleTarget.battleAttack = (gArenaState.opponentIsMagic\n"
         "        ? GetUnitMagicFem(gArenaState.opponentUnit) : GetUnitPower(gArenaState.opponentUnit)) + 5;\n")])

    # saves
    game_write = ("    for (i = 0; i < UNIT_SAVE_AMOUNT_BLUE; i++)\n"
                  "        WriteGameSavePackedUnit(&gUnitArrayBlue[i], &dest->units[i]);\n")
    suspend_read = "    SetBonusContentClaimFlags(LoadSavedBonusClaimFlags(gPlaySt.gameSaveSlot));\n"
    patch("src/bmsave.c", [
        ("void CopyGameSave(int index_src, int index_dest)\n{", SAVE.lstrip("\n")
         + "void CopyGameSave(int index_src, int index_dest)\n{"),
        ("    WriteAndVerifySramFast(gGenericBuffer, dest, sizeof(struct GameSaveBlock));\n",
         "    WriteAndVerifySramFast(gGenericBuffer, dest, sizeof(struct GameSaveBlock));\n"
         "    CopyMagicFem(index_src, index_dest);\n"),
        (game_write, game_write + "    WriteMagicFem(slot, UNIT_SAVE_AMOUNT_BLUE);\n"),
        ("    for (i = 0; i < UNIT_SAVE_AMOUNT_BLUE; i++)\n        LoadSavedUnit(src->units + i, &gUnitArrayBlue[i]);\n",
         "    for (i = 0; i < UNIT_SAVE_AMOUNT_BLUE; i++)\n        LoadSavedUnit(src->units + i, &gUnitArrayBlue[i]);\n"
         "    ReadMagicFem(slot, UNIT_SAVE_AMOUNT_BLUE);\n"),
        ("    for (i = 0; i < UNIT_SAVE_AMOUNT_BLUE; i++)\n        EncodeSuspendSavePackedUnit(&gUnitArrayBlue[i], buf++);\n",
         "    WriteMagicFem(slot, MAG_SAVE_UNITS_FEM);\n"
         "    for (i = 0; i < UNIT_SAVE_AMOUNT_BLUE; i++)\n        EncodeSuspendSavePackedUnit(&gUnitArrayBlue[i], buf++);\n"),
        (suspend_read, suspend_read + "    ReadMagicFem(slot + gSuspendSaveIdOffset, MAG_SAVE_UNITS_FEM);\n"),
    ])
    return files
