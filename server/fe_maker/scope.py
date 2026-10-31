"""What a project keeps of the game (ticket 71): chosen at creation or at any time after, in the Game options tab.

Nothing leaves the built game's tables, which the engine and the kept chapters may still need: what the project does
not keep leaves its lists, and a chapter it does not keep leaves the story and becomes a free slot (newchapter.py). A
record that is ticked again comes back as in the game; a chapter does not, so each change first copies data/ to
backups/<time>/.
"""

from __future__ import annotations

import shutil
import time

from . import newchapter
from .decomp import units
from .decomp.gamedata import DecompData

BACKUPS_DIR = "backups"


def _used(project, kept_chapters: set[int], data: DecompData) -> tuple[set[str], set[str], set[str]]:
    """Characters, classes and items the kept chapters' units use."""
    characters, classes, items = set(), set(), set()
    groups = units.read_unit_groups(project.decomp_dir)
    edits = project.load("chapters").get("unitGroups", {})
    settings = data.chapter_settings["chapters"]
    for index in kept_chapters:
        symbol = data._chapter_event_symbol(settings[index])
        if not symbol:
            continue
        for group in units.chapter_unit_groups(project.decomp_dir, symbol):
            name = group["name"]
            # an emptied group stays empty (ticket 102)
            for unit in edits[name] if name in edits else (groups[name].units if name in groups else []):
                characters.add(unit.get("character"))
                classes.add(unit.get("class"))
                items.update(unit.get("items") or [])
    return characters, classes, items


def _story(project, data: DecompData) -> list[int]:
    """The chapters of the project's story, in order."""
    order = newchapter.story_order(data.chapter_links(project.load("dialogues").get("scripts", {})))
    return order + sorted({int(k) for k in project.load("chapters").get("added", {})} - set(order))


def contents(project) -> dict:
    """Each list of the game, what the project keeps of it, and what the kept chapters need."""
    data = DecompData(project.decomp_dir)
    data._load_chapter_events()
    story = _story(project, data)
    titles = project.load("chapters").get("titles", {})
    settings = data.chapter_settings["chapters"]

    def chapter_title(index: int) -> str:
        text = settings[index].get("chapTitleTextId", 0)
        return titles.get(str(index)) or (data.texts.get_name(text) if text in data.texts.messages else "") or str(index)

    def rows(game: list[dict], mine: list[dict], only: set[str] | None = None) -> list[dict]:
        ids = {r["id"] for r in mine}
        names = {r["id"]: r["name"] for r in game} | {r["id"]: r["name"] for r in mine}
        order = [r["id"] for r in game] + [r["id"] for r in mine if r["id"] not in {g["id"] for g in game}]
        return [{"id": i, "name": names[i], "kept": i in ids} for i in order if only is None or i in only]

    reusable = set(data.reusable_characters())
    added = {c["id"] for c in project.load("characters") if c["id"].startswith("CHARACTER_NEW")}
    named = reusable | {newchapter.BLANK_LORD} | added
    characters, classes, items = _used(project, set(story), data)
    return {
        "chapters": [{"id": i, "name": chapter_title(i), "kept": True} for i in story],
        "characters": rows(data.export_characters(), project.load("characters"), named),
        "classes": rows(data.export_classes(), project.load("classes")),
        "items": rows(data.export_items(), project.load("items")),
        "supports": project.load("dialogues").get("supports") != [],
        "needed": {"characters": sorted(c for c in characters if c), "classes": sorted(c for c in classes if c),
                   "items": sorted(items)},
    }


def _backup(project) -> str:
    target = project.root / BACKUPS_DIR / time.strftime("%Y-%m-%d-%H%M%S")
    shutil.copytree(project.root / "data", target)
    return str(target)


def _keep(records: list[dict], game: list[dict], kept: set[str], managed: set[str] | None = None) -> list[dict]:
    """The project's records in `kept` (those outside `managed` stay), and the game's ones ticked again."""
    mine = {r["id"] for r in records}
    out = [r for r in records if r["id"] in kept or (managed is not None and r["id"] not in managed)]
    return out + [r for r in game if r["id"] in kept and r["id"] not in mine]


def apply(project, chapters: list[int], characters: list[str], classes: list[str], items: list[str], supports: bool,
          title: str = "", hero: str = "") -> dict:
    """Keep these and nothing else. What the kept chapters and characters need stays: it is reported in "forced"."""
    data = DecompData(project.decomp_dir)
    data._load_chapter_events()
    story = _story(project, data)
    kept_chapters = set(chapters) & set(story)
    backup = _backup(project)

    if not set(story) <= kept_chapters:
        newchapter.drop_chapters(project, data, kept_chapters, title, hero)
        data = DecompData(project.decomp_dir)
        data._load_chapter_events()
    story = _story(project, data)

    need_characters, need_classes, need_items = _used(project, set(story), data)
    game_characters, game_classes, game_items = data.export_characters(), data.export_classes(), data.export_items()
    named = set(data.reusable_characters()) | {c["id"] for c in project.load("characters") if c["id"].startswith("CHARACTER_NEW")}
    want = (set(characters) | (need_characters & named)) | {newchapter.BLANK_LORD}
    new_characters = _keep(project.load("characters"), game_characters, want, named)
    want_classes = set(classes) | {c for c in need_classes if c} | {c["class"] for c in new_characters}
    new_classes = _keep(project.load("classes"), game_classes, want_classes)
    known = {c["id"] for c in new_classes}
    for record in new_classes:
        record["promotions"] = [p for p in record.get("promotions", []) if p in known]
    want_items = set(items) | need_items
    new_items = _keep(project.load("items"), game_items, want_items)

    project.save("characters", new_characters)
    project.save("classes", new_classes)
    project.save("items", new_items)
    stored = project.load("chapters")
    stored["blankCharacters"] = len(new_characters) < len(game_characters)
    project.save("chapters", stored)
    dialogues = project.load("dialogues")
    if not supports:
        dialogues["supports"] = []
    elif dialogues.get("supports") == []:
        dialogues.pop("supports")
    project.save("dialogues", dialogues)
    return {"backup": backup,
            "forced": {"characters": sorted((want - set(characters)) & named), "classes": sorted(want_classes - set(classes)),
                       "items": sorted(want_items - set(items))}}
