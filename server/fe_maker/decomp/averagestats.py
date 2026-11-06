"""Stats of a unit when it enters a chapter, as the game computes them (LoadUnit, src/bmunit.c).

Automatic levels are random: this gives their average. Playable characters, bosses and every
blue unit level up with the character's growths from the sheet's level (UnitAutolevelRealistic);
other units with the class's growths from level 1, and 9 more levels in a promoted class
(UnitAutolevel, GetCurrentPromotedLevelBonus; 19 in hard mode, not counted here).
"""

from . import strmag

STATS = ("hp", "pow", "skl", "spd", "def", "res", "lck")
LUCK_MAX = 30
FIRST_GENERIC = 0x40


def average_stats(character: dict | None, cls: dict, level: int, autolevel: bool, side: str, number: int,
                  classes: dict[str, dict] | None = None) -> dict[str, int]:
    """`character`: the sheet (None for a generic unit); `number`: its number in the game.
    `classes`, by id, when Strength and Magic are split (game option strMagSplit): Magic too, as `mag`."""
    character = character or {"bases": {}, "growths": {}, "level": 1}
    abilities = cls.get("abilities", [])
    personal = side == "player" or "boss" in abilities or number < FIRST_GENERIC
    if not autolevel:
        levels = 0
    elif personal:
        levels = max(level - character.get("level", 1), 0)
    else:
        levels = max(level - 1, 0) + (9 if "promoted" in abilities else 0)
    growths = character["growths"] if personal else cls["growths"]
    result = {}
    for stat in STATS:
        value = character["bases"].get(stat, 0) + cls["bases"].get(stat, 0) + growths.get(stat, 0) * levels / 100
        result[stat] = min(int(value + 0.5), cls["maxes"].get(stat, LUCK_MAX))
    if classes is not None:
        base, growth, maximum, _gain = strmag.class_magic(cls)
        personal_base, personal_growth = strmag.character_magic(character, classes)
        base += personal_base
        if personal:
            growth = personal_growth
        result["mag"] = min(int(base + growth * levels / 100 + 0.5), maximum)
    return result
