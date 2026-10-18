// Fictional test data written for FE Maker. Not taken from the game.
struct ProcCmd CONST_DATA gProcScr_GameControl[] =
{
    PROC_NAME("TEST"),
    PROC_CALL(TestInit),
    PROC_REPEAT(GameControl_8009A60_Null),

PROC_LABEL(LGAMECTRL_GAME_INTRO_UI),
    PROC_CALL(TestShowIntro),
    PROC_END,
};
