// Fictional test data written for FE Maker. Not taken from the game.
CONST_DATA struct ClassData gClassData[] = {
    [CLASS_TESTLORD - 1] = {
        .nameTextId = 0x5,
        .number = CLASS_TESTLORD,
        .baseHP  = 10,
        .basePow = 2,
        .baseMov = 5,
        .attributes = CA_LORD | CA_LOCK_4,
        .pBattleAnimDef = AnimConf_TestLord,
        .pMovCostTable = {
            TerrainTable_MovCost_CommonT1Normal,
            TerrainTable_MovCost_CommonT1Rain,
            TerrainTable_MovCost_CommonT1Snow,
        },
        .pTerrainAvoidLookup = TerrainTable_Avo_Common,
        .pTerrainDefenseLookup = TerrainTable_Def_Common,
        .pTerrainResistanceLookup = TerrainTable_Res_Common,
    },
    [CLASS_TESTKNIGHT - 1] = {
        .nameTextId = 0x6,
        .number = CLASS_TESTKNIGHT,
        .baseHP  = 12,
        .baseDef = 6,
        .baseMov = 4,
        .pBattleAnimDef = AnimConf_TestKnight,
        .pMovCostTable = {
            TerrainTable_MovCost_ArmorNormal,
            TerrainTable_MovCost_ArmorRain,
            TerrainTable_MovCost_ArmorSnow,
        },
        .pTerrainAvoidLookup = TerrainTable_Avo_Common,
        .pTerrainDefenseLookup = TerrainTable_Def_Common,
        .pTerrainResistanceLookup = TerrainTable_Res_Common,
    },
    [CLASS_TESTUNUSED - 1] = {
        .nameTextId = 0x6,
        .number = CLASS_TESTUNUSED,
        .baseHP  = 15,
        .pBattleAnimDef = AnimConf_TestKnight,
    },
};
