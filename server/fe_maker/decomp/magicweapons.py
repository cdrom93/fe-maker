"""Magic weapons: which weapons strike with magic, and how they look when they do.

The game decides this by item number, for its three magic swords only:
- src/bmbattle.c, SetBattleUnitWeapon: Wind Sword and Light Brand are magic at range only, the Runesword always, each with
  the magic type it counts as for the triangle;
- src/bmbattle.c, ComputeBattleUnitSpecialWeaponStats and BattleGenerateUiStats: half the Force, no critical;
- src/banim-battleparse.c: the Runesword plays its ranged animation even at close range.
These lists are rewritten from the project's items, so that any sword, lance or axe can do the same.

An animation casts its spell in its `attack_range` mode. Lances and swords have one, but plain axes have none: at range the
game gives them a thrown-axe animation, chosen by item (Hand Axe, Tomahawk, Hatchet). The mode is rebuilt from the close
attack: the wind-up, the weapon raised, the spell, and back to standing.
"""

from __future__ import annotations

import re
from pathlib import Path

from . import banim
from .tweaks import TweakError

BATTLE_FILE = "src/bmbattle.c"
PARSE_FILE = "src/banim-battleparse.c"
MODES = ("none", "range", "always")
# Item -> (when it is magic, what it counts as then), as in SetBattleUnitWeapon.
GAME_WEAPONS = {"ITEM_SWORD_WINDSWORD": ("range", "ITYPE_ANIMA"), "ITEM_SWORD_LIGHTBRAND": ("range", "ITYPE_LIGHT"),
                "ITEM_SWORD_RUNESWORD": ("always", "ITYPE_DARK")}
TYPES_WITHOUT_SPELL = ("ITYPE_SWORD", "ITYPE_LANCE", "ITYPE_AXE")

_SWITCH_RE = re.compile(r"            switch \(GetItemIndex\(bu->weapon\)\) \{\n.*?"
                        r"            \} // switch \(GetItemIndex\(bu->weapon\)\)\n", re.DOTALL)
_UI_STATS = "if (GetItemIndex(gBattleActor.weapon) == ITEM_SWORD_RUNESWORD) {"
_SPECIAL_CASES = "        case ITEM_SWORD_LIGHTBRAND:\n        case ITEM_SWORD_RUNESWORD:\n        case ITEM_SWORD_WINDSWORD:\n"
_FORCE_RANGED = ("    if (GetItemIndex(bul_sp04->weaponBefore) == ITEM_SWORD_RUNESWORD && distance_sp14 == EKR_DISTANCE_CLOSE)\n"
                 "        distance_sp14 = EKR_DISTANCE_FAR;\n"
                 "    if (GetItemIndex(bur_sp08->weaponBefore) == ITEM_SWORD_RUNESWORD && distance_sp18 == EKR_DISTANCE_CLOSE)\n"
                 "        distance_sp18 = EKR_DISTANCE_FAR;\n")
_MAX_DRIFT = 24    # pixels: past this, a wind-up has left the unit's place (a leap toward the enemy)


def _replace(source: str, old: str, new: str, rel: str) -> str:
    if old not in source:
        raise TweakError(f"The magic weapons do not match this version of the decomp ({rel})")
    return source.replace(old, new, 1)


def _case(item: str, mode: str, magic_type: str | None) -> str:
    strip = "bu->weaponAttributes = bu->weaponAttributes &~ IA_MAGICDAMAGE;"
    if mode == "always":
        body = f"                bu->weaponType = {magic_type};\n" if magic_type else ""
    elif magic_type:
        body = (f"                if (gBattleStats.range >= 2)\n                    bu->weaponType = {magic_type};\n"
                f"                else\n                    {strip}\n")
    else:
        body = f"                if (gBattleStats.range < 2)\n                    {strip}\n"
    return f"            case {item}:\n{body}                break;\n\n"


