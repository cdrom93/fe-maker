// Fictional test data written for FE Maker. Not taken from the game.
#include "global.h"

CONST_DATA struct CharacterData gCharacterData[] = {
    [CHARACTER_TESTHERO - 1] = {
        .nameTextId = 0x2,
        .number = CHARACTER_TESTHERO,
        .defaultClass = CLASS_TESTLORD,
        .portraitId = 0x1,
        .baseLevel = 1,

        .baseHP  = 3,
        .basePow = 1,
        .baseLck = 4,

        .baseRanks = {
            [ITYPE_SWORD] = WPN_EXP_E,
        },

        .growthHP  = 50,
        .growthPow = 25,
        .attributes = CA_FEMALE, // keep me
        .pSupportData = &SupportData_TestHero,
    },
    [CHARACTER_TESTRIVAL - 1] = {
        .nameTextId = 0x3,
        .number = CHARACTER_TESTRIVAL,
        .defaultClass = CLASS_TESTKNIGHT,
        .portraitId = 0x2,
        .baseLevel = 5,
        .baseDef = 7,
    },
};
