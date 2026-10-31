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

chapters.json "added" {index: {"after": index}} remembers which slots the project took; "cleared" lists the chapters
whose event lists are emptied at build time (DecompData.apply_chapters).

A blank project (ticket 66, `start_blank`) clears chapter 0, the one the engine starts on, the same way: the game's
other chapters are then no longer part of the story (chapters.json "blank"), so they are free slots and the
editors hide them. Without its characters, only the first lord stays in the list, the others wait to be reused by
"new character" (`DecompData.reusable_characters`).
"""

from __future__ import annotations

from collections import Counter

from .decomp import dialogues, maps, objectives, story, units
from .decomp.gamedata import DecompData
from .validation import MAP_MIN_HEIGHT, MAP_MIN_WIDTH, Problem

PLAIN = 0x01   # terrain byte of plains (src/data/terrain names)
MAX_SIZE = (64, 64)
BLANK_LORD = "CHARACTER_EIRIKA"   # a blank project needs one unit, and the game is lost when this one dies
BLANK_LORD_ITEMS = ("ITEM_SWORD_RAPIER", "ITEM_VULNERARY")


class ChapterError(Exception):
    pass


def story_order(links: list[list[dict]]) -> list[int]:
    """The chapters a story reaches from the first one, in the order it reaches them."""
    order = [0]
    for chapter in order:
        for link in sorted(links[chapter], key=lambda link: not link.get("ending")):
            to = link.get("to")
            if isinstance(to, int) and 0 <= to < len(links) and to not in order:
                order.append(to)
    return order


def reached_chapters(links: list[list[dict]]) -> set[int]:
    return set(story_order(links))


def unplayed_groups(project) -> set[str]:
    """Unit groups of the game a blank project does not use: they are still in the decomp, nobody meets them."""
    stored = project.load("chapters")
    if not stored.get("blank"):
        return set()
    data = DecompData(project.decomp_dir)
    data._load_chapter_events()
    played = reached_chapters(data.chapter_links(project.load("dialogues").get("scripts", {})))
    played |= {int(k) for k in stored.get("added", {})}
    groups = units.all_chapter_unit_groups(project.decomp_dir)
    return set(units.read_unit_groups(project.decomp_dir)) - {g["name"] for index in played for g in groups.get(index, [])}


def free_slots(data: DecompData, scripts: dict, taken: set[int], blank: bool = False) -> list[int]:
    """Chapters a new one can take: own map, own event group, reached neither by the game's story (unless the project
    is blank) nor the project's (a chapter of the game's story the project has cut off for now is not free: ticket 55)."""
    data._load_chapter_events()
    chapters = data.chapter_settings["chapters"]
    reached = reached_chapters(data.chapter_links(scripts))
    if not blank:
        reached |= reached_chapters(data.chapter_links())
    symbols = Counter(data._chapter_event_symbol(c) for c in chapters)
    layouts = {i: len(info["chapters"]) for info in maps.layouts(data.decomp_dir).values() for i in info["chapters"]}
    return [i for i, c in enumerate(chapters)
            if i not in reached and i not in taken and layouts.get(i) == 1
            and (symbol := data._chapter_event_symbol(c)) and symbols[symbol] == 1]


def _opening(loads: list[dict]) -> list[dict]:
    opening = []
    for g in loads:
        op = "LOAD2" if g["origin"] == "players" else "LOAD1"
        if g["origin"] in ("players", "opening"):
            opening += [{"op": op, "args": ["1", g["name"]]}, {"op": "ENUN"}]
    return opening + [{"op": "NoFade"}, {"op": "ENDA"}]


def _clear_chapter(project, data: DecompData, n: int, width: int, height: int, title: str, chapters: dict, maps_data: dict,
                   army: list | None) -> tuple[dict, list[dict]]:
    """Chapter n as an empty one, `army` (units, else its own) in a block at the top left; its event group and the
    groups it loads."""
    symbol = data._chapter_event_symbol(data.chapter_settings["chapters"][n])
    group = objectives.event_group(data.event_sources, symbol)

    # The slot's own player group (the tower's are placeholders) is reused, the other groups emptied.
    games = units.read_unit_groups(project.decomp_dir)
    loads = units.chapter_unit_groups(project.decomp_dir, symbol)
    edits = chapters.setdefault("unitGroups", {})
    for g in loads:
        if g["origin"] == "players":
            own = len(games[g["name"]].units)
            source = army if army is not None else games[g["name"]].units
            edits[g["name"]] = [{**u, "slot": i if i < own else None, "x": i % width, "y": i // width,
                                 "endX": i % width, "endY": i // width} for i, u in enumerate(source)]
        else:
            edits[g["name"]] = []
    chapters.setdefault("objectives", {})[str(n)] = {"type": "defeat_all"}
    chapters.setdefault("titles", {})[str(n)] = title.strip()[:40] or f"Chapter {n}"
    if n not in chapters.setdefault("cleared", []):
        chapters["cleared"].append(n)

    # An empty map on the slot's tile sheet: its most used plain tile.
    stem, info = next((s, i) for s, i in maps.layouts(project.decomp_dir).items() if n in i["chapters"])
    assets = maps.with_base(project.decomp_dir, info["assets"], maps_data.get("bases", {}).get(stem))
    terrain = maps.read_config(assets.config)[1]
    _w, _h, cells = maps.read_layout(info["assets"].layout)
    plains = Counter(m for m in cells if m < len(terrain) and terrain[m] == PLAIN)
    plain = plains.most_common(1)[0][0] if plains else next((m for m, t in enumerate(terrain) if t == PLAIN), 0)
    maps_data.setdefault("layouts", {})[stem] = {"rows": [[plain] * width for _ in range(height)]}
    if info.get("changes"):
        maps_data.setdefault("changes", {})[stem] = []
    return group, loads


def start_blank(project, characters: bool, title: str, hero: str) -> None:
    """Turn a new project into a blank one: chapter 0 emptied, the game's other chapters out of the story; with
    `characters`, the game's characters too except the first lord (renamed `hero`) and their supports."""
    data = DecompData(project.decomp_dir)
    dialogues, chapters, maps_data = project.load("dialogues"), project.load("chapters"), project.load("maps")
    scripts = dialogues.setdefault("scripts", {})
    data._load_chapter_events()
    chapters["blank"] = True
    project.set_world_map(False)   # the world map only knows the game's places (story.py)
    if characters:
        players = next(g["name"] for g in units.chapter_unit_groups(
            project.decomp_dir, data._chapter_event_symbol(data.chapter_settings["chapters"][0])) if g["origin"] == "players")
        lord = next(c for c in project.load("characters") if c["id"] == BLANK_LORD)
        army = [{**units.read_unit_groups(project.decomp_dir)[players].units[0], "character": BLANK_LORD, "class": lord["class"],
                 "level": lord["level"], "items": list(BLANK_LORD_ITEMS)}]
    else:
        army = None
    group, loads = _clear_chapter(project, data, 0, 15, 10, title, chapters, maps_data, army)
    scripts[group["beginningSceneEvents"]] = _opening(loads)
    scripts[group["endingSceneEvents"]] = [{"op": "ENDA"}]
    if characters:
        removed = data.blank_dropped_characters()
        kept = [c for c in project.load("characters") if c["id"] not in removed]
        for c in kept:
            if c["id"] == BLANK_LORD:
                c["name"] = hero.strip() or c["name"]
        project.save("characters", kept)
        dialogues["supports"] = []
        chapters["blankCharacters"] = "all"
    project.save("chapters", chapters)
    project.save("maps", maps_data)
    project.save("dialogues", dialogues)


