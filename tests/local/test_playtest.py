"""Local-only playtests: build a project, play the ROM without any window, check the game's memory.

Run with:  FE_MAKER_ROM=path/to/fe8.gba python -m pytest tests/local/test_playtest.py -s
"""

import os
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "server"))

from fe_maker.decomp.gamedata import DecompData  # noqa: E402
from fe_maker.playtest import UNIT_SIZE, Game  # noqa: E402
from fe_maker.project import Project  # noqa: E402

ROM = os.environ.get("FE_MAKER_ROM")
pytestmark = pytest.mark.skipif(not ROM, reason="set FE_MAKER_ROM to run tests that need the ROM")


def _without_preparations(project, *chapters):
    """Added chapters stop on the preparations screen: these tests go straight to the battle."""
    data = project.load("chapters")
    data["prep"] = {str(index): False for index in chapters}
    project.save("chapters", data)


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
    objects = {"11,5": {"item": "ITEM_ELIXIR", "face": "FID_Seth", "text": "Prenez cet élixir."},
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


def test_fog_of_war(tmp_path):
    project = Project.create(tmp_path / "fog", "Fog")
    chapters = project.load("chapters")
    chapters["fog"] = {"0": 4}
    project.save("chapters", chapters)
    out = project.build(Path(ROM), on_output=lambda line: None, for_test=True)

    with Game(out.rom_path, out.map_path) as game:
        assert game.wait_until(lambda: game.chapter() == 0 and game.turn() == 1 and game.units(), seconds=60)
        game.run(60)
        game.screenshot().save(tmp_path / "fog.png")
        print("screenshot:", tmp_path / "fog.png")
        assert game.read("gPlaySt", 0x0D) == 4   # chapterVisionRange


def test_imported_battle_animation(tmp_path):
    """Ticket 44: a battle animation converted from FEditor's format (here one of the game's, exported then
    imported back) is added after the game's and played when Seth (Paladin) attacks with his sword."""
    import shutil

    from fe_maker.decomp import banim, banim_import

    project = Project.create(tmp_path / "banim", "Banim")
    decomp = project.decomp_dir
    entry = next(e for e in project_classes(decomp) if e.fields["number"] == "CLASS_PALADIN")
    conf = entry.fields["pBattleAnimDef"].lstrip("&").strip()
    number = next(d["number"] for d in banim.configs(decomp)[conf] if d["weapon"] == "ITYPE_SWORD")
    symbol = next(a.symbol for a in banim.table(decomp) if a.number == number)
    script, frames = banim_import.export_feditor(decomp, symbol)
    converted = banim_import.convert(banim_import.symbol_of("1"), script, frames)
    folder = project.root / "assets" / "animations" / "1"
    shutil.rmtree(folder, ignore_errors=True)
    for rel, content in banim_import.stored_files(banim_import.symbol_of("1"), converted).items():
        path = folder / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content) if isinstance(content, bytes) else path.write_text(content, encoding="utf-8", newline="\n")
    project.save("animations", {"animations": {"1": {"name": "Paladin (round trip)", "frames": converted.frames,
                                                     "sheets": len(converted.sheets)}},
                                "classes": {"CLASS_PALADIN": {"sword": "new:1"}}})
    out = project.build(Path(ROM), on_output=lambda line: print(line, end=""), for_test=True)
    new_index = len(banim.table(decomp))   # numbers start at 1, indexes at 0

    with Game(out.rom_path, out.map_path) as game:
        _on_map(game)
        game.run(210)
        seth = next(u for u in game.units() if u["character"] == 2)
        # The simplified prologue puts an enemy right next to Seth: he attacks without moving.
        enemy = next(u for u in game.units("Red") if abs(u["x"] - seth["x"]) + abs(u["y"] - seth["y"]) == 1)
        game.move_cursor(seth["x"], seth["y"])
        game.press("A")
        game.press("A", wait=60)
        game.press("A", wait=30)      # Attack
        game.press("A", wait=30)      # his first weapon, a sword
        game.press("A", wait=30)      # the target
        game.press("A", wait=30)      # the forecast
        seen = game.wait_until(lambda: game.read("gBanimIdx", 2, width=16) == new_index
                               or game.read("gBanimIdx", 0, width=16) == new_index, seconds=20, step=5)
        game.run(120)
        game.screenshot().save(tmp_path / "battle.png")
        print("screenshot:", tmp_path / "battle.png")
        assert seen
        # The battle ends and the game goes on: the enemy loses HP or dies.
        assert game.wait_until(lambda: all(u["hp"] < enemy["hp"] for u in game.units("Red")
                                           if (u["x"], u["y"]) == (enemy["x"], enemy["y"]))
                               and game.phase() == "player", seconds=60, step=20)


def project_classes(decomp):
    from fe_maker.decomp.gamedata import DecompData

    return DecompData(decomp).classes.entries


