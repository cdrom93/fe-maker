import json
import shutil
from pathlib import Path

import pytest

from fe_maker import migrations
from fe_maker.project import DATA_FILES, Project

OLD_PROJECT = Path(__file__).parent / "fixtures" / "project-v1"


@pytest.fixture
def old_project(tmp_path):
    """A copy of the reference project of format 1: never edit the fixture, every later version must open it."""
    root = tmp_path / "old"
    shutil.copytree(OLD_PROJECT, root)
    (root / "assets").mkdir()
    return root


def meta_of(root):
    return json.loads((root / "fe-maker.json").read_text(encoding="utf-8"))


def add_step(monkeypatch, step):
    monkeypatch.setattr(migrations, "MIGRATIONS", [step])
    monkeypatch.setattr(migrations, "FORMAT_VERSION", 2)


def test_the_reference_project_still_opens(old_project, decomp_dir):
    project = Project(old_project, decomp_dir)
    assert project.meta["formatVersion"] == migrations.FORMAT_VERSION
    for kind in DATA_FILES:
        assert project.load(kind) is not None                # data files added since are created
    character = project.load("characters")[0]
    assert character["bases"]["hp"] == 33 and "affinity" in character   # the work stays, new fields are filled
    assert project.test_options["start"] == "menu"
    assert "src/data_characters.c" in {p.relative_to(o).as_posix() for o in [project.generate_overlay(decomp_dir)]
                                       for p in o.rglob("*.*")}


def test_a_same_format_project_gets_no_copy(old_project, decomp_dir):
    Project(old_project, decomp_dir)                              # now at this version's format
    shutil.rmtree(old_project / "backups")
    Project(old_project, decomp_dir)
    assert not (old_project / "backups").exists()


def test_format_2_puts_the_level_of_added_allies_on_their_sheet(old_project, decomp_dir):
    chapters = json.loads((old_project / "data" / "chapters.json").read_text(encoding="utf-8"))
    characters = json.loads((old_project / "data" / "characters.json").read_text(encoding="utf-8"))
    first, second = characters[0], characters[1]
    second_level = second["level"]
    chapters["unitGroups"] = {
        "A": [{"slot": None, "side": "player", "character": first["id"], "level": 7},
              {"slot": None, "side": "player", "character": first["id"], "level": 9},           # the first one counts
              {"slot": 0, "side": "player", "character": second["id"], "level": 7},             # the game's unit
              {"slot": None, "side": "enemy", "character": second["id"], "level": 8},
              {"slot": None, "side": "player", "character": second["id"], "level": 9, "autolevel": True}],
    }
    (old_project / "data" / "chapters.json").write_text(json.dumps(chapters), encoding="utf-8")
    project = Project(old_project, decomp_dir)
    levels = {c["id"]: c["level"] for c in project.load("characters")}
    assert levels[first["id"]] == 7 and levels[second["id"]] == second_level


def test_a_newer_project_is_refused_and_left_alone(old_project, decomp_dir):
    meta = meta_of(old_project)
    meta["formatVersion"] = migrations.FORMAT_VERSION + 1
    (old_project / "fe-maker.json").write_text(json.dumps(meta), encoding="utf-8")
    before = (old_project / "fe-maker.json").read_bytes()
    with pytest.raises(migrations.ProjectTooNew):
        Project(old_project, decomp_dir)
    assert (old_project / "fe-maker.json").read_bytes() == before
    assert not (old_project / "backups").exists()


def test_a_conversion_runs_after_a_copy(old_project, decomp_dir, monkeypatch):
    def rename_the_author(root, meta):
        meta["authors"] = [meta.pop("author")]
        (root / "data" / "items.json").write_text("[]", encoding="utf-8")

    original = (old_project / "data" / "items.json").read_bytes()
    add_step(monkeypatch, rename_the_author)
    project = Project(old_project, decomp_dir)
    assert project.meta["formatVersion"] == 2 and project.meta["authors"] == ["Tester"]
    assert meta_of(old_project)["formatVersion"] == 2                # written to disk: it only runs once
    saved = next((old_project / "backups").iterdir())
    assert saved.name.endswith("format-1")
    assert (saved / "items.json").read_bytes() == original
    assert meta_of(saved)["formatVersion"] == 1


def test_a_project_with_no_format_number_is_format_1(old_project, decomp_dir, monkeypatch):
    meta = meta_of(old_project)
    del meta["formatVersion"]
    (old_project / "fe-maker.json").write_text(json.dumps(meta), encoding="utf-8")
    add_step(monkeypatch, lambda root, meta: meta.update(converted=True))
    assert Project(old_project, decomp_dir).meta["converted"] is True


def test_a_failed_conversion_leaves_the_project_as_it_was(old_project, decomp_dir, monkeypatch):
    def half_done(root, meta):
        (root / "data" / "items.json").write_text("[]", encoding="utf-8")
        raise ValueError("oops")

    original = (old_project / "data" / "items.json").read_bytes()
    add_step(monkeypatch, half_done)
    with pytest.raises(migrations.MigrationFailed):
        Project(old_project, decomp_dir)
    assert (old_project / "data" / "items.json").read_bytes() == original
    assert not (old_project / "data" / "fe-maker.json").exists()
    assert meta_of(old_project)["formatVersion"] == 1
