// Fictional test data written for FE Maker. Not taken from the game.
CONST_DATA struct REDA REDAs_PrologueTest1[] = {
    {
        .x = 3,
        .y = 4,
    },
};

CONST_DATA struct UnitDefinition UnitDef_Event_PrologueAlly[] = {
    {
        .charIndex = CHARACTER_TESTHERO,
        .classIndex = CLASS_TESTLORD,
        .allegiance = FACTION_ID_BLUE,
        .level = 1,
        .xPosition = 1,
        .yPosition = 1,
        .redaCount = 1,
        .redas = REDAs_PrologueTest1,
    },
    { 0 },
};

CONST_DATA struct UnitDefinition UnitDef_Event_PrologueEnemy[] = {
    {
        .charIndex = CHARACTER_TESTRIVAL,
        .classIndex = CLASS_TESTKNIGHT,
        .allegiance = FACTION_ID_RED,
        .level = 2,
        .xPosition = 6,
        .yPosition = 6,
    },
    { 0 },
};
