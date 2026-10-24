"""Who opens the convoy, and in which chapters (ticket 29).

In FE8 the "Supply" command is shown to the route's lord (Eirika, or Ephraim on his route) and to
the units next to them (SupplyUsability, src/bmmenu.c), and there is no convoy in the prologue,
chapter 1, chapter 5x and Castle Frelia (HasConvoyAccess, src/bmcontainer.c). The CA_SUPPLY class
or character attribute is not that: it is FE7's convoy carrier (no trading, back after death).

A project can choose the characters who open the convoy (units next to them can use it too) and
the chapters without convoy; both functions are rewritten only when the project changes them.
"""

from __future__ import annotations

import re

MENU_FILE = "src/bmmenu.c"
CONTAINER_FILE = "src/bmcontainer.c"
DEFAULT_OPENERS = ("CHARACTER_EIRIKA", "CHARACTER_EPHRAIM")   # the route's lord in the game
DEFAULT_NO_CONVOY = (0x00, 0x01, 0x05, 0x38)   # prologue, chapter 1, chapter 5x, Castle Frelia


class ConvoyError(Exception):
    pass


def has_convoy(chapter_index: int) -> bool:
    """The game's rule (on the world map, the game looks at the next chapter the same way)."""
    return chapter_index not in DEFAULT_NO_CONVOY


def _replace_function(source: str, signature: str, body: str) -> str:
    """The C source with the function starting with `signature` replaced (up to its closing brace
    at the start of a line)."""
    start = source.find(signature)
    if start < 0:
        raise ConvoyError(f"{signature} not found")
    m = re.compile(r"^}\r?\n", re.M).search(source, start)
    if m is None:
        raise ConvoyError(f"end of {signature} not found")
    return source[:start] + body + source[m.end():]


def with_openers(menu_source: str, openers: list[str]) -> str:
    """src/bmmenu.c where the listed characters (and the units next to them) open the convoy."""
    # Comparisons, not a table: the link script drops these files' .rodata section.
    checks = "".join(f"""
    if (gActiveUnit->pCharacterData->number == {pid} || IsAdjacentForSupply({pid}))
    {{
        return MENU_ENABLED;
    }}
""" for pid in openers)
    body = f"""u8 SupplyUsability(const struct MenuItemDef * def, int number)
{{
    // FE Maker: the characters who open the convoy; the units next to them can use it too
    if (!HasConvoyAccess())
    {{
        return MENU_NOTSHOWN;
    }}

    if (gActiveUnit->pClassData->number == CLASS_PHANTOM)
    {{
        return MENU_NOTSHOWN;
    }}
{checks}
    return MENU_NOTSHOWN;
}}
"""
    return _replace_function(menu_source, "u8 SupplyUsability(", body)


def with_chapters(container_source: str, no_convoy: list[int]) -> str:
    """src/bmcontainer.c without convoy in the listed chapters (by index)."""
    checks = "".join(f"""
    if (chapterId == 0x{i:02X})
        return false;
""" for i in sorted(no_convoy))
    body = f"""bool8 HasConvoyAccess(void)
{{
    // FE Maker: the chapters without convoy (comparisons: the link script drops this file's .rodata)
    u32 chapterId = gPlaySt.chapterIndex;

    if (gGMData.state.bits.state_0)
        chapterId = GetNextUnclearedChapter();
{checks}
    return true;
}}
"""
    return _replace_function(container_source, "bool8 HasConvoyAccess(void)", body)