def test_test_this_chapter(tmp_path):
    """"Test this chapter": the test build starts on the chosen chapter's map (here chapter 2)."""
    project = Project.create(tmp_path / "ch2", "Ch2")
    project.set_test_options({"start": "map", "chapter": 2})
    out = project.build(Path(ROM), on_output=lambda line: None, for_test=True)
    with Game(out.rom_path, out.map_path) as game:
        ok = game.wait_until(lambda: game.chapter() == 2 and game.turn() == 1 and game.units(), seconds=300, step=30, tap="A")
        game.run(300)
        game.screenshot().save(tmp_path / "ch2.png")
        print("screenshot:", tmp_path / "ch2.png", "units", game.units())
        assert ok


def test_test_chapter_one_army(tmp_path):
    """Ticket 45: chapter 1 does not load its army (the game moves the prologue's army onto its places): the test
    build loads the chapter's own player units, Eirika and Seth are on the map."""
    project = Project.create(tmp_path / "ch1", "Ch1")
    project.set_test_options({"start": "map", "chapter": 1})
    out = project.build(Path(ROM), on_output=lambda line: None, for_test=True)
    with Game(out.rom_path, out.map_path) as game:
        ok = game.wait_until(lambda: game.chapter() == 1 and game.turn() == 1 and game.units("Red"),
                             seconds=300, step=30, tap="A")
        game.run(600)
        game.screenshot().save(tmp_path / "ch1.png")
        blue = game.units("Blue")
        print("screenshot:", tmp_path / "ch1.png", "blue", blue)
        assert ok
        assert {1, 2} <= {u["character"] for u in blue if u["x"] >= 0}


def test_added_characters_on_the_prologue_map(tmp_path):
    """An ally and an enemy the project adds (free entries 0x1B and 0x55 of the character table)."""
    import copy

    from fe_maker.decomp import units
    from fe_maker.decomp.gamedata import DecompData

    project = Project.create(tmp_path / "added", "Added")
    data = DecompData(project.decomp_dir)
    chars = project.load("characters")
    ally = data.new_character(True, {c["id"] for c in chars})
    ally.update(name="Aliénor", portraitId=2, level=3, **{"class": "CLASS_MYRMIDON_F"})
    ally["bases"]["hp"] = 4
    ally["weaponRanks"] = {"sword": "C"}
    enemy = data.new_character(False, {c["id"] for c in chars})
    enemy.update(name="Morgane", level=5, **{"class": "CLASS_FIGHTER"})
    project.save("characters", [*chars, ally, enemy])
    groups = units.read_unit_groups(project.decomp_dir)
    allies = copy.deepcopy(groups["UnitDef_Event_PrologueAlly"].units)
    allies.append({**copy.deepcopy(allies[1]), "slot": None, "character": ally["id"], "class": "CLASS_MYRMIDON_F",
                   "level": 3, "x": 9, "y": 6, "endX": 9, "endY": 6, "items": ["ITEM_SWORD_IRON"]})
    enemies = copy.deepcopy(groups["UnitDef_Event_PrologueEnemy"].units)
    enemies[1]["character"] = enemy["id"]
    project.save("chapters", {"unitGroups": {"UnitDef_Event_PrologueAlly": allies,
                                             "UnitDef_Event_PrologueEnemy": enemies}, "objectives": {}})
    myrmidon = next(c for c in project.load("classes") if c["id"] == "CLASS_MYRMIDON_F")
    out = project.build(Path(ROM), on_output=lambda line: print(line, end=""), for_test=True)

    with Game(out.rom_path, out.map_path) as game:
        assert game.wait_until(lambda: game.chapter() == 0 and game.turn() == 1 and game.units(), seconds=60)
        game.run(60)
        new_ally = next(u for u in game.units() if u["character"] == 0x1B)
        assert (new_ally["x"], new_ally["y"], new_ally["level"]) == (9, 6, 3)
        assert new_ally["maxHP"] == 4 + myrmidon["bases"]["hp"]
        assert any(u["character"] == 0x55 for u in game.units("Red"))
        game.move_cursor(9, 6)
        game.run(30)
        game.screenshot().save(tmp_path / "added.png")
        print("screenshot:", tmp_path / "added.png")


def test_added_weapon_in_seth_inventory(tmp_path):
    """A weapon the project adds (a copy of the javelin, item 0xCE) carried by Seth in the prologue."""
    import copy

    from fe_maker.decomp import units
    from fe_maker.decomp.gamedata import DecompData

    project = Project.create(tmp_path / "weapon", "Weapon")
    items = project.load("items")
    axe = DecompData(project.decomp_dir).new_item("ITEM_LANCE_JAVELIN", {i["id"] for i in items})
    axe.update(name="Pilum", might=11)
    project.save("items", [*items, axe])
    allies = copy.deepcopy(units.read_unit_groups(project.decomp_dir)["UnitDef_Event_PrologueAlly"].units)
    allies[0]["items"] = [axe["id"], "ITEM_SWORD_STEEL"]
    project.save("chapters", {"unitGroups": {"UnitDef_Event_PrologueAlly": allies}, "objectives": {}})
    out = project.build(Path(ROM), on_output=lambda line: print(line, end=""), for_test=True)

    with Game(out.rom_path, out.map_path) as game:
        assert game.wait_until(lambda: game.chapter() == 0 and game.turn() == 1 and game.units(), seconds=60)
        seth = next(u for u in game.units() if u["character"] == 2)
        assert seth["items"][0] == 0xCE
        item = game.address("gItemData") + 0xCE * 36
        assert game.read(item, 0x15) == 11   # might


