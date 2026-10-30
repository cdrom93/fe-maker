from PIL import Image

from fe_maker.decomp import chaptitle, fonts


def test_title_strip(decomp_dir, tmp_path, monkeypatch):
    # A fictional font sheet: the letter "H" is a vertical bar of ink.
    sheet = Image.new("RGBA", (256, 256), (0, 0, 0, 0))
    cell = ord("H")
    for y in range(4, 10):
        sheet.putpixel(((cell % 16) * 16 + 2, (cell // 16) * 16 + y), fonts.SHEET_COLORS[chaptitle.INK])
    monkeypatch.setattr(chaptitle, "_letters", lambda _dir: (sheet, {cell: 5}))
    monkeypatch.setattr(fonts, "char_byte", lambda c: ord(c))
    template = tmp_path / "template.png"
    blank = Image.new("P", chaptitle.SIZE, 0)
    blank.putpalette([i * 5 for i in range(48)])   # 16 colors, as the game's strips
    blank.save(template)
    (tmp_path / "strip.png").write_bytes(chaptitle.strip(decomp_dir, "H", template))
    img = Image.open(tmp_path / "strip.png")
    assert img.size == chaptitle.SIZE and img.mode == "P"
    assert {i for _n, i in img.getcolors()} == {0, 1, 3, 5, 6}   # background, stroke (2 pixels), outline
    box = img.point(lambda i: 255 if i == 1 else 0).getbbox()
    assert box[1] == 1 and box[3] == 7   # the letters start on row 1


def _letter(pixels, left, height, color=1):
    """A fictional letter of a strip: a block of ink with its outline."""
    for x in range(left, left + 4):
        for y in range(2, 2 + height):
            pixels[x, y] = color
    for y in range(2, 2 + height):
        pixels[left - 1, y] = 5
        pixels[left + 4, y] = 6


def _strip_with(heights):
    img = Image.new("P", chaptitle.SIZE, 0)
    for k, height in enumerate(heights):
        _letter(img.load(), 10 + k * 8, height)
    return img.load()


def test_letters_are_learned_from_the_game_strips():
    # a = 4 rows, b = 6, c = 8; two strips agree on a and b, c is found between known letters
    a, b, c = 4, 6, 8
    strips = [("ab", _strip_with([a, b])), ("ba", _strip_with([b, a])), ("acb", _strip_with([3, 3, a, c, b, a][:5]))]
    known = chaptitle._learn(strips)
    assert set(known) >= {"a", "b", "c"}
    assert sum(1 for color in known["c"].cells.values() if color == 1) == 4 * c
    assert known["a"].width == 4


def test_an_accent_is_added_above_a_letter_with_room():
    base = chaptitle.Glyph({(0, 6): 1, (1, 6): 1}, 2)
    accented = chaptitle._accented(base, "\u0301")
    assert len(accented.cells) > len(base.cells) and accented.width == 2
    high = chaptitle.Glyph({(0, 1): 1, (1, 1): 1}, 2)
    assert chaptitle._accented(high, "\u0301") is high
