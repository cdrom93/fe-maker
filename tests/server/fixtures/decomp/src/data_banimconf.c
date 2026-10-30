// Fictional test data written for FE Maker. Not taken from the game.
CONST_DATA struct BattleAnimDef AnimConf_TestLord[] = {
    {
        .wtype = 0x0100 | ITYPE_SWORD,
        .index = 0x0001,
    },
    { 0 }
};

CONST_DATA struct BattleAnimDef AnimConf_TestKnight[] = {
    {
        .wtype = 0x0100 | ITYPE_LANCE,
        .index = 0x0002,
    },
    {
        .wtype = 0x0100 | ITYPE_SWORD,
        .index = 0x0003,
    },
    {
        .wtype = 0x0100 | ITYPE_AXE,
        .index = 0x0002,
    },
    {
        .wtype = ITEM_AXE_HANDAXE,
        .index = 0x0003,
    },
    { 0 }
};
