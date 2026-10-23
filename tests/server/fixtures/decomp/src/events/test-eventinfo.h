// Fictional test data written for FE Maker. Not taken from the game.
CONST_DATA EventListScr EventScr_TestOpening[] = {
    LOAD1(1, UnitDef_TestEnemies)
    CALL(EventScr_TestShared)
    ENDA
};

CONST_DATA EventListScr EventScr_TestShared[] = {
    LOAD2(1, UnitDef_TestChapter)
    ENDA
};

CONST_DATA EventListScr EventScr_TestTurn3[] = {
    LOAD1(1, UnitDef_TestReinforcements)
    ENDA
};

CONST_DATA EventListScr EventListScr_Test_Turn[] = {
    TURN(EVFLAG_TMP(7), EventScr_TestTurn3, 3, 3, FACTION_BLUE)
    END_MAIN
};

CONST_DATA struct ChapterEventGroup TestChapterEvents = {
    .turnBasedEvents      = EventListScr_Test_Turn,
    .playerUnitsInNormal  = UnitDef_TestChapter,
    .beginningSceneEvents = EventScr_TestOpening,
};

// A cutscene played on another map before the battle.
CONST_DATA EventListScr EventScr_TestCutscene[] = {
    LOMA(CHAPTER_TEST_OTHER)
    LOAD2(1, UnitDef_TestCutsceneActors)
    LOMA(CHAPTER_TEST)
    ENDA
};

CONST_DATA EventListScr EventScr_TestOpeningWithCutscene[] = {
    CALL(EventScr_TestCutscene)
    LOAD1(1, UnitDef_TestEnemies)
    ENDA
};

CONST_DATA struct ChapterEventGroup TestCutsceneChapterEvents = {
    .playerUnitsInNormal  = UnitDef_TestChapter,
    .beginningSceneEvents = EventScr_TestOpeningWithCutscene,
};