def tidy_scripts(project) -> None:
    """A dialogue removed before its command left with it (ticket 104): nothing can show it, and the scene may be hidden."""
    stored = project.load("dialogues")
    scripts = stored.get("scripts", {})
    kept = dialogues.without_lost_messages(scripts, stored.get("quotes", []))
    if kept != scripts:
        project.save("dialogues", {**stored, "scripts": kept})


def tidy_blank(project) -> None:
    """Blank projects made when the summons, citizens and the like stayed in the list (ticket 89): they leave it, unless
    the project changed them or uses them."""
    chapters = project.load("chapters")
    if chapters.get("blankCharacters") is not True:
        return
    data = DecompData(project.decomp_dir)
    game = {c["id"]: c for c in data.export_characters()}
    if any(c["id"] in data.reusable_characters() for c in project.load("characters")):
        return   # scope.py: the user chose which characters to keep
    dropped = data.blank_dropped_characters()
    used = {u.get("character") for group in chapters.get("unitGroups", {}).values() for u in group}
    project.save("characters", [c for c in project.load("characters")
                                if c["id"] not in dropped or c["id"] in used or game.get(c["id"]) != c])
    chapters["blankCharacters"] = "all"
    project.save("chapters", chapters)


def drop_chapters(project, data: DecompData, kept: set[int], title: str, hero: str) -> None:
    """Keep only these chapters of the story (scope.py): the others are free slots; a kept chapter that led to one
    leads nowhere; without the first chapter the project starts blank."""
    scripts = project.load("dialogues").get("scripts", {})
    links = data.chapter_links(scripts)
    edited = {}

    def next_kept(chapter: int, seen: set[int]) -> int | None:
        """The first kept chapter after a removed one (the game's stopovers, Castle Frelia...)."""
        if chapter in kept:
            return chapter
        seen.add(chapter)
        for link in links[chapter] if chapter < len(links) else []:
            to = link.get("to")
            if isinstance(to, int) and to not in seen and (found := next_kept(to, seen)) is not None:
                return found
        return None

    for index in kept:
        for link in links[index]:
            if isinstance(link.get("to"), int) and link["to"] not in kept:
                script = link["script"]
                commands = edited.setdefault(script, list(scripts.get(script) or data.script_commands(script)))
                to = next_kept(link["to"], {index})
                commands[link["at"]] = {"op": "#", "text": ""} if to is None else {"op": "MNC2", "args": [f"0x{to:X}"]}
    dialogues = project.load("dialogues")
    for name, commands in edited.items():
        dialogues.setdefault("scripts", {})[name] = [c for c in commands if c.get("op") != "#" or c.get("text")]
    project.save("dialogues", dialogues)
    chapters = project.load("chapters")
    chapters["blank"] = True
    chapters["added"] = {k: v for k, v in chapters.get("added", {}).items() if int(k) in kept}
    project.save("chapters", chapters)
    project.set_world_map(False)
    if 0 not in kept:
        start_blank(project, False, title, hero)