def test_added_class_moves_on_the_map(tmp_path):
    """Seth in a class the project adds (a copy of the paladin, class 0x80): his moving map sprite comes from
    the extended unit_icon_move_table, his promotion row from gPromoJidLut."""
    from fe_maker.decomp.gamedata import DecompData

    project = Project.create(tmp_path / "klass", "Klass")
    classes = project.load("classes")
    knight = DecompData(project.decomp_dir).new_class("CLASS_PALADIN", {c["id"] for c in classes})
    knight.update(name="Templier", mov=9)
    project.save("classes", [*classes, knight])
    chars = project.load("characters")
    next(c for c in chars if c["id"] == "CHARACTER_SETH")["class"] = knight["id"]
    project.save("characters", chars)
    out = project.build(Path(ROM), on_output=lambda line: print(line, end=""), for_test=True)

    with Game(out.rom_path, out.map_path) as game:
        _on_map(game)
        seth = next(u for u in game.units() if u["character"] == 2)
        assert seth["class"] == 0x80
        game.move_cursor(seth["x"], seth["y"])
        game.press("A")
        game.move_cursor(seth["x"] - 2, seth["y"])
        game.press("A")
        game.run(60)
        game.screenshot().save(tmp_path / "moved.png")
        print("screenshot:", tmp_path / "moved.png")
        game.press("UP")     # the menu wraps: its last line, Wait
        game.press("A")
        game.run(30)
        moved = next(u for u in game.units() if u["character"] == 2)
        assert (moved["x"], moved["y"]) == (seth["x"] - 2, seth["y"])


def test_condition_in_the_prologue_opening(tmp_path):
    """Conditions and jumps written by the editor's forms compile and run (the prologue still starts)."""
    from fe_maker.decomp.gamedata import DecompData

    project = Project.create(tmp_path / "cond", "Cond")
    commands = DecompData(project.decomp_dir).script_commands("EventScr_Prologue_BeginningScene")
    at = next(i for i, c in enumerate(commands) if c["op"] == "LABEL") + 1
    block = [{"op": "CHECK_ALIVE", "args": ["CHARACTER_SETH"]}, {"op": "BEQ", "args": ["0x7", "EVT_SLOT_C", "EVT_SLOT_0"]},
             {"op": "CHECK_TURNS"}, {"op": "SVAL", "args": ["EVT_SLOT_1", "5"]},
             {"op": "BGE", "args": ["0x7", "EVT_SLOT_C", "EVT_SLOT_1"]}, {"op": "GOTO", "args": ["0x7"]},
             {"op": "LABEL", "args": ["0x7"]}]
    dialogues = project.load("dialogues")
    dialogues.setdefault("scripts", {})["EventScr_Prologue_BeginningScene"] = commands[:at] + block + commands[at:]
    project.save("dialogues", dialogues)
    out = project.build(Path(ROM), on_output=lambda line: print(line, end=""), for_test=True)
    with Game(out.rom_path, out.map_path) as game:
        _on_map(game)


def test_imported_map_sprite(tmp_path):
    """A map sprite imported for the paladin class (here the game's archer sheets, as if from the PC): Seth stands
    and walks with it."""
    from fe_maker.decomp import mapsprites
    from fe_maker.decomp.assets import MAP_SPRITE_PALETTES, read_agbpal

    project = Project.create(tmp_path / "sprite", "Sprite")
    icons = project.decomp_dir / "graphics" / "unit_icon"
    stand, size, walk = mapsprites.convert((icons / "wait" / "unit_icon_wait_Archer_sheet.png").read_bytes(),
                                           (icons / "move" / "unit_icon_move_Archer_sheet.png").read_bytes(),
                                           read_agbpal(project.decomp_dir / MAP_SPRITE_PALETTES["player"]))
    folder = project.root / "assets" / "mapsprites" / "PALADIN"
    folder.mkdir(parents=True)
    (folder / "stand.png").write_bytes(stand)
    (folder / "walk.png").write_bytes(walk)
    project.save("mapsprites", {"classes": {"CLASS_PALADIN": "PALADIN"},
                                "sprites": {"PALADIN": {"name": "Archer", "size": size, "walk": True}}})
    out = project.build(Path(ROM), on_output=lambda line: print(line, end=""), for_test=True)

    with Game(out.rom_path, out.map_path) as game:
        _on_map(game)
        seth = next(u for u in game.units() if u["character"] == 2)
        game.screenshot().save(tmp_path / "standing.png")
        game.move_cursor(seth["x"], seth["y"])
        game.press("A")
        game.move_cursor(seth["x"] - 2, seth["y"])
        game.press("A", wait=10)
        game.screenshot().save(tmp_path / "walking.png")
        game.run(60)
        game.press("UP")
        game.press("A")
        game.run(30)
        moved = next(u for u in game.units() if u["character"] == 2)
        assert (moved["x"], moved["y"]) == (seth["x"] - 2, seth["y"])
        print("screenshots:", tmp_path)


