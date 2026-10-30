import re

import pytest

from fe_maker.decomp import gamedata, weaponrange

# Fictional excerpts in the shape of the decomp's src/bmitem.c and src/bmidoten.c.
ITEM = """int GetItemReachBits(int item) {
    switch (GetItemEncodedRange(item)) {

    case 0x11:
        return REACH_RANGE1;

    default:
        return REACH_NONE;

    } // switch (GetItemEncodedRange(item))
}

char* GetItemDisplayRangeString(int item) {
    switch (GetItemEncodedRange(item)) {

    default: // bad
        return GetStringFromIndex(rangeTextIdLookup[9]);

    } // switch (GetItemEncodedRange(item))
}
"""

RANGE_MAP = """void GenerateUnitCompleteAttackRange(struct Unit* unit)
{
    switch (GetUnitWeaponReachBits(unit, -1))
    {

    case REACH_RANGE1:
        break;

    } // switch (GetUnitWeaponReachBits(unit, -1))
}

void GenerateUnitStandingReachRange(struct Unit* unit, int reach)
{
    int x = unit->xPos;
    int y = unit->yPos;

    switch (reach)
    {

    case REACH_RANGE1:
        MapAddInBoundedRange(x, y, 1, 1);
        break;

    } // switch (reach)
}
"""


def test_every_range_gets_a_reach_and_a_text():
    out = weaponrange.with_item_ranges(ITEM)
    assert "REACH_RANGE1" not in out and "bits |= 1 << (8 + distance);" in out
    assert "'0' + max" in out and out.count("GetStringFromIndex(rangeTextIdLookup[9])") == 1   # "--" stays for the rest


def test_staves_keep_the_games_reach():
    out = weaponrange.with_range_map(RANGE_MAP)
    assert "static void FemAddReach" in out
    standing = out[out.index("void GenerateUnitStandingReachRange"):]
    assert standing.index("if (reach >> 8)") < standing.index("switch (reach)")
    complete = out[out.index("void GenerateUnitCompleteAttackRange"):out.index("void GenerateUnitStandingReachRange")]
    assert re.search(r"#if 0\n    switch .*#endif", complete, re.DOTALL)


def test_a_changed_decomp_stops_the_build():
    with pytest.raises(weaponrange.RangeError):
        weaponrange.with_range_map("void Other(void) {}")
    with pytest.raises(weaponrange.RangeError):
        weaponrange.with_item_ranges("void Other(void) {}")


def _with_range(data, encoded):
    items = data.export_items()
    items[0]["range"] = {"min": encoded >> 4, "max": encoded & 0xF}
    data.apply_items(items)
    return data


def test_only_a_range_the_game_does_not_list_rewrites_the_engine(decomp_dir):
    assert not gamedata.DecompData(decomp_dir).other_ranges
    assert not _with_range(gamedata.DecompData(decomp_dir), 0x12).other_ranges
    assert _with_range(gamedata.DecompData(decomp_dir), 0x1A).other_ranges
