// Fictional test data written for FE Maker. Not taken from the game.
struct AiItemFn CONST_DATA gTestAiItems[] = {
    { ITEM_TESTBLADE, AiTestBlade },
    { ITEM_NONE, NULL },
};

int TestItemEffect(int item)
{
    switch (GetItemIndex(item)) {
    case ITEM_TESTBLADE:
        return 1;
    }
    if (GetItemIndex(gUnits[2]->items[0]) == ITEM_TESTBLADE)
        return 2;
    if (bu->weaponBefore != ITEM_TESTBLADE)
        return 3;
    return 0;
}
