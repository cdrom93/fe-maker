import io
import struct

from PIL import Image

from fe_maker.decomp import banim


def _decomp(tmp_path):
    """A fictional animation in the decomp's layout: table, class settings, script, sheet, palette."""
    (tmp_path / "src").mkdir()
    (tmp_path / "src/banim_data.c").write_text(
        'struct BattleAnim banim_data[] = {\n'
        '\t{"tstm_sw1", &banim_tstm_sw1_modes_bin, &banim_tstm_sw1_motion_o},\n};\n', encoding="utf-8")
    (tmp_path / "src/data_banimconf.c").write_text(
        "CONST_DATA struct BattleAnimDef AnimConf_Test[] = {\n"
        "    {\n        .wtype = 0x0100 | ITYPE_SWORD,\n        .index = 0x0001,\n    },\n    { 0 }\n};\n", encoding="utf-8")
    (tmp_path / "data/banim").mkdir(parents=True)
    (tmp_path / "data/banim/banim_tstm_sw1_motion.s").write_text(
        "banim_tstm_sw1_oam_r:\n"
        "banim_tstm_sw1_oam_frame_0_r:\n"
        "\tbanim_frame_oam 0x0, 0x0, 0x0, -4, -8\n"        # 8 x 8, first tile
        "\tbanim_frame_oam 0x4000, 0x0, 0x1, 4, -8\n"      # 16 x 8, second tile
        "\tbanim_frame_end\n"
        "banim_tstm_sw1_script:\n"
        "banim_tstm_sw1_mode_stand:\n"
        "\tbanim_code_frame 7, banim_tstm_sw1_sheet_0, 0, banim_tstm_sw1_oam_frame_0_r - banim_tstm_sw1_oam_r\n"
        "\tbanim_code_end_mode\n", encoding="utf-8")
    (tmp_path / "graphics/banim").mkdir(parents=True)
    sheet = Image.new("P", (256, 64), 0)
    sheet.putpalette([0, 0, 0] * 256)
    for x in range(8, 24):
        sheet.putpixel((x, 0), 1)
    sheet.save(tmp_path / "graphics/banim/banim_tstm_sw1_sheet_0.png")
    colours = [0, 31] + [0] * 14   # colour 1: pure red (BGR555)
    (tmp_path / "graphics/banim/banim_tstm_sw1.agbpal").write_bytes(struct.pack("<16H", *colours) * 4)
    return tmp_path


def test_battle_animation_frames(tmp_path):
    decomp = _decomp(tmp_path)
    assert [(a.number, a.name, a.symbol) for a in banim.table(decomp)] == [(1, "tstm_sw1", "banim_tstm_sw1")]
    assert banim.configs(decomp) == {"AnimConf_Test": [{"weapon": "ITYPE_SWORD", "number": 1}]}
    assert banim.modes_of(decomp, "banim_tstm_sw1") == ["stand"]
    png, info = banim.mode_strip(decomp, "banim_tstm_sw1", "stand")
    assert info == {"durations": [7], "width": 24, "height": 8}

    strip = Image.open(io.BytesIO(png))
    assert strip.getpixel((0, 0))[3] == 0                 # colour 0 is transparent
    assert strip.getpixel((8, 0)) == (255, 0, 0, 255)     # the second sprite starts with tile 1's red row


def _frame(color_box):
    """A 248 x 160 FEditor frame: a filled rectangle (x0, y0, x1, y1) of colour 3."""
    image = Image.new("P", (248, 160), 0)
    image.putpalette([0, 0, 0, 255, 255, 255, 0, 0, 0, 255, 0, 0] + [0] * (768 - 12))
    x0, y0, x1, y1 = color_box
    for y in range(y0, y1):
        for x in range(x0, x1):
            image.putpixel((x, y), 3)
    return image


