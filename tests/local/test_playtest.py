"""Local-only playtests: build a project, play the ROM without any window, check the game's memory.

Run with:  FE_MAKER_ROM=path/to/fe8.gba python -m pytest tests/local/test_playtest.py -s
"""

import os
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "server"))

from fe_maker.playtest import Game  # noqa: E402
from fe_maker.project import Project  # noqa: E402

ROM = os.environ.get("FE_MAKER_ROM")
pytestmark = pytest.mark.skipif(not ROM, reason="set FE_MAKER_ROM to run tests that need the ROM")


def test_edited_character_is_on_the_prologue_map(tmp_path):
    project = Project.create(tmp_path / "play", "Play")
    chars = project.load("characters")
    eirika = next(c for c in chars if c["id"] == "CHARACTER_EIRIKA")
    eirika["bases"]["hp"] = 20
    project.save("characters", chars)
    lord = next(c for c in project.load("classes") if c["id"] == eirika["class"])
    out = project.build(Path(ROM), on_output=lambda line: print(line, end=""), for_test=True)

    with Game(out.rom_path, out.map_path) as game:
        assert game.wait_until(lambda: game.chapter() == 0 and game.turn() == 1 and game.units(), seconds=60)
        game.run(60)
        game.screenshot().save(tmp_path / "prologue.png")
        print("screenshot:", tmp_path / "prologue.png", "after", game.frame, "frames")
        assert game.phase() == "player"
        # A unit's HP is its class base plus the character's own base.
        unit = next(u for u in game.units() if u["character"] == 1)
        assert unit["maxHP"] == unit["hp"] == 20 + lord["bases"]["hp"]


def _objects_project(tmp_path):
    """The prologue map drawn with tile sheet 2, a door, a chest and a village next to the start;
    Eirika carries a chest key, Seth a door key and opens the convoy, available in the prologue."""
    import copy
    from collections import Counter

    from fe_maker.decomp import mapobjects, maps, units

    project = Project.create(tmp_path / "objects", "Objects")
    decomp = project.decomp_dir
    layout = maps.layouts(decomp)["PrologueMap"]
    width, height, cells = maps.read_layout(layout["assets"].layout)
    rows = [cells[y * width:(y + 1) * width] for y in range(height)]
    target = maps.with_base(decomp, layout["assets"], "TileConfiguration2")
    rows = maps.convert_by_terrain(decomp, maps.read_config(layout["assets"].config)[1], target, [rows])[0][0]
    terrain = maps.read_config(target.config)[1]
    rule = mapobjects.rules(decomp)["TileConfiguration2.bin"]
    plain = Counter(m for row in rows for m in row if terrain[m] == 0x01).most_common(1)[0][0]
    for y in range(3, 9):
        rows[y][5:14] = [plain] * 9
    for t, (x, y) in ((0x03, (11, 5)), (0x21, (9, 7)), (0x1E, (7, 5))):
        rows[y][x] = next(m for m in rule["tiles"] if terrain[m] == t)
    objects = {"11,5": {"item": "ITEM_ELIXIR", "face": "FID_VillagerGirlYoung", "text": "Prenez cet élixir."},
               "9,7": {"gold": 3000}}
    project.save("maps", {"layouts": {"PrologueMap": {"rows": rows}}, "bases": {"PrologueMap": "TileConfiguration2"},
                          "objects": {"PrologueMap": objects}})
    group = copy.deepcopy(units.read_unit_groups(decomp)["UnitDef_Event_PrologueAlly"].units)
    keys = {"CHARACTER_EIRIKA": ["ITEM_SWORD_RAPIER", "ITEM_CHESTKEY"], "CHARACTER_SETH": ["ITEM_SWORD_STEEL", "ITEM_DOORKEY"]}
    for unit in group:
        unit["items"] = keys[unit["character"]]
    project.save("chapters", {"unitGroups": {"UnitDef_Event_PrologueAlly": group}, "objectives": {}, "convoy": {"0": True}})
    chars = project.load("characters")
    next(c for c in chars if c["id"] == "CHARACTER_SETH")["convoyAccess"] = True
    project.save("characters", chars)
    return project.build(Path(ROM), on_output=lambda line: print(line, end=""), for_test=True)


