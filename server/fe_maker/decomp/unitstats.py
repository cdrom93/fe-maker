"""An event command that changes a unit's stat ("AddEvent: Set Unit Status" of FEBuilder, redone in C).

Written by events.render_command as three slots and a call: slot 1 the character, slot 2 the stat, slot 3 the amount.
The function works on the unit as it stands, so the change lasts while the unit does (saves included), and does nothing
if the character has no unit yet. Values stay within the class's limits and what a save can hold (5 bits, 6 for max HP,
4 for the move bonus, all unsigned). The files are rewritten only when a project uses the command.
"""

from __future__ import annotations

FILE = "src/bmunit.c"
HEADER = "include/eventscript.h"
FUNCTION = "FemChangeStat"
STATS = ("hp", "pow", "skl", "spd", "def", "res", "lck", "con", "mov")

_CODE = """
/* FE Maker: an event changes a unit's stat: slot 1 the character, slot 2 the stat, slot 3 the amount */
#include "event.h"

static int FemClamp(int value, int bottom, int top)
{
    return value < bottom ? bottom : value > top ? top : value;
}

void FemChangeStat(void)
{
    struct Unit * unit = GetUnitStructFromEventParameter(gEventSlots[1]);
    int amount = (int) gEventSlots[3];

    if (!unit)
        return;

    switch (gEventSlots[2]) {
    case 0:
        unit->maxHP = FemClamp(unit->maxHP + amount, 1, 63);
        break;
    case 1:
        unit->pow = FemClamp(unit->pow + amount, 0, 31);
        break;
    case 2:
        unit->skl = FemClamp(unit->skl + amount, 0, 31);
        break;
    case 3:
        unit->spd = FemClamp(unit->spd + amount, 0, 31);
        break;
    case 4:
        unit->def = FemClamp(unit->def + amount, 0, 31);
        break;
    case 5:
        unit->res = FemClamp(unit->res + amount, 0, 31);
        break;
    case 6:
        unit->lck = FemClamp(unit->lck + amount, 0, 31);
        break;
    case 7:
        unit->conBonus = FemClamp(unit->conBonus + amount, 0, 31);
        break;
    case 8:
        unit->movBonus = FemClamp(unit->movBonus + amount, 0, 15);
        break;
    }

    UnitCheckStatCaps(unit);
    if (gEventSlots[2] == 0)
        unit->curHP = FemClamp(unit->curHP + amount, 1, unit->maxHP);
}
"""


def uses(sources: list[str]) -> bool:
    return any(f"ASMC({FUNCTION})" in source for source in sources)


def with_function(source: str) -> str:
    return source.replace("\r\n", "\n").rstrip("\n") + "\n" + _CODE


def with_declaration(source: str) -> str:
    return source.replace("\r\n", "\n").rstrip("\n") + f"\n\nvoid {FUNCTION}(void);\n"
