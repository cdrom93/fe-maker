"""A character's battle colours drawn from their portrait.

The portrait gives colours by place: hair at the top, skin in the middle, clothes at the bottom. The class's palette is
cut into families of shades, and the game says which of them belong to the rider: the slots its characters change in
this class (the horse, the wings and the weapon never move). The largest of those families is the clothing, the highest
of the others the hair. A wyvern is the exception: its body and wings are the largest ones and take the hue of the
clothes (or of the hair, if the clothes are grey or white) over their own shades, and the hair comes first in the palette.
An animation without game palettes (imported) has every family painted.
"""

from __future__ import annotations

import colorsys
from collections import defaultdict

from PIL import Image

Rgb = tuple[int, int, int]

FACE_SIZE = (96, 80)
# Parts of a portrait where each thing is: left, top, right, bottom
PLACES = {"hair": (20, 0, 76, 24), "skin": (34, 34, 62, 58), "cloth": (8, 64, 88, 80)}
MOVED = 24         # a slot the game's palettes change by more than this distance belongs to the character
SEEN_PIXELS = 6    # below this, the slot is not really seen in the standing frame
LIGHT_GAP = 60     # shades this much lighter or darker than the sprite's would flatten it: its relief stays
LAST_SKIN_START = 6
WYVERN_SATURATION = 0.7   # the game's wyverns are muted, a tone taken from a cape is not
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
    return s1 >= 0.1 and s2 >= 0.1 and min(turn, 1 - turn) < 0.09


def _skin(colour: Rgb) -> bool:
    h, s, v = _hsv(colour)
    return 0.02 <= h <= 0.12 and 0.15 <= s <= 0.75 and v >= 0.55


def _warm(colour: Rgb) -> bool:
    hue = _hsv(colour)[0]
    return hue <= 0.17 or hue >= 0.95


def families(colours: list[Rgb]) -> list[list[int]]:
    """Slots that follow each other in close hues, the transparent one left out."""
    found: list[list[int]] = []
    for slot in range(1, len(colours)):
        if found and _close(colours[found[-1][-1]], colours[slot]):
            found[-1].append(slot)
        else:
            found.append([slot])
    return found


def portrait_ramps(face: Image.Image) -> dict:
    """The colours of a 96 x 80 face from dark to light: "hair", "skin", and "cloth": groups by hue, the most used first."""
    img = face.convert("RGBA")
    seen: dict[Rgb, dict[str, float]] = defaultdict(lambda: defaultdict(float))
    for y in range(img.height):
        for x in range(img.width):
            r, g, b, a = img.getpixel((x, y))
            if a < 128 or max(r, g, b) < 50:   # the outline says nothing
                continue
            for role, (left, top, right, bottom) in PLACES.items():
                if left <= x < right and top <= y < bottom:
                    seen[(r, g, b)][role] += 1 / ((right - left) * (bottom - top))
    roles: dict[str, list[Rgb]] = {"hair": [], "skin": [], "cloth": []}
    weight = {}
    for colour, places in seen.items():
        role = max(places, key=lambda p: places[p])
        roles[role].append(colour)
        weight[colour] = places[role]
    groups: list[list[Rgb]] = []
    for colour in sorted(roles["cloth"], key=lambda c: -weight[c]):
        group = next((g for g in groups if _close(g[0], colour)), None)
        if group is None:
            groups.append([colour])
        else:
            group.append(colour)
    groups.sort(key=lambda g: -sum(weight[c] for c in g))
    warm = [c for c in roles["skin"] if _warm(c)]     # no skin in the shadows of a blue collar
    return {"hair": sorted(roles["hair"], key=_light), "skin": sorted(warm, key=_light),
            "cloth": [sorted(g, key=_light) for g in groups]}


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


def _paint(colours: list[Rgb], slots: list[int], base: list[Rgb], ramp: list[Rgb]) -> None:
    """The family's shades from the ramp, dark to dark, or tinted if the ramp cannot give them."""
    if not ramp:
        return
    ordered = sorted(slots, key=lambda s: _light(base[s]))
    gap = sum(map(_light, ramp)) / len(ramp) - sum(_light(base[s]) for s in slots) / len(slots)
    if len(ramp) < len(ordered) or abs(gap) > LIGHT_GAP:
        _tint(colours, slots, base, ramp[len(ramp) // 2])
        return
    last = len(ordered) - 1 or 1
    for rank, slot in enumerate(ordered):
        place = rank / last * (len(ramp) - 1)
        low, high = int(place), min(int(place) + 1, len(ramp) - 1)
        part = place - low
        colours[slot] = tuple(round(a * (1 - part) + b * part) for a, b in zip(ramp[low], ramp[high]))  # type: ignore[assignment]


def from_portrait(base: list[Rgb], game: list[list[Rgb]], seen: dict[int, tuple[int, float]], ramps: dict,
                  wyvern: bool = False) -> list[Rgb]:
    """16 colours: `base`, the class's, with the character's families taken from `ramps` (portrait_ramps). `game`: the
    palettes the game has for this same animation, `seen`: what `usage` read from it."""
    def moved(slot: int) -> bool:
        colours = [base[slot], *(g[slot] for g in game)]
        return not game or max(_distance(a, b) for a in colours for b in colours) >= MOVED

    def pixels(family: list[int]) -> int:
        return sum(seen[s][0] for s in family)

    def height(family: list[int]) -> float:
        return sum(seen[s][0] * seen[s][1] for s in family) / pixels(family)

    painted = []
    for family in families(base):
        slots = [s for s in family if moved(s) and s in seen]
        if not slots or pixels(slots) < SEEN_PIXELS or min(_hsv(base[s])[2] for s in slots) >= 0.97:
            continue
        if len(slots) == 1 and _hsv(base[slots[0]])[2] < 0.35:   # a lone dark colour is a shadow
            continue
        painted.append(slots)
    colours = list(base)
    # Skin comes first in a palette (a brown horse looks like it); its darkest shade is too dark to tell
    skin = [f for f in painted if f[0] <= LAST_SKIN_START and 2 * sum(_skin(base[s]) for s in f) >= len(f)]
    rest = sorted((f for f in painted if f not in skin), key=pixels, reverse=True)
    if skin:
        _paint(colours, max(skin, key=pixels), base, ramps["skin"])
    if not rest:
        return colours
    main, others = rest[0], rest[1:]
    hair = min(others, key=(lambda f: f[0]) if wyvern else height, default=None)
    if hair is not None:
        _paint(colours, hair, base, ramps["hair"])
        others.remove(hair)
    cloth = ramps["cloth"]
    if wyvern:
        ramp = next((r for r in [*cloth[:1], ramps["hair"]] if r and _hsv(r[len(r) // 2])[1] >= 0.25), None)
        for family in [main, *others] if ramp else []:
            _tint(colours, family, base, ramp[len(ramp) // 2], WYVERN_SATURATION)
    else:
        for family, ramp in zip([main, *others], cloth):
            _paint(colours, family, base, ramp)
    return colours
