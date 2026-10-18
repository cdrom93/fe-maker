// Fictional test data written for FE Maker. Not taken from the game.
CONST_DATA struct ClassData gClassData[] = {
    [CLASS_TESTLORD - 1] = {
        .nameTextId = 0x5,
        .number = CLASS_TESTLORD,
        .baseHP  = 10,
        .basePow = 2,
        .baseMov = 5,
        .pBattleAnimDef = AnimConf_TestLord,
    },
    [CLASS_TESTKNIGHT - 1] = {
        .nameTextId = 0x6,
        .number = CLASS_TESTKNIGHT,
        .baseHP  = 12,
        .baseDef = 6,
        .baseMov = 4,
        .pBattleAnimDef = AnimConf_TestKnight,
    },
};
