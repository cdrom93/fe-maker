"""Launch the user's emulator (mGBA) on a built ROM."""

from __future__ import annotations

import subprocess
from pathlib import Path


class EmulatorError(Exception):
    pass


def launch(mgba_path: str | None, rom: Path) -> None:
    if not mgba_path or not Path(mgba_path).exists():
        raise EmulatorError("mGBA not found. Install it or set its path in the settings.")
    subprocess.Popen([mgba_path, str(rom)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