def test_changed_next_chapter_in_game(tmp_path):
    """Ticket 31: the prologue (survive one turn) ends on chapter 2 instead of chapter 1."""
    from fe_maker.decomp import story
    from fe_maker.decomp.gamedata import DecompData

    project = Project.create(tmp_path / "flow", "Flow")
    decomp = DecompData(project.decomp_dir)
    link = next(link for link in decomp.chapter_links()[0] if link["ending"])
    commands = decomp.script_commands(link["script"])
    assert story.links(commands)[0]["to"] == 1
    commands[link["at"]] = {"op": link["op"], "args": ["0x2"]}
    project.save("dialogues", {"messages": {}, "scripts": {link["script"]: commands}})
    project.save("chapters", {"unitGroups": {}, "objectives": {"0": {"type": "defense", "turns": 1, "seize": [],
                                                                       "statusText": "Survive"}}})
    assert [p for p in project.validate() if p.severity == "error"] == []
    out = project.build(Path(ROM), on_output=lambda line: print(line, end=""), for_test=True)

    with Game(out.rom_path, out.map_path) as game:
        _on_map(game)
        # End the turn from the map menu (A on an empty tile, End is the last entry).
        game.move_cursor(1, 1)
        game.press("A")
        game.press("UP")
        game.press("A")
        ok = game.wait_until(lambda: game.chapter() == 2, seconds=240, step=30, tap="A")
        game.screenshot().save(tmp_path / "after.png")
        print("screenshot:", tmp_path / "after.png", "chapter", game.chapter(), "turn", game.turn())
        assert ok


def _on_map(game):
    assert game.wait_until(lambda: game.chapter() == 0 and game.turn() == 1 and game.phase() == "player" and game.units())
    game.run(90)


def test_painted_door_chest_village_and_convoy_in_game(tmp_path):
    out = _objects_project(tmp_path)
    with Game(out.rom_path, out.map_path) as game:
        _on_map(game)
        assert game.terrain(7, 5) == 0x1E and game.terrain(9, 7) == 0x21 and game.terrain(11, 5) == 0x03
        # Seth (door key) opens the door from where he stands, then Canto: "Supply" opens the convoy.
        game.move_cursor(8, 5)
        game.press("A")
        game.press("A")
        game.press("DOWN")   # Attack, Door, ...
        game.press("A")
        game.run(120)
        assert game.terrain(7, 5) != 0x1E
        game.press("A")
        game.press("DOWN")   # Supply, Wait
        game.press("A")
        game.run(30)
        # Eirika (chest key) opens the chest: 3000 gold.
        game.move_cursor(9, 5)
        game.press("A")
        game.move_cursor(9, 7)
        game.press("A")
        game.run(60)
        game.press("DOWN")   # Attack, Chest, ...
        game.press("A")
        assert game.wait_until(lambda: game.gold() == 3000, seconds=20, step=20, tap="A")
        assert game.terrain(9, 7) == 0x20
    with Game(out.rom_path, out.map_path) as game:
        _on_map(game)
        # Eirika visits the village: an elixir, and the village closes.
        game.move_cursor(9, 5)
        game.press("A")
        game.move_cursor(11, 5)
        game.press("A")
        game.run(60)
        game.press("A")      # Visit
        assert game.wait_until(lambda: 0x6D in next(u for u in game.units() if u["character"] == 1)["items"],
                               seconds=30, step=20, tap="A")
        assert game.wait_until(lambda: game.terrain(11, 5) == 0x04, seconds=10, tap="A")


def test_enemy_destroys_a_painted_village(tmp_path):
    """Ticket 35: an enemy that pillages ruins a village painted by the project."""
    import copy

    from fe_maker.decomp import mapobjects, maps, units

    project = Project.create(tmp_path / "ruins", "Ruins")
    decomp = project.decomp_dir
    layout = maps.layouts(decomp)["PrologueMap"]
    width, height, cells = maps.read_layout(layout["assets"].layout)
    rows = [cells[y * width:(y + 1) * width] for y in range(height)]
    rule = mapobjects.rules(decomp)[layout["assets"].config.name]
    template = rule["ruins"][0]
    # The game's village, gate at (11, 5)
    (gi, gj), before = template["gate"], template["before"]
    for j, row in enumerate(before):
        rows[5 - gj + j][11 - gi:11 - gi + len(row)] = list(row)
    plain = rows[5][9]       # plains in front of the gate, for the looter to reach it
    rows[6][10:13] = [plain] * 3
    rows[7][10:13] = [plain] * 3
    project.save("maps", {"layouts": {"PrologueMap": {"rows": rows}}})
    group = copy.deepcopy(units.read_unit_groups(decomp)["UnitDef_Event_PrologueEnemy"].units)
    looter = group[1]
    looter.update({"x": 12, "y": 7, "endX": 12, "endY": 7, "ai": [6, 5, 2, 0]})
    # Only the looter, and a chapter to survive: O'Neill dying on Seth's counter would end it first
    project.save("chapters", {"unitGroups": {"UnitDef_Event_PrologueEnemy": [looter]},
                              "objectives": {"0": {"type": "defense", "turns": 5, "seize": [], "statusText": "Survive"}}})
    out = project.build(Path(ROM), on_output=lambda line: print(line, end=""), for_test=True)

    with Game(out.rom_path, out.map_path) as game:
        _on_map(game)
        assert game.terrain(11, 5) == 0x03
        taken = {(u["x"], u["y"]) for army in ("Blue", "Red") for u in game.units(army)}
        game.move_cursor(*next(c for c in ((0, 0), (14, 0), (0, 9), (14, 9), (7, 0)) if c not in taken))
        game.press("A")
        game.press("UP")
        game.press("A")      # End the turn: the enemy phase
        ok = game.wait_until(lambda: game.terrain(11, 5) == mapobjects.RUINS_TERRAIN, seconds=120, step=30, tap="A")
        game.screenshot().save(tmp_path / "ruins.png")
        print("screenshot:", tmp_path / "ruins.png", "enemies", game.units("Red"))
        assert ok


