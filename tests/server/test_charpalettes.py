import pytest

from fe_maker.decomp import banim_import, charpalettes

CONFIG = """CONST_DATA u8 gAnimCharaPalConfig[0x100][7] = {
    [CHARACTER_EIRIKA - 1] = {
        [1] = CLASS_EIRIKA_LORD,
    },
    [CHARACTER_SETH - 1] = {
        [3] = CLASS_PALADIN,
    },
};

CONST_DATA u8 gAnimCharaPalConfigUnused[0x100][7] = {0};

 CONST_DATA u8 gAnimCharaPalIt[0x100][7] = {
    /* Data is index in character_battle_animation_palette_table */
    [CHARACTER_EIRIKA - 1] = {
        [1] = 0,
    },
    [CHARACTER_SETH - 1] = {
        [3] = 0x2,
    },
};
"""
TABLE = """#include "banim_data.h"

struct BattleAnimCharaPal character_battle_animation_palette_table[] = {
\t{"mer", banim_pal_mer}, // 0
\t{"set", banim_pal_set}, // 1
};

DataBlockHead banim_pal_head = {
};
"""
DATA = '\t.section .data\n\t.global banim_pal_mer\nbanim_pal_mer:\n\t.incbin "x.agbpal.lz"\n\t.align 2, 0\n'
SOURCES = {charpalettes.CONFIG_FILE: CONFIG, charpalettes.TABLE_FILE: TABLE, charpalettes.DATA_FILE: DATA}
RED = [["#ff0000"] * 16] * 5


def test_the_game_slots_are_read():
    assert charpalettes.game_slots(CONFIG) == {"CHARACTER_SETH": {"CLASS_PALADIN": 1}}   # row 0: Eirika has none
    assert charpalettes.game_palettes(TABLE) == ["banim_pal_mer", "banim_pal_set"]


def test_colours_go_through_the_game_format_unchanged():
    assert charpalettes.to_hex(0x7FFF) == "#ffffff" and charpalettes.to_hex(0) == "#000000"
    for colour in range(0, 0x8000, 37):
        hexa = charpalettes.to_hex(colour)
        assert int.from_bytes(charpalettes.encode([[hexa] * 16] * 5)[:2], "little") == colour


def test_a_new_palette_is_added_after_the_game_s():
    files, first = charpalettes.apply(SOURCES, {"CHARACTER_SETH": {"CLASS_PALADIN": RED}})
    assert first == 2
    assert 'extern char banim_pal_fem_2[];' in files[charpalettes.TABLE_FILE]
    assert '{"set", banim_pal_set}, // 1\n\t{"fem", banim_pal_fem_2}, // 2\n};' in files[charpalettes.TABLE_FILE]
    assert 'banim_pal_fem_2.agbpal.lz"' in files[charpalettes.DATA_FILE]
    assert len(files[f"{charpalettes.PALETTE_DIR}/banim_pal_fem_2.agbpal"]) == 160
    assert charpalettes.game_slots(files[charpalettes.CONFIG_FILE])["CHARACTER_SETH"] == {"CLASS_PALADIN": 2}


def test_same_colours_share_a_palette_and_new_characters_get_an_entry():
    edits = {"CHARACTER_EIRIKA": {"CLASS_EIRIKA_LORD": RED}, "CHARACTER_NEW_30": {"CLASS_NEW_80": RED}}
    files, _first = charpalettes.apply(SOURCES, edits)
    slots = charpalettes.game_slots(files[charpalettes.CONFIG_FILE])
    assert slots["CHARACTER_EIRIKA"] == {"CLASS_EIRIKA_LORD": 2} and slots["CHARACTER_NEW_30"] == {"CLASS_NEW_80": 2}
    assert slots["CHARACTER_SETH"] == {"CLASS_PALADIN": 1}
    assert files[charpalettes.TABLE_FILE].count('"fem"') == 1


def test_null_goes_back_to_the_class_colours():
    files, first = charpalettes.apply(SOURCES, {"CHARACTER_SETH": {"CLASS_PALADIN": None}})
    assert first is None and charpalettes.TABLE_FILE not in files
    assert "CHARACTER_SETH" not in charpalettes.game_slots(files[charpalettes.CONFIG_FILE])


def test_more_classes_than_the_game_has_slots_is_refused():
    edits = {"CHARACTER_SETH": {f"CLASS_{n}": RED for n in range(8)}}
    with pytest.raises(charpalettes.PaletteError):
        charpalettes.apply(SOURCES, edits)


def test_imported_animations_keep_their_colours_but_not_over_a_new_palette():
    source = banim_import._UNIQUE_PALETTE * 2
    assert "chara_pal >=" not in banim_import.without_unique_palettes(source, 0x200)
    assert "(bid < 0x200 || chara_pal >= 108)" in banim_import.without_unique_palettes(source, 0x200, 108)
