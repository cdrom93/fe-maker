import json

import pytest

from fe_maker.project import Project, ProjectError


def test_create_and_generate_overlay(tmp_path, decomp_dir):
    root = tmp_path / "my-game"
    project = Project.create(root, "My Game", "Me", decomp_dir=decomp_dir)
    meta = json.loads((root / "fe-maker.json").read_text(encoding="utf-8"))
    assert meta["name"] == "My Game"
    assert (root / "CREDITS.txt").is_file()
    assert "build/" in (root / ".gitignore").read_text(encoding="utf-8")

    # Unmodified project: nothing to overlay.
    overlay = project.generate_overlay(decomp_dir)
    assert list(overlay.rglob("*.*")) == []

    chars = project.load("characters")
    chars[0]["bases"]["hp"] = 8
    (root / "data" / "characters.json").write_text(json.dumps(chars), encoding="utf-8")
    overlay = project.generate_overlay(decomp_dir)
    assert [p.relative_to(overlay).as_posix() for p in overlay.rglob("*.*")] == ["src/data_characters.c"]
    content = (overlay / "src" / "data_characters.c").read_bytes()
    assert b"\r\n" not in content


def test_old_project_gets_new_fields(tmp_path, decomp_dir, monkeypatch):
    import fe_maker.project as project_module

    monkeypatch.setattr(project_module, "DECOMP_DIR", decomp_dir)
    root = tmp_path / "old"
    Project.create(root, "Old", decomp_dir=decomp_dir)
    path = root / "data" / "characters.json"
    chars = json.loads(path.read_text(encoding="utf-8"))
    for c in chars:
        del c["abilities"], c["affinity"]
    path.write_text(json.dumps(chars), encoding="utf-8")
    loaded = Project(root)._fill_new_fields("characters", json.loads(path.read_text(encoding="utf-8")), decomp_dir)
    assert loaded[0]["abilities"] == ["female"]
    assert "affinity" in loaded[0]


def test_refuses_non_empty_folder(tmp_path, decomp_dir):
    (tmp_path / "file.txt").write_text("x")
    with pytest.raises(ProjectError):
        Project.create(tmp_path, "X", decomp_dir=decomp_dir)


def test_old_blank_projects_lose_the_characters_left_in_their_list(tmp_path, decomp_dir, monkeypatch):
    from fe_maker import newchapter
    from fe_maker.decomp.gamedata import DecompData

    project = Project.create(tmp_path / "blank", "Blank", decomp_dir=decomp_dir)
    characters = project.load("characters")
    hero, rival = characters[0]["id"], characters[1]["id"]
    monkeypatch.setattr(DecompData, "blank_dropped_characters", lambda self: {hero, rival})
    monkeypatch.setattr(DecompData, "reusable_characters", lambda self: {})
    characters[1]["level"] += 1   # changed by the user: stays
    project.save("characters", characters)
    project.save("chapters", {**project.load("chapters"), "blankCharacters": True})
    newchapter.tidy_blank(project)
    ids = [c["id"] for c in project.load("characters")]
    assert hero not in ids and rival in ids
    assert project.load("chapters")["blankCharacters"] == "all"


def test_show_original_stays_in_the_project(tmp_path, decomp_dir):
    project = Project.create(tmp_path / "shown", "Shown", decomp_dir=decomp_dir)
    assert project.show_original
    project.set_show_original(False)
    assert not Project(project.root, decomp_dir).show_original


def test_a_cleared_chapter_starts_with_no_boss(tmp_path, decomp_dir, monkeypatch):
    from fe_maker import api

    project = Project.create(tmp_path / "blank", "Blank", decomp_dir=decomp_dir)
    project.save("chapters", {**project.load("chapters"), "cleared": [3]})
    monkeypatch.setattr(api.state, "project", project)
    objective = {"type": "defeat_boss", "boss": "CHARACTER_BAZBA"}
    assert api._project_objective(objective, 3)["boss"] is None
    assert api._project_objective(objective, 2)["boss"] == "CHARACTER_BAZBA"