def _end_turn(game):
    taken = {(u["x"], u["y"]) for army in ("Blue", "Red", "Green") for u in game.units(army)}
    game.move_cursor(*next((x, y) for y in range(10) for x in range(15) if (x, y) not in taken))
    game.press("A")
    game.press("UP")
    game.press("A")


def test_other_character_seizes(tmp_path):
    """Ticket 37: Seth seizes when the project lets him (in the game, only the route's lord can)."""
    project = Project.create(tmp_path / "seize", "Seize")
    chars = project.load("characters")
    next(c for c in chars if c["id"] == "CHARACTER_SETH")["canSeize"] = True
    project.save("characters", chars)
    project.save("chapters", {"unitGroups": {}, "objectives": {"0": {"type": "seize", "seize": [{"x": 6, "y": 5}],
                                                                     "seizeLabel": "throne", "statusText": "Seize"}}})
    out = project.build(Path(ROM), on_output=lambda line: print(line, end=""), for_test=True)
    with Game(out.rom_path, out.map_path) as game:
        _on_map(game)
        game.run(210)
        seth = next(u for u in game.units() if u["character"] == 2)
        game.move_cursor(seth["x"], seth["y"])
        game.press("A")
        game.move_cursor(6, 5)
        game.press("A", wait=60)
        game.press("A", wait=60)      # Seize, the first entry
        assert game.wait_until(lambda: game.chapter() == 1, seconds=120, step=30, tap="A")


def test_world_map_ending_in_test_builds(tmp_path):
    """Ticket 38: chapter 1 ends through the world map (MoveToChapter); a test build goes on to Castle
    Frelia (56), not back to the prologue."""
    project = Project.create(tmp_path / "wm", "WM")
    survive = {"type": "defense", "turns": 1, "seize": [], "statusText": "Survive"}
    project.save("chapters", {"unitGroups": {}, "objectives": {"0": survive, "1": survive}})
    out = project.build(Path(ROM), on_output=lambda line: print(line, end=""), for_test=True)
    with Game(out.rom_path, out.map_path) as game:
        for chapter in (0, 1):
            assert game.wait_until(lambda: game.chapter() == chapter and game.turn() == 1 and game.phase() == "player"
                                   and game.units(), seconds=300, step=30, tap="A")
            game.run(300)
            _end_turn(game)
        assert game.wait_until(lambda: game.chapter() not in (0, 1), seconds=300, step=30, tap="A")
        assert game.chapter() == 0x38


def test_chapter_one_straight_to_chapter_two(tmp_path):
    """Ticket 39: chapter 1 sent straight to chapter 2 (no world map) used to stay on a black screen: the game
    took chapter 2 for a skirmish (its world map place never reached). It is now played as a story chapter."""
    from fe_maker.decomp.gamedata import DecompData

    project = Project.create(tmp_path / "direct", "Direct")
    survive = {"type": "defense", "turns": 1, "seize": [], "statusText": "Survive"}
    project.save("chapters", {"unitGroups": {}, "objectives": {"0": survive, "1": survive}})
    commands = DecompData(project.decomp_dir).script_commands("EventScr_Ch1_EndingScene")
    at = next(i for i, c in enumerate(commands) if c.get("op") == "MoveToChapter")
    commands[at] = {"op": "MNC2", "args": ["0x2"]}
    dialogues = project.load("dialogues")
    dialogues["scripts"] = {"EventScr_Ch1_EndingScene": commands}
    project.save("dialogues", dialogues)
    out = project.build(Path(ROM), on_output=lambda line: print(line, end=""), for_test=True)
    with Game(out.rom_path, out.map_path) as game:
        for chapter in (0, 1):
            assert game.wait_until(lambda: game.chapter() == chapter and game.turn() == 1 and game.phase() == "player"
                                   and game.units(), seconds=300, step=30, tap="A")
            game.run(300)
            _end_turn(game)
        assert game.wait_until(lambda: game.chapter() == 2 and game.turn() == 1 and game.phase() == "player",
                               seconds=300, step=30, tap="A")
