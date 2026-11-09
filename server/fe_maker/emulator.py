"""Launch the user's emulator (mGBA) on a built ROM, with FE Maker's key bindings.

mGBA stores keyboard bindings in its config.ini, section [gba.input.QT_K], as Qt
key codes, and rewrites that file when it exits. FE Maker therefore closes the
game window it opened before, then writes the bindings, then starts mGBA.
"""

from __future__ import annotations

import configparser
import os
import platform
import subprocess
import sys
from pathlib import Path

GBA_BUTTONS = ["A", "B", "L", "R", "Start", "Select", "Up", "Down", "Left", "Right"]

DEFAULT_KEYS = {
    "A": "A", "B": "Z", "L": "Q", "R": "S", "Start": "Enter", "Select": "Space",
    "Up": "ArrowUp", "Down": "ArrowDown", "Left": "ArrowLeft", "Right": "ArrowRight",
}

# Non-character keys, named like the browser's KeyboardEvent.key -> Qt::Key
_SPECIAL_KEYS = {
    "Escape": 0x01000000, "Tab": 0x01000001, "Backspace": 0x01000003, "Enter": 0x01000004,
    "Insert": 0x01000006, "Delete": 0x01000007, "Home": 0x01000010, "End": 0x01000011,
    "ArrowLeft": 0x01000012, "ArrowUp": 0x01000013, "ArrowRight": 0x01000014, "ArrowDown": 0x01000015,
    "PageUp": 0x01000016, "PageDown": 0x01000017, "Shift": 0x01000020, "Control": 0x01000021,
    "Alt": 0x01000023, "Space": 0x20,
}


class EmulatorError(Exception):
    pass


def qt_key_code(name: str) -> int:
    """Browser key name ('A', 'Enter', 'ArrowUp'...) -> Qt key code used by mGBA."""
    if name in _SPECIAL_KEYS:
        return _SPECIAL_KEYS[name]
    if len(name) == 1 and name.isascii() and name.isprintable():
        return ord(name.upper())
    if len(name) >= 2 and name[0] == "F" and name[1:].isdigit():
        return 0x01000030 + int(name[1:]) - 1
    raise EmulatorError(f"Unsupported key: {name}")


def validate_keys(keys: dict[str, str]) -> dict[str, str]:
    missing = [b for b in GBA_BUTTONS if not keys.get(b)]
    if missing:
        raise EmulatorError("Missing keys: " + ", ".join(missing))
    for name in keys.values():
        qt_key_code(name)
    used = [keys[b] for b in GBA_BUTTONS]
    if len(set(used)) != len(used):
        raise EmulatorError("The same key is used for two buttons")
    return {b: keys[b] for b in GBA_BUTTONS}


def mgba_config_path() -> Path:
    if sys.platform == "win32":
        return Path(os.environ.get("APPDATA", Path.home())) / "mGBA" / "config.ini"
    if platform.system() == "Darwin":
        return Path.home() / "Library" / "Application Support" / "mGBA" / "config.ini"
    return Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")) / "mgba" / "config.ini"


def write_key_bindings(keys: dict[str, str], config_path: Path | None = None) -> None:
    """Set the keyboard section of mGBA's config, leaving every other setting untouched."""
    path = config_path or mgba_config_path()
    parser = configparser.RawConfigParser(strict=False)
    parser.optionxform = str  # keep key case (keyA, keyStart...)
    if path.is_file():
        parser.read(path, encoding="utf-8")
    section = "gba.input.QT_K"
    if not parser.has_section(section):
        parser.add_section(section)
    for button in GBA_BUTTONS:
        parser.set(section, f"key{button}", str(qt_key_code(keys[button])))
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        parser.write(f, space_around_delimiters=False)


def write_sound(volume: int | None, mute: bool, config_path: Path | None = None) -> None:
    """Set mGBA's volume (percent of its 0-256 scale, 256 = 100 %) and mute, in [ports.qt]; None leaves mGBA's own."""
    if volume is None:
        return
    path = config_path or mgba_config_path()
    parser = configparser.RawConfigParser(strict=False)
    parser.optionxform = str
    if path.is_file():
        parser.read(path, encoding="utf-8")
    section = "ports.qt"
    if not parser.has_section(section):
        parser.add_section(section)
    parser.set(section, "volume", str(round(max(0, min(100, volume)) * 256 / 100)))
    parser.set(section, "mute", "1" if mute else "0")
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        parser.write(f, space_around_delimiters=False)


class Emulator:
    """Keeps track of the game window FE Maker opened, so a new test replaces it."""

    def __init__(self) -> None:
        self._process: subprocess.Popen | None = None

    def close_previous(self) -> None:
        if self._process and self._process.poll() is None:
            self._process.terminate()
            try:
                self._process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self._process.kill()
        self._process = None

    def launch(self, mgba_path: str | None, rom: Path, keys: dict[str, str], volume: int | None = None,
               mute: bool = False) -> None:
        if not mgba_path or not Path(mgba_path).exists():
            raise EmulatorError("mGBA not found. Install it or set its path in the settings.")
        self.close_previous()
        write_key_bindings(keys)
        write_sound(volume, mute)
        # Detached from FE Maker: closing or restarting the server must not close the game being played.
        if sys.platform == "win32":
            detach = {"creationflags": subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP}
        else:
            detach = {"start_new_session": True}
        self._process = subprocess.Popen([mgba_path, str(rom)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                         stdin=subprocess.DEVNULL, **detach)
