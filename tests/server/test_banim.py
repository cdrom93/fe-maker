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
    import io
    strip = Image.open(io.BytesIO(png))
    assert strip.getpixel((0, 0))[3] == 0                 # colour 0 is transparent
    assert strip.getpixel((8, 0)) == (255, 0, 0, 255)     # the second sprite starts with tile 1's red row
