"""Local-only playtests: build a project, play the ROM without any window, check the game's memory.

Run with:  FE_MAKER_ROM=path/to/fe8.gba python -m pytest tests/local/test_playtest.py -s
"""

import os
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "server"))

from fe_maker.playtest import Game  # noqa: E402
from fe_maker.project import Project  # noqa: E402

ROM = os.environ.get("FE_MAKER_ROM")
pytestmark = pytest.mark.skipif(not ROM, reason="set FE_MAKER_ROM to run tests that need the ROM")


def test_edited_character_is_on_the_prologue_map(tmp_path):
    project = Project.create(tmp_path / "play", "Play")
    chars = project.load("characters")
    eirika = next(c for c in chars if c["id"] == "CHARACTER_EIRIKA")
    eirika["bases"]["hp"] = 20
    project.save("characters", chars)
    lord = next(c for c in project.load("classes") if c["id"] == eirika["class"])
    out = project.build(Path(ROM), on_output=lambda line: print(line, end=""), for_test=True)

    with Game(out.rom_path, out.map_path) as game:
        assert game.wait_until(lambda: game.chapter() == 0 and game.turn() == 1 and game.units(), seconds=60)
        game.run(60)
        game.screenshot().save(tmp_path / "prologue.png")
        print("screenshot:", tmp_path / "prologue.png", "after", game.frame, "frames")
        assert game.phase() == "player"
        # A unit's HP is its class base plus the character's own base.
        unit = next(u for u in game.units() if u["character"] == 1)
        assert unit["maxHP"] == unit["hp"] == 20 + lord["bases"]["hp"]
