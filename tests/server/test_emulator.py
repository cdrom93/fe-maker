import pytest

from fe_maker.emulator import DEFAULT_KEYS, EmulatorError, qt_key_code, validate_keys, write_key_bindings


def test_qt_key_codes():
    assert qt_key_code("A") == 65
    assert qt_key_code("z") == 90
    assert qt_key_code("Enter") == 0x01000004
    assert qt_key_code("Space") == 32
    assert qt_key_code("ArrowUp") == 0x01000013
    assert qt_key_code("F1") == 0x01000030


def test_write_keeps_other_settings(tmp_path):
    config = tmp_path / "config.ini"
    config.write_text(
        "[gba.input.SDLB]\nkeyA=-1\n\n[gba.input.QT_K]\nkeyA=88\nkeyB=90\n\n[ports.qt]\nwidth=480\n",
        encoding="utf-8",
    )
    write_key_bindings(DEFAULT_KEYS, config)
    text = config.read_text(encoding="utf-8")
    assert "keyA=65" in text
    assert "keyStart=16777220" in text
    assert "keySelect=32" in text
    assert "[gba.input.SDLB]\nkeyA=-1" in text
    assert "width=480" in text


def test_write_creates_config(tmp_path):
    config = tmp_path / "mGBA" / "config.ini"
    write_key_bindings(DEFAULT_KEYS, config)
    assert "keyL=81" in config.read_text(encoding="utf-8")


def test_validate_rejects_duplicates_and_missing():
    keys = dict(DEFAULT_KEYS, B="A")
    with pytest.raises(EmulatorError):
        validate_keys(keys)
    keys = dict(DEFAULT_KEYS)
    del keys["Start"]
    with pytest.raises(EmulatorError):
        validate_keys(keys)


def test_sound_goes_to_mgba_config_and_keeps_the_rest(tmp_path):
    from fe_maker.emulator import write_sound

    config = tmp_path / "config.ini"
    config.write_text("[ports.qt]\nwidth=480\n", encoding="utf-8")
    write_sound(50, True, config)
    text = config.read_text(encoding="utf-8")
    assert "volume=128" in text and "mute=1" in text and "width=480" in text
    write_sound(None, False, config)   # left to mGBA: nothing written
    assert config.read_text(encoding="utf-8") == text


def test_mgba_options_written_and_checked(tmp_path):
    import pytest

    from fe_maker.emulator import EmulatorError, validate_options, write_options

    config = tmp_path / "config.ini"
    config.write_text("[ports.qt]\nshader=x\n", encoding="utf-8")
    options = validate_options({"pauseOnFocusLost": True, "scale": 3, "fastForwardRatio": -1, "fullscreen": None})
    assert options == {"pauseOnFocusLost": True, "scale": 3, "fastForwardRatio": -1}
    write_options(options, config)
    text = config.read_text(encoding="utf-8")
    assert "pauseOnFocusLost=1" in text and "width=720" in text and "height=480" in text
    assert "fastForwardRatio=-1" in text and "shader=x" in text
    with pytest.raises(EmulatorError):
        validate_options({"scale": 9})
    with pytest.raises(EmulatorError):
        validate_options({"rm -rf": True})
