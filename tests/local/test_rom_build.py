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


def test_test_build_starting_on_map(tmp_path):
    project = Project.create(tmp_path / "quick", "Quick")
    assert project.test_options["start"] == "map"
    out = project.build(Path(ROM), on_output=lambda line: print(line, end=""), for_test=True)
    assert out.patch_path is None
    assert out.rom_path.read_bytes() != Path(ROM).read_bytes()


def test_modified_project_and_patch(tmp_path):
    project = Project.create(tmp_path / "modded", "Modded")
    chars = project.load("characters")
    eirika = next(c for c in chars if c["id"] == "CHARACTER_EIRIKA")
    eirika["name"] = "Erika"
    eirika["bases"]["hp"] = 20
    eirika["class"] = "CLASS_CAVALIER_F"
    eirika["weaponRanks"]["lance"] = "D"
    eirika["abilities"] = ["female", "lock4", "canto"]
    eirika["affinity"] = "fire"
    problems = [p for p in project.save("characters", chars) if p.severity == "error"]
    assert problems == []
    items = project.load("items")
    iron = next(i for i in items if i["id"] == "ITEM_SWORD_IRON")
    iron["might"] = 9
    iron["reservedFor"] = {"characters": ["CHARACTER_SETH"], "classes": ["CLASS_THIEF"]}
    project.save("items", items)

    classes = project.load("classes")
    thief = next(c for c in classes if c["id"] == "CLASS_THIEF")
    thief["maxes"]["spd"] = 30
    thief["movement"] = "Fly"
    thief["promotions"] = ["CLASS_ASSASSIN", "CLASS_HERO"]
    project.save("classes", classes)
    combat = project.load("combat")
    combat["triangle"][0]["hit"] = -20
    combat["effectiveness"]["ItemEffectiveness_Horse"].append("CLASS_THIEF")
    project.save("combat", combat)
    import copy

    from fe_maker.decomp import units

    group = copy.deepcopy(units.read_unit_groups(project.decomp_dir)["UnitDef_Event_PrologueEnemy"].units)
    group[0]["endX"], group[0]["level"], group[0]["items"] = 11, 9, ["ITEM_AXE_STEEL", "ITEM_VULNERARY"]
    project.save("chapters", {"unitGroups": {"UnitDef_Event_PrologueEnemy": group}})
    assert [p for p in project.validate() if p.severity == "error"] == []

    out = project.build(Path(ROM), on_output=lambda line: print(line, end=""))
    built = out.rom_path.read_bytes()
    assert not out.matches_original
    assert ups.apply(Path(ROM).read_bytes(), out.patch_path.read_bytes()) == built
