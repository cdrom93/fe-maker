"""A character's battle colours drawn from their portrait.

The portrait gives colours by place, then by hue: its hair is the largest group of hues around the head, whatever else
crowns it. The class's palette is cut into families of shades, and the game says which slots belong to the character:
the ones its characters change in this class (the horse, the wings and the weapon never move). Hair comes first, because
it is what tells units apart: slots 6 and 7 of the palette, sometimes 5, small and high on the sprite, unless the class
hides it under a helmet; then the largest family is the clothing. Wyverns have a layout of their own: the rider's accent
in 2-3, the wings' membrane in 7-9 and the body in 10-13, two colours kept apart. An animation without game palettes
(imported) has every family painted.
"""

from __future__ import annotations

import colorsys
from collections import defaultdict
from collections.abc import Callable

from PIL import Image

Rgb = tuple[int, int, int]

FACE_SIZE = (96, 80)
# Parts of a portrait where each thing is: left, top, right, bottom
PLACES = {"hair": (0, 0, 96, 30), "skin": (34, 34, 62, 58), "cloth": (8, 64, 88, 80)}
MOVED = 24         # a slot the game's palettes change by more than this distance belongs to the character
SEEN_PIXELS = 6    # below this, the slot is not really seen in the standing frame
LIGHT_GAP = 60     # shades this much lighter or darker than the sprite's would flatten it: its relief stays
LAST_SKIN_START = 6
LIGHTEST_CLOTH = 60       # a group of the clothes all darker than this is a shadow
MOST_HAIR_PIXELS = 60     # slots 6 and 7 holding more than this are clothes: the hair is under a helmet
SAME_HEIGHT = 4           # slot 5 is hair too when it stands as high as them (it is often the clothes or the horse)
WYVERN_HAIR, WYVERN_WINGS, WYVERN_BODY = (2, 3), (7, 8, 9), (10, 11, 12, 13)
WYVERN_SATURATION = 0.7   # the game's wyverns are muted, a tone taken from a cape is not
SAME_HUE = 0.09           # wings of the same hue as the body turn by this much, so that they still stand out
CODED = tuple((i * 16, 255 - i * 16, 128) for i in range(16))  # a strip drawn in these tells each pixel's colour number


def _hsv(colour: Rgb) -> tuple[float, float, float]:
    return colorsys.rgb_to_hsv(*(c / 255 for c in colour))


def _light(colour: Rgb) -> float:
    return 0.3 * colour[0] + 0.59 * colour[1] + 0.11 * colour[2]


def _distance(a: Rgb, b: Rgb) -> float:
    return sum((x - y) ** 2 for x, y in zip(a, b)) ** 0.5


def _close(a: Rgb, b: Rgb) -> bool:
    (h1, s1, _), (h2, s2, _) = _hsv(a), _hsv(b)
    if s1 < 0.15 and s2 < 0.15:
        return True
    turn = abs(h1 - h2)
    return s1 >= 0.1 and s2 >= 0.1 and min(turn, 1 - turn) < SAME_HUE


def _skin(colour: Rgb) -> bool:
    h, s, v = _hsv(colour)
    return 0.02 <= h <= 0.12 and 0.15 <= s <= 0.75 and v >= 0.55


def families(colours: list[Rgb]) -> list[list[int]]:
    """Slots that follow each other in close hues, the transparent one left out."""
    found: list[list[int]] = []
    for slot in range(1, len(colours)):
        if found and _close(colours[found[-1][-1]], colours[slot]):
            found[-1].append(slot)
        else:
            found.append([slot])
    return found


def _groups(colours: list[Rgb], pixels: dict[Rgb, int]) -> list[list[Rgb]]:
    """Colours by hue, each group from dark to light, the most used group first."""
    groups: list[list[Rgb]] = []
    for colour in colours:
        near = [g for g in groups if any(_close(c, colour) for c in g)]
        groups = [g for g in groups if g not in near] + [[colour, *(c for g in near for c in g)]]
    groups.sort(key=lambda g: -sum(pixels[c] for c in g))
    return [sorted(g, key=_light) for g in groups]


