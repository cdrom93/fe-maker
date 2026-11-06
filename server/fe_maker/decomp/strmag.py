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
TEMP_TABLE_SET = "#define SET_TEMP_BONUSES_FEM(aUnit, v) (gTempBonusesFem[(u8) (aUnit)->index] = (v) & 0xFFFFFF)\n"

UNIT_FUNCTIONS = """int GetUnitMagicFem(struct Unit* unit) {
    return UNIT_MAG_FEM(unit);
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

static void ReadMagicFem(int slot, int count)
{
    u8 buf[4 + MAG_SAVE_UNITS_FEM];
    int i;

    ReadSramFast(MAG_SAVE_FEM(slot), buf, sizeof(buf));
    if ((buf[0] | buf[1] << 8 | buf[2] << 16 | (u32) buf[3] << 24) != gPlaySt.time_saved)
        return;
    for (i = 0; i < count; i++)
        MagSavedUnitFem(i)->_u3A = buf[4 + i];
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
             "            SET_TEMP_BONUSES_FEM(unit, entry[1] | entry[2] << 8 | entry[3] << 16);\n")])
    patch("include/bmbattle.h", [
        ("    /* 7E */ s8 hasItemEffectTarget;\n    /* 7F */ /* pad */\n",
         "    /* 7E */ s8 hasItemEffectTarget;\n    /* 7F */ s8 changeMagFem; /* FE Maker: Magic gained (ticket 27) */\n"),
        ("\n#endif // GUARD_BMBATTLE_H", BATTLE_HELPER + "#endif // GUARD_BMBATTLE_H")])
    iwram = "sym_iwram.txt"
    iwram_end = ". = ALIGN(4); *libc.a:sbrkr.o(COMMON);"
    if temp_table:
        patch(iwram, [(iwram_end, iwram_end + "\n\n/* FE Maker: temporary bonuses by unit number (ticket 27) */\n"
                       ". = ALIGN(4); gTempBonusesFem = .;\n. = . + 0x300;")])

    # the unit: data, loading, automatic levels, caps, copies
    bmunit = text("src/bmunit.c")
    power = _getter_body(bmunit, "Power")
    unit_pairs = [
        (power, _tables(decomp_dir, characters, classes) + UNIT_FUNCTIONS + power),
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
