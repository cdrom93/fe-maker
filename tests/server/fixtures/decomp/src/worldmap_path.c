// Fictional excerpt for tests (shape of the decomp's src/worldmap_path.c).

u32 GetBattleMapKind(void)
{
    int i;
    u32 chapterId = gPlaySt.chapterIndex;

    switch (chapterId)
    {
        case 0:
            return BATTLEMAP_KIND_STORY;
    }

    return BATTLEMAP_KIND_SKIRMISH;
}
