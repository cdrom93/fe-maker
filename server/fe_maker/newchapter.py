"""Chapters the project adds (decision of 30/10/2026: free slots of the game's chapter table for now; a larger
table comes later).

A free slot is a chapter of the game with its own map and its own event group, that the project's story does not
reach: in the original game the floors of the Tower of Valni and of the Lagdou Ruins (post-game content) and the two
debug chapters. Adding a chapter after another one clears such a slot with the editors' own project data:

- its title (chapters.json "titles", a text of its own);
- an empty map of the chosen size (one screen at least), on the slot's tile sheet (maps.json "layouts");
- its enemy groups emptied, the army's places in a block at the top left (chapters.json "unitGroups");
- objective "defeat all enemies" (chapters.json "objectives");
- a simple opening: the army, then the (empty) groups the editor shows for the chapter (dialogues.json "scripts");
- the story: the chapter before now leads to it (MNC2), and it leads where the chapter before used to go.

chapters.json "added" {index: {"after": index}} remembers which slots the project took.
"""

from __future__ import annotations

from collections import Counter

from .decomp import maps, objectives, story, units
from .decomp.gamedata import DecompData
from .validation import MAP_MIN_HEIGHT, MAP_MIN_WIDTH

PLAIN = 0x01   # terrain byte of plains (src/data/terrain names)
MAX_SIZE = (64, 64)


class ChapterError(Exception):
    pass


def free_slots(data: DecompData, scripts: dict, taken: set[int]) -> list[int]:
    """Chapters a new one can take: own map, own event group, reached neither by the game's story nor the project's
    (a chapter of the game's story the project has cut off for now is not free: ticket 55)."""
    data._load_chapter_events()
    chapters = data.chapter_settings["chapters"]
    reached = set()
    for links in (data.chapter_links(), data.chapter_links(scripts)):
        seen, todo = {0}, [0]
        while todo:
            for link in links[todo.pop()]:
                to = link.get("to")
                if isinstance(to, int) and 0 <= to < len(chapters) and to not in seen:
                    seen.add(to)
                    todo.append(to)
        reached |= seen
    symbols = Counter(data._chapter_event_symbol(c) for c in chapters)
    layouts = {i: len(info["chapters"]) for info in maps.layouts(data.decomp_dir).values() for i in info["chapters"]}
    return [i for i, c in enumerate(chapters)
            if i not in reached and i not in taken and layouts.get(i) == 1
            and (symbol := data._chapter_event_symbol(c)) and symbols[symbol] == 1]


def add_chapter(project, after: int, width: int, height: int, title: str) -> int:
    """Take a free slot for a new chapter after chapter `after`; returns its index."""
    if not (MAP_MIN_WIDTH <= width <= MAX_SIZE[0] and MAP_MIN_HEIGHT <= height <= MAX_SIZE[1]):
        raise ChapterError("badMapSize")
    data = DecompData(project.decomp_dir)
    dialogues, chapters, maps_data = project.load("dialogues"), project.load("chapters"), project.load("maps")
    scripts = dialogues.setdefault("scripts", {})
    added = chapters.setdefault("added", {})
    data._load_chapter_events()
    if not 0 <= after < len(data.chapter_settings["chapters"]):
        raise ChapterError("unknownChapter")
    slots = free_slots(data, scripts, {int(k) for k in added})
    if not slots:
        raise ChapterError("noFreeChapter")
    n = slots[0]
    symbol = data._chapter_event_symbol(data.chapter_settings["chapters"][n])
    group = objectives.event_group(data.event_sources, symbol)

    # Units: the army of the chapter before (its player group, as the project has it) in a block at the top left;
    # the slot's own player group (the tower's are placeholders) is reused, the other groups emptied.
    games = units.read_unit_groups(project.decomp_dir)
    loads = units.chapter_unit_groups(project.decomp_dir, symbol)
    edits = chapters.setdefault("unitGroups", {})
    before = units.chapter_unit_groups(project.decomp_dir, data._chapter_event_symbol(data.chapter_settings["chapters"][after]))
    army = next((g["name"] for g in before if g["origin"] == "players"), None)
    for g in loads:
        if g["origin"] == "players":
            own = len(games[g["name"]].units)
            source = (edits.get(army) or games[army].units) if army else games[g["name"]].units
            edits[g["name"]] = [{**u, "slot": i if i < own else None, "x": i % width, "y": i // width,
                                 "endX": i % width, "endY": i // width} for i, u in enumerate(source)]
        else:
            edits[g["name"]] = []
    chapters.setdefault("objectives", {})[str(n)] = {"type": "defeat_all"}
    chapters.setdefault("titles", {})[str(n)] = title.strip()[:40] or f"Chapter {n}"
    added[str(n)] = {"after": after}

    # An empty map on the slot's tile sheet: its most used plain tile.
    stem, info = next((s, i) for s, i in maps.layouts(project.decomp_dir).items() if n in i["chapters"])
    assets = maps.with_base(project.decomp_dir, info["assets"], maps_data.get("bases", {}).get(stem))
    terrain = maps.read_config(assets.config)[1]
    _w, _h, cells = maps.read_layout(info["assets"].layout)
    plains = Counter(m for m in cells if m < len(terrain) and terrain[m] == PLAIN)
    plain = plains.most_common(1)[0][0] if plains else next((m for m, t in enumerate(terrain) if t == PLAIN), 0)
    maps_data.setdefault("layouts", {})[stem] = {"rows": [[plain] * width for _ in range(height)]}

    # Opening: the army, then the groups of the chapter; story: the chapter before leads here.
    opening = []
    for g in loads:
        op = "LOAD2" if g["origin"] == "players" else "LOAD1"
        if g["origin"] in ("players", "opening"):
            opening += [{"op": op, "args": ["1", g["name"]]}, {"op": "ENUN"}]
    scripts[group["beginningSceneEvents"]] = opening + [{"op": "NoFade"}, {"op": "ENDA"}]
    ending = [{"op": "ENDA"}]
    link = next((link for link in data.chapter_links(scripts)[after] if link["ending"]), None)
    if link is not None:
        before = list(scripts.get(link["script"]) or data.script_commands(link["script"]))
        ending = [before[link["at"]], {"op": "ENDA"}]
        before[link["at"]] = {"op": "MNC2", "args": [f"0x{n:X}"]}
        scripts[link["script"]] = before
    elif (name := data.chapter_endings()[after]):   # the chapter before led nowhere: now it leads here
        scripts[name] = story.with_next(scripts.get(name) or data.script_commands(name), n)
    scripts[group["endingSceneEvents"]] = ending

    project.save("chapters", chapters)
    project.save("maps", maps_data)
    project.save("dialogues", dialogues)
    return n
