"""Play a built ROM without any window, to check a game automatically.

mGBA runs in the `fe-maker-playtest` Docker image (docker/playtest), driven
over stdin/stdout by `Game`: hold keys for some frames, read and write memory,
take a screenshot. Memory is found by the decomp's symbol names, read from the
linker map the build writes next to the ROM (`fireemblem8.map`).
Idea taken from laqieer's FEBuilderGBA fork (headless playtests, see CREDITS.md).
"""

from __future__ import annotations

import re
import subprocess
from collections.abc import Callable, Iterable
from pathlib import Path

from PIL import Image

from .builder import BuildError, find_docker
from .paths import DOCKER_DIR

IMAGE = "fe-maker-playtest"
KEYS = ("A", "B", "SELECT", "START", "RIGHT", "LEFT", "UP", "DOWN", "R", "L")
FPS = 60
UNIT_SIZE = 0x48

_MAP_SYMBOL_RE = re.compile(r"^\s+0x([0-9a-f]{8})\s+([A-Za-z_]\w*)\s*$", re.MULTILINE)


class PlaytestError(Exception):
    pass


def read_symbols(map_path: Path) -> dict[str, int]:
    """Addresses of the global symbols of a GNU ld map file."""
    return {name: int(address, 16) for address, name in _MAP_SYMBOL_RE.findall(map_path.read_text(errors="replace"))}


def key_mask(keys: Iterable[str]) -> int:
    mask = 0
    for key in keys:
        if key not in KEYS:
            raise PlaytestError(f"Unknown key: {key}")
        mask |= 1 << KEYS.index(key)
    return mask


def ensure_image(on_output: Callable[[str], None] | None = None) -> None:
    """Build the playtest image (a few minutes the first time, then cached)."""
    docker = find_docker()
    result = subprocess.run(
        [docker, "build", "-q", "-t", IMAGE, str(DOCKER_DIR / "playtest")],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
    )
    if on_output:
        on_output(result.stdout + result.stderr)
    if result.returncode != 0:
        raise BuildError("Playtest image build failed:\n" + result.stderr[-2000:])


class Game:
    """A running game. Use as a context manager: `with Game(rom, map_path) as game: ...`."""

    def __init__(self, rom: Path, map_path: Path | None = None):
        self.rom = Path(rom).resolve()
        self.symbols = read_symbols(map_path) if map_path else {}
        self.frame = 0
        self._process: subprocess.Popen[bytes] | None = None

    def __enter__(self) -> Game:
        ensure_image()
        self._process = subprocess.Popen(
            [find_docker(), "run", "--rm", "-i", "-v", f"{self.rom}:/rom/game.gba:ro", IMAGE, "/rom/game.gba"],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
        )
        ready = self._line()
        if not ready.startswith("ready"):
            raise PlaytestError(f"Emulator did not start: {ready}")
        return self

    def __exit__(self, *exc: object) -> None:
        if self._process:
            try:
                self._send("quit")
                self._process.wait(timeout=10)
            except (OSError, subprocess.TimeoutExpired):
                self._process.kill()
            self._process = None

    def _line(self) -> str:
        assert self._process and self._process.stdout
        return self._process.stdout.readline().decode("ascii", "replace").strip()

    def _send(self, command: str) -> None:
        assert self._process and self._process.stdin
        self._process.stdin.write((command + "\n").encode("ascii"))
        self._process.stdin.flush()

    def _ask(self, command: str) -> str:
        self._send(command)
        answer = self._line()
        if not answer.startswith("ok"):
            raise PlaytestError(f"{command}: {answer or 'emulator stopped'}")
        return answer[2:].strip()

    # Input

    def run(self, frames: int, keys: Iterable[str] = ()) -> None:
        """Run frames while holding keys (none by default)."""
        self._ask(f"frames {frames} {key_mask(keys)}")
        self.frame += frames

    def press(self, *keys: str, wait: int = 20) -> None:
        """Tap keys for a few frames, then let the game react."""
        self.run(4, keys)
        self.run(wait)

    def wait_until(self, condition: Callable[[], bool], seconds: float = 60, step: int = 10) -> bool:
        """Run until condition() holds (checked every `step` frames). False if it never did."""
        for _ in range(int(seconds * FPS / step)):
            if condition():
                return True
            self.run(step)
        return condition()

    # Memory

    def address(self, symbol: str | int) -> int:
        if isinstance(symbol, int):
            return symbol
        if symbol not in self.symbols:
            raise PlaytestError(f"Unknown symbol: {symbol}")
        return self.symbols[symbol]

    def read(self, symbol: str | int, offset: int = 0, width: int = 8, signed: bool = False) -> int:
        value = int(self._ask(f"read {width} {self.address(symbol) + offset}"))
        if signed and value >= 1 << (width - 1):
            value -= 1 << width
        return value

    def write(self, symbol: str | int, value: int, offset: int = 0, width: int = 8) -> None:
        self._ask(f"write {width} {self.address(symbol) + offset} {value & ((1 << width) - 1)}")

    def screenshot(self) -> Image.Image:
        assert self._process and self._process.stdout
        size = int(self._ask("screen"))
        data = self._process.stdout.read(size)
        return Image.frombytes("RGBX", (240, 160), data).convert("RGB")

    # Game state (FE8)

    def chapter(self) -> int:
        return self.read("gPlaySt", 0x0E, signed=True)

    def turn(self) -> int:
        return self.read("gPlaySt", 0x10, width=16)

    def phase(self) -> str:
        return {0x00: "player", 0x40: "npc", 0x80: "enemy"}.get(self.read("gPlaySt", 0x0F), "other")

    def units(self, army: str = "Blue") -> list[dict[str, int]]:
        """Units present in an army (gUnitArrayBlue / Red / Green): character number and main stats."""
        base = self.address(f"gUnitArray{army}")
        found = []
        for index in range({"Blue": 62, "Red": 50, "Green": 20}[army]):
            unit = base + index * UNIT_SIZE
            character = self.read(unit, width=32)
            if not character:
                continue
            found.append({
                "character": self.read(character, 4),
                "class": self.read(self.read(unit, 4, width=32), 4),
                "level": self.read(unit, 0x08, signed=True),
                "x": self.read(unit, 0x10, signed=True),
                "y": self.read(unit, 0x11, signed=True),
                "maxHP": self.read(unit, 0x12, signed=True),
                "hp": self.read(unit, 0x13, signed=True),
            })
        return found