def test_feditor_script_converted():
    from fe_maker.decomp import banim_import as bi

    modes = [n for n in range(1, 13) if n not in (2, 4)]
    script = "".join(f"/// - Mode {n}\nC03   # a comment\n2 p- A.png\n1 p- B.png\n~~~\n" for n in modes)
    frames = {"A.png": _frame((140, 70, 160, 100)), "b.PNG": _frame((150, 80, 151, 81))}
    parsed = bi.parse_script(script)
    assert parsed.files == ["A.png", "B.png"] and parsed.modes[2] == parsed.modes[1]
    converted = bi.convert("banim_fem_9", script, {"A.png": frames["A.png"], "B.png": frames["b.PNG"]})
    assert converted.frames == 2 and len(converted.sheets) == 1 and len(converted.palette) == 128
    motion = converted.motion
    assert "banim_fem_9_mode_attack_close_back:" in motion and "\tbanim_code_85 0x3\n" in motion
    # frame B: one 8 x 8 sprite at (150 - 0x94, 80 - 0x58) on the right, mirrored on the left
    assert "banim_fem_9_oam_frame_1_r:\n\tbanim_frame_oam 0x0, 0x0, " in motion
    right = motion.split("banim_fem_9_oam_frame_1_r:\n")[1].split("\n")[0]
    left = motion.split("banim_fem_9_oam_frame_1_l:\n")[1].split("\n")[0]
    assert right.endswith(", 2, -8") and left.endswith(", -10, -8") and ", 0x1000, " in left
    sheet = Image.open(io.BytesIO(converted.sheets[0]))
    assert sheet.size == (256, 64) and sheet.mode == "P"
    import pytest

    with pytest.raises(bi.ImportError_, match="missingModes"):
        bi.parse_script("/// - Mode 1\n1 p- A.png\n~~~\n")


def test_animations_registered_after_the_game():
    from fe_maker.decomp import banim_import as bi

    sources = {bi.TABLE_FILE: 'banim_data[] = {\n\t{"a"},\n};\n__attribute__((section(".data.banim_array_len")))\nx;\n',
               bi.POINTERS_FILE: "#pragma once\n", bi.SHEETS_INCLUDE: "", bi.LINKER_SCRIPT: "# list\n"}
    out = bi.register(sources, [("banim_fem_1", 2)], first_number=202)
    assert '{"fem_1", &banim_fem_1_modes_bin,' in out[bi.TABLE_FILE] and "// 0xC9 (FE Maker)" in out[bi.TABLE_FILE]
    assert out[bi.TABLE_FILE].index("fem_1") < out[bi.TABLE_FILE].index("banim_array_len")
    assert "extern char banim_fem_1_agbpal;" in out[bi.POINTERS_FILE]
    assert out[bi.SHEETS_INCLUDE] == "\t.extern banim_fem_1_sheet_0\n\t.extern banim_fem_1_sheet_1\n"
    assert "graphics/banim/banim_fem_1_sheet_1.4bpp.lz\n" in out[bi.LINKER_SCRIPT]
    assert "data/banim/banim_fem_1_motion.o|.data.script>lz\n" in out[bi.LINKER_SCRIPT]
    source, names = bi.class_configs("// confs\n", {"CLASS_MYRMIDON": [{"weapon": "ITYPE_SWORD", "number": 202},
                                                                       {"weapon": "ITEM_SWORD_KILLER", "number": 3}]})
    assert names == {"CLASS_MYRMIDON": "AnimConf_FEM_MYRMIDON"}
    assert ".wtype = 0x0100 | ITYPE_SWORD,\n        .index = 0x00CA," in source and ".wtype = ITEM_SWORD_KILLER," in source


def test_other_armies_recoloured():
    from fe_maker.decomp import banim_import as bi

    player = [(0, 0, 0), (82, 131, 255), (180, 213, 246), (200, 50, 50)] + [(0, 0, 0)] * 12
    enemy = bi.recolour(player, "enemy")
    assert enemy[1][0] > 200 and enemy[1][2] < 100       # the strong blue turns red
    assert enemy[2] == player[2] and enemy[3] == player[3]   # light blue (metal) and other colours stay
    other = bi.recolour(player, "other")
    assert max(other[1]) - min(other[1]) < 60            # greyed
    image = Image.new("P", (8, 8))
    image.putpalette([c for rgb in player for c in rgb] + [0] * 720)
    data = bi.palette_bytes(image, {"ally": [10, 200, 10] * 16})
    assert len(data) == 128 and data[64:66] == struct.pack("<H", (10 >> 3) | (200 >> 3) << 5 | (10 >> 3) << 10)