def test_game_options(tmp_path):
    """Game options page: a new game starts with fast text and no auto cursor; the comfort changes compile."""
    project = Project.create(tmp_path / "options", "Options")
    project.set_game_options({"textSpeed": 2, "autoCursor": 1, "skipOpening": True, "quickChapterTitle": True,
                              "holdAToSpeedUp": True})
    out = project.build(Path(ROM), on_output=lambda line: print(line, end=""), for_test=True)
    with Game(out.rom_path, out.map_path) as game:
        _on_map(game)
        bits = game.read("gPlaySt", 0x40)   # PlaySt_OptionBits: autoCursor bit 4, textSpeed bits 5-6
        assert (bits >> 5) & 3 == 2 and (bits >> 4) & 1 == 1


def test_stationary_enemy_shows_no_movement_range(tmp_path):
    """Game option "no movement range for units that never move": O'Neill (prologue boss, movement AI 3) selected,
    his movement map holds only his own tile."""
    project = Project.create(tmp_path / "range", "Range")
    project.set_game_options({"stationaryRange": True})
    out = project.build(Path(ROM), on_output=lambda line: print(line, end=""), for_test=True)
    with Game(out.rom_path, out.map_path) as game:
        _on_map(game)
        boss = next(u for u in game.units("Red") if u["character"] == 0x68)   # CHARACTER_ONEILL
        game.move_cursor(boss["x"], boss["y"])
        game.press("A")
        game.run(30)
        width, height = game.read("gBmMapSize", 0, width=16), game.read("gBmMapSize", 2, width=16)
        rows = game.read("gBmMapMovement", width=32)
        reachable = sum(1 for y in range(height) for x in range(width)
                        if game.read(game.read(rows + 4 * y, width=32) + x) < 0x7F)
        game.screenshot().save(tmp_path / "range.png")
        print("screenshot:", tmp_path / "range.png")
        assert reachable == 1


def test_added_chapter(tmp_path):
    """A chapter added after the prologue (a free slot, the tower's first floor): "Test this chapter" starts on its
    empty 15 x 10 map with the army in a block at the top left."""
    from fe_maker import newchapter

    project = Project.create(tmp_path / "added", "Added")
    index = newchapter.add_chapter(project, 0, 15, 10, "Le Fort")
    _without_preparations(project, index)
    project.set_test_options({"start": "map", "chapter": index})
    out = project.build(Path(ROM), on_output=lambda line: None, for_test=True)
    with Game(out.rom_path, out.map_path) as game:
        ok = game.wait_until(lambda: game.chapter() == index and game.turn() == 1 and game.units(), seconds=300, step=30,
                             tap="A")
        game.run(120)
        game.screenshot().save(tmp_path / "added.png")
        print("screenshot:", tmp_path / "added.png", "units", game.units())
        assert ok
        assert (game.read("gBmMapSize", 0, width=16), game.read("gBmMapSize", 2, width=16)) == (15, 10)
        assert all(u["y"] == 0 for u in game.units())


def test_imported_music_in_the_prologue(tmp_path):
    """A MIDI (here one of the game's) imported as the prologue's player phase music: it takes a free row of the song
    table and the music player plays it on the map."""
    import shutil

    project = Project.create(tmp_path / "music", "Music")
    folder = project.root / "assets" / "music"
    folder.mkdir(parents=True)
    shutil.copy(project.decomp_dir / "sound/songs/midi/song010_agbfe3_bgm_map_pl3.mid", folder / "theme.mid")
    project.save("music", {"songs": {"theme": {"name": "Theme"}}, "chapters": {"0": {"bluePhase": "theme"}}})
    out = project.build(Path(ROM), on_output=lambda line: print(line, end=""), for_test=True)
    with Game(out.rom_path, out.map_path) as game:
        _on_map(game)
        game.run(120)
        header = game.read("gSongTable", 87 * 8, width=32)
        players = [game.read("gMPlayTable", 12 * i, width=32) for i in range(2)]   # struct MusicPlayer: info first
        playing = {game.read(info, 0, width=32) for info in players}   # MusicPlayerInfo: songHeader first
        print("song 87", hex(header), "playing", [hex(p) for p in playing])
        assert header in playing


def test_added_chapter_title_picture(tmp_path):
    """A chapter the project adds has its own title strip (chap_title_data row 0x58), and leads where the chapter
    before led (ticket 55: the Campaign page sees that link)."""
    from fe_maker import newchapter
    from fe_maker.decomp.gamedata import DecompData

    project = Project.create(tmp_path / "title", "Title")
    index = newchapter.add_chapter(project, 0, 15, 10, "Le Fort de l'Aube")
    _without_preparations(project, index)
    scripts = project.load("dialogues")["scripts"]
    assert [link["to"] for link in DecompData(project.decomp_dir).chapter_links(scripts)[index]] == [1]
    project.set_test_options({"start": "map", "chapter": index})
    out = project.build(Path(ROM), on_output=lambda line: None, for_test=True)
    with Game(out.rom_path, out.map_path) as game:
        assert game.read("gChapterDataTable", index * 0x94 + 0x0E) == 0x58
        assert game.read("chap_title_data", 0x58 * 12, width=32) == game.address("chap_title_fem_88")


