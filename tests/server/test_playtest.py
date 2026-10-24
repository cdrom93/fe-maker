import pytest

from fe_maker import playtest

# Fictional excerpt in the layout of a GNU ld map file.
MAP = """ .bss           0x0202bcb0      0x4a0 build/bmsave.o
                0x0202bcf0                gPlaySt
                0x0202be4c                gUnitArrayBlue
 *(.text)
 .text          0x08000000      0x12c build/crt0.o
                0x080000c0                AgbMain
                0x080000c4                SomeFunction ; comment
"""


def test_symbols_are_read_from_the_linker_map(tmp_path):
    path = tmp_path / "fireemblem8.map"
    path.write_text(MAP)
    symbols = playtest.read_symbols(path)
    assert symbols == {"gPlaySt": 0x0202BCF0, "gUnitArrayBlue": 0x0202BE4C, "AgbMain": 0x080000C0}


def test_key_mask():
    assert playtest.key_mask(["A"]) == 1
    assert playtest.key_mask(["START", "L"]) == (1 << 3) | (1 << 9)
    with pytest.raises(playtest.PlaytestError):
        playtest.key_mask(["X"])
