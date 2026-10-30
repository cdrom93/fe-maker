"""Weapon ranges the game does not list (ticket 59).

The engine stores a range as two numbers but only knows some pairs: GetItemReachBits (the red squares) and
GetItemDisplayRangeString (the "Rng" of the item windows) are switches on the pair, anything else draws no range and
shows "--", although the weapon can attack. When the project gives a weapon another range these functions are
rewritten: the reach gets one bit per distance from bit 8, and the two functions of bmidoten.c that read it add
those distances. Nothing changes for a project that keeps the game's ranges.
"""

from __future__ import annotations

import re

ITEM_FILE = "src/bmitem.c"
RANGE_MAP_FILE = "src/bmidoten.c"
# Ranges with both a reach and a text in the game (0x10: 1 to mag / 2, 0xFF: whole map, 0: not a weapon).
GAME_RANGES = {0x00, 0x10, 0x11, 0x12, 0x13, 0x22, 0x23, 0x3A, 0xFF}

_REACH_BITS = """int GetItemReachBits(int item) {
    // FE Maker: one bit per distance, from bit 8 (bmidoten.c)
    int distance, bits = 0;

    for (distance = 1; distance <= GetItemMaxRange(item); ++distance)
        if (distance >= GetItemMinRange(item))
            bits |= 1 << (8 + distance);

    return bits;
}
"""

_DISPLAY = """    default: // bad
        // FE Maker: any other range, drawn at once by the callers
        if (GetItemMaxRange(item)) {
            char* text = (char*) gGenericBuffer;
            int min = GetItemMinRange(item), max = GetItemMaxRange(item);

            if (min >= 10) {
                *text++ = '1';
                min -= 10;
            }
            *text++ = '0' + min;
            *text++ = '-';
            if (max >= 10) {
                *text++ = '1';
                max -= 10;
            }
            *text++ = '0' + max;
            *text = 0;
            return (char*) gGenericBuffer;
        }
"""

_ADD_REACH = """// FE Maker: the distances of a reach (one bit per distance from bit 8, see GetItemReachBits)
static void FemAddReach(int x, int y, int reach)
{
    int distance, first = 0;

    for (distance = 1; distance <= 16; ++distance)
    {
        if ((reach >> (8 + distance)) & 1)
        {
            if (!first)
                first = distance;
        }
        else if (first)
        {
            MapAddInBoundedRange(x, y, first, distance - 1);
            first = 0;
        }
    }
}

"""


class RangeError(Exception):
    pass


def _swap(source: str, old: str, new: str) -> str:
    if source.count(old) != 1:
        raise RangeError(f"not found: {old.splitlines()[0]}")
    return source.replace(old, new)


def with_item_ranges(source: str) -> str:
    """src/bmitem.c knowing every range."""
    source, found = re.subn(r"int GetItemReachBits\(int item\) \{.*?\} // switch \(GetItemEncodedRange\(item\)\)\n\}\n",
                            _REACH_BITS, source, count=1, flags=re.DOTALL)
    if not found:
        raise RangeError("GetItemReachBits not found")
    return _swap(source, "    default: // bad\n", _DISPLAY)


def with_range_map(source: str) -> str:
    """src/bmidoten.c drawing the reach of every range."""
    source = _swap(source, "void GenerateUnitCompleteAttackRange(struct Unit* unit)\n",
                   _ADD_REACH + "void GenerateUnitCompleteAttackRange(struct Unit* unit)\n")
    source = _swap(source, "    switch (GetUnitWeaponReachBits(unit, -1))\n    {\n",
                   "    if (GetUnitWeaponReachBits(unit, -1))\n    {\n"
                   "        int reach = GetUnitWeaponReachBits(unit, -1);\n\n"
                   "        FOR_EACH_IN_MOVEMENT_RANGE({\n            FemAddReach(ix, iy, reach);\n        })\n"
                   "    }\n\n    #if 0\n    switch (GetUnitWeaponReachBits(unit, -1))\n    {\n")
    source = _swap(source, "    } // switch (GetUnitWeaponReachBits(unit, -1))\n",
                   "    } // switch (GetUnitWeaponReachBits(unit, -1))\n    #endif\n")
    head = "    int y = unit->yPos;\n\n    switch (reach)\n    {\n\n    case REACH_RANGE1:\n"
    return _swap(source, head,
                 "    int y = unit->yPos;\n\n    if (reach >> 8)\n    {\n"
                 "        // FE Maker: weapons; staves keep the game's reach\n"
                 "        FemAddReach(x, y, reach);\n        return;\n    }\n\n"
                 "    switch (reach)\n    {\n\n    case REACH_RANGE1:\n")
