"""Character and class packages (packages.py): one file from a project to another, with what the sheets need."""

import io
import json
import zipfile

import pytest

from fe_maker import packages
from fe_maker.decomp.gamedata import DecompData
from fe_maker.project import Project


def _source_project(tmp_path, decomp_dir):
    """A project with an added class (an imported animation, a map sprite) and an added character in it, with its
    own portrait."""
    project = Project.create(tmp_path / "a", "A", decomp_dir=decomp_dir)
    data = DecompData(decomp_dir)
    cls = {**data.new_class("CLASS_TESTKNIGHT", set()), "name": "Rune Knight", "promotions": ["CLASS_TESTLORD"]}
    project.save("classes", [*project.load("classes"), cls])
    folder = project.root / "assets" / "animations" / "1"
    (folder / "data" / "banim").mkdir(parents=True)
    (folder / "graphics" / "banim").mkdir(parents=True)
    (folder / "data" / "banim" / "banim_fem_1_motion.s").write_text("banim_fem_1_sheet_0:\n.word banim_fem_10\n")
    (folder / "graphics" / "banim" / "banim_fem_1_sheet_0.png").write_bytes(b"sheet")
    source = {"name": "Knight", "authors": ["Someone"], "license": "F2U", "url": "https://example.org/k", "folder": "K"}
    project.save("animations", {"animations": {"1": {"name": "Knight", "weapon": "Lance", "frames": 3, "sheets": 1,
                                                       "source": source}},
                                "classes": {cls["id"]: {"lance": "new:1", "sword": 12}}})
    sprite = project.root / "assets" / "mapsprites" / "NEW_80"
    sprite.mkdir(parents=True)
    (sprite / "stand.png").write_bytes(b"stand")
    project.save("mapsprites", {"classes": {cls["id"]: "NEW_80"}, "sprites": {"NEW_80": {"name": "Knight", "walk": False}}})
    (project.root / "assets" / "portraits").mkdir(parents=True)
    (project.root / "assets" / "portraits" / "3.png").write_bytes(b"face")
    project.save("portraits", {"3": {"file": "portraits/3.png", "mouth": [1, 2], "eyes": [3, 4], "name": "Ana"}})
    hero = {**data.new_character(True, {c["id"] for c in project.load("characters")}), "name": "Ana",
            "class": cls["id"], "portraitId": 3, "battleColors": {cls["id"]: None}}
    project.save("characters", [*project.load("characters"), hero])
    return project, cls["id"], hero["id"]


def test_a_character_goes_to_another_project_with_its_class(tmp_path, decomp_dir):
    source, class_id, hero_id = _source_project(tmp_path, decomp_dir)
    data = packages.export_character(source, decomp_dir, hero_id)
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        manifest = json.loads(archive.read("package.json"))
        names = set(archive.namelist())
    assert manifest["kind"] == "character" and manifest["character"]["ally"]
    assert {"files/portraits/3.png", "files/animations/1/data/banim/banim_fem_1_motion.s",
            f"files/mapsprite/{class_id}/stand.png"} <= names

    target = Project.create(tmp_path / "b", "B", decomp_dir=decomp_dir)
    target.save("animations", {"animations": {"1": {"name": "Other"}}, "classes": {}})
    target.save("portraits", {"3": {"file": "portraits/3.png", "name": "Other"}})
    result = packages.import_package(target, decomp_dir, data)
    new_class = result["classes"][class_id]
    hero = next(c for c in target.load("characters") if c["id"] == result["id"])
    assert hero["name"] == "Ana" and hero["class"] == new_class and hero["portraitId"] == 4
    assert hero["battleColors"] == {new_class: None}
    assert target.load("portraits")["4"]["mouth"] == [1, 2]
    assert (target.root / "assets" / "portraits" / "4.png").read_bytes() == b"face"
    cls = next(c for c in target.load("classes") if c["id"] == new_class)
    assert cls["name"] == "Rune Knight" and cls["promotions"] == ["CLASS_TESTLORD"]
    animations = target.load("animations")
    assert animations["classes"][new_class] == {"lance": "new:2", "sword": 12}
    motion = target.root / "assets" / "animations" / "2" / "data" / "banim" / "banim_fem_2_motion.s"
    assert motion.read_text() == "banim_fem_2_sheet_0:\n.word banim_fem_10\n"   # only its own symbol renamed
    assert animations["animations"]["2"]["source"]["authors"] == ["Someone"]       # the credits follow
    assert "Someone" in (target.root / "CREDITS.txt").read_text(encoding="utf-8")
    key = target.load("mapsprites")["classes"][new_class]
    assert (target.root / "assets" / "mapsprites" / key / "stand.png").read_bytes() == b"stand"


def test_a_class_package_and_links_left_out(tmp_path, decomp_dir):
    source, class_id, _hero = _source_project(tmp_path, decomp_dir)
    classes = source.load("classes")
    next(c for c in classes if c["id"] == class_id)["promotions"] = ["CLASS_TESTLORD", "CLASS_NEW_81"]
    source.save("classes", classes)
    data = packages.export_class(source, decomp_dir, class_id)
    target = Project.create(tmp_path / "b", "B", decomp_dir=decomp_dir)
    result = packages.import_package(target, decomp_dir, data)
    assert result["kind"] == "class" and result["warnings"] == ["promotionsLeft"]
    assert next(c for c in target.load("classes") if c["id"] == result["id"])["promotions"] == ["CLASS_TESTLORD"]
    assert packages.file_name("class", "Rune Knight") == "Rune Knight.femclass"


def test_not_a_package(tmp_path, decomp_dir):
    target = Project.create(tmp_path / "b", "B", decomp_dir=decomp_dir)
    for data in (b"nothing", _zip({"format": "other"}), _zip({"format": packages.FORMAT, "kind": "class", "version": 9})):
        with pytest.raises(packages.PackageError):
            packages.import_package(target, decomp_dir, data)


def _zip(manifest):
    out = io.BytesIO()
    with zipfile.ZipFile(out, "w") as archive:
        archive.writestr("package.json", json.dumps(manifest))
    return out.getvalue()
