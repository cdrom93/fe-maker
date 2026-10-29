import json
import os

import pytest

from fe_maker import ferepo

BASE = "https://raw.githubusercontent.com/Klokinator/FE-Repo/refs/heads/main/"
# Fictional index entries, in the repository's format (a category, then raw URLs).
URLS = [
    BASE + "Portrait%20Repository%2FFE08%20Mugs%20(Sacred%20Stones)%2FAmelia%20(Knight)%20%7BAlice%2C%20Bob%7D%20%5BF2E%5D.png",
    BASE + "Portrait%20Repository%2FGeneric%20Characters%2FVillager%20%C3%89lodie%20%7BCarol%7D.png",
    BASE + "Portrait%20Repository%2FREADME.md",
]


def test_describe_names():
    a = ferepo.describe(URLS[0])
    assert a == {"url": URLS[0], "folder": "FE08 Mugs (Sacred Stones)", "name": "Amelia (Knight)",
                 "authors": ["Alice", "Bob"], "license": "F2E"}
    b = ferepo.describe(URLS[1])
    assert b["name"] == "Villager Élodie" and b["authors"] == ["Carol"] and b["license"] == "F2U"


def test_search():
    index = {ferepo.PORTRAITS: URLS}
    found, total = ferepo.search(index, ferepo.PORTRAITS, "elodie")
    assert total == 1 and found[0]["name"] == "Villager Élodie"
    assert ferepo.search(index, ferepo.PORTRAITS, "")[1] == 2          # PNG files only
    assert ferepo.search(index, ferepo.PORTRAITS, "knight bob")[1] == 1


def test_index_cache_and_offline(tmp_path, monkeypatch):
    monkeypatch.setenv("FE_MAKER_HOME", str(tmp_path))
    calls = []

    def download(url, limit):
        calls.append(url)
        return json.dumps({ferepo.PORTRAITS: URLS}).encode()

    monkeypatch.setattr(ferepo, "_download", download)
    index, _when = ferepo.load_index()
    assert index[ferepo.PORTRAITS] == URLS and len(calls) == 1
    ferepo.load_index()
    assert len(calls) == 1                                           # cached
    old = (tmp_path / "ferepo" / "file_urls.json")
    os.utime(old, (0, 0))

    def offline(url, limit):
        raise ferepo.FeRepoError("unreachable")

    monkeypatch.setattr(ferepo, "_download", offline)
    assert ferepo.load_index()[0][ferepo.PORTRAITS] == URLS             # the last index, offline


def test_fetch_only_repository_pictures(tmp_path, monkeypatch):
    monkeypatch.setenv("FE_MAKER_HOME", str(tmp_path))
    with pytest.raises(ferepo.FeRepoError, match="notFeRepo"):
        ferepo.fetch("https://example.com/a.png")
    monkeypatch.setattr(ferepo, "_download", lambda url, limit: b"\x89PNG fake")
    assert ferepo.fetch(URLS[0]) == b"\x89PNG fake"
    monkeypatch.setattr(ferepo, "_download", lambda url, limit: b"not a png")
    assert ferepo.fetch(URLS[0]) == b"\x89PNG fake"                    # cached
    with pytest.raises(ferepo.FeRepoError, match="notAnImage"):
        ferepo.fetch(URLS[1])


def test_credits(tmp_path, decomp_dir):
    from fe_maker.project import RESOURCES_HEADER, Project

    project = Project.create(tmp_path / "p", "P", decomp_dir=decomp_dir)
    (project.root / "CREDITS.txt").write_text("Credits\n\nMy own thanks.\n", encoding="utf-8")
    project.save("portraits", {"1": {"file": "portraits/1.png", "mouth": [2, 6], "eyes": [3, 4],
                                     "source": ferepo.describe(URLS[0])}})
    project.update_credits()
    text = (project.root / "CREDITS.txt").read_text(encoding="utf-8")
    assert text.startswith("Credits\n\nMy own thanks.\n") and RESOURCES_HEADER in text
    assert "- Amelia (Knight) by Alice, Bob (F2E), FE-Repo: " in text
    project.save("portraits", {})
    project.update_credits()
    assert (project.root / "CREDITS.txt").read_text(encoding="utf-8") == "Credits\n\nMy own thanks.\n"


def test_browse_by_folder_and_license():
    index = {ferepo.PORTRAITS: URLS}
    assert ferepo.folders(index, ferepo.PORTRAITS) == [{"name": "FE08 Mugs (Sacred Stones)", "count": 1},
                                                       {"name": "Generic Characters", "count": 1}]
    found, total = ferepo.search(index, ferepo.PORTRAITS, "", folder="Generic Characters")
    assert total == 1 and found[0]["name"] == "Villager Élodie"
    assert ferepo.search(index, ferepo.PORTRAITS, "", f2e_only=True)[0][0]["name"] == "Amelia (Knight)"
    assert ferepo.search(index, ferepo.PORTRAITS, "", offset=1)[0][0]["name"] == "Villager Élodie"


TREE = ferepo.TREE_PREFIX
# Fictional animation folders, listed as GitHub "tree" URLs like the real index.
ANIMATION_URLS = [
    TREE + "Battle%20Animations%2FInfantry%20-%20(Swd)%20Myrms%2FBlade%20Dancer%20%7BAlice%7D%20%5BF2E%5D",
    TREE + "Battle%20Animations%2FMagi%20-%20Dark-Type%2FDruid%20%7BBob%7D",
]


def test_animations_are_folders(tmp_path, monkeypatch):
    monkeypatch.setenv("FE_MAKER_HOME", str(tmp_path))
    index = {ferepo.ANIMATIONS: ANIMATION_URLS}
    found, total = ferepo.search(index, ferepo.ANIMATIONS, "dancer")
    assert total == 1 and found[0]["name"] == "Blade Dancer" and found[0]["authors"] == ["Alice"]
    assert found[0]["license"] == "F2E" and found[0]["folder"] == "Infantry - (Swd) Myrms"
    assert [f["name"] for f in ferepo.folders(index, ferepo.ANIMATIONS)] == ["Infantry - (Swd) Myrms", "Magi - Dark-Type"]

    asked = []
    listing = [{"name": "1. Sword", "type": "dir"},
               {"name": "Sword.gif", "type": "file", "size": 9}]

    def download(url, limit):
        asked.append(url)
        return json.dumps(listing).encode()

    monkeypatch.setattr(ferepo, "_download", download)
    files = ferepo.folder_files(ANIMATION_URLS[0])
    assert asked[0].startswith(ferepo.API_PREFIX + "Battle%20Animations/")
    assert files[0]["type"] == "dir" and files[0]["url"].startswith(TREE)
    folder = "Battle%20Animations/Infantry%20-%20%28Swd%29%20Myrms/Blade%20Dancer%20%7BAlice%7D%20%5BF2E%5D"
    assert ferepo.preview(files) == ferepo.URL_PREFIX + "main/" + folder + "/Sword.gif"
    assert ferepo.folder_files(ANIMATION_URLS[0]) == files and len(asked) == 1     # cached
    with pytest.raises(ferepo.FeRepoError, match="notFeRepo"):
        ferepo.folder_files("https://example.com/tree/x")
