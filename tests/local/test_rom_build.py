"""Local-only tests that need the user's ROM and Docker. Never run in public CI.

Run with:  FE_MAKER_ROM=path/to/fe8.gba python -m pytest tests/local -s
"""

import os
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "server"))

from fe_maker import ups  # noqa: E402
from fe_maker.project import Project  # noqa: E402

ROM = os.environ.get("FE_MAKER_ROM")
pytestmark = pytest.mark.skipif(not ROM, reason="set FE_MAKER_ROM to run tests that need the ROM")


def test_unmodified_project_rebuilds_original_rom(tmp_path):
    project = Project.create(tmp_path / "vanilla", "Vanilla")
    out = project.build(Path(ROM), on_output=lambda line: print(line, end=""))
    assert out.matches_original
    assert out.rom_path.read_bytes() == Path(ROM).read_bytes()


def test_modified_project_and_patch(tmp_path):
    project = Project.create(tmp_path / "modded", "Modded")
    chars = project.load("characters")
    eirika = next(c for c in chars if c["id"] == "CHARACTER_EIRIKA")
    eirika["name"] = "Erika"
    eirika["bases"]["hp"] = 20
    eirika["class"] = "CLASS_CAVALIER_F"
    eirika["weaponRanks"]["lance"] = "D"
    problems = [p for p in project.save("characters", chars) if p.severity == "error"]
    assert problems == []
    items = project.load("items")
    next(i for i in items if i["id"] == "ITEM_SWORD_IRON")["might"] = 9
    project.save("items", items)

    out = project.build(Path(ROM), on_output=lambda line: print(line, end=""))
    built = out.rom_path.read_bytes()
    assert not out.matches_original
    assert ups.apply(Path(ROM).read_bytes(), out.patch_path.read_bytes()) == built
