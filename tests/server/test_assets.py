import io

from PIL import Image

from fe_maker.decomp import assets


def _make_sprite(tmp_path):
    """A fictional 16x32 map sprite whose only visible pixels are a 3x2 block."""
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "unit_icon_wait_data.c").write_text(
        "{ 0, UNIT_ICON_SIZE_16x32, gUnitIconWait_Test },\n", encoding="utf-8")
    sheets = tmp_path / "graphics" / "unit_icon" / "wait"
    sheets.mkdir(parents=True)
    sheet = Image.new("P", (16, 96), 0)
    for x in range(5, 8):
        for y in range(20, 22):
            sheet.putpixel((x, y), 1)
    sheet.save(sheets / "gUnitIconWait_Test.png")
    palettes = tmp_path / "graphics" / "unit_icon" / "palette"
    palettes.mkdir()
    (palettes / "unit_icon_pal_player.agbpal").write_bytes(b"\x00\x00\x1f\x00" + b"\x00" * 28)
    assets.map_sprite_table.cache_clear()
    return tmp_path


def test_map_sprite_frame_and_trim(tmp_path):
    decomp = _make_sprite(tmp_path)
    full = Image.open(io.BytesIO(assets.map_sprite(decomp, 0)))
    assert full.size == (32, 64)
    trimmed = Image.open(io.BytesIO(assets.map_sprite(decomp, 0, trim=True))).convert("RGBA")
    assert trimmed.size == (6, 4)  # 3x2 visible pixels at x2
    assert trimmed.getpixel((0, 0)) == (255, 0, 0, 255)