def battle_with(source: str, weapons: dict[str, tuple[str, str | None]]) -> str:
    """src/bmbattle.c with these magic weapons: item -> (mode, ITYPE they count as or None)."""
    cases = "".join(_case(item, mode, magic_type) for item, (mode, magic_type) in weapons.items())
    switch = f"            switch (GetItemIndex(bu->weapon)) {{\n\n{cases}            }} // switch (GetItemIndex(bu->weapon))\n"
    source, found = _SWITCH_RE.subn(switch, source, count=1)
    if not found:
        raise TweakError(f"The magic weapons do not match this version of the decomp ({BATTLE_FILE})")
    always = [item for item, (mode, _type) in weapons.items() if mode == "always"]
    test = " || ".join(f"GetItemIndex(gBattleActor.weapon) == {item}" for item in always) or "FALSE"
    source = _replace(source, _UI_STATS, f"if ({test}) {{", BATTLE_FILE)
    return _replace(source, _SPECIAL_CASES, "".join(f"        case {item}:\n" for item in weapons), BATTLE_FILE)


def parse_with(source: str, weapons: dict[str, tuple[str, str | None]]) -> str:
    """src/banim-battleparse.c: the weapons that are always magic play their ranged animation at close range too."""
    lines = "".join(_FORCE_RANGED.replace("ITEM_SWORD_RUNESWORD", item) for item, (mode, _type) in weapons.items()
                    if mode == "always")
    return _replace(source, _FORCE_RANGED, lines, PARSE_FILE)


def _width(attr0: int, attr1: int) -> int:
    return banim.SIZES.get(attr0 >> 14 & 3, banim.SIZES[0])[attr1 >> 14 & 3][0]


def _centre(sprites: list) -> float:
    if not sprites:
        return 0
    return (min(s[3] for s in sprites) + max(s[3] + _width(s[0], s[1]) for s in sprites)) / 2


def _wind_up(lines: list[str], frames: dict) -> list[str]:
    """The start of a close attack: until the blow, and while the unit stays in its place."""
    keep: list[str] = []
    start = None
    for line in lines:
        if re.search(r"banim_code_(prepare_hp_deplete|hit_|wait_hp_deplete)", line):
            break
        m = banim._FRAME_RE.search(line)
        if m:
            centre = _centre(frames.get(m.group(4), []))
            start = centre if start is None else start
            if abs(centre - start) > _MAX_DRIFT:
                break
        keep.append(line)
    while keep and "banim_code_frame" not in keep[-1]:
        keep.pop()
    return keep


def _frame(line: str, duration: int) -> str:
    return re.sub(r"(banim_code_frame )\d+", rf"\g<1>{duration}", line)


def motion_with_spell(decomp_dir: Path, symbol: str, text: str) -> str:
    """The animation's script, with ranged modes that cast the spell; the same text if they already do."""
    frames = banim.motion(decomp_dir, symbol).frames

    def section(mode: str) -> re.Match | None:
        return re.search(rf"^{symbol}_mode_{mode}:\n(.*?^\s*banim_code_end_mode\n)", text, re.MULTILINE | re.DOTALL)

    for ranged, close in (("attack_range", "attack_close"), ("attack_range_critical", "attack_close_critical")):
        target, model = section(ranged), section(close)
        if target is None or model is None or "banim_code_call_spell_anim" in target.group(1):
            continue
        wind_up = _wind_up(model.group(1).splitlines(), frames)
        moves = [line for line in wind_up if "banim_code_frame" in line]
        if not moves:
            continue
        body = [*wind_up, "\tbanim_code_call_spell_anim", _frame(moves[-1], 3), _frame(moves[-1], 1),
                "\tbanim_code_wait_hp_deplete", "\tbanim_code_start_opposite_turn", _frame(moves[0], 3),
                "\tbanim_code_end_dodge", "\tbanim_code_end_mode"]
        text = text[:target.start(1)] + "\n".join(body) + "\n" + text[target.end(1):]
    return text


def animations_with_spell(decomp_dir: Path, weapon_types: set[str]) -> dict[str, str]:
    """data/banim/*_motion.s to rewrite so that the classes' animations for these ITYPEs can cast a spell."""
    numbers = {d["number"] for defs in banim.configs(decomp_dir).values() for d in defs if d["weapon"] in weapon_types}
    animations = banim.table(decomp_dir)
    result = {}
    for number in sorted(n for n in numbers if n <= len(animations)):
        symbol = animations[number - 1].symbol
        rel = f"{banim.MOTION_DIR}/{symbol}_motion.s"
        if not (decomp_dir / rel).is_file():
            continue
        text = (decomp_dir / rel).read_text(encoding="utf-8")
        new = motion_with_spell(decomp_dir, symbol, text)
        if new != text:
            result[rel] = new
    return result
