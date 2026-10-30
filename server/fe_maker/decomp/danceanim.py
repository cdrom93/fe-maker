"""Units that dance without a dancer's map sprite (ticket 81).

The dance on the map switches the unit's walking sprite to its sixth animation, which only the sprites of dancers
have: with another class, the game reads past the sprite's list and the screen breaks, or stays black, in the original
game too. Those classes dance without the animation. The file is rewritten only when the project
gives the dance to another class or character.
"""

from __future__ import annotations

FILE = "src/mapanim_spellassoc.c"
DANCER_CLASSES = ("CLASS_DANCER", "CLASS_BARD")
ABILITIES = {"dance", "play"}
_SUBJECT = "gManimSt.actor[gManimSt.subjectActorId].mu->sprite_anim"
_START = f"""    {_SUBJECT}->frameTimer = 0;
    {_SUBJECT}->frameInterval = 0x100;
    AP_SwitchAnimation({_SUBJECT}, 0x5);
"""
_STOP = f"""    {_SUBJECT}->frameTimer = 0;
    {_SUBJECT}->frameInterval = 0;
"""
_FIRST = "void sub_80812C0(void)\n"
_CHECK = """/* FE Maker: only the sprites of dancers have the dance's animation */
static int FemHasDanceAnim(void)
{
    int number = gManimSt.actor[gManimSt.subjectActorId].unit->pClassData->number;

    return number == CLASS_DANCER || number == CLASS_BARD;
}

"""


class DanceAnimError(Exception):
    pass


def with_guard(source: str) -> str:
    if not all(part in source for part in (_START, _STOP, _FIRST)):
        raise DanceAnimError(f"The dance's animation does not match this version of the decomp ({FILE})")
    source = source.replace(_START, f"    if (FemHasDanceAnim())\n    {{\n{_START}    }}\n", 1)
    source = source.replace(_STOP, f"    if (FemHasDanceAnim())\n    {{\n{_STOP}    }}\n", 1)
    return source.replace(_FIRST, _CHECK + _FIRST, 1)