def story_problems(project) -> list[Problem]:
    """What is left to do on the chapters a blank project or an added chapter brought: shown in "To do"."""
    stored = project.load("chapters")
    if not stored.get("blank") and not stored.get("added"):
        return []
    data = DecompData(project.decomp_dir)
    data._load_chapter_events()
    links = data.chapter_links(project.load("dialogues").get("scripts", {}))
    settings = data.chapter_settings["chapters"]
    titles = stored.get("titles", {})
    edits = stored.get("unitGroups", {})
    games = units.read_unit_groups(project.decomp_dir)
    problems = []
    for index in story_order(links) + sorted({int(k) for k in stored.get("added", {})} - set(story_order(links))):
        if str(index) not in stored.get("added", {}) and not (stored.get("blank") and index in stored.get("cleared", [])):
            continue
        title = titles.get(str(index), str(index))
        loads = units.chapter_unit_groups(project.decomp_dir, data._chapter_event_symbol(settings[index]))
        groups = [edits[g["name"]] if g["name"] in edits else games[g["name"]].units for g in loads
                  if g["name"] in edits or g["name"] in games]
        enemies = sum(u.get("side") == "enemy" for group in groups for u in group)
        if not enemies:
            problems.append(Problem("warning", "chapters", str(index), "units", "chapterNoEnemies", {"title": title}))
        if not links[index]:
            problems.append(Problem("warning", "chapters", str(index), "story", "chapterNoNext", {"title": title}))
    return problems


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
    slots = free_slots(data, scripts, {int(k) for k in added}, chapters.get("blank", False))
    if not slots:
        raise ChapterError("noFreeChapter")
    n = slots[0]
    games = units.read_unit_groups(project.decomp_dir)
    edits = chapters.setdefault("unitGroups", {})
    before = units.chapter_unit_groups(project.decomp_dir, data._chapter_event_symbol(data.chapter_settings["chapters"][after]))
    army = next((g["name"] for g in before if g["origin"] == "players"), None)
    source = (edits.get(army) or games[army].units) if army else None
    added[str(n)] = {"after": after}
    group, loads = _clear_chapter(project, data, n, width, height, title, chapters, maps_data, source)

    # Opening: the army, then the groups of the chapter; story: the chapter before leads here.
    scripts[group["beginningSceneEvents"]] = _opening(loads)
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
