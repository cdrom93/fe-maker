"""Small combat tables of the decomp: promotions, effectiveness lists, weapon triangle.

- gPromoJidLut (src/classchg-data.c): up to two promotion choices per class.
- ItemEffectiveness_* (src/data_itemuse.c): class lists an item is effective against,
  terminated by CLASS_NONE / 0.
- sWeaponTriangleRules (src/bmbattle.c): attacker type, defender type, hit and
  damage bonus, terminated by { -1 }.

Each table is re-rendered only when the project changes it, so an unmodified
project still rebuilds the original ROM.
"""

from __future__ import annotations

import re

PROMOTIONS_FILE = "src/classchg-data.c"
EFFECTIVENESS_FILE = "src/data_itemuse.c"
TRIANGLE_FILE = "src/bmbattle.c"

_LUT_RE = re.compile(r"(CONST_DATA\s+u8\s+gPromoJidLut\s*\[\s*\]\s*\[\s*2\s*\]\s*=\s*\{)(.*?)(\n\};)", re.DOTALL)
_LUT_ENTRY_RE = re.compile(r"\[\s*(\w+)\s*\]\s*=\s*\{([^}]*)\}")
_EFF_RE = re.compile(r"(CONST_DATA\s+u8\s+(ItemEffectiveness_\w+)\s*\[\s*\]\s*=\s*\{)(.*?)(\};)", re.DOTALL)
_TRI_RE = re.compile(r"(sWeaponTriangleRules\s*\[\s*\]\s*=\s*\{)(.*?)(\n\};)", re.DOTALL)
_TRI_ENTRY_RE = re.compile(r"\{\s*(ITYPE_\w+)\s*,\s*(ITYPE_\w+)\s*,\s*([+-]?\d+)\s*,\s*([+-]?\d+)\s*\}")


class CombatTableError(Exception):
    pass


def _find(regex: re.Pattern, source: str, what: str) -> re.Match:
    m = regex.search(source)
    if not m:
        raise CombatTableError(f"{what} not found in this version of the decomp")
    return m


# ---------- promotions ----------

def parse_promotions(source: str) -> dict[str, list[str]]:
    """Class id -> promotion choices (0 to 2 class ids)."""
    body = _find(_LUT_RE, source, "gPromoJidLut").group(2)
    result = {}
    for m in _LUT_ENTRY_RE.finditer(body):
        choices = [c.strip() for c in m.group(2).split(",") if c.strip() not in ("", "0", "CLASS_NONE")]
        result[m.group(1)] = choices
    return result


def render_promotions(source: str, promotions: dict[str, list[str]]) -> str:
    m = _find(_LUT_RE, source, "gPromoJidLut")
    width = max((len(k) for k in promotions), default=0) + 2
    lines = []
    for cls, choices in promotions.items():
        if not choices:
            continue
        key = f"[{cls}]".ljust(width)
        lines.append(f"    {key} = {{{', '.join(choices)}}},")
    return source[: m.start(2)] + "\n" + "\n".join(lines) + source[m.end(2):]


# ---------- effectiveness ----------

def parse_effectiveness(source: str) -> dict[str, list[str]]:
    """List name (ItemEffectiveness_Horse) -> class ids."""
    result = {}
    for m in _EFF_RE.finditer(source):
        tokens = [t.strip() for t in re.sub(r"//[^\n]*|/\*.*?\*/", "", m.group(3), flags=re.DOTALL).split(",")]
        result[m.group(2)] = [t for t in tokens if t and t not in ("0", "CLASS_NONE")]
    return result


def render_effectiveness(source: str, lists: dict[str, list[str]]) -> str:
    def replace(m: re.Match) -> str:
        name = m.group(2)
        if name not in lists:
            return m.group(0)
        body = "".join(f"\n    {cls}," for cls in lists[name]) + "\n    CLASS_NONE,\n"
        return m.group(1) + body + m.group(4)

    return _EFF_RE.sub(replace, source)


# ---------- weapon triangle ----------

def parse_triangle(source: str) -> list[dict]:
    body = _find(_TRI_RE, source, "sWeaponTriangleRules").group(2)
    return [
        {"attacker": a, "defender": d, "hit": int(h), "damage": int(dmg)}
        for a, d, h, dmg in _TRI_ENTRY_RE.findall(body)
    ]


def render_triangle(source: str, rules: list[dict]) -> str:
    m = _find(_TRI_RE, source, "sWeaponTriangleRules")
    lines = [
        f"    {{ {r['attacker']}, {r['defender']}, {r['hit']:+d}, {r['damage']:+d} }},"
        for r in rules
    ]
    body = "\n" + "\n".join(lines) + "\n\n    { -1 },"
    return source[: m.start(2)] + body + source[m.end(2):]