def portrait_ramps(face: Image.Image) -> dict:
    """The colours of a 96 x 80 face from dark to light: "hair", "skin", and "cloth": groups by hue, the most used first."""
    img = face.convert("RGBA")
    seen: dict[Rgb, dict[str, float]] = defaultdict(lambda: defaultdict(float))
    pixels: dict[Rgb, int] = defaultdict(int)
    for y in range(img.height):
        for x in range(img.width):
            r, g, b, a = img.getpixel((x, y))
            if a < 128 or max(r, g, b) < 50:   # the outline says nothing
                continue
            pixels[(r, g, b)] += 1
            for role, (left, top, right, bottom) in PLACES.items():
                if left <= x < right and top <= y < bottom:
                    seen[(r, g, b)][role] += 1 / ((right - left) * (bottom - top))
    roles: dict[str, list[Rgb]] = {"hair": [], "skin": [], "cloth": []}
    for colour, places in seen.items():
        role = max(places, key=lambda p: places[p])
        if role == "skin" and not _skin(colour):         # a fringe over the face, the shadow of a collar
            role = max((p for p in places if p != "skin"), key=lambda p: places[p], default="hair")
        roles[role].append(colour)
    hair = _groups(roles["hair"], pixels)
    if hair:                  # its darkest shades are the outline around it: two slots of hair would miss the colour itself
        middle = sum(_light(c) * pixels[c] for c in hair[0]) / sum(pixels[c] for c in hair[0])
        hair = [[c for c in hair[0] if _light(c) >= middle / 2]]
    cloth = _groups(roles["cloth"], {c: seen[c].get("cloth", 0) for c in roles["cloth"]})
    return {"hair": hair[0] if hair else [], "skin": sorted(roles["skin"], key=_light),
            "cloth": [g for g in cloth if _light(g[-1]) >= LIGHTEST_CLOTH]}


def usage(strip: Image.Image, width: int) -> dict[int, tuple[int, float]]:
    """Colour number -> pixels and mean height (from the top of the sprite) in the first frame of a strip drawn in CODED."""
    img = strip.convert("RGBA")
    counts: dict[int, list[int]] = defaultdict(lambda: [0, 0])
    for y in range(img.height):
        for x in range(min(width, img.width)):
            r, _g, _b, a = img.getpixel((x, y))
            if a > 128:
                counts[round(r / 16)][0] += 1
                counts[round(r / 16)][1] += y
    top = min((total / n for n, total in counts.values()), default=0)
    return {slot: (n, total / n - top) for slot, (n, total) in counts.items()}


def _tint(colours: list[Rgb], slots: list[int], base: list[Rgb], tone: Rgb, strength: float = 1) -> None:
    """The family keeps its shades, in the colour of `tone`."""
    hue, saturation, _ = _hsv(tone)
    for slot in slots:
        rgb = colorsys.hsv_to_rgb(hue, saturation * strength, _hsv(base[slot])[2])
        colours[slot] = (round(rgb[0] * 255), round(rgb[1] * 255), round(rgb[2] * 255))


