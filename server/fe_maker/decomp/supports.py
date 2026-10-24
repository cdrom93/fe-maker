"""Supports between characters (src/data_supports.c, gSupportTalkList in src/data_event_trigger.c).

- Each character with supports points to a SupportData (gCharacterData .pSupportData): up to 7
  partners, with the points they start with (supportExpBase) and the points they gain each turn
  they start next to each other (supportExpGrowth). Levels: C at 81 points, B at 161, A at 241;
  the points stop one short of a level (80, 160, 240) until the pair has its conversation, which
  adds the last point (CanUnitSupportNow, bmreliance.c): a pair that starts at 81 or more is
  already at C and never sees the C conversation;
  a character reaches 5 levels at most in all (include/bmreliance.h).
- The game lists each pair on both sides with the same numbers (83 pairs, checked).
- gSupportTalkList gives each pair its 3 conversations (C, B, A), whatever the order of the pair.

FE Maker sees supports as pairs {a, b, base, growth}. Project data: data/dialogues.json "supports"
(the whole list, once edited); new pairs' conversations are new quotes {"kind": "support", "a",
"b", "rank": 1-3, "steps"}.
"""

from __future__ import annotations

import re

from .cparse import _blank_comments

SUPPORTS_FILE = "src/data_supports.c"
TALKS_FILE = "src/data_event_trigger.c"
MAX_PARTNERS = 7          # UNIT_SUPPORT_MAX_COUNT
MAX_LEVELS = 5            # MAX_SIMULTANEOUS_SUPPORT_COUNT
LEVEL_POINTS = (81, 161, 241)   # SUPPORT_EXP_C, B, A
MAX_POINTS = 255

_BLOCK_RE = re.compile(r"CONST_DATA struct SupportData (SupportData_\w+) = \{(.*?)\n\};\n", re.S)
_TALK_RE = re.compile(r"^[ \t]*\{\s*(CHARACTER_\w+),\s*(CHARACTER_\w+),\s*(0x[0-9A-Fa-f]+|\d+),\s*(0x[0-9A-Fa-f]+|\d+),"
                      r"\s*(0x[0-9A-Fa-f]+|\d+),\s*\},[ \t]*\n", re.M)


class SupportError(Exception):
    pass


def _list(body: str, field: str) -> list[str]:
    m = re.search(rf"\.{field}\s*=\s*\{{(.*?)\}}", body, re.S)
    return [v.strip() for v in m.group(1).split(",") if v.strip()] if m else []


def read_blocks(source: str) -> dict[str, list[tuple[str, int, int]]]:
    """SupportData name -> [(partner, base, growth)] (its first supportCount partners)."""
    out = {}
    for name, body in _BLOCK_RE.findall(_blank_comments(source)):
        m = re.search(r"\.supportCount\s*=\s*(\d+)", body)
        count = int(m.group(1)) if m else 0
        partners = _list(body, "characters")
        base = [int(v, 0) for v in _list(body, "supportExpBase")]
        growth = [int(v, 0) for v in _list(body, "supportExpGrowth")]
        out[name] = list(zip(partners, base, growth))[:count]
    return out


def read_talks(source: str) -> dict[tuple[str, str], list[int]]:
    """(a, b) sorted -> message of the C, B and A conversations."""
    return {tuple(sorted((a, b))): [int(c, 0), int(bb, 0), int(aa, 0)]
            for a, b, c, bb, aa in _TALK_RE.findall(source)}


def pairs_of(blocks: dict[str, list[tuple[str, int, int]]], owners: dict[str, str]) -> list[dict]:
    """Pairs {a, b, base, growth} from the characters' support lists (owners: SupportData -> character),
    in the order the game lists them."""
    out, seen = [], set()
    for name, partners in blocks.items():
        a = owners.get(name)
        if a is None:
            continue
        for b, base, growth in partners:
            key = tuple(sorted((a, b)))
            if key not in seen:
                seen.add(key)
                out.append({"a": a, "b": b, "base": base, "growth": growth})
    return out


def partners_by_character(pairs: list[dict], original: dict[str, list[tuple[str, int, int]]]) -> dict[str, list]:
    """Character -> [(partner, base, growth)]: the original order for pairs still there, new ones after."""
    wanted: dict[str, dict[str, tuple[int, int]]] = {}
    for p in pairs:
        for x, y in ((p["a"], p["b"]), (p["b"], p["a"])):
            wanted.setdefault(x, {})[y] = (int(p["base"]), int(p["growth"]))
    out = {}
    for char in set(wanted) | set(original):
        mine = wanted.get(char, {})
        kept = [(b, *mine[b]) for b, _base, _growth in original.get(char, []) if b in mine]
        added = [(b, *v) for b, v in mine.items() if b not in {k[0] for k in kept}]
        out[char] = kept + added
    return out


def render_block(name: str, partners: list[tuple[str, int, int]]) -> str:
    """A SupportData as the decomp writes it (unused slots stay zero)."""
    def column(values: list) -> str:
        return "".join(f"        {v},\n" for v in values)

    return (f"CONST_DATA struct SupportData {name} = {{\n"
            f"    .characters = {{\n{column([p[0] for p in partners])}    }},\n"
            f"    .supportExpBase = {{\n{column([p[1] for p in partners])}    }},\n"
            f"    .supportExpGrowth = {{\n{column([p[2] for p in partners])}    }},\n"
            f"    .supportCount = {len(partners)},\n}};\n")


def write_blocks(source: str, changed: dict[str, list[tuple[str, int, int]]]) -> str:
    """data_supports.c with these SupportData replaced (or added at the end)."""
    for name, partners in changed.items():
        block = render_block(name, partners)
        m = re.search(rf"CONST_DATA struct SupportData {re.escape(name)} = \{{.*?\n\}};\n", source, re.S)
        if m:
            source = source[:m.start()] + block + source[m.end():]
        else:
            source = source.rstrip("\n") + "\n\n" + block
    return source


def add_talks(source: str, talks: list[tuple[str, str, list[int]]]) -> str:
    """gSupportTalkList with new pairs, before its terminator ({ 0xFFFF, ... })."""
    m = re.search(r"gSupportTalkList\[\]\s*=\s*\{.*?\n([ \t]*\{\s*0xFFFF)", source, re.S)
    if not m:
        raise SupportError("gSupportTalkList not found")
    lines = "".join(f"    {{ {a}, {b}, 0x{c:04X}, 0x{bb:04X}, 0x{aa:04X}, }},\n" for a, b, (c, bb, aa) in talks)
    return source[:m.start(1)] + lines + source[m.start(1):]


def skipped_levels(base: int) -> list[int]:
    """Levels (1-3) a pair already has at the start: their conversations are never seen."""
    return [level for level, points in enumerate(LEVEL_POINTS, 1) if base >= points]


def turns_to(level: int, base: int, growth: int) -> int | None:
    """Turns spent side by side before a level's conversation can be seen (None: never). Each
    earlier conversation seen adds one point."""
    talks = sum(1 for k in range(1, level) if base < LEVEL_POINTS[k - 1])
    need = LEVEL_POINTS[level - 1] - 1 - base - talks
    if need <= 0:
        return 0
    return -(-need // growth) if growth > 0 else None
