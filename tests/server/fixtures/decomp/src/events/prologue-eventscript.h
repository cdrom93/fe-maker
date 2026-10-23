// Fictional test data written for FE Maker. Not taken from the game.
CONST_DATA EventListScr EventScr_Prologue_BeginningScene[] = {
    CALL(EventScr_TestLongCutscene)
    LOAD1(1, UnitDef_Event_PrologueAlly)
    ENUN
    Text(0x1)
    LOAD1(1, UnitDef_Event_PrologueEnemy)
    ENUN
    ENDA
};

CONST_DATA EventListScr EventScr_Prologue_EndingScene[] = {
    ENDA
};
