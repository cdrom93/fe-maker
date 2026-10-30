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