def _paint(colours: list[Rgb], slots: list[int], base: list[Rgb], ramp: list[Rgb], faithful: bool = False) -> None:
    """The family's shades from the ramp, dark to dark, or tinted if the ramp cannot give them. `faithful`: the ramp's own
    colours even when they are far lighter or darker than the sprite's."""
    if not ramp or not slots:
        return
    ordered = sorted(slots, key=lambda s: _light(base[s]))
    gap = sum(map(_light, ramp)) / len(ramp) - sum(_light(base[s]) for s in slots) / len(slots)
    if len(ramp) < 2 or (abs(gap) > LIGHT_GAP and not faithful):
        _tint(colours, slots, base, ramp[len(ramp) // 2])
        return
    last = len(ordered) - 1 or 1
    for rank, slot in enumerate(ordered):
        place = rank / last * (len(ramp) - 1)
        low, high = int(place), min(int(place) + 1, len(ramp) - 1)
        part = place - low
        colours[slot] = tuple(round(a * (1 - part) + b * part) for a, b in zip(ramp[low], ramp[high]))  # type: ignore[assignment]


def _wyvern(colours: list[Rgb], base: list[Rgb], usable: Callable[[int], bool], ramps: dict) -> None:
    """The body takes the clothes, or the hair if they are grey or white; the wings' membrane takes the other one."""
    hair, cloth = ramps["hair"], ramps["cloth"][0] if ramps["cloth"] else []
    hair_tone = hair[len(hair) // 2] if hair else None
    cloth_tone = cloth[len(cloth) // 2] if cloth else None
    _paint(colours, [s for s in WYVERN_HAIR if usable(s)], base, hair, faithful=True)
    bright = cloth_tone is not None and _hsv(cloth_tone)[1] >= 0.25
    body, wings = (cloth_tone, hair_tone) if bright or hair_tone is None else (hair_tone, cloth_tone)
    if body is None:
        return
    if wings is None or _close(body, wings):
        hue, saturation, value = _hsv(body)
        red, green, blue = colorsys.hsv_to_rgb((hue + SAME_HUE) % 1, saturation, value)
        wings = (round(red * 255), round(green * 255), round(blue * 255))
    _tint(colours, [s for s in WYVERN_BODY if usable(s)], base, body, WYVERN_SATURATION)
    _tint(colours, [s for s in WYVERN_WINGS if usable(s)], base, wings, WYVERN_SATURATION)


def from_portrait(base: list[Rgb], game: list[list[Rgb]], seen: dict[int, tuple[int, float]], ramps: dict,
                  wyvern: bool = False) -> list[Rgb]:
    """16 colours: `base`, the class's, with the character's families taken from `ramps` (portrait_ramps). `game`: the
    palettes the game has for this same animation, `seen`: what `usage` read from it."""
    def moved(slot: int) -> bool:
        colours = [base[slot], *(g[slot] for g in game)]
        return not game or max(_distance(a, b) for a in colours for b in colours) >= MOVED

    def usable(slot: int) -> bool:
        return slot in seen and moved(slot)

    def pixels(family: list[int]) -> int:
        return sum(seen[s][0] for s in family)

    def height(family: list[int]) -> float:
        return sum(seen[s][0] * seen[s][1] for s in family) / pixels(family)

    colours = list(base)
    if wyvern:
        _wyvern(colours, base, usable, ramps)
        return colours
    hair = [s for s in (6, 7) if usable(s)]
    if pixels(hair) > MOST_HAIR_PIXELS:
        hair = []
    elif hair and usable(5) and abs(seen[5][1] - height(hair)) <= SAME_HEIGHT:
        hair.insert(0, 5)
    painted = []
    for family in families(base):
        slots = [s for s in family if usable(s) and s not in hair]
        if not slots or pixels(slots) < SEEN_PIXELS or min(_hsv(base[s])[2] for s in slots) >= 0.97:
            continue
        if len(slots) == 1 and _hsv(base[slots[0]])[2] < 0.35:   # a lone dark colour is a shadow
            continue
        painted.append(slots)
    # Skin comes first in a palette (a brown horse looks like it); its darkest shade is too dark to tell
    skin = [f for f in painted if f[0] <= LAST_SKIN_START and 2 * sum(_skin(base[s]) for s in f) >= len(f)]
    rest = sorted((f for f in painted if f not in skin), key=pixels, reverse=True)
    if skin:
        _paint(colours, max(skin, key=pixels), base, ramps["skin"])
    if not hair and len(rest) > 1:      # a palette laid out otherwise: the highest family that is not the largest
        hair = min(rest[1:], key=height)
        rest.remove(hair)
    _paint(colours, hair, base, ramps["hair"], faithful=True)
    for family, ramp in zip(rest, ramps["cloth"]):
        _paint(colours, family, base, ramp)
    return colours