def test_a_range_the_game_does_not_list_is_drawn_and_shown(tmp_path):
    project = Project.create(tmp_path / "range", "Range")
    items = project.load("items")
    items[2]["range"] = {"min": 1, "max": 10}   # Seth's Steel Sword (ticket 59)
    project.save("items", items)
    out = project.build(Path(ROM), on_output=lambda line: None, for_test=True)

    with Game(out.rom_path, out.map_path) as game:
        assert game.wait_until(lambda: game.chapter() == 0 and game.turn() == 1 and game.units(), seconds=60)
        game.run(60)
        seth = next(u for u in game.units() if u["character"] == 2)
        game.move_cursor(seth["x"], seth["y"])
        game.run(20)
        game.press("A", wait=40)
        game.press("A", wait=60)   # stays: the action menu, on Attack, draws the weapons' range
        rows = game.read("gBmMapRange", 0, 32)
        row = game.read(rows + 4 * seth["y"], 0, 32)
        assert game.read(row + seth["x"] - 7, 0, 8) and not game.read(row + seth["x"], 0, 8)


def test_blank_project_starts_on_its_empty_chapter(tmp_path):
    from fe_maker import newchapter

    project = Project.create(tmp_path / "blank", "Blank")
    newchapter.start_blank(project, True, "Chapitre 1", "Heros")
    assert not [p for p in project.validate() if p.severity == "error"]
    assert newchapter.add_chapter(project, 0, 15, 10, "Chapitre 2") == 1   # the game's chapter 1 is free now
    out = project.build(Path(ROM), on_output=lambda line: None, for_test=True)

    with Game(out.rom_path, out.map_path) as game:
        assert game.wait_until(lambda: game.chapter() == 0 and game.turn() == 1 and game.units(), seconds=60)
        game.run(120)
        assert [u["character"] for u in game.units()] == [1] and game.units("Red") == [] and game.chapter() == 0


def test_a_three_chapter_hack_from_a_blank_project_to_the_end(tmp_path):
    """The alpha's witness hack: only what the interface does, played to the title screen."""
    from fe_maker import newchapter
    from fe_maker.decomp import story
    from fe_maker.decomp.gamedata import DecompData

    project = Project.create(tmp_path / "hack", "Hack")
    newchapter.start_blank(project, True, "Le Départ", "Aelis")
    characters = project.load("characters")
    hero = next(c for c in characters if c["id"] == newchapter.BLANK_LORD)
    hero["bases"].update(pow=30, skl=30, spd=30)
    friend = DecompData(project.decomp_dir).new_character(True, {c["id"] for c in characters}, True)
    friend["name"] = "Bran"
    project.save("characters", [*characters, friend])

    chapters = project.load("chapters")
    army = chapters["unitGroups"]["UnitDef_Event_PrologueAlly"]
    army.append({**army[0], "slot": None, "character": friend["id"], "class": friend["class"], "x": 1, "y": 0, "endX": 1,
                 "endY": 0, "items": []})
    project.save("chapters", chapters)
    second = newchapter.add_chapter(project, 0, 15, 10, "La Forêt")
    third = newchapter.add_chapter(project, second, 15, 10, "Le Château")
    _without_preparations(project, second, third)
    chapters = project.load("chapters")
    dialogues = project.load("dialogues")
    data = DecompData(project.decomp_dir)
    for index in (0, second, third):
        opening = dialogues["scripts"][data.chapter_openings()[index]]
        group = next(c["args"][1] for c in opening if c["op"] == "LOAD1")
        chapters["unitGroups"][group] = [{
            "slot": None, "character": "CHARACTER_SOLDIER_83", "class": "CLASS_SOLDIER", "level": 1, "autolevel": False,
            "side": "enemy", "x": 0, "y": 1, "endX": 0, "endY": 1, "items": ["ITEM_LANCE_IRON"], "ai": [0, 0, 0, 0],
            "fixedPath": False}]
    project.save("chapters", chapters)
    ending = data.chapter_endings()[third]
    dialogues["scripts"][ending] = [{"op": "MNTS", "args": ["0"]}, {"op": "ENDA"}]
    project.save("dialogues", dialogues)
    assert not [p for p in project.validate() if p.severity == "error"]
    assert story.links(dialogues["scripts"][ending])[0]["kind"] == "title"
    out = project.build(Path(ROM), on_output=lambda line: None, for_test=True)

    with Game(out.rom_path, out.map_path) as game:
        for chapter in (0, second, third):
            assert game.wait_until(lambda: game.chapter() == chapter and game.turn() == 1 and game.units("Red"), seconds=60,
                                   tap="A")
            game.run(60)
            assert len(game.units()) == 2, "the army follows"
            game.move_cursor(0, 0)
            game.run(20)
            game.press("A", wait=40)
            game.press("A", wait=60)   # stays: the action menu, on Attack
            game.press("A", wait=40)   # Attack
            game.press("A", wait=40)   # the weapon
            game.press("A", wait=40)   # the target
            assert game.wait_until(lambda: not game.units("Red"), seconds=60, tap="A")
        game.wait_until(lambda: False, seconds=40, tap="A")   # to the title screen, then its menu
        game.screenshot().save(tmp_path / "end.png")
        game.screenshot().save(tmp_path / "end.png")
        print("screenshot (the save menu, seen 30/10/2026):", tmp_path / "end.png")


