"""Temporary event flags past the 40th (ticket 112).

The game's chapter flags 1-99 have room for 16 bytes, but ResetChapterFlags clears the first 5 at each chapter and a
suspend keeps those 5: a flag above 40 stayed set in the next chapters, where another event of the same number never
ran (a door whose number was a village's in the chapter before). The game uses 28 at most, a project more: chapters
clear them all and the suspend keeps the 7 bytes its save block has room for (flags up to 56, numbered first by what
must not come back: conversations and map objects). The file is rewritten only when a project uses such a flag.
"""

from __future__ import annotations

import re

FILE = "src/eventinfo.c"
LAST_GAME_FLAG = 40                 # the last one the game clears
LAST_FLAG = 99                      # 100 and more are permanent flags
_RESET = "for (i = 0; i < (32 + 8) / 8; i++) {\n        gChapterFlagBits[i] = 0;"
_SIZE = "int GetChapterFlagBitsSize(void) {\n    return 5;"


class ChapterFlagsError(Exception):
    pass


def uses_late_flags(sources: list[str]) -> bool:
    return any(LAST_GAME_FLAG < int(n) <= LAST_FLAG for s in sources for n in re.findall(r"EVFLAG_TMP\(\s*(\d+)\s*\)", s))


def with_late_flags(source: str) -> str:
    text = source.replace("\r\n", "\n")
    if _RESET not in text or _SIZE not in text:
        raise ChapterFlagsError(f"The chapter flags do not match this version of the decomp ({FILE})")
    return (text.replace(_RESET, "for (i = 0; i < 16; i++) {\n        gChapterFlagBits[i] = 0;", 1)
            .replace(_SIZE, "int GetChapterFlagBitsSize(void) {\n    return 7;", 1))
