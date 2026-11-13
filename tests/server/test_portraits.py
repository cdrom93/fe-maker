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


def test_face_with_expression():
    img = _sheet(mouth=(2, 6), eyes=(3, 4))
    sheet, _ = pt.indexed(img)
    plain, closed, smile = (Image.open(io.BytesIO(pt.face_png(sheet, positions={"mouth": [2, 6], "eyes": [3, 4]}, **k)))
                            for k in ({}, {"eyes": "closed"}, {"smile": True}))
    eye_cells = [(24 + x, 32 + y) for x in range(32) for y in range(16)]
    mouth_cells = [(16 + x, 48 + y) for x in range(32) for y in range(16)]
    assert [closed.getpixel(c) for c in eye_cells] == [sheet.crop((96, 64, 128, 80)).convert("RGBA").getpixel((x - 24, y - 32))
                                                       if sheet.getpixel((96 + x - 24, 64 + y - 32)) else plain.getpixel((x, y))
                                                       for x, y in eye_cells]
    sx, sy = pt.MOUTHS_AT[pt.SMILE_MOUTH]
    assert all(smile.getpixel((x, y)) == sheet.convert("RGBA").getpixel((sx + x - 16, sy + y - 48))
               for x, y in mouth_cells if sheet.getpixel((sx + x - 16, sy + y - 48)))
    assert [smile.getpixel(c) for c in eye_cells] == [plain.getpixel(c) for c in eye_cells]


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


def test_new_portraits_are_added_after_the_game_ones(tmp_path, decomp_dir):
    decomp = tmp_path / "decomp"
    shutil.copytree(decomp_dir, decomp)
    (decomp / "src" / "portrait_data.c").write_text(
        "struct FaceData CONST_DATA portrait_data[] =\n{\n"
        "\t{portrait_Test_tileset, portrait_Test_chibi, portrait_Test_palette, portrait_Test_mouth, 0, 2, 5, 3, 3, "
        "FACE_BLINK_NORMAL}, // 0\n};\n", encoding="utf-8")
    (decomp / "include").mkdir(exist_ok=True)
    (decomp / "include" / "portrait_pointer.h").write_text("extern unsigned char portrait_Test_tileset[];\n", encoding="utf-8")
    (decomp / "data" / "data_portrait.s").write_text(
        '\t.global portrait_Test_tileset\nportrait_Test_tileset:\n\t.incbin "graphics/portrait/portrait_Test_tileset.4bpp.fk"\n',
        encoding="utf-8")
    assert pt.first_new_id(decomp) == 2 and pt.is_new(decomp, 3) and not pt.is_new(decomp, 1)
    assets = tmp_path / "assets"
    (assets / "portraits").mkdir(parents=True)
    _sheet().save(assets / "portraits" / "3.png")
    d = DecompData(decomp)
    d.apply_portraits({"3": {"file": "portraits/3.png", "mouth": [2, 6], "eyes": [3, 4], "name": "Amelia"}}, assets)
    files = d.changed_files()
    assert "graphics/portrait/portrait_New3_tileset.png" in files and "graphics/portrait/portrait_New3_palette.agbpal" in files
    table = files["src/portrait_data.c"]
    # id 2 is unused: the mystery portrait keeps the table contiguous; id 3 is the new one.
    assert "portrait_Mystery_1_mouth, 0, 2, 5, 3, 3, FACE_BLINK_NORMAL}, // 1\n" in table
    assert "{portrait_New3_tileset, portrait_New3_chibi, portrait_New3_palette, portrait_New3_mouth, 0, 2, 6, 3, 4, " \
        "FACE_BLINK_NORMAL}, // 2\n};" in table
    assert 'portrait_New3_chibi:\n\t.incbin "graphics/portrait/portrait_New3_chibi.4bpp.lz"' in files["data/data_portrait.s"]
    assert files["data/data_portrait.s"].startswith("\t.global portrait_Test_tileset")
    assert "extern unsigned short portrait_New3_palette[];" in files["include/portrait_pointer.h"]
    assert "[FID_New3] = 0x03, 0x01" in files["texts/textdefs.txt"]
    from fe_maker.decomp.dialogues import read_faces
    assert read_faces(files["texts/textdefs.txt"])["FID_New3"] == 3


def test_new_portraits_validation(tmp_path, decomp_dir):
    from fe_maker.validation import validate

    d = DecompData(decomp_dir)
    first = pt.first_new_id(decomp_dir)
    chars = d.export_characters()
    chars[0]["portraitId"] = first
    dialogues = {"messages": {"0x1": [{"kind": "face", "pos": "MidLeft", "face": pt.face_code(first)}]}}
    problems = validate(chars, d.export_items(), d, dialogues=dialogues)
    codes = {(p.field, p.code) for p in problems}
    assert ("portraitId", "unknownPortrait") in codes and ("face", "unknownFace") in codes
    _sheet().save(tmp_path / "a.png")
    added = {str(first): {"file": "a.png", "mouth": [2, 6], "eyes": [3, 4], "name": "Amelia"}}
    problems = validate(chars, d.export_items(), d, dialogues=dialogues, portraits=added, assets_dir=tmp_path)
    assert not [p for p in problems if p.code in ("unknownPortrait", "unknownFace")]


def test_the_acting_units_portrait_in_a_dialogue(decomp_dir):
    """Ticket 73: FID_Active, the portrait of the unit visiting a village, is a portrait dialogues may show."""
    from fe_maker.decomp.dialogues import ACTIVE_FACE
    from fe_maker.validation import validate

    d = DecompData(decomp_dir)
    dialogues = {"messages": {"0x1": [{"kind": "face", "pos": "MidLeft", "face": ACTIVE_FACE}]}}
    problems = validate(d.export_characters(), d.export_items(), d, dialogues=dialogues)
    assert not [p for p in problems if p.code == "unknownFace"]