def test_the_comfort_switches_build_and_the_game_starts(tmp_path):
    project = Project.create(tmp_path / "comfort", "Comfort")
    project.set_game_options({"quickExpBar": True, "quickLevelUp": True, "noSupportAnimations": True, "objective": 1,
                              "windowColor": 2})
    out = project.build(Path(ROM), on_output=lambda line: None, for_test=True)
    with Game(out.rom_path, out.map_path) as game:
        assert game.wait_until(lambda: game.chapter() == 0 and game.turn() == 1 and game.units(), seconds=60)


def test_the_added_line_of_the_options_menu_is_whole(tmp_path):
    project = Project.create(tmp_path / "menu", "Menu")
    project.set_game_options({"noSupportAnimations": True})
    out = project.build(Path(ROM), on_output=lambda line: None, for_test=True)
    with Game(out.rom_path, out.map_path) as game:
        assert game.wait_until(lambda: game.chapter() == 0 and game.turn() == 1 and game.units(), seconds=60)
        game.run(60)
        game.move_cursor(0, 0)
        game.run(20)
        game.press("A", wait=30)
        for _ in range(2):   # Unit, Status, then Options
            game.press("DOWN", wait=12)
        game.press("A", wait=90)
        game.press("DOWN", wait=14)
        game.screenshot().save(tmp_path / "second.png")   # the added line, under Animation
        for _ in range(12):
            game.press("DOWN", wait=14)
        game.run(30)
        game.screenshot().save(tmp_path / "menu.png")
        print("screenshots:", tmp_path / "second.png", tmp_path / "menu.png")
        tilemap = game.address("gBG1TilemapBuffer")
        name = [[game.read(tilemap, (y * 32 + x) * 2, width=16) for x in range(2, 14)] for y in (30, 31)]
        assert all(any(half) for half in name)   # both halves of the 14th row


def test_a_priest_given_the_dance_dances_without_breaking_the_game(tmp_path):
    from fe_maker.decomp import units

    project = Project.create(tmp_path / "dance", "Dance")
    project.set_game_options({"noSupportAnimations": True})
    characters = project.load("characters")
    seth = next(c for c in characters if c["id"] == "CHARACTER_SETH")
    seth.update({"abilities": [*seth.get("abilities", []), "dance"], "class": "CLASS_PRIEST",
                 "weaponRanks": dict.fromkeys(seth["weaponRanks"], 0)})
    project.save("characters", characters)
    chapters = project.load("chapters")
    groups = units.read_unit_groups(project.decomp_dir)
    army = [dict(u) for u in groups["UnitDef_Event_PrologueAlly"].units]
    next(u for u in army if u["character"] == "CHARACTER_SETH").update({"class": "CLASS_PRIEST", "items": ["ITEM_STAFF_HEAL"]})
    chapters.setdefault("unitGroups", {})["UnitDef_Event_PrologueAlly"] = army
    project.save("chapters", chapters)
    out = project.build(Path(ROM), on_output=lambda line: None, for_test=True)
    with Game(out.rom_path, out.map_path) as game:
        assert game.wait_until(lambda: game.chapter() == 0 and game.turn() == 1 and game.units(), seconds=60)
        game.run(60)
        found = game.units()
        dancer = next(u for u in found if u["character"] == 2)
        friend = game.address("gUnitArrayBlue") + 0x48 * found.index(next(u for u in found if u["character"] == 1))
        game.write(friend, game.read(friend, 0x0C, width=32) | 0x42, offset=0x0C, width=32)   # she has acted
        game.run(10)
        game.move_cursor(dancer["x"], dancer["y"])
        game.run(20)
        for _ in range(4):   # the dancer, stays, Dance, the only target
            game.press("A", wait=30)
        game.run(240)
        game.screenshot().save(tmp_path / "danced.png")
        print("screenshot:", tmp_path / "danced.png")
        assert not game.read(friend, 0x0C, width=32) & 0x42   # she can act again
        assert 0 < game.units()[0]["x"] < 40                  # the game still runs on its units


def test_a_scene_moved_to_another_turn_builds_and_plays(tmp_path):
    from fe_maker.decomp.gamedata import DecompData

    project = Project.create(tmp_path / "turn", "Turn")
    scene = next(s for s in DecompData(project.decomp_dir).chapter_dialogues(0)
                 if s["trigger"]["kind"] == "turn" and not s["trigger"].get("via"))
    dialogues = project.load("dialogues")
    dialogues["triggers"] = {scene["script"]: {"turn": "4", "faction": "FACTION_RED"}}
    project.save("dialogues", dialogues)
    out = project.build(Path(ROM), on_output=lambda line: None, for_test=True)
    with Game(out.rom_path, out.map_path) as game:
        assert game.wait_until(lambda: game.chapter() == 0 and game.turn() == 1 and game.units(), seconds=60)


