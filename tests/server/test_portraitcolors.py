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
    assert colours[6] == RED[0] and colours[9] == RED[2]         # three reds for four shades, spread over them
    far = dict(RAMPS, cloth=[[(10, 0, 0), (40, 5, 5), (60, 10, 10)]], hair=[(20, 0, 0), (50, 10, 10)])
    dark = portraitcolors.from_portrait(BASE, [game_palette()], SEEN, far)
    assert [portraitcolors._hsv(c)[2] for c in dark[6:10]] == [portraitcolors._hsv(c)[2] for c in ARMOUR]   # its own relief
    assert dark[4:6] == far["hair"]                              # but the hair stays what the portrait shows
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


def test_hair_glued_to_the_skin_in_the_palette_is_still_hair():
    """Like the Cleric: slots 3-9 are all warm shades, the hair is the part of them the game changes."""
    base = [(0, 0, 0), (255, 255, 255), (255, 255, 213), (255, 197, 148), (115, 74, 49), (246, 189, 156), (197, 123, 90),
            (115, 74, 49), *ARMOUR, *[BLACK] * 4]
    other = list(base)
    other[5:8] = [(250, 230, 120), (200, 170, 60), (120, 90, 30)]
    seen = {3: (6, 6.0), 4: (15, 11.0), 5: (2, 0.0), 6: (9, 2.0), 7: (18, 2.0), 8: (100, 12.0), 9: (100, 12.0)}
    pink = [(192, 88, 112), (224, 144, 176), (240, 200, 216)]
    colours = portraitcolors.from_portrait(base, [other], seen, dict(RAMPS, hair=pink))
    assert colours[5:8] == [pink[2], pink[1], pink[0]]
    assert colours[3:5] == base[3:5]


def test_a_class_with_a_helmet_has_its_clothes_in_slots_6_and_7():
    base = list(BASE)
    other = game_palette()
    seen = {4: (10, 2.0), 5: (10, 2.0), 6: (54, 10.0), 7: (61, 10.0), 8: (300, 15.0), 9: (300, 15.0)}
    assert portraitcolors.from_portrait(base, [other], seen, RAMPS)[6] != RAMPS["hair"][0]


def wyvern_palette():
    wings = [(222, 222, 164), (156, 156, 106), (205, 197, 148)]
    body = [(123, 238, 213), (74, 189, 156), (65, 139, 106), (41, 98, 82)]
    return [(172, 213, 164), (255, 255, 255), (57, 106, 230), (41, 189, 255), *SKIN, *wings, *body, (65, 49, 32), BLACK]


def test_a_wyvern_keeps_its_wings_apart_from_its_body():
    base = wyvern_palette()
    other = list(base)
    other[2:4] = [(123, 123, 57), (205, 205, 123)]
    other[7:10] = [(189, 189, 123), (123, 123, 57), (213, 213, 98)]
    other[10:14] = [(230, 172, 139), (189, 123, 90), (139, 82, 49), (106, 41, 16)]
    seen = {slot: (100, 20.0) for slot in (2, 3, 7, 8, 9, 10, 11, 12, 13)}
    colours = portraitcolors.from_portrait(base, [other], seen, RAMPS, wyvern=True)
    assert colours[2:4] == GOLD
    value = [portraitcolors._hsv(c)[2] for c in colours[10:14]]
    assert value == [portraitcolors._hsv(c)[2] for c in base[10:14]]               # the body keeps its shades, in red
    assert all(c[0] > c[1] and c[0] > c[2] for c in colours[10:14])
    assert all(c[0] > c[2] and c[1] > c[2] for c in colours[7:10])                 # the wings in the gold of the hair

    pale = portraitcolors.from_portrait(base, [other], seen, dict(RAMPS, cloth=[[(240, 240, 240)]]), wyvern=True)
    assert all(c[0] > c[2] and c[1] > c[2] for c in pale[10:14])                   # white clothes: the hair for the body
    same = portraitcolors.from_portrait(base, [other], seen, dict(RAMPS, hair=RED), wyvern=True)
    assert same[7] != same[10] and portraitcolors._hsv(same[7])[0] != portraitcolors._hsv(same[10])[0]


def test_portrait_ramps_read_by_place():
    face = Image.new("RGBA", portraitcolors.FACE_SIZE, (0, 0, 0, 0))
    for box, colour in (((20, 0, 76, 24), GOLD[1]), ((34, 34, 62, 58), SKIN[1]), ((8, 64, 88, 80), RED[1])):
        face.paste(colour + (255,), box)
    ramps = portraitcolors.portrait_ramps(face)
    assert ramps == {"hair": [GOLD[1]], "skin": [SKIN[1]], "cloth": [[RED[1]]]}
    face.paste((60, 30, 90, 255), (34, 34, 40, 58))
    ramps = portraitcolors.portrait_ramps(face)
    assert ramps["skin"] == [SKIN[1]] and ramps["hair"] == [GOLD[1]]
    face.paste((30, 30, 60, 255), (8, 64, 20, 80))
    assert portraitcolors.portrait_ramps(face)["cloth"] == [[RED[1]]]    # too dark to be anything but a shadow


def test_hair_under_a_crown_of_flowers_is_found_by_its_hue():
    face = Image.new("RGBA", portraitcolors.FACE_SIZE, (0, 0, 0, 0))
    face.paste((70, 190, 130, 255), (20, 0, 76, 10))        # the crown
    face.paste((240, 200, 216, 255), (34, 34, 62, 40))      # the fringe, over the face
    face.paste((224, 144, 176, 255), (20, 10, 76, 30))
    face.paste((224, 144, 176, 255), (4, 10, 20, 30))       # the hair on the sides
    face.paste((192, 88, 112, 255), (76, 10, 92, 30))
    face.paste(SKIN[1] + (255,), (34, 40, 62, 58))
    assert portraitcolors.portrait_ramps(face)["hair"] == [(192, 88, 112), (224, 144, 176), (240, 200, 216)]


def test_usage_reads_the_coded_colours():
    strip = Image.new("RGBA", (4, 4), (0, 0, 0, 0))
    strip.putpixel((1, 1), portraitcolors.CODED[3] + (255,))
    strip.putpixel((2, 3), portraitcolors.CODED[5] + (255,))
    strip.putpixel((3, 3), portraitcolors.CODED[5] + (255,))
    assert portraitcolors.usage(strip, 3) == {3: (1, 0.0), 5: (1, 2.0)}
