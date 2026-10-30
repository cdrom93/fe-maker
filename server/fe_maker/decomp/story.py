"""How chapters follow each other (ticket 31).

A chapter ends with an event command that starts the next one (include/EAstdlib.h, src/eventscr.c
EvtChangeChapter...):
- MNCH(n): through the world map, then chapter n (most of the game);
- MNC2(n): straight to chapter n, without the world map (prologue -> chapter 1, chapter 5 -> 5x...);
- MNC3(n): straight to chapter n, without the save screen (end of the routes, before the final chapter);
- MNC4: the game's ending; MNTS: back to the title screen.
MoveToChapter(n) is another name for MNCH(n) (chapter 1).
The argument is the chapter's index (its place in the chapter table, as FE Maker numbers chapters).
A few scripts use MNCH(-1) / MNCH(0xffff) to go back to the world map without a chapter.

Without the world map (project option, tweaks.without_world_map, ticket 39): MNCH becomes MNC2 and every chapter
is a story chapter. Through the world map, the next chapter is the one of the place the lord stands on, so
MNCH's argument is only a hint (chapter 1 -> 56, Castle Frelia, a stopover). And a chapter from 2 on whose world
map place was never reached is taken for a skirmish (GetBattleMapKind) and runs the skirmish opening, which
waits for the world map: a black screen. See docs/audit-decomp.md, item 57.

The route split (chapter 8) is a menu that runs one of two scripts, each with its MNCH. Optional
skirmish maps (Tower of Valni, Lagdou Ruins) are reached from the world map, not from these commands.
"""

from __future__ import annotations

CHANGE_OPS = {"MNCH": "worldMap", "MoveToChapter": "worldMap", "MNC2": "direct", "MNC3": "noSave", "MNC4": "ending",
              "MNTS": "title"}
# ops that take a chapter (MoveToChapter: MNCH, include/EA_Standard_Library/End_Of_Chapter_Helpers.h)
TO_CHAPTER = ("MNCH", "MoveToChapter", "MNC2", "MNC3")
NO_CHAPTER = 0xFFFF


def _number(arg: str) -> int | None:
    try:
        n = int(str(arg).strip(), 0)
    except ValueError:
        return None
    n &= 0xFFFF
    return None if n == NO_CHAPTER else n


def with_next(commands: list[dict], chapter: int) -> list[dict]:
    """A script that had no next chapter, with MNC2 before its last commands (mirrored in ChapterFlow.svelte)."""
    at = len(commands)
    while at > 0 and commands[at - 1].get("op") in ("ENDA", "NoFade", ""):
        at -= 1
    return [*commands[:at], {"op": "MNC2", "args": [f"0x{chapter:X}"]}, *commands[at:]]


def links(commands: list[dict]) -> list[dict]:
    """Chapter changes of a script: {"at": command index, "op", "kind", "to": chapter index or None}."""
    out = []
    for i, c in enumerate(commands):
        op = c.get("op")
        if op not in CHANGE_OPS:
            continue
        to = _number(c["args"][0]) if op in TO_CHAPTER and c.get("args") else None
        if op in TO_CHAPTER and to is None:
            continue   # back to the world map, no chapter
        out.append({"at": i, "op": op, "kind": CHANGE_OPS[op], "to": to})
    return out