def test_a_removed_scene_builds_and_plays(tmp_path):
    from fe_maker.decomp.gamedata import DecompData

    project = Project.create(tmp_path / "gone", "Gone")
    scene = next(s for s in DecompData(project.decomp_dir).chapter_dialogues(0)
                 if s["trigger"]["kind"] == "turn" and not s["trigger"].get("via"))
    dialogues = project.load("dialogues")
    dialogues["removedScenes"] = [scene["script"]]
    project.save("dialogues", dialogues)
    out = project.build(Path(ROM), on_output=lambda line: None, for_test=True)
    with Game(out.rom_path, out.map_path) as game:
        assert game.wait_until(lambda: game.chapter() == 0 and game.turn() == 1 and game.units(), seconds=60)


def test_hp_bars_under_wounded_units(tmp_path):
    project = Project.create(tmp_path / "bars", "Bars")
    project.set_game_options({"hpBars": True})
    out = project.build(Path(ROM), on_output=lambda line: None, for_test=True)
    with Game(out.rom_path, out.map_path) as game:
        assert game.wait_until(lambda: game.chapter() == 0 and game.turn() == 1 and game.units(), seconds=60)
        game.run(60)
        seth = next(i for i, u in enumerate(game.units()) if u["character"] == 2)
        unit = game.address("gUnitArrayBlue") + seth * 0x48
        game.write(unit, 5, offset=0x13)
        game.run(30)
        game.screenshot().save(tmp_path / "bar.png")
        print("screenshot:", tmp_path / "bar.png", game.units())


def test_casual_mode_brings_a_fallen_unit_back(tmp_path):
    from fe_maker import newchapter
    from fe_maker.decomp.gamedata import DecompData

    project = Project.create(tmp_path / "casual", "Casual")
    newchapter.start_blank(project, True, "Un", "Aelis")
    project.set_game_options({"casualMode": True})
    characters = project.load("characters")
    next(c for c in characters if c["id"] == newchapter.BLANK_LORD)["bases"].update(pow=30, skl=30, spd=30)
    friend = DecompData(project.decomp_dir).new_character(True, {c["id"] for c in characters}, True)
    friend["name"] = "Bran"
    project.save("characters", [*characters, friend])
    chapters = project.load("chapters")
    army = chapters["unitGroups"]["UnitDef_Event_PrologueAlly"]
    army.append({**army[0], "slot": None, "character": friend["id"], "class": friend["class"], "x": 1, "y": 0, "endX": 1,
                 "endY": 0, "items": []})
    chapters["unitGroups"]["UnitDef_Event_PrologueEnemy"] = [{
        "slot": None, "character": "CHARACTER_SOLDIER_83", "class": "CLASS_SOLDIER", "level": 1, "autolevel": False,
        "side": "enemy", "x": 0, "y": 1, "endX": 0, "endY": 1, "items": ["ITEM_LANCE_IRON"], "ai": [0, 0, 0, 0],
        "fixedPath": False}]
    project.save("chapters", chapters)
    second = newchapter.add_chapter(project, 0, 15, 10, "Deux")
    _without_preparations(project, second)
    out = project.build(Path(ROM), on_output=lambda line: None, for_test=True)

    with Game(out.rom_path, out.map_path) as game:
        assert game.wait_until(lambda: game.chapter() == 0 and game.turn() == 1 and game.units("Red"), seconds=60)
        game.run(60)
        unit = game.address("gUnitArrayBlue") + 0x48   # the second unit: Bran falls
        dead_hidden = 1 << 2 | 1 << 0
        game.write(unit, game.read(unit, 0x0C, width=32) | dead_hidden, offset=0x0C, width=32)
        game.move_cursor(0, 0)
        game.run(20)
        game.press("A", wait=40)
        game.press("A", wait=60)
        game.press("A", wait=40)
        game.press("A", wait=40)
        game.press("A", wait=40)
        assert game.wait_until(lambda: game.chapter() == second and game.turn() == 1, seconds=90, tap="A")
        assert game.wait_until(lambda: not game.read(unit, 0x0C, width=32) & dead_hidden, seconds=30, tap="A")


def test_a_project_keeps_only_what_is_chosen(tmp_path):
    """Keep the first two chapters, a few characters and little else: it builds, the chapters' needs stay."""
    from fe_maker import scope

    project = Project.create(tmp_path / "scope", "Scope")
    result = scope.apply(project, [0, 1, 2], ["CHARACTER_SETH"], ["CLASS_PALADIN"], ["ITEM_VULNERARY"], False, "Un", "Hero")
    assert (tmp_path / "scope" / "backups").is_dir() and "ITEM_SWORD_STEEL" in result["forced"]["items"]
    assert not [p.to_dict() for p in project.validate() if p.severity == "error"]
    assert {c["id"] for c in project.load("characters")} >= {"CHARACTER_EIRIKA", "CHARACTER_SETH"}
    assert project.load("dialogues")["scripts"]["EventScr_Ch1_EndingScene"][-2:] != []   # chapter 1 no longer leads on
    assert "CHARACTER_TANA" not in {c["id"] for c in project.load("characters")}
    assert "ITEM_SWORD_SILVER" in {i["id"] for i in project.load("items")} or len(project.load("items")) < 150
    out = project.build(Path(ROM), on_output=lambda line: None, for_test=True)
    with Game(out.rom_path, out.map_path) as game:
        assert game.wait_until(lambda: game.chapter() == 0 and game.turn() == 1 and game.units(), seconds=60)


