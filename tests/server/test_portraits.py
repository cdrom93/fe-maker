import io
import shutil

import pytest
from PIL import Image

from fe_maker.decomp import portraits as pt
from fe_maker.decomp.gamedata import DecompData

# Fictional portrait sheets drawn by the tests (flat colors), not taken from the game.
COLORS = [(160, 200, 160), (40, 40, 40), (200, 150, 120), (250, 250, 250), (120, 40, 40)]


def _sheet(mouth=(2, 6), eyes=(3, 4)) -> Image.Image:
    img = Image.new("RGB", pt.SHEET_SIZE, COLORS[0])
    img.paste(COLORS[2], (16, 8, 80, 80))                    # the face (inside the parts the game shows)
    for k, (x, y) in enumerate(pt.MOUTHS_AT):                # mouth frames, one on the face
        img.paste(COLORS[4], (x + 8, y + 4, x + 24, y + 8 + k % 3))
    mx, my = 8 * mouth[0], 8 * mouth[1]
    img.paste(img.crop((0, 80, 32, 96)), (mx, my))
    for x, y in pt.EYES_AT:
        img.paste(COLORS[1], (x + 4, y + 6, x + 28, y + 9))
    ex, ey = 8 * eyes[0], 8 * eyes[1]
    img.paste(img.crop((96, 48, 128, 64)), (ex, ey))
    img.paste(COLORS[3], (100, 20, 124, 44))                 # mini portrait
    return img


def test_indexed_sheet_and_errors():
    sheet, colors = pt.indexed(_sheet())
    assert pt.cut_pixels(sheet) == 0
    assert colors[0] == COLORS[0] and len(colors) == 5 and sheet.getpixel((0, 0)) == 0
    with pytest.raises(pt.PortraitError, match="badSize"):
        pt.indexed(Image.new("RGB", (96, 80)))
    noisy = Image.new("RGB", pt.SHEET_SIZE)
    noisy.putdata([(i % 256, i // 256 % 256, 0) for i in range(128 * 112)])
    with pytest.raises(pt.PortraitError, match="tooManyColors"):
        pt.indexed(noisy)


def test_detect_mouth_and_eyes():
    sheet, _ = pt.indexed(_sheet(mouth=(3, 5), eyes=(2, 3)))
    assert pt.detect(sheet) == {"mouth": [3, 5], "eyes": [2, 3]}


def test_files_round_trip(tmp_path):
    sheet, _ = pt.indexed(_sheet())
    files = pt.from_sheet(sheet)
    folder = tmp_path / "graphics" / "portrait"
    folder.mkdir(parents=True)
    for part in ("tileset", "mouth", "chibi"):
        (folder / f"portrait_Test_{part}.png").write_bytes(files[part])
        assert Image.open(io.BytesIO(files[part])).mode == "P"
    (folder / "portrait_Test_palette.agbpal").write_bytes(files["palette"])
    assert len(files["palette"]) == 32
    again = pt.to_sheet(tmp_path, "Test")
    assert again.tobytes() == sheet.tobytes()


def test_imported_portrait_reaches_the_overlay(tmp_path, decomp_dir):
    decomp = tmp_path / "decomp"
    shutil.copytree(decomp_dir, decomp)
    (decomp / "src" / "portrait_data.c").write_text(
        "struct FaceData CONST_DATA portrait_data[] =\n{\n"
        "\t{NULL, NULL, NULL, NULL, 0, 0, 0, 0, 0, FACE_BLINK_NORMAL}, // 0\n"
        "\t{portrait_Test_tileset, portrait_Test_chibi, portrait_Test_palette, portrait_Test_mouth, 0, 2, 5, 3, 3, "
        "FACE_BLINK_NORMAL}, // 1\n};\n", encoding="utf-8")
    assets = tmp_path / "assets"
    (assets / "portraits").mkdir(parents=True)
    _sheet().save(assets / "portraits" / "1.png")
    d = DecompData(decomp)
    d.apply_portraits({"2": {"file": "portraits/1.png", "mouth": [2, 6], "eyes": [3, 4]}}, assets)
    files = d.changed_files()
    assert "graphics/portrait/portrait_Test_tileset.png" in files and "graphics/portrait/portrait_Test_palette.agbpal" in files
    assert "portrait_Test_mouth, 0, 2, 6, 3, 4, FACE_BLINK_NORMAL}" in files["src/portrait_data.c"]
