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


def test_refuses_non_empty_folder(tmp_path, decomp_dir):
    (tmp_path / "file.txt").write_text("x")
    with pytest.raises(ProjectError):
        Project.create(tmp_path, "X", decomp_dir=decomp_dir)