def test_an_event_changes_a_units_stats(tmp_path):
    project = Project.create(tmp_path / "stats", "Stats")
    project.set_test_options({"start": "map", "simplePrologue": False})
    script = "EventScr_Prologue_BeginningScene"
    original = DecompData(project.decomp_dir).script_commands(script)
    change = [{"op": "ChangeStat", "args": ["CHARACTER_EIRIKA", stat, amount]}
              for stat, amount in (("hp", "5"), ("pow", "3"), ("spd", "-2"), ("mov", "2"), ("lck", "-99"))]
    end = next(i for i, c in enumerate(original) if c["op"] in ("NoFade", "ENDA"))
    project.save("dialogues", {"scripts": {script: original[:end] + change + original[end:]}})
    eirika = next(c for c in project.load("characters") if c["id"] == "CHARACTER_EIRIKA")
    lord = next(c for c in project.load("classes") if c["id"] == eirika["class"])
    base = {s: eirika["bases"][s] + lord["bases"][s] for s in ("hp", "pow", "spd")}
    out = project.build(Path(ROM), on_output=lambda line: None, for_test=True)
    with Game(out.rom_path, out.map_path) as game:
        assert game.wait_until(lambda: game.turn() == 1 and game.phase() == "player", seconds=240, step=20, tap="START")
        index, eirika = next((i, u) for i, u in enumerate(game.units()) if u["character"] == 1)
        unit = game.address("gUnitArrayBlue") + index * UNIT_SIZE
        assert eirika["maxHP"] == eirika["hp"] == base["hp"] + 5
        assert game.read(unit, 0x14) == base["pow"] + 3
        assert game.read(unit, 0x16) == base["spd"] - 2
        assert game.read(unit, 0x19) == 0     # never below 0
        assert game.read(unit, 0x1D) == 2     # the move bonus


def test_select_shows_the_danger_zone(tmp_path):
    project = Project.create(tmp_path / "danger", "Danger")
    project.set_game_options({"dangerZone": True})
    out = project.build(Path(ROM), on_output=lambda line: None, for_test=True)
    with Game(out.rom_path, out.map_path) as game:
        def range_shown():
            return bool(game.read("gBmSt", offset=4) & 8)   # BM_FLAG_3

        _on_map(game)
        game.screenshot().save(tmp_path / "before.png")
        assert not range_shown()
        game.press("SELECT", wait=60)
        assert range_shown()
        game.screenshot().save(tmp_path / "danger.png")
        game.press("R", wait=30)   # no stat screen from here: there is no active unit
        game.screenshot().save(tmp_path / "danger-r.png")
        assert range_shown()
        game.press("B", wait=60)
        assert not range_shown()
        game.screenshot().save(tmp_path / "danger-b.png")
        game.press("SELECT", wait=60)
        game.press("SELECT", wait=60)
        assert not range_shown()
        print("screenshot:", tmp_path / "danger.png")


def _items(game):
    return next((u["items"] for u in game.units() if u["character"] == 1), [])


def test_a_condition_gives_an_item_to_a_living_character(tmp_path):
    project = Project.create(tmp_path / "gift", "Gift")
    project.set_test_options({"start": "map", "simplePrologue": False})
    script = "EventScr_Prologue_BeginningScene"
    original = DecompData(project.decomp_dir).script_commands(script)
    gift = [{"op": "CHECK_ALIVE", "args": ["CHARACTER_EIRIKA"]}, {"op": "BEQ", "args": ["0x70", "EVT_SLOT_C", "EVT_SLOT_0"]},
            {"op": "GiveItem", "args": ["CHARACTER_EIRIKA", "ITEM_ELIXIR"]}, {"op": "LABEL", "args": ["0x70"]},
            {"op": "CHECK_ALIVE", "args": ["CHARACTER_EIRIKA"]}, {"op": "BNE", "args": ["0x71", "EVT_SLOT_C", "EVT_SLOT_0"]},
            {"op": "GiveItem", "args": ["CHARACTER_EIRIKA", "ITEM_ANTITOXIN"]}, {"op": "LABEL", "args": ["0x71"]}]
    end = next(i for i, c in enumerate(original) if c["op"] in ("NoFade", "ENDA"))
    project.save("dialogues", {"scripts": {script: original[:end] + gift + original[end:]}})
    out = project.build(Path(ROM), on_output=lambda line: None, for_test=True)
    with Game(out.rom_path, out.map_path) as game:
        elixir, antitoxin = 0x6D, 0x6F
        assert game.wait_until(lambda: game.chapter() == 0 and elixir in _items(game), seconds=240, step=20, tap="START")
        assert antitoxin not in _items(game)   # the second condition's block is skipped
