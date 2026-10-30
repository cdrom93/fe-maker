from PIL import Image

from fe_maker.decomp import chaptitle, fonts


def test_title_strip(decomp_dir, tmp_path, monkeypatch):
    # A fictional font sheet: the letter "H" is a vertical bar of ink.
    sheet = Image.new("RGBA", (256, 256), (0, 0, 0, 0))
    cell = ord("H")
    for y in range(4, 10):
        sheet.putpixel(((cell % 16) * 16 + 2, (cell // 16) * 16 + y), fonts.SHEET_COLORS[chaptitle.INK])
    monkeypatch.setattr(chaptitle, "_letters", lambda _dir: (sheet, {cell: 5}))
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
    assert chaptitle.text_width(decomp_dir, "H", 0) < chaptitle.text_width(decomp_dir, "H")
