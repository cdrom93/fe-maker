import io

import pytest
from PIL import Image

from fe_maker import ferepo
from fe_maker.decomp import mapsprites

# Fictional 16-color palette: color 0 (transparent) then 15 colors.
PALETTE = [(0, 0, 0)] + [(i * 16, 255 - i * 16, 100) for i in range(1, 16)]


def _png(img: Image.Image) -> bytes:
    buffer = io.BytesIO()
    img.save(buffer, "PNG")
    return buffer.getvalue()


def test_colors_go_to_the_palette_and_the_background_is_transparent():
    img = Image.new("RGB", (16, 48), (1, 2, 3))   # background: the top left pixel's color
    img.putpixel((5, 5), PALETTE[3])
    img.putpixel((6, 5), (PALETTE[7][0] + 2, PALETTE[7][1] - 1, PALETTE[7][2]))   # close to color 7
    stand, size, walk = mapsprites.convert(_png(img), None, PALETTE)
    assert size == "UNIT_ICON_SIZE_16x16" and walk is None
    out = Image.open(io.BytesIO(stand))
    assert out.mode == "P" and out.getpixel((0, 0)) == 0 and out.getpixel((5, 5)) == 3 and out.getpixel((6, 5)) == 7


def test_indexed_sheets_keep_index_0_transparent():
    img = Image.new("P", (32, 480), 0)
    img.putpalette([128, 160, 128] + [c for rgb in PALETTE[1:] for c in rgb])
    img.putpixel((3, 3), 4)
    _stand, _size, walk = mapsprites.convert(_png(Image.new("P", (16, 96), 0)), _png(img), PALETTE)
    out = Image.open(io.BytesIO(walk))
    assert out.getpixel((0, 0)) == 0 and out.getpixel((3, 3)) == 4   # source color 4 is the palette's color 4


def test_sizes_are_checked():
    with pytest.raises(mapsprites.MapSpriteError, match="badStandSize"):
        mapsprites.convert(_png(Image.new("RGB", (16, 16))), None, PALETTE)
    with pytest.raises(mapsprites.MapSpriteError, match="badWalkSize"):
        mapsprites.convert(_png(Image.new("RGB", (32, 96))), _png(Image.new("RGB", (32, 32))), PALETTE)
    with pytest.raises(mapsprites.MapSpriteError, match="notAnImage"):
        mapsprites.convert(b"not a png", None, PALETTE)


def test_rows_added_after_the_game_rows():
    # Fictional table in the decomp's shape: the last row has no comma.
    table = ("UnitIconWait unit_icon_wait_table[] = {\n\t{2, UNIT_ICON_SIZE_16x32, unit_icon_wait_A_sheet}, // 0\n"
             "\t{0, UNIT_ICON_SIZE_16x16, unit_icon_wait_B_sheet} // 1\n};\n")
    out = mapsprites.with_wait_rows(table, ["{2, UNIT_ICON_SIZE_16x16, unit_icon_wait_FEM_X_sheet}"])
    assert "unit_icon_wait_B_sheet}, // 1\n\t{2, UNIT_ICON_SIZE_16x16, unit_icon_wait_FEM_X_sheet}, // 2\n};" in out
    assert mapsprites.wait_rows(out)[-1].endswith("unit_icon_wait_FEM_X_sheet}")


def test_ferepo_pairs_standing_and_walking_sheets():
    base = "https://raw.githubusercontent.com/Klokinator/FE-Repo/refs/heads/main/Map%20Sprites/Infantry/"
    index = {ferepo.MAP_SPRITES: [base + "Hero%20%7BAnn%7D-stand.png", base + "Hero%20%7BAnn%7D-walk.png",
                                  base + "Monk%20%7BBob%7D-stand.png"]}
    entries, total = ferepo.map_sprites(index)
    assert total == 2
    hero = next(e for e in entries if e["name"] == "Hero")
    assert hero["authors"] == ["Ann"] and hero["walk"].endswith("-walk.png")
    assert next(e for e in entries if e["name"] == "Monk")["walk"] is None
