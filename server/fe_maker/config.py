"""Per-user application settings (ROM location, emulator, recent projects)."""

from __future__ import annotations

import json
import os
import platform
import shutil
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path

from .emulator import DEFAULT_KEYS
from .rom import check_rom

MGBA_CANDIDATES = [
    r"C:\Program Files\mGBA\mGBA.exe",
    r"C:\Program Files (x86)\mGBA\mGBA.exe",
    "/Applications/mGBA.app/Contents/MacOS/mGBA",
    "/usr/bin/mgba-qt",
    "/usr/local/bin/mgba-qt",
]


def config_dir() -> Path:
    override = os.environ.get("FE_MAKER_HOME")
    if override:
        return Path(override)
    if sys.platform == "win32":
        return Path(os.environ.get("APPDATA", Path.home())) / "FE Maker"
    if platform.system() == "Darwin":
        return Path.home() / "Library" / "Application Support" / "FE Maker"
    return Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")) / "fe-maker"


def default_projects_dir() -> Path:
    return Path.home() / "FE Maker Projects"


TILED_CANDIDATES = [
    r"C:\Program Files\Tiled	iled.exe",
    r"C:\Program Files (x86)\Tiled	iled.exe",
    "/Applications/Tiled.app/Contents/MacOS/Tiled",
    "/usr/bin/tiled",
]


def find_tiled() -> str | None:
    """The Tiled map editor, if installed (ticket 25)."""
    found = shutil.which("tiled")
    if found:
        return found
    local = os.environ.get("LOCALAPPDATA")
    candidates = TILED_CANDIDATES + ([str(Path(local) / "Programs" / "Tiled" / "tiled.exe")] if local else [])
    return next((c for c in candidates if Path(c).exists()), None)


def find_mgba() -> str | None:
    for name in ("mgba-qt", "mGBA", "mgba"):
        found = shutil.which(name)
        if found:
            return found
    local = os.environ.get("LOCALAPPDATA")
    for candidate in [*MGBA_CANDIDATES, *([str(Path(local) / "Programs" / "mGBA" / "mGBA.exe")] if local else [])]:
        if Path(candidate).exists():
            return candidate
    # the one FE Maker installs from the home page (mgbafetch.py)
    return next((str(p) for p in sorted((config_dir() / "mgba").glob("*/mGBA.exe"))), None)


@dataclass
class Settings:
    language: str = "fr"
    mgba_path: str | None = None
    recent_projects: list[str] = field(default_factory=list)
    keys: dict[str, str] = field(default_factory=lambda: dict(DEFAULT_KEYS))  # GBA button -> keyboard key
    volume: int | None = None   # mGBA's volume in percent for tests; None: left to mGBA
    mute: bool = False          # written with the volume only
    mgba_options: dict = field(default_factory=dict)   # emulator.MGBA_OPTIONS the user set; the others left to mGBA
    tester_name: str = ""     # optional name joined to the tickets (context "tester"); not checked

    @property
    def rom_path(self) -> Path:
        return config_dir() / "rom" / "baserom.gba"

    def mgba(self) -> str | None:
        """mGBA's program: the one set in the settings while it is there, else the one found on this computer (the
        home page and the tests look at the same places, ticket 85)."""
        if self.mgba_path and Path(self.mgba_path).is_file():
            return self.mgba_path
        return find_mgba()

    @property
    def has_rom(self) -> bool:
        return self.rom_path.is_file()

    @classmethod
    def load(cls) -> Settings:
        path = config_dir() / "settings.json"
        if path.is_file():
            data = json.loads(path.read_text(encoding="utf-8"))
            return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})
        return cls(mgba_path=find_mgba())

    def save(self) -> None:
        path = config_dir() / "settings.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(asdict(self), indent=2), encoding="utf-8")

    def install_rom(self, data: bytes) -> None:
        """Validate and store a private copy of the user's ROM."""
        tmp = config_dir() / "rom" / "upload.tmp"
        tmp.parent.mkdir(parents=True, exist_ok=True)
        tmp.write_bytes(data)
        try:
            check_rom(tmp)
        except Exception:
            tmp.unlink()
            raise
        tmp.replace(self.rom_path)

    def add_recent(self, project_dir: Path) -> None:
        p = str(project_dir.resolve())
        self.recent_projects = [p] + [r for r in self.recent_projects if r != p][:9]
        self.save()
