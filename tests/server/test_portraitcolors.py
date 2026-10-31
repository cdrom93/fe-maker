from PIL import Image

from fe_maker.decomp import portraitcolors

BLACK = (40, 40, 40)
SKIN = [(130, 80, 60), (240, 170, 110), (255, 230, 200)]
HAIR = [(40, 120, 40), (90, 220, 60)]
ARMOUR = [(30, 30, 160), (60, 90, 230), (120, 160, 255), (170, 210, 255)]
HORSE = [(90, 60, 30), (150, 100, 50), (200, 150, 90)]
BASE = [(0, 0, 0), *SKIN, *HAIR, *ARMOUR, *HORSE, BLACK, (255, 255, 255)]
SEEN = {slot: (50, 20.0) for slot in range(1, 15)}
SEEN.update({4: (20, 2.0), 5: (20, 2.0)})                 # the hair is at the top
SEEN.update({slot: (200, 15.0) for slot in (6, 7, 8, 9)})  # the armour is the largest part
SEEN.update({slot: (300, 30.0) for slot in (10, 11, 12)})  # so would the horse be, but the game never changes it

RED = [(100, 0, 0), (180, 20, 20), (240, 80, 80)]
GOLD = [(120, 90, 20), (240, 210, 60)]
RAMPS = {"hair": GOLD, "skin": [(100, 60, 40), (220, 170, 130), (250, 220, 190)], "cloth": [RED, [(40, 40, 120)]]}


def game_palette():
    other = list(BASE)
    other[4:6] = [(120, 40, 40), (200, 80, 60)]
    other[6:10] = [(30, 90, 30), (60, 150, 60), (120, 200, 120), (170, 230, 170)]
    return other


def test_the_rider_takes_the_portrait_and_the_horse_stays():
    colours = portraitcolors.from_portrait(BASE, [game_palette()], SEEN, RAMPS)
    assert colours[10:13] == HORSE
    assert colours[4:6] == GOLD
    assert all(c[0] > 2 * c[2] for c in colours[6:10])          # three reds for four shades: the armour's own relief
    assert [portraitcolors._hsv(c)[2] for c in colours[6:10]] == [portraitcolors._hsv(c)[2] for c in ARMOUR]
    assert colours[1:4] == SKIN                                  # the game keeps skin colours: not the character's
    assert colours[13:] == [BLACK, (255, 255, 255)]


def test_without_game_palettes_the_largest_family_is_the_clothing():
    colours = portraitcolors.from_portrait(BASE, [], SEEN, RAMPS)
    assert colours[10] == RED[0] and colours[12] == RED[2]


def test_a_skin_with_a_dark_shade_is_skin_without_game_palettes():
    base = [(0, 0, 0), (255, 197, 148), (197, 131, 82), (115, 74, 49), *ARMOUR, *[BLACK] * 7, (255, 255, 255)]
    seen = {slot: (500, 20.0) for slot in (1, 2, 3)} | {slot: (100, 20.0) for slot in (4, 5, 6, 7)}
    colours = portraitcolors.from_portrait(base, [], seen, RAMPS)
    assert colours[1:4] == list(reversed(RAMPS["skin"]))
    assert all(c[0] > 2 * c[2] for c in colours[4:8])


def test_a_wyvern_is_all_of_the_clothes_colour_and_its_rider_keeps_the_hair():
    wings = [(150, 200, 200), (200, 240, 240)]
    body = [(40, 60, 90), (70, 90, 120), (110, 140, 160), (150, 180, 200)]
    base = [(0, 0, 0), (60, 100, 240), (90, 200, 255), *SKIN, *wings, *body, *[BLACK] * 3, (255, 255, 255)]
    other = list(base)
    other[1:3] = [(120, 120, 60), (200, 200, 120)]
    other[6:8] = [(180, 180, 90), (220, 220, 140)]
    other[8:12] = [(100, 40, 20), (140, 80, 50), (190, 120, 90), (230, 170, 140)]
    seen = {1: (20, 25.0), 2: (20, 25.0), **{s: (200, 10.0) for s in (6, 7)}, **{s: (400, 20.0) for s in (8, 9, 10, 11)}}
    colours = portraitcolors.from_portrait(base, [other], seen, RAMPS, wyvern=True)
    assert colours[1:3] == GOLD
    assert all(c[0] > 2 * c[2] for c in colours[6:12])
    assert [portraitcolors._hsv(c)[2] for c in colours[8:12]] == [portraitcolors._hsv(c)[2] for c in body]
    pale = dict(RAMPS, cloth=[[(240, 240, 240)]])
    assert portraitcolors.from_portrait(base, [other], seen, pale, wyvern=True)[8][0] > 0
    assert portraitcolors.from_portrait(base, [other], seen, pale, wyvern=True)[8][2] < 60     # the hair's gold, not white


def test_portrait_ramps_read_by_place():
    face = Image.new("RGBA", portraitcolors.FACE_SIZE, (0, 0, 0, 0))
    for box, colour in (((20, 0, 76, 24), GOLD[1]), ((34, 34, 62, 58), SKIN[1]), ((8, 64, 88, 80), RED[1])):
        face.paste(colour + (255,), box)
    ramps = portraitcolors.portrait_ramps(face)
    assert ramps == {"hair": [GOLD[1]], "skin": [SKIN[1]], "cloth": [[RED[1]]]}
    face.paste((60, 30, 90, 255), (34, 34, 40, 58))
    assert portraitcolors.portrait_ramps(face)["skin"] == [SKIN[1]]


def test_usage_reads_the_coded_colours():
    strip = Image.new("RGBA", (4, 4), (0, 0, 0, 0))
    strip.putpixel((1, 1), portraitcolors.CODED[3] + (255,))
    strip.putpixel((2, 3), portraitcolors.CODED[5] + (255,))
    strip.putpixel((3, 3), portraitcolors.CODED[5] + (255,))
    assert portraitcolors.usage(strip, 3) == {3: (1, 0.0), 5: (1, 2.0)}
