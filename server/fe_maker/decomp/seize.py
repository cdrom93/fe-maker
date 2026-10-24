"""Who can seize (ticket 37).

In FE8 the "Seize" command is only for the route's lord: Eirika, or Ephraim on his route and in
chapter 5 (CanUnitSeize, src/bmdifficulty.c). The CA_LORD attribute does not change it. A project
can let other characters seize, or stop Eirika or Ephraim from it; the function is rewritten only
when the project changes who can.
"""

from __future__ import annotations

FILE = "src/bmdifficulty.c"
DEFAULT_SEIZERS = ("CHARACTER_EIRIKA", "CHARACTER_EPHRAIM")   # depending on the route in the game
_HEAD = "s8 CanUnitSeize(struct Unit* unit) {\n    int leaderId;\n"


class SeizeError(Exception):
    pass


def with_seizers(source: str, seizers: list[str]) -> str:
    """src/bmdifficulty.c where the listed characters can seize; Eirika and Ephraim keep the game's
    route rule when listed, and never seize when not."""
    if _HEAD not in source:
        raise SeizeError("CanUnitSeize not found")
    added = [pid for pid in seizers if pid not in DEFAULT_SEIZERS]
    removed = [pid for pid in DEFAULT_SEIZERS if pid not in seizers]
    # Comparisons, not a table (the link script may drop the file's .rodata)
    checks = "".join(f"\n    if (unit->pCharacterData->number == {pid})\n        return 1;\n" for pid in added)
    checks += "".join(f"\n    if (unit->pCharacterData->number == {pid})\n        return 0;\n" for pid in removed)
    return source.replace(_HEAD, _HEAD + "\n    // FE Maker: the characters who can seize" + checks, 1)
