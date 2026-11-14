"""Local-only playtests: build a project, play the ROM without any window, check the game's memory.

Run with:  FE_MAKER_ROM=path/to/fe8.gba python -m pytest tests/local/test_playtest.py -m <domain> (tests/conftest.py)
"""

import os
import sys
from pathlib import Path

import pytest
from PIL import Image

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "server"))

from romcache import build as cached_build  # noqa: E402

from fe_maker import api  # noqa: E402
from fe_maker.decomp.gamedata import DecompData  # noqa: E402
from fe_maker.playtest import UNIT_SIZE, Game  # noqa: E402
from fe_maker.project import Project  # noqa: E402

ROM = os.environ.get("FE_MAKER_ROM")
pytestmark = pytest.mark.skipif(not ROM, reason="set FE_MAKER_ROM to run tests that need the ROM")


def build(project):
    """A test build of the project, reused from the cache (romcache.py) when nothing it reads changed."""
    return cached_build(project, Path(ROM), on_output=lambda line: print(line, end=""))


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
    out = build(project)

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
    return build(project)


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
    out = build(project)

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
    out = build(project)

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
    out = build(project)
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
    out = build(project)
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
    out = build(project)
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
    out = build(project)

    with Game(out.rom_path, out.map_path) as game:
        assert game.wait_until(lambda: game.chapter() == 0 and game.turn() == 1 and game.units(), seconds=60)
        game.run(60)
        game.screenshot().save(tmp_path / "fog.png")
        print("screenshot:", tmp_path / "fog.png")
        assert game.read("gPlaySt", 0x0D) == 4   # chapterVisionRange


def test_imported_battle_animation(tmp_path):
    """Ticket 44: a battle animation converted from FEditor's format (here one of the game's, exported then
    imported back) is added after the game's and played when Seth (Paladin) attacks with his sword."""

    from fe_maker.decomp import banim

    project = Project.create(tmp_path / "banim", "Banim")
    decomp = project.decomp_dir
    _import_paladin_animation(project)
    out = build(project)
    new_index = len(banim.table(decomp))   # numbers start at 1, indexes at 0

    with Game(out.rom_path, out.map_path) as game:
        enemy = _seth_attacks(game)
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


def test_sound_command_of_an_imported_animation(tmp_path):
    """Ticket 132: FEditor's "S" command, which the game's scripts cannot hold, plays its song during the attack."""
    project = Project.create(tmp_path / "sound", "Sound")
    _import_paladin_animation(project, sound="SF5")
    out = build(project)
    with Game(out.rom_path, out.map_path) as game:
        header = game.read(game.address("gSongTable") + 8 * 0xF5, width=32)
        player = game.read(game.address("gSongTable") + 8 * 0xF5 + 4, width=16)
        info = game.read(game.address("gMPlayTable") + 12 * player, width=32)
        assert game.read(info, width=32) != header
        _seth_attacks(game)
        assert game.wait_until(lambda: game.read(info, width=32) == header, seconds=30, step=2)


def test_ally_level_comes_from_the_sheet(tmp_path):
    """A sheet's new level reaches the unit the game places."""
    project = Project.create(tmp_path / "level", "Level")
    characters = project.load("characters")
    next(c for c in characters if c["id"] == "CHARACTER_SETH")["level"] = 3
    project.save("characters", characters)
    out = build(project)

    with Game(out.rom_path, out.map_path) as game:
        _on_map(game)
        seth = next(u for u in game.units() if u["character"] == 2)
        assert seth["level"] == 3


@pytest.mark.parametrize("imported", [False, True])
def test_character_colours_in_battle(tmp_path, imported):
    """A character's own colours for a class are drawn in battle, over the game's animation or an imported one."""
    project = Project.create(tmp_path / "colours", "Colours")
    if imported:
        _import_paladin_animation(project)
    characters = project.load("characters")
    seth = next(c for c in characters if c["id"] == "CHARACTER_SETH")
    line = ["#000000"] + ["#ff0000"] * 15
    seth["battleColors"] = {"CLASS_PALADIN": [line] * 5}
    project.save("characters", characters)
    out = build(project)
    row = 108   # the first after the game's

    with Game(out.rom_path, out.map_path) as game:
        _seth_attacks(game)
        assert game.wait_until(lambda: row in (game.read("gBanimUniquePal", 0, width=16, signed=True),
                                               game.read("gBanimUniquePal", 2, width=16, signed=True)), seconds=20, step=5)
        game.run(120)
        shot = game.screenshot().convert("RGB")
        shot.save(tmp_path / "battle.png")
        print("screenshot:", tmp_path / "battle.png")
        red = sum(1 for pixel in shot.get_flattened_data() if pixel[0] > 230 and pixel[1] < 16 and pixel[2] < 16)
        assert red > 200


def test_class_generic_portrait_reaches_the_game(tmp_path):
    project = Project.create(tmp_path / "generic", "Generic")
    classes = project.load("classes")
    next(c for c in classes if c["id"] == "CLASS_SOLDIER")["genericPortrait"] = 0x7F
    project.save("classes", classes)
    out = build(project)

    with Game(out.rom_path, out.map_path) as game:
        game.run(10)
        assert game.read("gClassData", (0x4E - 1) * 0x54 + 8, width=16) == 0x7F


def test_item_sheet_reaches_the_game(tmp_path):
    """Type, properties, effect, rank points, bonuses and spell, as the engine reads them."""
    project = Project.create(tmp_path / "items", "Items")
    items = project.load("items")
    sheet = {i["id"]: i for i in items}
    sheet["ITEM_VULNERARY"]["weaponType"] = "sword"
    sheet["ITEM_SWORD_IRON"].update(properties=["brave", "unbreakable"], weaponEffect="poison", weaponExp=3,
                                    statBonuses={"spd": 5, "lck": -2})
    sheet["ITEM_ANIMA_FIRE"]["spellFrom"] = "ITEM_ANIMA_THUNDER"
    sheet["ITEM_ANIMA_EXCALIBUR"]["statBonuses"] = None
    project.save("items", items)
    out = build(project)

    size, row_size, vulnerary, iron_sword, excalibur = 0x24, 0x10, 0x6C, 0x01, 0x3E
    with Game(out.rom_path, out.map_path) as game:
        game.run(10)
        attributes = game.read("gItemData", iron_sword * size + 8, width=32)
        assert attributes & (1 << 0) and attributes & (1 << 3) and attributes & (1 << 5)     # weapon, unbreakable, brave
        assert game.read("gItemData", vulnerary * size + 8, width=32) & 1                    # can be equipped
        assert game.read("gItemData", iron_sword * size + 0x1F, width=8) == 1                # poison
        assert game.read("gItemData", iron_sword * size + 0x20, width=8) == 3
        assert game.read("ItemBonus_FEM_ITEM_SWORD_IRON", 3, width=8) == 5
        assert game.read("ItemBonus_FEM_ITEM_SWORD_IRON", 6, width=8) == 0xFE
        assert game.read("gItemData", excalibur * size + 0x0C, width=32) == 0

        def spell(item):
            row = 0
            while game.read("gSpellAssocData", row * row_size, width=16) not in (item, 0xFFFF):
                row += 1
            return game.read("gSpellAssocData", row * row_size + 4, width=16)

        assert spell(0x38) == 0x19      # Fire (0x38) casts Thunder's effect


def test_portrait_colours_in_battle(tmp_path):
    """Colours drawn from a portrait build and show in battle, in the slots of the game's animation."""
    project = Project.create(tmp_path / "portrait", "Portrait")
    api.state.project = project
    characters = project.load("characters")
    seth = next(c for c in characters if c["id"] == "CHARACTER_SETH")
    franz = next(c for c in characters if c["id"] == "CHARACTER_FRANZ")     # Seth in Franz's green
    colours = api.portrait_colors("CLASS_PALADIN", portrait=franz["portraitId"])["colours"]
    assert colours != api._class_palette("CLASS_PALADIN")[0]
    seth["battleColors"] = {"CLASS_PALADIN": [colours] * 5}
    project.save("characters", characters)
    out = build(project)

    with Game(out.rom_path, out.map_path) as game:
        _seth_attacks(game)
        assert game.wait_until(lambda: 108 in (game.read("gBanimUniquePal", 0, width=16, signed=True),
                                               game.read("gBanimUniquePal", 2, width=16, signed=True)), seconds=20, step=5)
        game.run(120)
        shot = game.screenshot().convert("RGB")
        shot.save(tmp_path / "battle.png")
        print("screenshot:", tmp_path / "battle.png")
        wanted = {tuple(int(c[i:i + 2], 16) >> 3 for i in (1, 3, 5)) for c in colours[8:12]}
        found = sum(1 for pixel in shot.get_flattened_data() if tuple(c >> 3 for c in pixel) in wanted)
        assert found > 100


def _seth_attacks(game):
    """Seth attacks the enemy next to him in the simplified prologue; returns this enemy."""
    _on_map(game)
    game.run(210)
    seth = next(u for u in game.units() if u["character"] == 2)
    enemy = next(u for u in game.units("Red") if abs(u["x"] - seth["x"]) + abs(u["y"] - seth["y"]) == 1)
    game.move_cursor(seth["x"], seth["y"])
    game.press("A")
    game.press("A", wait=60)
    game.press("A", wait=30)      # Attack
    game.press("A", wait=30)      # his first weapon, a sword
    game.press("A", wait=30)      # the target
    game.press("A", wait=30)      # the forecast
    return enemy


def _import_paladin_animation(project, sound=""):
    import shutil

    from fe_maker.decomp import banim, banim_import

    decomp = project.decomp_dir
    entry = next(e for e in project_classes(decomp) if e.fields["number"] == "CLASS_PALADIN")
    conf = entry.fields["pBattleAnimDef"].lstrip("&").strip()
    number = next(d["number"] for d in banim.configs(decomp)[conf] if d["weapon"] == "ITYPE_SWORD")
    symbol = next(a.symbol for a in banim.table(decomp) if a.number == number)
    script, frames = banim_import.export_feditor(decomp, symbol)
    for mode in (1, 3):
        script = script.replace(f"/// - Mode {mode}\n", f"/// - Mode {mode}\n{sound}\n" if sound else f"/// - Mode {mode}\n", 1)
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


def project_classes(decomp):
    from fe_maker.decomp.gamedata import DecompData

    return DecompData(decomp).classes.entries


def test_test_this_chapter(tmp_path):
    """"Test this chapter": the test build starts on the chosen chapter's map (here chapter 2)."""
    project = Project.create(tmp_path / "ch2", "Ch2")
    project.set_test_options({"start": "map", "chapter": 2})
    out = build(project)
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
    out = build(project)
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
    out = build(project)

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
    out = build(project)

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
    out = build(project)

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
    out = build(project)
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
    out = build(project)

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
    out = build(project)
    with Game(out.rom_path, out.map_path) as game:
        _on_map(game)
        bits = game.read("gPlaySt", 0x40)   # PlaySt_OptionBits: autoCursor bit 4, textSpeed bits 5-6
        assert (bits >> 5) & 3 == 2 and (bits >> 4) & 1 == 1


def test_stationary_enemy_shows_no_movement_range(tmp_path):
    """Game option "no movement range for units that never move": O'Neill (prologue boss, movement AI 3) selected,
    his movement map holds only his own tile."""
    project = Project.create(tmp_path / "range", "Range")
    project.set_game_options({"stationaryRange": True})
    out = build(project)
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
    out = build(project)
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
    table and the music player plays it on the map. A game song chosen for the enemy phase and the victory theme
    threshold reach the chapter's data; the battle songs' source with an imported song still builds, and a boss theme
    reaches the boss table."""
    import shutil

    project = Project.create(tmp_path / "music", "Music")
    folder = project.root / "assets" / "music"
    folder.mkdir(parents=True)
    shutil.copy(project.decomp_dir / "sound/songs/midi/song010_agbfe3_bgm_map_pl3.mid", folder / "theme.mid")
    project.save("music", {"songs": {"theme": {"name": "Theme"}},
                           "chapters": {"0": {"bluePhase": "theme", "redPhase": 20}}, "victory": {"0": 0},   # never (game: 1)
                           "battle": {"playerAttacks": "theme"}, "bosses": {"CHARACTER_ONEILL": 20}})
    out = build(project)
    with Game(out.rom_path, out.map_path) as game:
        _on_map(game)
        game.run(120)
        # A game song chosen for the enemy phase and the victory theme threshold, in the chapter's data
        assert game.read("gChapterDataTable", 0x16 + 2, width=16) == 20   # mapBgmIds[MAP_BGM_RED]
        assert game.read("gChapterDataTable", 0x86) == 0   # victorySongEnemyThreshold (a threshold above the
        # enemies left would play the victory theme instead of the imported song)
        # O'Neill's boss theme in the rewritten boss table (character, song pairs ended by -1)
        pairs = [(game.read("gBanimBossBGMs", 8 * i, width=32), game.read("gBanimBossBGMs", 8 * i + 4, width=32))
                 for i in range(32)]
        assert (DecompData(project.decomp_dir).character_number("CHARACTER_ONEILL"), 20) in pairs
        header = game.read("gSongTable", 87 * 8, width=32)
        players = [game.read("gMPlayTable", 12 * i, width=32) for i in range(2)]   # struct MusicPlayer: info first
        playing = {game.read(info, 0, width=32) for info in players}   # MusicPlayerInfo: songHeader first
        print("song 87", hex(header), "playing", [hex(p) for p in playing])
        assert header in playing


def test_map_music_comes_back_after_a_battle(tmp_path):
    """Ticket 74: the player phase's song chosen among the game's songs that the song table puts on the battles' music
    player (0: the opening's). FE Maker plays it from a copy of its row on the map's player (1), so the battle only
    pauses it and the game takes it up again right after the battle, in the same player phase."""
    place = (BENCH_SPOTS[0][0] + 1, BENCH_SPOTS[0][1])
    project = _bench(tmp_path, "battlesong", [["ITEM_SWORD_IRON"]], enemy_at=place)
    project.save("music", {"chapters": {"0": {"bluePhase": 2}}, "victory": {"0": 0}})   # one enemy: no victory song
    out = build(project)
    with Game(out.rom_path, out.map_path) as game:
        lord = _bench_units(game)[0]
        song = game.read(game.address("gSongTable") + 2 * 8, 0, width=32)   # struct Song: its header first

        def heard() -> bool:   # gMPlayTable's players (12 bytes each), MusicPlayerInfo: songHeader, status
            for n in range(2):
                info = game.read("gMPlayTable", 12 * n, width=32)
                status = game.read(info, 4, width=32)
                if game.read(info, 0, width=32) == song and status & 0xFFFF and not status & 0x80000000:
                    return True
            return False

        assert heard()
        _bench_attack(game, lord)
        stopped = False
        for _ in range(60):                     # the battle's song, then the phase's again
            game.run(20)
            stopped = stopped or not heard()
            if stopped and heard():
                break
        assert stopped and heard() and game.turn() == 1


def test_a_players_theme_and_the_sound_room(tmp_path):
    """Tickets 76 and 77: an imported song, the lord's theme, joins the sound room's list (gSoundRoomTable, before its
    end mark) and plays when she fights, though she is on the player's side."""
    import shutil

    place = (BENCH_SPOTS[0][0] + 1, BENCH_SPOTS[0][1])
    project = _bench(tmp_path, "playertheme", [["ITEM_SWORD_IRON"]], enemy_at=place)
    folder = project.root / "assets" / "music"
    folder.mkdir(parents=True)
    shutil.copy(project.decomp_dir / "sound/songs/midi/song025_agbfe3_bgm_btl_pl_normal.mid", folder / "fight.mid")
    project.save("music", {"songs": {"fight": {"name": "Fight"}}, "bosses": {"CHARACTER_EIRIKA": "fight"},
                           "victory": {"0": 0}})
    out = build(project)
    with Game(out.rom_path, out.map_path) as game:
        lord = _bench_units(game)[0]
        rows = game.address("gSoundRoomTable")
        n = 0
        while game.read(rows + 16 * (n + 1), 0, width=32) != 0xFFFFFFFF:   # struct SoundRoomEnt: 16 bytes
            n += 1
        number = game.read(rows + 16 * n, 0, width=32)
        assert 0 < number < 128 and game.read(rows + 16 * n, 4, width=32) > 60
        song = game.read(game.address("gSongTable") + 8 * number, 0, width=32)
        _bench_attack(game, lord)
        battle = game.read("gMPlayTable", 0, width=32)   # gMPlayInfo_BGM1, the battles' player

        def theme() -> bool:
            status = game.read(battle, 4, width=32)
            return game.read(battle, 0, width=32) == song and bool(status & 0xFFFF) and not status & 0x80000000

        assert game.wait_until(theme, seconds=20, step=20)


def test_imported_music_in_a_scene(tmp_path):
    """An imported song named by the Music command of a sequence (FEM_SONG_<key>, defined at build) plays in the
    prologue's opening scene."""
    import shutil

    project = Project.create(tmp_path / "scene_music", "SceneMusic")
    project.set_test_options({"start": "map", "simplePrologue": False})   # the simple prologue has no opening scene
    folder = project.root / "assets" / "music"
    folder.mkdir(parents=True)
    shutil.copy(project.decomp_dir / "sound/songs/midi/song010_agbfe3_bgm_map_pl3.mid", folder / "theme.mid")
    project.save("music", {"songs": {"theme": {"name": "Theme"}}})
    commands = DecompData(project.decomp_dir).script_commands("EventScr_Prologue_BeginningScene")
    at = next(i for i, c in enumerate(commands) if c["op"] == "LABEL") + 1   # after the throne room scene
    commands.insert(at, {"op": "MUSC", "args": ["FEM_SONG_theme"]})
    dialogues = project.load("dialogues")
    dialogues.setdefault("scripts", {})["EventScr_Prologue_BeginningScene"] = commands
    project.save("dialogues", dialogues)
    out = build(project)
    with Game(out.rom_path, out.map_path) as game:
        header = game.read("gSongTable", 87 * 8, width=32)   # the first free row of the song table

        def playing():
            players = [game.read("gMPlayTable", 12 * i, width=32) for i in range(2)]
            return header in {game.read(info, 0, width=32) for info in players}

        assert game.wait_until(playing, seconds=240, step=20, tap="A")


def test_imported_music_on_the_title_screen(tmp_path):
    """An imported song chosen for the title screen (Music tab, screens) plays there."""
    import shutil

    project = Project.create(tmp_path / "title_music", "TitleMusic")
    project.set_test_options({"start": "normal"})
    folder = project.root / "assets" / "music"
    folder.mkdir(parents=True)
    shutil.copy(project.decomp_dir / "sound/songs/midi/song010_agbfe3_bgm_map_pl3.mid", folder / "theme.mid")
    project.save("music", {"songs": {"theme": {"name": "Theme"}}, "screens": {"title": "theme"}})
    out = build(project)
    with Game(out.rom_path, out.map_path) as game:
        header = game.read("gSongTable", 87 * 8, width=32)   # the first free row of the song table

        def playing():
            players = [game.read("gMPlayTable", 12 * i, width=32) for i in range(2)]
            return header in {game.read(info, 0, width=32) for info in players}

        assert game.wait_until(playing, seconds=120, step=30, tap="START")   # START skips the opening animation


def test_imported_music_with_general_midi_instruments(tmp_path):
    """An imported song played with NIMAP2 (General MIDI order): its own voicegroup after the game's, which the song
    header points to, and the song plays on the map. Needs the ROM in FE Maker's folder (rom/baserom.gba)."""
    import shutil

    from fe_maker.decomp import nimap

    if not nimap.rom_path().is_file():
        pytest.skip("no rom/baserom.gba in FE Maker's folder")
    project = Project.create(tmp_path / "nimap", "Nimap")
    folder = project.root / "assets" / "music"
    folder.mkdir(parents=True)
    shutil.copy(project.decomp_dir / "sound/songs/midi/song010_agbfe3_bgm_map_pl3.mid", folder / "theme.mid")
    project.save("music", {"songs": {"theme": {"name": "Theme", "voicegroup": nimap.KEY}},
                           "chapters": {"0": {"bluePhase": "theme"}}, "victory": {"0": 0}})
    out = build(project)
    with Game(out.rom_path, out.map_path) as game:
        _on_map(game)
        game.run(120)
        header = game.read("gSongTable", 87 * 8, width=32)
        assert game.read(header, 4, width=32) == game.address(f"voicegroup{nimap.number(project.decomp_dir):03d}")
        players = [game.read("gMPlayTable", 12 * i, width=32) for i in range(2)]
        assert header in {game.read(info, 0, width=32) for info in players}


def test_song_written_in_the_games_music_assembly(tmp_path):
    """A song in the game's music assembly (as FE-Repo-Music's .s files), turned into a MIDI file at import
    (songasm.py), built with NIMAP2 and playing on the map."""
    from fe_maker.decomp import nimap, songasm

    if not nimap.rom_path().is_file():
        pytest.skip("no rom/baserom.gba in FE Maker's folder")
    source = """
\t.equ\tloop_grp, voicegroup000
\t.equ\tloop_mvl, 110
\t.equ\tloop_tbs, 1
\t.global\tloop
loop_1:
\t.byte\tTEMPO , 140*loop_tbs/2
\t.byte\tVOICE , 48
\t.byte\tVOL , 100*loop_mvl/mxv
loop_1_B1:
\t.byte\tN24 , Cn3 , v100
\t.byte\tW24
\t.byte\tEn3
\t.byte\tW24
\t.byte\tGOTO
\t .word\tloop_1_B1
\t.byte\tFINE
loop:
\t.byte\t1
\t.byte\t0
\t.byte\t0
\t.byte\t0
\t.word\tloop_grp
\t.word\tloop_1
"""
    project = Project.create(tmp_path / "asm", "Asm")
    folder = project.root / "assets" / "music"
    folder.mkdir(parents=True)
    (folder / "loop.mid").write_bytes(songasm.to_midi(source))
    project.save("music", {"songs": {"loop": {"name": "Loop", "voicegroup": nimap.KEY,
                                              "volume": songasm.song_volume(source)}},
                           "chapters": {"0": {"bluePhase": "loop"}}, "victory": {"0": 0}})
    out = build(project)
    with Game(out.rom_path, out.map_path) as game:
        _on_map(game)
        game.run(120)
        header = game.read("gSongTable", 87 * 8, width=32)
        assert game.read(header, 0) == 1   # one track
        players = [game.read("gMPlayTable", 12 * i, width=32) for i in range(2)]
        assert header in {game.read(info, 0, width=32) for info in players}


def test_full_drum_kit(tmp_path):
    """Option fullDrums (drumfix): the drum voices it fills are in the built game, and the map plays."""
    from fe_maker.decomp import nimap

    if not nimap.rom_path().is_file():
        pytest.skip("no rom/baserom.gba in FE Maker's folder")
    project = Project.create(tmp_path / "drums", "Drums")
    project.set_game_options({"fullDrums": True})
    out = build(project)
    first = nimap.download_drumfix()[0x2228B4]
    with Game(out.rom_path, out.map_path) as game:
        _on_map(game)
        start = game.address("voicegroup079") + 0x2228B4 - 0x2226B0   # voicegroup079 at 0x082226B0 in the game
        built = bytes(game.read(start + i) for i in range(len(first)))
        assert built[:4] == first[:4] and built[8:12] == first[8:12]   # kind, key, pan, envelope (samples may move)
        assert game.read("gMPlayTable", 0, width=32) and game.read(game.read("gMPlayTable", 0, width=32), 0, width=32)


def test_sixteen_tracks_and_twelve_notes(tmp_path):
    """Option musicTracks: the music players have 16 tracks in free RAM and the driver mixes 12 notes; the map plays."""
    project = Project.create(tmp_path / "tracks", "Tracks")
    project.set_game_options({"musicTracks": True})
    out = build(project)
    with Game(out.rom_path, out.map_path) as game:
        _on_map(game)
        info = game.read("gMPlayTable", 0, width=32)   # BGM1's MusicPlayerInfo
        assert game.read(info, 8) == 16                        # trackCount
        assert game.read(info, 0x2C, width=32) == 0x02027000   # tracks
        assert game.read("gSoundInfo", 6) == 12                # maxChans
        assert game.read(info, 0, width=32) != 0               # a song plays on the map


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
    out = build(project)
    with Game(out.rom_path, out.map_path) as game:
        assert game.read("gChapterDataTable", index * 0x94 + 0x0E) == 0x58
        assert game.read("chap_title_data", 0x58 * 12, width=32) == game.address("chap_title_fem_88")


def test_a_range_the_game_does_not_list_is_drawn_and_shown(tmp_path):
    project = Project.create(tmp_path / "range", "Range")
    items = project.load("items")
    items[2]["range"] = {"min": 1, "max": 10}   # Seth's Steel Sword (ticket 59)
    project.save("items", items)
    out = build(project)

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
    out = build(project)

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
    out = build(project)

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
    out = build(project)
    with Game(out.rom_path, out.map_path) as game:
        assert game.wait_until(lambda: game.chapter() == 0 and game.turn() == 1 and game.units(), seconds=60)


def test_the_added_line_of_the_options_menu_is_whole(tmp_path):
    project = Project.create(tmp_path / "menu", "Menu")
    project.set_game_options({"noSupportAnimations": True})
    out = build(project)
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
    out = build(project)
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
    out = build(project)
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
    out = build(project)
    with Game(out.rom_path, out.map_path) as game:
        assert game.wait_until(lambda: game.chapter() == 0 and game.turn() == 1 and game.units(), seconds=60)


def test_hp_bars_under_wounded_units(tmp_path):
    project = Project.create(tmp_path / "bars", "Bars")
    project.set_game_options({"hpBars": True})
    out = build(project)
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
    out = build(project)

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
    out = build(project)
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
    out = build(project)
    with Game(out.rom_path, out.map_path) as game:
        assert game.wait_until(lambda: game.turn() == 1 and game.phase() == "player", seconds=240, step=20, tap="START")
        index, eirika = next((i, u) for i, u in enumerate(game.units()) if u["character"] == 1)
        unit = game.address("gUnitArrayBlue") + index * UNIT_SIZE
        assert eirika["maxHP"] == eirika["hp"] == base["hp"] + 5
        assert game.read(unit, 0x14) == base["pow"] + 3
        assert game.read(unit, 0x16) == base["spd"] - 2
        assert game.read(unit, 0x19) == 0     # never below 0
        assert game.read(unit, 0x1D) == 2     # the move bonus


def test_an_event_gives_a_skill_with_its_popup(tmp_path):
    """Ticket 39: the prologue's opening event gives Eirika Luna: "Eirika learned Luna." shows (the popup of a skill
    learned in battle), Luna goes into her learned list, and the chapter goes on to the player's turn."""
    from fe_maker.decomp import skills

    project = Project.create(tmp_path / "giveskill", "GiveSkill")
    project.set_test_options({"start": "map", "simplePrologue": False})
    project.set_game_options({**project.game_options, "skills": True})
    script = "EventScr_Prologue_BeginningScene"
    original = DecompData(project.decomp_dir).script_commands(script)
    end = next(i for i, c in enumerate(original) if c["op"] in ("NoFade", "ENDA"))
    give = [{"op": "GiveSkill", "args": ["CHARACTER_EIRIKA", "Luna"]}]
    project.save("dialogues", {"scripts": {script: original[:end] + give + original[end:]}})
    out = build(project)
    with Game(out.rom_path, out.map_path) as game:
        def popup():
            return bytes(game.read(int(skills.LEARNED_NAME, 16) + k) for k in range(5)) == b"Luna\0"

        assert game.wait_until(popup, seconds=240, step=10, tap="START")
        for k in range(6):
            game.run(15)
            game.screenshot().convert("RGB").save(tmp_path / f"popup{k}.png")
        print("screenshot:", tmp_path)
        assert game.wait_until(lambda: game.turn() == 1 and game.phase() == "player" and game.units(), seconds=120,
                               step=20, tap="START")
        index = next(i for i, u in enumerate(game.units()) if u["character"] == 1)
        number = game.read(game.read(game.address("gUnitArrayBlue") + index * UNIT_SIZE, width=32), 4)
        assert game.read(int(skills.LEARNED_TABLE, 16) + number * skills.LEARNED_MAX)   # Luna, her first learned skill


def test_select_shows_the_danger_zone(tmp_path):
    project = Project.create(tmp_path / "danger", "Danger")
    project.set_game_options({"dangerZone": True})
    out = build(project)
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
    out = build(project)
    with Game(out.rom_path, out.map_path) as game:
        elixir, antitoxin = 0x6D, 0x6F
        assert game.wait_until(lambda: game.chapter() == 0 and elixir in _items(game), seconds=240, step=20, tap="START")
        assert antitoxin not in _items(game)   # the second condition's block is skipped


def test_original_village_follows_a_moved_map(tmp_path):
    """The events of the game follow; its scenes do not (chapter 2's opening freezes), so this reads the source."""
    from fe_maker.decomp import maps

    project = Project.create(tmp_path / "moved", "Moved")
    decomp = project.decomp_dir
    layout = maps.layouts(decomp)["Ch2Map"]
    width, height, cells = maps.read_layout(layout["assets"].layout)
    dx, dy = 3, 2
    plain = max(set(cells), key=cells.count)
    rows = [[plain] * (width + dx) for _ in range(dy)] + \
        [[plain] * dx + cells[y * width:(y + 1) * width] for y in range(height)]
    changes = [{**c, "x": c["x"] + dx, "y": c["y"] + dy} for c in maps.read_changes(decomp, layout["changes"])]
    project.save("maps", {"layouts": {"Ch2Map": {"rows": rows}}, "changes": {"Ch2Map": changes},
                          "offsets": {"Ch2Map": [dx, dy]}})
    text = (project.generate_overlay() / "src/events/ch2-eventinfo.h").read_text(encoding="utf-8")
    assert "EventScr_Ch2_Village1, 7, 4)" in text and "EventScr_Ch2_Village3, 4, 14)" in text
    assert "EventScr_FEM_" not in text    # nothing recreated


def test_enemies_keep_their_dropped_item_and_average_stats(tmp_path):
    from fe_maker.decomp import averagestats, units

    project = Project.create(tmp_path / "drop", "Drop")
    project.set_test_options({"start": "map", "simplePrologue": False})
    decomp = DecompData(project.decomp_dir)
    game_units = units.read_unit_groups(project.decomp_dir)
    name = next(g["name"] for g in units.all_chapter_unit_groups(project.decomp_dir)[0]
                if g["origin"] != "cutscene" and any(u["side"] == "enemy" for u in game_units[g["name"]].units))
    group = [dict(u) for u in game_units[name].units]
    dropper = next(u for u in group if u["side"] == "enemy" and u["items"])
    dropper["itemDrop"] = True
    leveled = next(u for u in group if u["side"] == "enemy" and not units.is_named_character(u["character"]))
    leveled.update(level=12, autolevel=True)
    project.save("chapters", {"unitGroups": {name: group}})
    classes = {c["id"]: c for c in project.load("classes")}
    characters = {c["id"]: c for c in project.load("characters")}
    out = build(project)
    with Game(out.rom_path, out.map_path) as game:
        assert game.wait_until(lambda: game.turn() == 1 and game.phase() == "player", seconds=240, step=20, tap="START")
        red = game.address("gUnitArrayRed")
        compared = 0
        for index, unit in enumerate(game.units("Red")):
            mine = next((u for u in group if (u["endX"], u["endY"]) == (unit["x"], unit["y"])), None)
            if mine is None:
                continue
            state = game.read(red + index * UNIT_SIZE, 0x0C, width=32)
            assert bool(state & (1 << 12)) == (mine is dropper)
            character = characters.get(mine["character"])
            cls = classes[mine["class"] if mine["class"] in classes else character["class"]]
            average = averagestats.average_stats(character, cls, mine["level"], mine["autolevel"], "enemy",
                                                 decomp.character_number(mine["character"]))
            print(mine["character"], mine["level"], mine["autolevel"], average["hp"], unit["maxHP"])
            assert abs(average["hp"] - unit["maxHP"]) <= 4
            compared += 1
        assert compared >= 2


def test_an_imported_icon_is_in_the_game(tmp_path):
    from PIL import Image

    from fe_maker.decomp import itemicons
    from fe_maker.decomp.assets import ITEM_ICON_PALETTE, read_agbpal

    project = Project.create(tmp_path / "icon", "Icon")
    icon = itemicons.free_slots(DecompData(project.decomp_dir).item_icon_files())[0]
    palette = read_agbpal(project.decomp_dir / ITEM_ICON_PALETTE)[:16]
    picture = Image.new("RGB", (16, 16), (0, 0, 0))
    picture.putpixel((1, 0), palette[5])
    path = tmp_path / "picture.png"
    picture.save(path)
    (project.root / "assets" / "icons").mkdir(parents=True)
    (project.root / "assets" / "icons" / f"{icon}.png").write_bytes(itemicons.convert(path.read_bytes(), palette))
    project.save("icons", {"icons": {str(icon): {"name": "test"}}})
    out = build(project)
    with Game(out.rom_path, out.map_path) as game:
        tiles = game.address("item_icon_tiles") + icon * 0x80
        assert game.read(tiles) == 0x50     # pixel 1 of the first row, high nibble
        assert not any(game.read(tiles + n) for n in range(1, 0x80))


def test_weather_battle_background_and_camera_in_game(tmp_path):
    project = Project.create(tmp_path / "look", "Look")
    project.set_test_options({"start": "map", "simplePrologue": False})
    project.save("chapters", {"unitGroups": {}, "objectives": {}, "weather": {"0": "rain"}, "battleBg": {"0": 11},
                              "camera": {"0": [7, 5]}})
    out = build(project)
    with Game(out.rom_path, out.map_path) as game:
        assert game.wait_until(lambda: game.turn() == 1 and game.phase() == "player", seconds=240, step=20, tap="START")
        assert game.read("gPlaySt", 0x15) == 4     # chapterWeatherId: WEATHER_RAIN
        prologue = game.address("gChapterDataTable")
        assert [game.read(prologue + offset) for offset in (0x10, 0x11, 0x13)] == [7, 5, 11]


def test_event_commands_change_weather_hp_side_and_ai(tmp_path):
    project = Project.create(tmp_path / "evcmds", "Commands")
    project.set_test_options({"start": "map", "simplePrologue": False})
    script = "EventScr_Prologue_BeginningScene"
    original = DecompData(project.decomp_dir).script_commands(script)
    added = [{"op": "WEA1", "args": ["WEATHER_RAIN"]}, {"op": "SetHP", "args": ["CHARACTER_EIRIKA", "7"]},
             {"op": "CUSE", "args": ["CHARACTER_SETH"]}, {"op": "SetAI", "args": ["CHARACTER_SETH", "0x303"]},
             {"op": "SOUN", "args": ["0x5A"]}, {"op": "VCWF", "args": ["2"]}]
    end = next(i for i, c in enumerate(original) if c["op"] in ("NoFade", "ENDA"))
    project.save("dialogues", {"scripts": {script: original[:end] + added + original[end:]}})
    out = build(project)
    with Game(out.rom_path, out.map_path) as game:
        assert game.wait_until(lambda: game.turn() == 1 and game.phase() == "player", seconds=240, step=20, tap="START")
        assert game.read("gPlaySt", offset=0x15) == 4   # WEATHER_RAIN
        eirika = next(u for u in game.units() if u["character"] == 1)
        assert eirika["hp"] == 7
        assert any(u["character"] == 2 for u in game.units("Red"))   # Seth
        game.screenshot().save(tmp_path / "rain.png")


def test_screen_tint_counters_and_leaving_the_party(tmp_path):
    project = Project.create(tmp_path / "evtint", "Tint")
    project.set_test_options({"start": "map", "simplePrologue": False})
    script = "EventScr_Prologue_BeginningScene"
    original = DecompData(project.decomp_dir).script_commands(script)
    added = [{"op": "ScreenTint", "args": ["0", "150", "40", "40"]},
             {"op": "COUNTER_SET", "args": ["0", "3"]}, {"op": "COUNTER_INC", "args": ["0"]}, {"op": "STAL", "args": ["600"]},
             {"op": "COUNTER_CHECK", "args": ["0"]}, {"op": "SVAL", "args": ["EVT_SLOT_1", "4"]},
             {"op": "BNE", "args": ["0x7f", "EVT_SLOT_C", "EVT_SLOT_1"]},
             {"op": "REMU", "args": ["CHARACTER_SETH"]}, {"op": "LABEL", "args": ["0x7f"]}]
    end = next(i for i, c in enumerate(original) if c["op"] in ("NoFade", "ENDA"))
    project.save("dialogues", {"scripts": {script: original[:end] + added + original[end:]}})
    out = build(project)
    with Game(out.rom_path, out.map_path) as game:
        # gEventSlotCounter (sym_iwram.txt, not in the map file); the tint lasts while the scene runs
        assert game.wait_until(lambda: game.read(0x03000568, width=32) & 0xF == 4, seconds=240, step=20, tap="A")
        game.run(30)
        shot = game.screenshot().convert("RGB")
        shot.save(tmp_path / "tint.png")
        r, g, b = (sum(c) / len(c) for c in zip(*shot.getdata()))
        assert r > 2 * g and r > 2 * b   # tinted red
        assert game.wait_until(lambda: game.turn() == 1 and game.phase() == "player", seconds=240, step=20, tap="START")
        base = game.address("gUnitArrayBlue")
        seth = next(base + i * 0x48 for i in range(62) if game.read(base + i * 0x48, width=32)
                    and game.read(game.read(base + i * 0x48, width=32), 4) == 2)
        assert game.read(seth, 0x0C, width=32) & (1 << 16)   # Seth left the party (kept from chapter to chapter)


# ---------- test bench ----------
# A blank project (a 15 x 10 plain): each unit alone, far from the others and from one unarmed enemy, carrying only what
# the test gives it. Its command menu is always "Item, Wait" (no Rescue, Trade or Attack slipping in before).

BENCH_SPOTS = [(2, 2), (8, 2), (2, 7), (8, 7)]


def _bench(tmp_path, name, items_by_unit, enemy_at=(14, 9)):
    """A project on the bench: unit k stands at BENCH_SPOTS[k] with items_by_unit[k] (item ids); one unarmed enemy
    soldier stands at enemy_at (next to a unit, it is the only target of its Attack)."""
    from fe_maker import newchapter

    project = Project.create(tmp_path / name, name)
    newchapter.start_blank(project, True, "Banc", "Banc")
    characters = project.load("characters")
    chapters = project.load("chapters")
    army = chapters["unitGroups"]["UnitDef_Event_PrologueAlly"]
    lord = army[0]
    placed = []
    for k, items in enumerate(items_by_unit):
        if k == 0:
            unit = lord
        else:
            friend = DecompData(project.decomp_dir).new_character(True, {c["id"] for c in characters}, True)
            friend["name"] = f"Banc {k}"
            characters.append(friend)
            unit = {**lord, "slot": None, "character": friend["id"], "class": friend["class"]}
        x, y = BENCH_SPOTS[k]
        unit.update(x=x, y=y, endX=x, endY=y, items=list(items))
        placed.append(unit)
    chapters["unitGroups"]["UnitDef_Event_PrologueAlly"] = placed
    project.save("characters", characters)
    dialogues = project.load("dialogues")
    opening = dialogues["scripts"][DecompData(project.decomp_dir).chapter_openings()[0]]
    enemies = next(c["args"][1] for c in opening if c["op"] == "LOAD1")
    chapters["unitGroups"][enemies] = [{
        "slot": None, "character": "CHARACTER_SOLDIER_83", "class": "CLASS_SOLDIER", "level": 1, "autolevel": False,
        "side": "enemy", "x": enemy_at[0], "y": enemy_at[1], "endX": enemy_at[0], "endY": enemy_at[1],
        "items": [], "ai": [0, 0, 0, 0], "fixedPath": False}]
    project.save("chapters", chapters)
    return project


def _bench_units(game, turn=1):
    """The bench's units, in the order of BENCH_SPOTS: their addresses."""
    assert game.wait_until(lambda: game.chapter() == 0 and game.turn() == turn and game.phase() == "player" and game.units())
    game.run(120)
    base = game.address("gUnitArrayBlue")
    found = {(game.read(base + n * UNIT_SIZE, 0x10), game.read(base + n * UNIT_SIZE, 0x11)): base + n * UNIT_SIZE
             for n in range(62) if game.read(base + n * UNIT_SIZE, width=32)}
    return [found[spot] for spot in BENCH_SPOTS if spot in found]


def _bench_attack(game, unit):
    """On the bench: the unit attacks, where it stands, with its first weapon the enemy next to it."""
    game.move_cursor(game.read(unit, 0x10), game.read(unit, 0x11))
    game.press("A")
    game.press("A", wait=60)       # stays
    game.press("A", wait=30)       # Attack
    game.press("A", wait=30)       # the first weapon
    game.press("A", wait=30)       # the target
    game.press("A", wait=30)       # the forecast


def _bench_suspend_and_resume(game, units, wipe=None):
    """On the bench: Suspend from the map menu and quit, wipe the units' memory and the turn (so only the save can
    bring them back; `wipe`, a function, wipes more), then Resume Chapter from the title screen."""
    game.move_cursor(14, 2)
    game.press("A", wait=30)
    game.press("UP", wait=15)
    game.press("UP", wait=15)      # Suspend
    for _ in range(4):             # Suspend, Yes (quit), then the two lines of "Next time, choose Resume Chapter"
        game.press("A", wait=120)
    turn = game.turn()
    for unit in units:
        for offset in range(0x10, UNIT_SIZE):
            game.write(unit, 0, offset)
    game.write("gPlaySt", 0, 0x10, width=16)
    if wipe:
        wipe()
    for _ in range(6):             # to the title screen's menu
        game.press("START", wait=70)
    assert game.wait_until(lambda: game.turn() == turn, seconds=20, step=60, tap="A")   # Resume Chapter, the save



def _bench_use_item(game, unit, slot=0):
    """On the bench: the unit uses an item where it stands (Item is its first command)."""
    game.move_cursor(game.read(unit, 0x10), game.read(unit, 0x11))
    game.press("A")
    game.press("A", wait=60)       # stays
    game.press("A", wait=30)       # Item
    for _ in range(slot):
        game.press("DOWN", wait=15)
    game.press("A", wait=30)       # the item
    game.press("A", wait=30)       # Use
    game.run(300)


def _item_number(item):
    return int(item["id"].removeprefix("ITEM_NEW_"), 16)


def test_a_copied_vulnerary_heals_in_game(tmp_path):
    """Ticket 144: an item the project adds acts like its model (here a Vulnerary) wherever the engine tests its number.
    Ticket 162: its stat bonuses are kept for good on use, like a booster's."""
    probe = _bench(tmp_path, "copy", [[]])
    new = DecompData(probe.decomp_dir).new_item("ITEM_VULNERARY", {i["id"] for i in probe.load("items")})
    new["name"] = "Baume"
    new["statBonuses"] = {"hp": 3, "pow": 2}
    probe.save("items", [*probe.load("items"), new])
    chapters = probe.load("chapters")
    chapters["unitGroups"]["UnitDef_Event_PrologueAlly"][0]["items"] = [new["id"]]
    probe.save("chapters", chapters)
    out = build(probe)
    with Game(out.rom_path, out.map_path) as game:
        (unit,) = _bench_units(game)
        game.write(unit, 5, 0x13)
        max_hp, power = game.read(unit, 0x12), game.read(unit, 0x14)
        _bench_use_item(game, unit)
        assert game.read(unit, 0x13) > 5
        assert (game.read(unit, 0x12), game.read(unit, 0x14)) == (max_hp + 3, power + 2)
        assert game.read(unit, 0x1E, width=16) & 0xFF == _item_number(new)
        assert game.read(unit, 0x1E, width=16) >> 8 == new["uses"] - 1


@pytest.mark.parametrize("split", [False, True])
def test_copies_heal_and_protect_their_own_amount(tmp_path, split):
    """Ticket 144: a Vulnerary copy heals 3 HP, a Pure Water copy gives +3 Resistance, another +4 Speed; both bonuses
    drop by 1 at the next turn; a third one adds +5 Strength beside the Speed, and both survive a suspend.
    Ticket 164: a weaker drink on the same stat keeps the strongest bonus (the default rule); a malus shows.
    Ticket 27: with Strength and Magic split, the bonuses move from the unit's spare bytes to a table by unit number."""
    project = _bench(tmp_path, "amount", [[], [], []])
    project.set_game_options({**project.game_options, "statusGrowths": True})   # ticket 166: Select shows growths
    if split:
        project.set_game_options({**project.game_options, "strMagSplit": True})
    items = project.load("items")
    decomp = DecompData(project.decomp_dir)
    balm = decomp.new_item("ITEM_VULNERARY", {i["id"] for i in items})
    water = decomp.new_item("ITEM_PUREWATER", {i["id"] for i in items} | {balm["id"]})
    balm.update(name="Baume", effectAmount=3)
    water.update(name="Eau", effectAmount=3)
    tonic = decomp.new_item("ITEM_PUREWATER", {i["id"] for i in items} | {balm["id"], water["id"]})
    tonic.update(name="Tonique", effectAmount=4, effectStat="spd")
    force = decomp.new_item("ITEM_PUREWATER", {i["id"] for i in items} | {balm["id"], water["id"], tonic["id"]})
    force.update(name="Force", tempBonuses={"pow": 5, "def": -2, **({"mag": 3} if split else {})})   # ticket 164: several
    # stats, a malus; ticket 27: Magic too, with the split
    small = decomp.new_item("ITEM_PUREWATER", {i["id"] for i in items} | {balm["id"], water["id"], tonic["id"], force["id"]})
    small.update(name="Petite", tempBonuses={"pow": 2, "spd": -1})
    project.save("items", [*items, balm, water, tonic, force, small])
    chapters = project.load("chapters")
    for unit, item in zip(chapters["unitGroups"]["UnitDef_Event_PrologueAlly"], (balm, water, tonic)):
        unit["items"] = [item["id"]]
    chapters["unitGroups"]["UnitDef_Event_PrologueAlly"][2]["items"].append(force["id"])
    chapters["unitGroups"]["UnitDef_Event_PrologueAlly"][0]["items"].append(small["id"])
    project.save("chapters", chapters)
    out = build(project)

    def bonuses(unit):   # 4 signed bits per stat: Str, Skl, Spd, Def, Res, Lck
        if split:
            return game.read("gTempBonusesFem", 4 * game.read(unit, 0x0B), width=32)
        return game.read(unit, 0x3A) | game.read(unit, 0x3B) << 8 | game.read(unit, 0x47) << 16

    def set_bonuses(unit, value):
        if split:
            game.write("gTempBonusesFem", value, 4 * game.read(unit, 0x0B), width=32)
        else:
            game.write(unit, value, 0x3A)

    def wipe_table():
        for unit in (second, third):
            set_bonuses(unit, 0)

    with Game(out.rom_path, out.map_path) as game:
        first, second, third = _bench_units(game)
        game.write(first, 5, 0x13)
        _bench_use_item(game, first)
        assert game.read(first, 0x13) == 8
        _bench_use_item(game, second)
        assert game.read(second, 0x31) >> 4 == 3
        _bench_use_item(game, third)
        assert bonuses(third) == 0x400   # Speed +4
        # every unit has acted: the turn ends by itself
        # (lowered at the start of the phase, after its banner: TickActiveFactionTurn)
        assert game.wait_until(lambda: game.turn() == 2 and game.read(second, 0x31) >> 4 == 2, seconds=120, step=30)
        assert bonuses(third) == 0x300
        _bench_use_item(game, third, slot=1)
        drunk = 0x300E305 if split else 0xE305   # Strength +5, Defense -2 (Magic +3) beside Speed +3
        assert bonuses(third) == drunk
        _bench_suspend_and_resume(game, (second, third), wipe_table if split else None)
        _bench_units(game, turn=2)
        assert bonuses(third) == drunk and game.read(second, 0x31) >> 4 == 2
        set_bonuses(first, 0x05)   # Strength +5 already
        _bench_use_item(game, first, slot=1)
        assert bonuses(first) == 0xF05   # the strongest wins: Strength stays +5; Speed -1
        game.move_cursor(game.read(third, 0x10), game.read(third, 0x11))
        game.press("R", wait=120)       # the status screen: Defense shows its -2
        game.screenshot().save(tmp_path / "status.png")
        print("status screen:", tmp_path / "status.png")
        game.press("SELECT", wait=30)   # ticket 166: the growth rates, an HP line below Res
        game.screenshot().save(tmp_path / "growths.png")
        print("growths:", tmp_path / "growths.png")


def test_weapon_sheet_in_a_battle(tmp_path):
    """Double attack, poison and a Strength malus, played: the enemy takes two hits of the lowered damage and is poisoned."""
    place = (BENCH_SPOTS[0][0] + 1, BENCH_SPOTS[0][1])
    project = _bench(tmp_path, "battle", [["ITEM_SWORD_IRON"], []], enemy_at=place)   # a weapon the lord can wield; a
    # second unit, which does not act, keeps the turn from ending by itself (the enemy would then move)
    items = project.load("items")
    next(i for i in items if i["id"] == "ITEM_SWORD_IRON").update(
        properties=["brave"], weaponEffect="poison", hit=255, crit=0, might=1, statBonuses={"pow": -9, "spd": -15})
    project.save("items", items)
    characters = project.load("characters")
    lord = project.load("chapters")["unitGroups"]["UnitDef_Event_PrologueAlly"][0]["character"]
    next(c for c in characters if c["id"] == lord)["bases"].update(pow=12, skl=20)   # a known hit through the malus
    next(c for c in characters if c["id"] == "CHARACTER_SOLDIER_83")["bases"]["hp"] = 40   # outlives the hits
    project.save("characters", characters)
    out = build(project)
    with Game(out.rom_path, out.map_path) as game:
        attacker, _idle = _bench_units(game)
        def now():
            return next((u for u in game.units("Red") if (u["x"], u["y"]) == place), None)

        before = now()["hp"]
        _bench_attack(game, attacker)
        assert game.wait_until(lambda: game.phase() == "player" and (now() is None or now()["hp"] < before),
                               seconds=60, step=20)
        game.run(120)
        attack = game.read("gBattleActor", 0x5A, width=16, signed=True)
        defense = game.read("gBattleTarget", 0x5C, width=16, signed=True)
        print("attack", attack, "defense", defense, "hp", before, "->", now())
        assert now() is not None and before - now()["hp"] == 2 * (attack - defense) > 0
        base = game.address("gUnitArrayRed")
        unit = next(base + n * UNIT_SIZE for n in range(50) if game.read(base + n * UNIT_SIZE, width=32)
                    and (game.read(base + n * UNIT_SIZE, 0x10), game.read(base + n * UNIT_SIZE, 0x11)) == place)
        assert game.read(unit, 0x30) & 0xF == 1


def test_hp_bars_hide_under_a_portrait(tmp_path):
    """Ticket 161: HP bars and talk bubbles stood over the portraits (same object layer): hidden while a face shows.
    On the prologue: the bench's blank chapter shows no unit icons."""
    project = Project.create(tmp_path / "faces", "Faces")
    project.set_game_options({"hpBars": True, "talkBubbles": True})
    out = build(project)
    with Game(out.rom_path, out.map_path) as game:
        _on_map(game)
        game.run(60)
        seth = next(i for i, u in enumerate(game.units()) if u["character"] == 2)
        game.write(game.address("gUnitArrayBlue") + seth * UNIT_SIZE, 5, offset=0x13)
        game.run(30)
        game.screenshot().save(tmp_path / "bar.png")
        taken = {(u["x"], u["y"]) for army in ("Blue", "Red", "Green") for u in game.units(army)}
        game.move_cursor(*next((x, y) for y in range(10) for x in range(15) if (x, y) not in taken))
        game.press("A", wait=30)
        game.press("UP", wait=15)
        game.press("UP", wait=15)
        game.press("A", wait=120)      # Suspend: a portrait asks whether to quit
        game.screenshot().save(tmp_path / "face.png")
        bar_row = 0x06010000 + 0x342 * 0x20 + 16   # the first bar's top border, in tiles a portrait shares (ticket 51)
        assert game.read(bar_row, width=32) != 0xFFFFFFF0, "the bars' tiles were written over the portrait"
        game.press("B", wait=30)
        game.press("B", wait=120)      # No: the portrait leaves, the bars' tiles come back
        game.screenshot().save(tmp_path / "after.png")
        assert game.read(bar_row, width=32) == 0xFFFFFFF0
        print("screenshots:", tmp_path)


def test_enemy_warnings(tmp_path):
    """FEBuilder's HP bar warnings: the lord, made a Cavalier, is selected; the soldier holds a Horseslayer (effective) and a
    Killer Lance (30 crit): its cache byte reads both (0x80 | 1 | 2) and the white "!" is drawn over it."""
    project = _bench(tmp_path, "warnings", [["ITEM_SWORD_IRON"]], enemy_at=(6, 5))
    project.set_game_options({**project.game_options, "enemyWarnings": True, "hpBars": True})
    chapters = project.load("chapters")
    enemies = next(units for units in chapters["unitGroups"].values()
                   if units and units[0].get("character") == "CHARACTER_SOLDIER_83")
    enemies[0]["items"] = ["ITEM_LANCE_HORSESLAYER", "ITEM_LANCE_KILLER"]
    project.save("chapters", chapters)
    out = build(project)
    with Game(out.rom_path, out.map_path) as game:
        lord = _bench_units(game)[0]
        enemy = game.address("gUnitArrayRed")
        game.write(enemy + 0x28 + 1, 71)   # struct Unit ranks[ITYPE_LANCE]: C (the Killer Lance's), as the game checks
        game.write(lord, game.address("gClassData") + (0x05 - 1) * 0x54, offset=4, width=32)   # a Cavalier
        game.move_cursor(game.read(lord, 0x10), game.read(lord, 0x11))
        game.press("A")
        game.run(30)
        game.screenshot().save(tmp_path / "warnings.png")
        cache = 0x02027A00
        assert game.read(cache) == game.read(lord, 0xB)
        assert game.read(cache + (game.read(enemy, 0xB) & 0x3F)) == 0x83
        print("screenshot:", tmp_path / "warnings.png")


def test_talk_bubble_is_vision_quests(tmp_path):
    """Ticket 69 (10/11): Vision Quest's round bubble, at the upper left of the unit Eirika can support with."""
    project = Project.create(tmp_path / "bubble", "Bubble")
    project.set_game_options({"talkBubbles": True})
    out = build(project)
    with Game(out.rom_path, out.map_path) as game:
        _on_map(game)
        game.run(60)
        base = game.address("gUnitArrayBlue")
        units = game.units()
        for index in range(len(units)):
            for support in range(7):
                game.write(base + index * UNIT_SIZE, 80, offset=0x32 + support)   # a C support ready
        eirika = next(u for u in units if u["character"] == 1)
        seth = next(u for u in units if u["character"] == 2)
        game.move_cursor(eirika["x"], eirika["y"])
        game.press("A", wait=30)       # her move range: the bubble shows on Seth
        shot = game.screenshot()
        shot.save(tmp_path / "bubble.png")
        shot.resize((720, 480), Image.NEAREST).save(tmp_path / "bubble3x.png")
        print("screenshot:", tmp_path / "bubble3x.png", "seth at", seth["x"], seth["y"])
        assert game.read(0x06010000 + 0x360 * 0x20 + 4, width=32) == 0xC11111C0


def test_magic_split_from_strength(tmp_path):
    """Ticket 27: with strMagSplit, a tome hits with Magic (the unit's byte 0x3A), a sword with Strength; Magic comes back
    after a suspend."""
    place = (BENCH_SPOTS[0][0] + 1, BENCH_SPOTS[0][1])
    project = _bench(tmp_path, "strmag", [["ITEM_ANIMA_FIRE"], []], enemy_at=place)
    options = dict(project.game_options)
    options["strMagSplit"] = True
    options["statusGrowths"] = True
    project.set_game_options(options)
    chapters = project.load("chapters")
    lord = chapters["unitGroups"]["UnitDef_Event_PrologueAlly"][0]
    lord["class"] = "CLASS_MAGE_F"
    project.save("chapters", chapters)
    characters = project.load("characters")
    hero = next(c for c in characters if c["id"] == lord["character"])
    hero["class"] = "CLASS_MAGE_F"
    hero["weaponRanks"] = {}
    hero["bases"].update(pow=1, mag=9, skl=20)
    hero["growths"].update(mag=100)      # a sure Magic gain at the level up
    next(c for c in characters if c["id"] == "CHARACTER_SOLDIER_83")["bases"]["hp"] = 60
    project.save("characters", characters)
    items = project.load("items")
    next(i for i in items if i["id"] == "ITEM_ANIMA_FIRE")["statBonuses"] = {"mag": 3}   # a Magic bonus while equipped
    project.save("items", items)
    out = build(project)
    with Game(out.rom_path, out.map_path) as game:
        attacker, idle = _bench_units(game)
        magic = game.read(attacker, 0x3A, signed=True)
        strength = game.read(attacker, 0x14, signed=True)
        assert magic >= 9 and magic != strength
        game.move_cursor(game.read(attacker, 0x10), game.read(attacker, 0x11))
        game.press("R", wait=120)          # the status screen: Str, then Mag (with the tome's +3)
        game.screenshot().save(tmp_path / "status.png")
        print("status screen:", tmp_path / "status.png")
        game.press("SELECT", wait=30)      # ticket 166: the growth rates (Magic's too), then the stats again
        game.screenshot().save(tmp_path / "growths.png")
        print("growths:", tmp_path / "growths.png")
        game.press("SELECT", wait=30)
        game.press("B", wait=90)
        magic += 3
        game.write(attacker, 99, 0x09)     # one more experience point: a level up after the battle
        _bench_attack(game, attacker)
        shots = []
        for _ in range(60):               # the level up screen, among these
            game.run(20)
            shots.append(game.screenshot())
        sheet = Image.new("RGB", (240 * 6, 160 * 10))
        for index, shot in enumerate(shots):
            sheet.paste(shot, (240 * (index % 6), 160 * (index // 6)))
        sheet.save(tmp_path / "battle.png")
        print("battle and level up:", tmp_path / "battle.png")
        assert game.wait_until(lambda: game.phase() == "player" and game.read("gBattleActor", 0x5A, width=16), seconds=60)
        game.run(120)
        attack = game.read("gBattleActor", 0x5A, width=16, signed=True)
        print("magic", magic, "strength", strength, "attack", attack)
        assert attack == 5 + magic                     # Fire's might + Magic (with the tome's bonus)
        assert game.read(attacker, 0x3A, signed=True) == magic - 3 + 1   # the level up's Magic
        magic = game.read(attacker, 0x3A, signed=True)
        _bench_suspend_and_resume(game, [attacker, idle])
        assert game.read(attacker, 0x3A, signed=True) == magic
        game.run(120)                      # the resumed map takes keys once it is shown
        game.move_cursor(14, 2)            # the unit list (map menu, Unit), its page 2: Str, then Mag
        game.press("A", wait=60)
        game.press("A", wait=180)
        game.press("RIGHT", wait=90)
        game.screenshot().save(tmp_path / "unit_list.png")
        print("unit list:", tmp_path / "unit_list.png")


def test_skills_in_battle_and_on_the_status_screen(tmp_path):
    """Skills lot 1 (docs/competences.md): a character's Str+2 and Darting Blow, its class's Def+2, counted in battle;
    the status screen shows "Skills" and their icons in the right column (ticket 171), R shows a skill's text."""
    place = (BENCH_SPOTS[0][0] + 1, BENCH_SPOTS[0][1])
    project = _bench(tmp_path, "skills", [["ITEM_SWORD_IRON"], []], enemy_at=place)
    project.set_game_options({**project.game_options, "strMagSplit": True, "skills": True})
    items = project.load("items")
    next(i for i in items if i["id"] == "ITEM_SWORD_IRON").update(weight=0, hit=255, might=0)
    project.save("items", items)
    characters = project.load("characters")
    lord_unit = project.load("chapters")["unitGroups"]["UnitDef_Event_PrologueAlly"][0]
    lord = next(c for c in characters if c["id"] == lord_unit["character"])
    lord["skills"] = ["StrBonus", "BlowDarting"]
    next(c for c in characters if c["id"] == "CHARACTER_SOLDIER_83")["bases"]["hp"] = 60
    project.save("characters", characters)
    classes = project.load("classes")
    next(c for c in classes if c["id"] == lord_unit["class"])["skills"] = ["DefBonus"]
    project.save("classes", classes)
    out = build(project)
    with Game(out.rom_path, out.map_path) as game:
        attacker, _idle = _bench_units(game)
        pow_, spd, def_ = game.read(attacker, 0x14), game.read(attacker, 0x16), game.read(attacker, 0x17)
        game.move_cursor(game.read(attacker, 0x10), game.read(attacker, 0x11))
        game.press("R", wait=120)
        game.screenshot().save(tmp_path / "status.png")
        print("status screen:", tmp_path / "status.png")
        for key in ("R", "DOWN", "DOWN", "DOWN", "DOWN", "DOWN", "DOWN", "DOWN", "DOWN", "RIGHT"):   # Mov, then the 4th skill
            game.press(key, wait=20)
        game.run(120)                   # the help box writes its text letter by letter
        game.screenshot().save(tmp_path / "help.png")
        print("help:", tmp_path / "help.png")
        game.press("B", wait=30)
        game.press("B", wait=60)
        _bench_attack(game, attacker)
        game.run(240)
        actor = game.address("gBattleActor")
        assert game.read(actor, 0x14) == pow_ + 2
        assert game.read(actor, 0x17) == def_ + 2
        assert game.read(actor, 0x5E, width=16, signed=True) == spd + 6


def test_batch_5_passives_in_battle(tmp_path):
    """Skills batch 5: the lord's Push Speed (+5 at full HP), Fortress Def (Str -3, Def +5), Heavy Blade (crit +15 when
    its attack beats the foe's, after both units' skills) and its class's Avoid +10; the attacked soldier's Fierce
    Stance (+6 attack) and Chivalry (+2 attack and defense against a foe at full HP)."""
    place = (BENCH_SPOTS[0][0] + 1, BENCH_SPOTS[0][1])
    project = _bench(tmp_path, "batch5", [["ITEM_SWORD_IRON"], []], enemy_at=place)
    project.set_game_options({**project.game_options, "skills": True})
    items = project.load("items")
    next(i for i in items if i["id"] == "ITEM_SWORD_IRON").update(weight=0, hit=255, might=20, crit=0)
    next(i for i in items if i["id"] == "ITEM_LANCE_IRON").update(might=0, hit=0)
    project.save("items", items)
    chapters = project.load("chapters")
    for units in chapters["unitGroups"].values():   # the soldier gets a weapon (unarmed, the game shows its attack as 255)
        for unit in units:
            if unit.get("character") == "CHARACTER_SOLDIER_83":
                unit["items"] = ["ITEM_LANCE_IRON"]
    project.save("chapters", chapters)
    characters = project.load("characters")
    lord_unit = chapters["unitGroups"]["UnitDef_Event_PrologueAlly"][0]
    lord = next(c for c in characters if c["id"] == lord_unit["character"])
    lord["skills"] = ["PushSpeed", "FortressDef", "HeavyBlade"]
    soldier = next(c for c in characters if c["id"] == "CHARACTER_SOLDIER_83")
    soldier["bases"]["hp"] = 60
    soldier["skills"] = ["StanceFierce", "Chivalry"]
    project.save("characters", characters)
    classes = project.load("classes")
    next(c for c in classes if c["id"] == lord_unit["class"])["skills"] = ["Avoid"]
    project.save("classes", classes)
    out = build(project)
    with Game(out.rom_path, out.map_path) as game:
        attacker, _idle = _bench_units(game)
        pow_, skl, spd, def_, lck = (game.read(attacker, k) for k in (0x14, 0x15, 0x16, 0x17, 0x19))
        _bench_attack(game, attacker)
        game.run(240)
        actor, target = game.address("gBattleActor"), game.address("gBattleTarget")

        def stat(unit, offset):
            return game.read(unit, offset, width=16, signed=True)
        assert (game.read(actor, 0x14), game.read(actor, 0x16), game.read(actor, 0x17)) == (pow_ - 3, spd + 5, def_ + 5)
        assert stat(actor, 0x62) == (spd + 5) * 2 + game.read(actor, 0x57, signed=True) + lck + 10   # Avoid +10
        tri = game.read(target, 0x54, signed=True)                      # the lance's triangle bonus
        assert stat(target, 0x5A) == game.read(target, 0x14) + tri + 8   # a lance of might 0: Str, +6 and +2
        assert stat(target, 0x5C) == game.read(target, 0x17) + game.read(target, 0x56, signed=True) + 2
        assert stat(actor, 0x5A) > stat(target, 0x5A)
        assert stat(actor, 0x66) == skl // 2 + 15                       # Heavy Blade


def test_batch_6_hit_crit_and_damage(tmp_path):
    """Skills batch 6: the lord's Hawkeye (hit 100 with a sword of hit 0), the soldier's Fortune (no crit against it,
    the sword's crit at 100) Dragon Skin and Counter Roar (-50 % and -30 % on
    the first hit, added up as C-SkillSys does)."""
    place = (BENCH_SPOTS[0][0] + 1, BENCH_SPOTS[0][1])
    project = _bench(tmp_path, "batch6", [["ITEM_SWORD_IRON"], []], enemy_at=place)
    project.set_game_options({**project.game_options, "skills": True})
    items = project.load("items")
    next(i for i in items if i["id"] == "ITEM_SWORD_IRON").update(weight=0, hit=0, might=20, crit=100)
    project.save("items", items)
    characters = project.load("characters")
    lord_unit = project.load("chapters")["unitGroups"]["UnitDef_Event_PrologueAlly"][0]
    next(c for c in characters if c["id"] == lord_unit["character"])["skills"] = ["Hawkeye", "InfinityEdge"]
    soldier = next(c for c in characters if c["id"] == "CHARACTER_SOLDIER_83")
    soldier["bases"]["hp"] = 60
    soldier["skills"] = ["Fortune", "DragonSkin", "CounterRoar"]   # Counter Roar: no icon, a "?"
    project.save("characters", characters)
    out = build(project)
    with Game(out.rom_path, out.map_path) as game:
        attacker, _idle = _bench_units(game)
        _bench_attack(game, attacker)
        game.run(240)
        actor = game.address("gBattleActor")

        def stat(offset):
            return game.read(actor, offset, width=16, signed=True)
        assert stat(0x64) == 100 and stat(0x6A) == 0      # Hawkeye, Fortune
        first = game.read(game.address("gBattleHitArray"), width=32)
        damage = (first >> 24) - 256 if first >> 24 > 127 else first >> 24   # hpChange, the damage dealt
        base = stat(0x5A) - game.read(game.address("gBattleTarget"), 0x5C, width=16, signed=True)
        assert damage == max(1, base * 256 // (256 + 256 + 256 * 30 // 70))   # Dragon Skin and Counter Roar add up


def test_batch_7_order_of_the_rounds(tmp_path):
    """Skills batch 7: the attacked soldier's Gale Wings (full HP: it strikes first) and its speed (it doubles), the
    slower lord's Bold Fighter (it doubles too) and Double Lion (one more hit a round, then 1 HP lost): C-SkillSys's
    round table gives soldier, lord, soldier, lord."""
    place = (BENCH_SPOTS[0][0] + 1, BENCH_SPOTS[0][1])
    project = _bench(tmp_path, "batch7", [["ITEM_SWORD_IRON"], []], enemy_at=place)
    project.set_game_options({**project.game_options, "skills": True})
    items = project.load("items")
    next(i for i in items if i["id"] == "ITEM_SWORD_IRON").update(weight=0, hit=255, might=1, crit=0)
    next(i for i in items if i["id"] == "ITEM_LANCE_IRON").update(weight=0, might=0, hit=0)
    project.save("items", items)
    chapters = project.load("chapters")
    for units in chapters["unitGroups"].values():
        for unit in units:
            if unit.get("character") == "CHARACTER_SOLDIER_83":
                unit["items"] = ["ITEM_LANCE_IRON"]
    project.save("chapters", chapters)
    characters = project.load("characters")
    lord_unit = chapters["unitGroups"]["UnitDef_Event_PrologueAlly"][0]
    next(c for c in characters if c["id"] == lord_unit["character"])["skills"] = ["BoldFighter", "DoubleLion"]
    soldier = next(c for c in characters if c["id"] == "CHARACTER_SOLDIER_83")
    soldier["bases"].update(hp=60, spd=40)
    soldier["skills"] = ["GaleWings"]
    project.save("characters", characters)
    out = build(project)
    with Game(out.rom_path, out.map_path) as game:
        attacker, _idle = _bench_units(game)
        max_hp = game.read(attacker, 0x12)
        _bench_attack(game, attacker)
        game.run(240)
        actor, target = game.address("gBattleActor"), game.address("gBattleTarget")
        assert game.read(target, 0x5E, width=16, signed=True) >= game.read(actor, 0x5E, width=16, signed=True) + 4
        hits = [game.read(game.address("gBattleHitArray") + 4 * i, width=32) for i in range(7)]
        foe = [bool((h >> 19) & 0x8) for h in hits]                     # BATTLE_HIT_INFO_RETALIATION
        follow = [bool(h & 0x4) for h in hits]                           # BATTLE_HIT_ATTR_FOLLOWUP
        assert foe[:6] == [True, False, False, True, False, False]
        assert follow[:6] == [False, False, False, True, True, True]
        assert (hits[5] >> 19) & 0x10 or (hits[6] >> 19) & 0x10      # BATTLE_HIT_INFO_END
        assert game.read(actor, 0x13) == max_hp - 1                      # Double Lion


def test_batch_8_status_sturdy_and_armsthrift(tmp_path):
    """Skills lot 8: the lord's Poison Point (the soldier poisoned) and Armsthrift (Luck 100: no use lost), the soldier's
    Sturdy (full HP: a deadly hit leaves it at 1 HP)."""
    place = (BENCH_SPOTS[0][0] + 1, BENCH_SPOTS[0][1])
    project = _bench(tmp_path, "batch8", [["ITEM_SWORD_IRON"], []], enemy_at=place)
    project.set_game_options({**project.game_options, "skills": True})
    items = project.load("items")
    next(i for i in items if i["id"] == "ITEM_SWORD_IRON").update(weight=0, hit=255, might=60, crit=0)
    project.save("items", items)
    characters = project.load("characters")
    lord_unit = project.load("chapters")["unitGroups"]["UnitDef_Event_PrologueAlly"][0]
    next(c for c in characters if c["id"] == lord_unit["character"])["skills"] = ["PoisonPoint", "Armsthrift"]
    soldier = next(c for c in characters if c["id"] == "CHARACTER_SOLDIER_83")
    soldier["bases"]["hp"] = 30
    soldier["skills"] = ["Sturdy"]
    project.save("characters", characters)
    out = build(project)
    with Game(out.rom_path, out.map_path) as game:
        attacker, _idle = _bench_units(game)
        game.write(attacker, 100, 0x19)           # Luck 100: Armsthrift always
        _bench_attack(game, attacker)
        game.run(240)
        actor, target = game.address("gBattleActor"), game.address("gBattleTarget")
        first = game.read(game.address("gBattleHitArray"), width=32)
        assert first & (1 << 6)                                          # BATTLE_HIT_ATTR_POISON
        assert game.read(target, 0x6F, signed=True) == 1                 # statusOut: poison
        assert game.read(target, 0x13) == 1                               # Sturdy: 1 HP left
        assert game.read(actor, 0x48, width=16) == game.read(actor, 0x4A, width=16)   # Armsthrift: same uses


def test_batch_9_auras_in_battle(tmp_path):
    """Skills batch 9: the lord attacks the soldier next to it, its friend two tiles away. The friend's Charm (reach 2)
    gives the lord +3 attack, its Spur Spd (reach 1) and Hex (the soldier is 3 tiles away) give nothing; the lord's
    Inner Flame 3 (no adjacent ally) +5 attack, Inner Flame 2 (an ally within 2) nothing; the soldier's Intimidate
    takes 10 off the lord's avoid, its Tantivy (no ally within 3) gives it +10 avoid."""
    place = (BENCH_SPOTS[0][0] + 1, BENCH_SPOTS[0][1])
    project = _bench(tmp_path, "batch9", [["ITEM_SWORD_IRON"], []], enemy_at=place)
    project.set_game_options({**project.game_options, "skills": True})
    items = project.load("items")
    next(i for i in items if i["id"] == "ITEM_SWORD_IRON").update(weight=0, hit=255, might=20, crit=0)
    next(i for i in items if i["id"] == "ITEM_LANCE_IRON").update(might=0, hit=0, weight=0)
    project.save("items", items)
    chapters = project.load("chapters")
    army = chapters["unitGroups"]["UnitDef_Event_PrologueAlly"]
    friend_spot = (BENCH_SPOTS[0][0], BENCH_SPOTS[0][1] + 2)
    army[1].update(x=friend_spot[0], y=friend_spot[1], endX=friend_spot[0], endY=friend_spot[1])
    for units in chapters["unitGroups"].values():
        for unit in units:
            if unit.get("character") == "CHARACTER_SOLDIER_83":
                unit["items"] = ["ITEM_LANCE_IRON"]
    project.save("chapters", chapters)
    characters = project.load("characters")
    next(c for c in characters if c["id"] == army[0]["character"])["skills"] = ["InnerFlame3", "InnerFlame2"]
    next(c for c in characters if c["id"] == army[1]["character"])["skills"] = ["Charm", "SpurSpd", "Hex"]
    soldier = next(c for c in characters if c["id"] == "CHARACTER_SOLDIER_83")
    soldier["bases"]["hp"] = 60
    soldier["skills"] = ["Intimidate", "Tantivy"]
    project.save("characters", characters)
    out = build(project)
    with Game(out.rom_path, out.map_path) as game:
        attacker = _bench_units(game)[0]
        pow_, spd, lck = (game.read(attacker, k) for k in (0x14, 0x16, 0x19))
        _bench_attack(game, attacker)
        game.run(240)
        actor, target = game.address("gBattleActor"), game.address("gBattleTarget")

        def stat(unit, offset):
            return game.read(unit, offset, width=16, signed=True)
        tri = game.read(actor, 0x54, signed=True)
        assert stat(actor, 0x5A) == pow_ + 20 + tri + 3 + 5                       # Charm, Inner Flame 3
        assert stat(actor, 0x5E) == spd                                         # no Spur Spd
        assert stat(actor, 0x62) == spd * 2 + game.read(actor, 0x57, signed=True) + lck - 10   # Intimidate
        t_spd, t_lck = game.read(target, 0x16), game.read(target, 0x19)
        assert stat(target, 0x62) == t_spd * 2 + game.read(target, 0x57, signed=True) + t_lck + 10   # Tantivy


def test_batch_10_mangs_list_first_part(tmp_path):
    """Skills batch 10: the lord (level 10, one item) with Light Weight (+3 Spd), Critical Force (crit Skl * 1.5) and
    Outdoor Fighter, its class's Elbow Room and Battle Veteran (+1 attack, +5 hit); the soldier's Swordbreaker (lance
    against a sword: +20 hit and avoid), Blue Flame (+2 attack, no ally with it) and Loyalty (no lord of its side)."""
    place = (BENCH_SPOTS[0][0] + 1, BENCH_SPOTS[0][1])
    project = _bench(tmp_path, "batch10", [["ITEM_SWORD_IRON"], []], enemy_at=place)
    project.set_game_options({**project.game_options, "skills": True})
    items = project.load("items")
    next(i for i in items if i["id"] == "ITEM_SWORD_IRON").update(weight=0, hit=0, might=20, crit=0)
    next(i for i in items if i["id"] == "ITEM_LANCE_IRON").update(might=0, hit=0, weight=0)
    project.save("items", items)
    chapters = project.load("chapters")
    for units in chapters["unitGroups"].values():
        for unit in units:
            if unit.get("character") == "CHARACTER_SOLDIER_83":
                unit["items"] = ["ITEM_LANCE_IRON"]
    project.save("chapters", chapters)
    characters = project.load("characters")
    lord_unit = chapters["unitGroups"]["UnitDef_Event_PrologueAlly"][0]
    next(c for c in characters if c["id"] == lord_unit["character"])["skills"] = ["LightWeight", "CriticalForce",
                                                                                   "OutdoorFighter"]
    soldier = next(c for c in characters if c["id"] == "CHARACTER_SOLDIER_83")
    soldier["bases"]["hp"] = 60
    soldier["skills"] = ["SwordBreaker", "BlueFlame", "Loyalty"]
    project.save("characters", characters)
    classes = project.load("classes")
    next(c for c in classes if c["id"] == lord_unit["class"])["skills"] = ["ElbowRoom", "BattleVeteran"]
    project.save("classes", classes)
    from fe_maker.decomp import skills
    terrains = {}
    for line in (REPO_ROOT / "decomp/include/constants/terrains.h").read_text().splitlines():
        if "TERRAIN_" in line and "=" in line:
            name, value = line.split("=")
            terrains[int(value.split(",")[0], 16)] = name.strip()[len("TERRAIN_"):]
    out = build(project)
    with Game(out.rom_path, out.map_path) as game:
        attacker, _idle = _bench_units(game)
        game.write(attacker, 10, 0x08)                                  # level 10
        pow_, skl, spd, lck = (game.read(attacker, k) for k in (0x14, 0x15, 0x16, 0x19))
        _bench_attack(game, attacker)
        game.run(240)
        actor, target = game.address("gBattleActor"), game.address("gBattleTarget")

        def stat(unit, offset):
            return game.read(unit, offset, width=16, signed=True)
        terrain = [game.read(actor, k, signed=True) for k in (0x56, 0x57, 0x58)]
        outdoor = 10 if terrains.get(game.read(actor, 0x55)) in skills.OUTDOOR_TERRAINS else 0
        elbow = 3 if terrain == [0, 0, 0] else 0
        assert game.read(actor, 0x16) == spd + 3                                # Light Weight
        assert stat(actor, 0x66) == skl * 3 // 2                                # Critical Force
        assert stat(actor, 0x5A) == pow_ + 20 + game.read(actor, 0x54, signed=True) + elbow + 1
        assert stat(actor, 0x60) == skl * 2 + lck // 2 + game.read(actor, 0x53, signed=True) + 5 + outdoor
        assert stat(actor, 0x62) == (spd + 3) * 2 + terrain[1] + lck + outdoor
        t_pow, t_skl, t_spd, t_lck = (game.read(target, k) for k in (0x14, 0x15, 0x16, 0x19))
        assert stat(target, 0x5A) == t_pow + game.read(target, 0x54, signed=True) + 2           # Blue Flame alone
        assert stat(target, 0x60) == t_skl * 2 + t_lck // 2 + game.read(target, 0x53, signed=True) + 20
        assert stat(target, 0x62) == t_spd * 2 + game.read(target, 0x57, signed=True) + t_lck + 20


def test_batch_10_after_combat(tmp_path):
    """Skills batch 10, after the battle: the lord (full HP, Skill 100) defeats the soldier. Its Fury takes 6 HP (the
    defeated soldier's Grisly Wound nothing), Lifetaker gives back a quarter, Despoil a Red Gem; its class's Breath
    of Life heals its friend two tiles away (1 HP) a fifth of its max HP. Each with the map's animations."""
    place = (BENCH_SPOTS[0][0] + 1, BENCH_SPOTS[0][1])
    project = _bench(tmp_path, "batch10b", [["ITEM_SWORD_IRON"], []], enemy_at=place)
    project.set_game_options({**project.game_options, "skills": True})
    items = project.load("items")
    next(i for i in items if i["id"] == "ITEM_SWORD_IRON").update(weight=0, hit=255, might=60, crit=0)
    project.save("items", items)
    chapters = project.load("chapters")
    army = chapters["unitGroups"]["UnitDef_Event_PrologueAlly"]
    friend_spot = (BENCH_SPOTS[0][0], BENCH_SPOTS[0][1] + 2)
    army[1].update(x=friend_spot[0], y=friend_spot[1], endX=friend_spot[0], endY=friend_spot[1])
    foes = next(units for units in chapters["unitGroups"].values()
                if any(u.get("character") == "CHARACTER_SOLDIER_83" for u in units))
    foes.append({**foes[0], "x": 14, "y": 9, "endX": 14, "endY": 9})   # a second foe: the first one's defeat is no win
    project.save("chapters", chapters)
    characters = project.load("characters")
    next(c for c in characters if c["id"] == army[0]["character"])["skills"] = ["Fury", "Lifetaker", "Despoil"]
    soldier = next(c for c in characters if c["id"] == "CHARACTER_SOLDIER_83")
    soldier["bases"]["hp"] = 20
    soldier["skills"] = ["GrislyWound"]
    project.save("characters", characters)
    classes = project.load("classes")
    next(c for c in classes if c["id"] == army[0]["class"])["skills"] = ["BreathOfLife"]
    project.save("classes", classes)
    out = build(project)
    with Game(out.rom_path, out.map_path) as game:
        lord = _bench_units(game)[0]
        base = game.address("gUnitArrayBlue")
        friend = next(base + n * UNIT_SIZE for n in range(62)
                      if (game.read(base + n * UNIT_SIZE, 0x10), game.read(base + n * UNIT_SIZE, 0x11)) == friend_spot)
        game.write(friend, 1, 0x13)
        top = game.read(lord, 0x12)
        game.write(lord, top, 0x13)
        _bench_attack(game, lord)
        for _ in range(60):                     # the battle caps Skill to the class's maximum: 100 again for Despoil
            game.run(15)
            game.write(lord, 100, 0x15)
        game.screenshot().save(tmp_path / "after.png")
        game.press("A", wait=60)                                        # the Red Gem's popup
        game.run(300)
        assert game.read(lord, 0x13) == min(top, max(1, top - 6) + top // 4)   # Fury, then Lifetaker
        assert game.read(friend, 0x13) == 1 + game.read(friend, 0x12) // 5   # Breath of Life
        assert game.read(lord, 0x20, width=16) & 0xFF == 0x76           # Despoil: a Red Gem
        game.move_cursor(0, 0)                  # the enemy phase (the AI's action has the same step) goes on
        game.press("A")
        game.press("UP")
        game.press("A")
        assert game.wait_until(lambda: game.turn() == 2 and game.phase() == "player", seconds=120, step=30)


def test_batch_10_savage_blow(tmp_path):
    """Skills batch 10: after the lord's attack, Savage Blow takes a fifth of its last hit's damage from each foe within
    2 tiles of its target, the target included (with the map's damage animation, never deadly); then Lunge: the lord
    and its target switch places."""
    place = (BENCH_SPOTS[0][0] + 1, BENCH_SPOTS[0][1])
    project = _bench(tmp_path, "savage", [["ITEM_SWORD_IRON"]], enemy_at=place)
    project.set_game_options({**project.game_options, "skills": True})
    items = project.load("items")
    next(i for i in items if i["id"] == "ITEM_SWORD_IRON").update(weight=0, hit=255, might=20, crit=0)
    project.save("items", items)
    chapters = project.load("chapters")
    foes = next(units for units in chapters["unitGroups"].values()
                if any(u.get("character") == "CHARACTER_SOLDIER_83" for u in units))
    near = (place[0] + 1, place[1])
    foes.append({**foes[0], "x": near[0], "y": near[1], "endX": near[0], "endY": near[1]})
    project.save("chapters", chapters)
    characters = project.load("characters")
    lord_id = chapters["unitGroups"]["UnitDef_Event_PrologueAlly"][0]["character"]
    next(c for c in characters if c["id"] == lord_id)["skills"] = ["SavageBlow", "Lunge", "Thunderstorm"]   # Thunderstorm: idle
    soldier = next(c for c in characters if c["id"] == "CHARACTER_SOLDIER_83")
    soldier["bases"]["hp"] = 60
    project.save("characters", characters)
    out = build(project)
    with Game(out.rom_path, out.map_path) as game:
        lord = _bench_units(game)[0]
        target, other = (game.address("gUnitArrayRed") + n * UNIT_SIZE for n in range(2))
        assert (game.read(other, 0x10), game.read(other, 0x11)) == near
        hp = game.read(target, 0x13), game.read(other, 0x13)
        start = game.read(lord, 0x10), game.read(lord, 0x11)
        _bench_attack(game, lord)
        assert game.wait_until(lambda: game.read("gBattleHitArray", 0, width=32) != 0, seconds=30, step=10)
        hits = [game.read("gBattleHitArray", 4 * i, width=32) for i in range(8)]
        hits = hits[:next(i for i, hit in enumerate(hits) if hit >> 19 & 0x10)]           # BATTLE_HIT_INFO_END
        mine = [hit >> 24 for hit in hits if not hit >> 19 & 8 and not hit & 2]          # RETALIATION, MISS
        assert game.wait_until(lambda: game.read(other, 0x13) < hp[1], seconds=40, step=10)
        game.run(30)
        game.screenshot().save(tmp_path / "savage.png")
        assert game.read(other, 0x13) == hp[1] - mine[-1] // 5
        assert game.read(target, 0x13) == hp[0] - sum(mine) - mine[-1] // 5
        assert (game.read(lord, 0x10), game.read(lord, 0x11)) == place                  # Lunge
        assert (game.read(target, 0x10), game.read(target, 0x11)) == start


def test_batch_10_pass(tmp_path):
    """Skills batch 10: with Pass the lord's movement goes through the enemy next to it (2 to the tile behind it,
    instead of 4 around it)."""
    place = (BENCH_SPOTS[0][0] + 1, BENCH_SPOTS[0][1])
    project = _bench(tmp_path, "pass", [["ITEM_SWORD_IRON"]], enemy_at=place)
    project.set_game_options({**project.game_options, "skills": True})
    characters = project.load("characters")
    lord_id = project.load("chapters")["unitGroups"]["UnitDef_Event_PrologueAlly"][0]["character"]
    next(c for c in characters if c["id"] == lord_id)["skills"] = ["Pass"]
    project.save("characters", characters)
    out = build(project)
    with Game(out.rom_path, out.map_path) as game:
        lord = _bench_units(game)[0]
        game.move_cursor(game.read(lord, 0x10), game.read(lord, 0x11))
        game.press("A")
        game.run(30)
        rows = game.read("gBmMapMovement", width=32)
        assert game.read(game.read(rows + 4 * place[1], width=32) + place[0] + 1) == 2


def test_batch_10_rally_and_smite(tmp_path):
    """Skills batch 10: the lord's Rally Strength (its menu's first command) gives its friend two tiles away +4
    Strength (its bit in RALLY_FEM) until the next player phase; then the friend steps next to the lord and Smite pushes
    it two tiles; the bonus is gone on turn 2."""
    project = _bench(tmp_path, "rally", [["ITEM_SWORD_IRON"], []])
    project.set_game_options({**project.game_options, "skills": True, "strMagSplit": True})   # Rally Magic: built
    chapters = project.load("chapters")
    army = chapters["unitGroups"]["UnitDef_Event_PrologueAlly"]
    lord_spot = BENCH_SPOTS[0]
    friend_spot = (lord_spot[0], lord_spot[1] + 2)
    army[1].update(x=friend_spot[0], y=friend_spot[1], endX=friend_spot[0], endY=friend_spot[1])
    project.save("chapters", chapters)
    characters = project.load("characters")
    next(c for c in characters if c["id"] == army[0]["character"])["skills"] = ["RallyStrength", "RallyMagic", "RallySpectrum"]
    next(c for c in characters if c["id"] == army[1]["character"])["skills"] = ["Smite"]
    project.save("characters", characters)
    out = build(project)
    with Game(out.rom_path, out.map_path) as game:
        lord = _bench_units(game)[0]
        base = game.address("gUnitArrayBlue")
        friend = next(base + n * UNIT_SIZE for n in range(62)
                      if (game.read(base + n * UNIT_SIZE, 0x10), game.read(base + n * UNIT_SIZE, 0x11)) == friend_spot)
        game.move_cursor(*lord_spot)
        game.press("A")
        game.press("A", wait=60)       # stays
        game.screenshot().save(tmp_path / "menu.png")
        game.press("A", wait=60)       # Rally-Str
        from fe_maker.decomp import skills
        rally = int(skills.RALLY_TABLE, 16) + game.read(friend, 0xB)
        assert game.read(rally) == 1   # Strength's bit
        game.move_cursor(*friend_spot)
        game.press("A")
        game.move_cursor(lord_spot[0], lord_spot[1] + 1)
        game.press("A", wait=60)       # next to the lord
        game.screenshot().save(tmp_path / "menu2.png")
        game.press("A", wait=30)       # Smite
        game.press("A", wait=30)       # the lord, its only target
        assert game.wait_until(lambda: (game.read(lord, 0x10), game.read(lord, 0x11)) == (lord_spot[0], lord_spot[1] - 2),
                               seconds=10, step=10)
        assert game.read(rally) == 1   # still there in the enemy phase to come
        # both units have acted: the turn ends by itself
        assert game.wait_until(lambda: game.phase() != "player", seconds=30, step=10)
        assert game.read(rally) == 1
        assert game.wait_until(lambda: game.turn() == 2 and game.phase() == "player", seconds=120, step=30)
        game.run(120)
        assert game.read(rally) == 0


def test_batch_10_rally_movement_and_celerity(tmp_path):
    """Skills batch 10: the lord has Celerity (Movement +2): its movement map reaches 2 tiles further; its Rally
    Movement gives its friend two tiles away +4 Movement (bit 7 of RALLY_FEM): the friend's map reaches further."""
    project = _bench(tmp_path, "rallymov", [["ITEM_SWORD_IRON"], []])
    project.set_game_options({**project.game_options, "skills": True})
    chapters = project.load("chapters")
    army = chapters["unitGroups"]["UnitDef_Event_PrologueAlly"]
    lord_spot = BENCH_SPOTS[0]
    friend_spot = (lord_spot[0], lord_spot[1] + 2)
    army[1].update(x=friend_spot[0], y=friend_spot[1], endX=friend_spot[0], endY=friend_spot[1])
    project.save("chapters", chapters)
    characters = project.load("characters")
    next(c for c in characters if c["id"] == army[0]["character"])["skills"] = ["RallyMovement", "Celerity"]
    project.save("characters", characters)
    out = build(project)
    with Game(out.rom_path, out.map_path) as game:
        from fe_maker.decomp import skills

        def reach():   # the farthest cost on the selected unit's movement map (0xFF: out of reach)
            width, height = game.read("gBmMapSize", 0, width=16), game.read("gBmMapSize", 2, width=16)
            rows = game.read("gBmMapMovement", width=32)
            costs = [game.read(game.read(rows + 4 * y, width=32) + x) for y in range(height) for x in range(width)]
            return max(cost for cost in costs if cost < 0x80)

        def base_mov(unit):   # struct Unit: movBonus at 0x1D; the class's baseMov at 0x12
            return game.read(game.read(unit, 4, width=32), 0x12) + game.read(unit, 0x1D, signed=True)

        lord = _bench_units(game)[0]
        base = game.address("gUnitArrayBlue")
        friend = next(base + n * UNIT_SIZE for n in range(62)
                      if (game.read(base + n * UNIT_SIZE, 0x10), game.read(base + n * UNIT_SIZE, 0x11)) == friend_spot)
        game.move_cursor(*lord_spot)
        game.press("A")
        game.run(30)
        assert reach() == base_mov(lord) + 2
        game.press("A", wait=60)       # stays
        game.press("A", wait=60)       # Rally-Mov
        assert game.read(int(skills.RALLY_TABLE, 16) + game.read(friend, 0xB)) == 0x80
        game.move_cursor(*friend_spot)
        game.press("A")
        game.run(30)
        assert reach() > base_mov(friend) + 2   # +4 (terrain may cut the last tile)


def test_batch_10_resolve(tmp_path):
    """Skills batch 10: under half HP, Resolve raises the lord's Strength, Skill and Speed by half in battle (the battle
    unit's copies); Lucky Seven, Triangle Adept, Skybreaker and Slayer are built with it."""
    place = (BENCH_SPOTS[0][0] + 1, BENCH_SPOTS[0][1])
    project = _bench(tmp_path, "resolve", [["ITEM_SWORD_IRON"]], enemy_at=place)
    project.set_game_options({**project.game_options, "skills": True})
    characters = project.load("characters")
    lord_id = project.load("chapters")["unitGroups"]["UnitDef_Event_PrologueAlly"][0]["character"]
    next(c for c in characters if c["id"] == lord_id)["skills"] = [
        "Resolve", "LuckySeven", "TriangleAdept", "Skybreaker", "Slayer"]
    project.save("characters", characters)
    out = build(project)
    with Game(out.rom_path, out.map_path) as game:
        lord = _bench_units(game)[0]
        game.write(lord, 1, 0x13)
        stats = [game.read(lord, offset) for offset in (0x14, 0x15, 0x16)]   # struct Unit: pow, skl, spd
        _bench_attack(game, lord)
        assert game.wait_until(lambda: game.read("gBattleHitArray", 0, width=32) != 0, seconds=30, step=10)
        assert [game.read("gBattleActor", offset) for offset in (0x14, 0x15, 0x16)] == [s + s // 2 for s in stats]


def test_batch_10_seals(tmp_path):
    """Skills batch 10, the seals: the lord hits the soldier (it survives) with Seal Strength, Seal Speed and Seal
    Defense; the soldier's counters (the temporary bonuses', 4 bits per stat in its spare bytes) read -6, then -5 once
    its phase has started."""
    place = (BENCH_SPOTS[0][0] + 1, BENCH_SPOTS[0][1])
    project = _bench(tmp_path, "batch10c", [["ITEM_SWORD_IRON"], []], enemy_at=place)
    project.set_game_options({**project.game_options, "skills": True})
    items = project.load("items")
    next(i for i in items if i["id"] == "ITEM_SWORD_IRON").update(weight=0, hit=255, might=1, crit=0)
    project.save("items", items)
    characters = project.load("characters")
    lord_unit = project.load("chapters")["unitGroups"]["UnitDef_Event_PrologueAlly"][0]
    next(c for c in characters if c["id"] == lord_unit["character"])["skills"] = ["SealStrength", "SealSpeed",
                                                                                   "SealDefense"]
    next(c for c in characters if c["id"] == "CHARACTER_SOLDIER_83")["bases"]["hp"] = 60
    project.save("characters", characters)
    out = build(project)
    with Game(out.rom_path, out.map_path) as game:
        lord = _bench_units(game)[0]
        red = game.address("gUnitArrayRed")
        hp = game.read(red, 0x13)
        _bench_attack(game, lord)
        game.run(600)
        assert game.read(red, 0x13) < hp                                  # hit
        assert (game.read(red, 0x3A) & 0xF, game.read(red, 0x3B)) == (0xA, 0xAA)   # Str, Spd, Def at -6
        game.move_cursor(0, 0)
        game.press("A")
        game.press("UP")
        game.press("A")
        assert game.wait_until(lambda: game.turn() == 2 and game.phase() == "player", seconds=120, step=30)
        assert (game.read(red, 0x3A) & 0xF, game.read(red, 0x3B)) == (0xB, 0xBB)   # -5 after its phase began


def test_batch_9_heals_at_the_start_of_the_turn(tmp_path):
    """Skills batch 9: the lord, its friend two tiles away, both at 1 HP. On turn 2 the lord gets Camaraderie (10 %,
    an ally within 2) and the friend's Amaterasu (20 %), not Relief (no ally within 2); the friend, with Relief and
    Amaterasu (an ally's only), stays at 1 HP."""
    project = _bench(tmp_path, "batch9heal", [["ITEM_SWORD_IRON"], []])
    project.set_game_options({**project.game_options, "skills": True})
    chapters = project.load("chapters")
    army = chapters["unitGroups"]["UnitDef_Event_PrologueAlly"]
    army[1].update(x=BENCH_SPOTS[0][0], y=BENCH_SPOTS[0][1] + 2, endX=BENCH_SPOTS[0][0], endY=BENCH_SPOTS[0][1] + 2)
    project.save("chapters", chapters)
    characters = project.load("characters")
    next(c for c in characters if c["id"] == army[0]["character"])["skills"] = ["Relief", "Camaraderie"]
    next(c for c in characters if c["id"] == army[1]["character"])["skills"] = ["Relief", "Amaterasu"]
    project.save("characters", characters)
    out = build(project)
    with Game(out.rom_path, out.map_path) as game:
        assert game.wait_until(lambda: game.turn() == 1 and game.phase() == "player" and game.units())
        game.run(120)
        base = game.address("gUnitArrayBlue")
        found = {(game.read(base + n * UNIT_SIZE, 0x10), game.read(base + n * UNIT_SIZE, 0x11)): base + n * UNIT_SIZE
                 for n in range(62) if game.read(base + n * UNIT_SIZE, width=32)}
        lord, friend = found[BENCH_SPOTS[0]], found[(BENCH_SPOTS[0][0], BENCH_SPOTS[0][1] + 2)]
        for unit in (lord, friend):
            game.write(unit, 1, 0x13)
        game.move_cursor(0, 0)                     # End the turn from the map menu
        game.press("A")
        game.press("UP")
        game.press("A")
        assert game.wait_until(lambda: game.turn() == 2 and game.phase() == "player", seconds=120, step=30)
        game.run(240)
        max_hp = game.read(lord, 0x12)
        assert game.read(lord, 0x13) == min(max_hp, 1 + max_hp * 10 // 100 + max_hp * 20 // 100)
        assert game.read(friend, 0x13) == 1


@pytest.mark.parametrize("shaded", [0, 1])
def test_batch_9_shade_plus_is_never_targeted(tmp_path, shaded):
    """Skills batch 9: an armed soldier halfway between the lord and its friend goes for the one without Shade+."""
    middle = ((BENCH_SPOTS[0][0] + BENCH_SPOTS[1][0]) // 2, BENCH_SPOTS[0][1])
    project = _bench(tmp_path, "batch9ai", [["ITEM_SWORD_IRON"], ["ITEM_SWORD_IRON"]], enemy_at=middle)
    project.set_game_options({**project.game_options, "skills": True})
    chapters = project.load("chapters")
    for units in chapters["unitGroups"].values():
        for unit in units:
            if unit.get("character") == "CHARACTER_SOLDIER_83":
                unit["items"] = ["ITEM_LANCE_IRON"]
    project.save("chapters", chapters)
    characters = project.load("characters")
    holder = chapters["unitGroups"]["UnitDef_Event_PrologueAlly"][shaded]["character"]
    next(c for c in characters if c["id"] == holder)["skills"] = ["ShadePlus"]
    project.save("characters", characters)
    out = build(project)
    with Game(out.rom_path, out.map_path) as game:
        _bench_units(game)
        game.move_cursor(0, 0)                     # End the turn from the map menu
        game.press("A")
        game.press("UP")
        game.press("A")
        assert game.wait_until(lambda: game.turn() == 2 and game.phase() == "player", seconds=120, step=30)
        game.run(120)
        red = game.address("gUnitArrayRed")
        x, y = game.read(red, 0x10), game.read(red, 0x11)
        print("soldier at", (x, y))
        other = BENCH_SPOTS[1 - shaded]
        assert abs(x - other[0]) + abs(y - other[1]) == 1      # next to the unit without Shade+
        assert (x, y) != middle


def test_learned_skill_counts_in_battle(tmp_path):
    """Skills batch 3: a skill in the lord's learned list (the RAM table at skills.LEARNED_TABLE) counts as its own;
    the soldier's sheet has Str+2 so that the skill is compiled."""
    from fe_maker.decomp import skills

    place = (BENCH_SPOTS[0][0] + 1, BENCH_SPOTS[0][1])
    project = _bench(tmp_path, "learned", [["ITEM_SWORD_IRON"], []], enemy_at=place)
    project.set_game_options({**project.game_options, "skills": True})
    characters = project.load("characters")
    next(c for c in characters if c["id"] == "CHARACTER_SOLDIER_83")["skills"] = ["StrBonus"]
    next(c for c in characters if c["id"] == "CHARACTER_SOLDIER_83")["bases"]["hp"] = 60
    project.save("characters", characters)
    used = [s.id for s in skills.used(characters, project.load("classes"), False)]
    out = build(project)
    with Game(out.rom_path, out.map_path) as game:
        attacker, _idle = _bench_units(game)
        pow_ = game.read(attacker, 0x14)
        number = game.read(game.read(attacker, width=32), 4)
        assert number < skills.LEARNED_CHARACTERS
        game.write(int(skills.LEARNED_TABLE, 16) + number * skills.LEARNED_MAX, used.index("StrBonus") + 1)
        _bench_attack(game, attacker)
        game.run(240)
        assert game.read(game.address("gBattleActor"), 0x14) == pow_ + 2


def test_skill_learned_at_a_level_up(tmp_path):
    """Skills batch 3: the lord's sheet learns Str+2 at level 2; with 99 experience, one battle levels it up and the
    skill goes into its learned list."""
    from fe_maker.decomp import skills

    place = (BENCH_SPOTS[0][0] + 1, BENCH_SPOTS[0][1])
    project = _bench(tmp_path, "learnlevel", [["ITEM_SWORD_IRON"], []], enemy_at=place)
    project.set_game_options({**project.game_options, "skills": True})
    characters = project.load("characters")
    lord_id = project.load("chapters")["unitGroups"]["UnitDef_Event_PrologueAlly"][0]["character"]
    lord = next(c for c in characters if c["id"] == lord_id)
    lord["learnedSkills"] = [{"skill": "StrBonus", "level": n} for n in (2, 3, 4, 5)]   # whatever its level (1 to 4)
    next(c for c in characters if c["id"] == "CHARACTER_SOLDIER_83")["bases"]["hp"] = 60
    project.save("characters", characters)
    used = [s.id for s in skills.used(characters, project.load("classes"), False)]
    out = build(project)
    with Game(out.rom_path, out.map_path) as game:
        attacker, _idle = _bench_units(game)
        level = game.read(attacker, 0x8)
        number = game.read(game.read(attacker, width=32), 4)
        table = int(skills.LEARNED_TABLE, 16) + number * skills.LEARNED_MAX
        assert game.read(table) == 0
        game.write(attacker, 99, 0x9)        # experience 99: the next hit levels up
        _bench_attack(game, attacker)
        assert game.wait_until(lambda: game.read(attacker, 0x8) == level + 1, seconds=30, step=10)
        print("level", level, "->", game.read(attacker, 0x8), "learned", [game.read(table + k) for k in range(4)])
        assert level < 5 and game.read(table) == used.index("StrBonus") + 1
        # then the popup "<lord> learned Str+2." with its icon: its instructions are written in free RAM
        inst = int(skills.LEARNED_NAME, 16) + 0x20
        assert game.wait_until(lambda: game.read(inst) == 0x0C, seconds=20, step=5)
        game.run(30)
        game.screenshot().save(tmp_path / "learned.png")
        print("screenshot:", tmp_path / "learned.png")


def test_experience_skills(tmp_path):
    """Skills batch 10: Paragon doubles the battle's experience, Discipline the weapon's (an iron sword gives 1 a hit:
    the rank goes up 2 a hit)."""
    place = (BENCH_SPOTS[0][0] + 1, BENCH_SPOTS[0][1])
    project = _bench(tmp_path, "experience", [["ITEM_SWORD_IRON"]], enemy_at=place)
    project.set_game_options({**project.game_options, "skills": True})
    characters = project.load("characters")
    lord_id = project.load("chapters")["unitGroups"]["UnitDef_Event_PrologueAlly"][0]["character"]
    next(c for c in characters if c["id"] == lord_id)["skills"] = ["Paragon", "Discipline"]
    next(c for c in characters if c["id"] == "CHARACTER_SOLDIER_83")["bases"]["hp"] = 60   # no kill
    project.save("characters", characters)
    out = build(project)
    with Game(out.rom_path, out.map_path) as game:
        lord = _bench_units(game)[0]
        exp, rank = game.read(lord, 0x9), game.read(lord, 0x28)   # struct Unit: exp, ranks[0] (swords)
        _bench_attack(game, lord)
        assert game.wait_until(lambda: game.read(lord, 0x9) != exp, seconds=30, step=10)
        gain, hits = game.read("gBattleActor", 0x6E), game.read("gBattleActor", 0x7B)   # expGain, wexpMultiplier
        print("exp", exp, "+", gain, "rank", rank, "->", game.read(lord, 0x28), "hits", hits)
        assert gain >= 2 and gain % 2 == 0 and game.read(lord, 0x9) == exp + gain
        assert hits >= 1 and game.read(lord, 0x28) == rank + 2 * hits


def test_batch_10_counter(tmp_path):
    """Skills batch 10: the enemy has Counter, the lord always hits (Hawkeye) at melee range: the damage goes back to
    the lord, the enemy keeps its HP. The lord also has the batch's other triggered skills, built with them."""
    place = (BENCH_SPOTS[0][0] + 1, BENCH_SPOTS[0][1])
    project = _bench(tmp_path, "counter", [["ITEM_SWORD_IRON"]], enemy_at=place)
    project.set_game_options({**project.game_options, "skills": True})
    characters = project.load("characters")
    lord_id = project.load("chapters")["unitGroups"]["UnitDef_Event_PrologueAlly"][0]["character"]
    next(c for c in characters if c["id"] == lord_id)["skills"] = [
        "Hawkeye", "Deadeye", "KillingMachine", "Nullify", "RightfulKing", "RightfulGod",
        "Hero", "CounterMagic", "DevilsLuck", "DevilsPact", "DevilsWhim", "AxeFaith", "Bargain", "Deal"]
    soldier = next(c for c in characters if c["id"] == "CHARACTER_SOLDIER_83")
    soldier["skills"] = ["Counter"]
    project.save("characters", characters)
    out = build(project)
    with Game(out.rom_path, out.map_path) as game:
        lord = _bench_units(game)[0]
        enemy = game.address("gUnitArrayRed")
        foe_hp = game.read(enemy, 0x13)   # struct Unit: curHP
        _bench_attack(game, lord)
        # the lord's hits (gBattleHitArray: attributes on 19 bits, 0x80 = BATTLE_HIT_ATTR_DEVIL, then the HP change)
        assert game.wait_until(lambda: game.read("gBattleHitArray", 0, width=32) != 0, seconds=30, step=10)
        hits = [game.read("gBattleHitArray", 4 * i, width=32) for i in range(2)]
        assert all(hit & 0x80 and hit >> 24 for hit in hits), [hex(hit) for hit in hits]
        game.run(600)                     # the damage went back to the lord (who may die of it), not to the enemy
        assert game.read(enemy, 0x13) == foe_hp


def test_batch_10_nihil(tmp_path):
    """Skills batch 10: the lord has Nihil (and Hawkeye, its own skill, which stays); the enemy's Counter is cancelled:
    the enemy loses HP."""
    place = (BENCH_SPOTS[0][0] + 1, BENCH_SPOTS[0][1])
    project = _bench(tmp_path, "nihil", [["ITEM_SWORD_IRON"]], enemy_at=place)
    project.set_game_options({**project.game_options, "skills": True})
    characters = project.load("characters")
    lord_id = project.load("chapters")["unitGroups"]["UnitDef_Event_PrologueAlly"][0]["character"]
    next(c for c in characters if c["id"] == lord_id)["skills"] = ["Nihil", "Hawkeye"]
    next(c for c in characters if c["id"] == "CHARACTER_SOLDIER_83")["skills"] = ["Counter"]
    project.save("characters", characters)
    out = build(project)
    with Game(out.rom_path, out.map_path) as game:
        lord = _bench_units(game)[0]
        enemy = game.address("gUnitArrayRed")
        foe_hp = game.read(enemy, 0x13)
        _bench_attack(game, lord)
        assert game.wait_until(lambda: game.read("gBattleHitArray", 0, width=32) != 0, seconds=30, step=10)
        game.run(600)
        assert game.read(enemy, 0x13) < foe_hp


def test_game_ability_given_as_a_skill(tmp_path):
    """Skills batch 4: Crit +15 (the game's CA_CRITBONUS) on the lord's sheet raises its crit rate in battle, through
    UNIT_CATTRIBUTES, as on a Swordmaster."""
    place = (BENCH_SPOTS[0][0] + 1, BENCH_SPOTS[0][1])
    project = _bench(tmp_path, "gameability", [["ITEM_SWORD_IRON"], []], enemy_at=place)
    project.set_game_options({**project.game_options, "skills": True})
    characters = project.load("characters")
    lord_id = project.load("chapters")["unitGroups"]["UnitDef_Event_PrologueAlly"][0]["character"]
    next(c for c in characters if c["id"] == lord_id)["skills"] = ["Crit", "Canto"]
    next(c for c in characters if c["id"] == "CHARACTER_SOLDIER_83")["bases"]["hp"] = 60
    project.save("characters", characters)
    out = build(project)
    with Game(out.rom_path, out.map_path) as game:
        attacker, _idle = _bench_units(game)
        skl = game.read(attacker, 0x15)
        _bench_attack(game, attacker)
        assert game.wait_until(lambda: game.read("gBattleActor", 0x5A, width=16), seconds=30, step=10)
        crit = game.read("gBattleActor", 0x66, width=16, signed=True)
        print("skill", skl, "crit", crit)
        assert crit == skl // 2 + 15          # Iron Sword: 0 crit


def test_canto_plus_moves_after_a_battle(tmp_path):
    """Skills batch 4: with Canto+, the lord (on foot, no Canto) can move again after a battle: the game's Canto."""
    place = (BENCH_SPOTS[0][0] + 1, BENCH_SPOTS[0][1])
    project = _bench(tmp_path, "cantoplus", [["ITEM_SWORD_IRON"], []], enemy_at=place)
    project.set_game_options({**project.game_options, "skills": True})
    characters = project.load("characters")
    lord_id = project.load("chapters")["unitGroups"]["UnitDef_Event_PrologueAlly"][0]["character"]
    next(c for c in characters if c["id"] == lord_id)["skills"] = ["CantoPlus"]
    next(c for c in characters if c["id"] == "CHARACTER_SOLDIER_83")["bases"]["hp"] = 60
    project.save("characters", characters)
    out = build(project)
    with Game(out.rom_path, out.map_path) as game:
        attacker, _idle = _bench_units(game)
        game.write(attacker, 40, 0x17)            # Defense 40: it survives
        _bench_attack(game, attacker)
        assert game.wait_until(lambda: game.read(attacker, 0xC, width=32) & 0x40, seconds=60, step=10)
        game.run(60)
        state = game.read(attacker, 0xC, width=32)
        game.screenshot().save(tmp_path / "canto.png")
        print("state", hex(state), "screenshot:", tmp_path / "canto.png")
        assert state & 0x40 and not state & 0x2   # cantoing, not grayed


def test_pivot_command(tmp_path):
    """Skills batch 4: Pivot, a command of the unit menu: the lord goes to the other side of the ally next to it."""
    project = _bench(tmp_path, "pivot", [["ITEM_SWORD_IRON"], []])
    chapters = project.load("chapters")
    friend = chapters["unitGroups"]["UnitDef_Event_PrologueAlly"][1]
    friend.update(x=3, y=2, endX=3, endY=2)          # right of the lord (2, 2)
    project.save("chapters", chapters)
    project.set_game_options({**project.game_options, "skills": True})
    characters = project.load("characters")
    lord_id = chapters["unitGroups"]["UnitDef_Event_PrologueAlly"][0]["character"]
    next(c for c in characters if c["id"] == lord_id)["skills"] = ["Pivot"]
    project.save("characters", characters)
    out = build(project)
    with Game(out.rom_path, out.map_path) as game:
        assert game.wait_until(lambda: game.chapter() == 0 and game.phase() == "player" and game.units())
        game.run(120)
        base = game.address("gUnitArrayBlue")
        lord = next(base + n * UNIT_SIZE for n in range(62)
                    if (game.read(base + n * UNIT_SIZE, 0x10), game.read(base + n * UNIT_SIZE, 0x11)) == (2, 2))
        game.move_cursor(2, 2)
        game.press("A")
        game.press("A", wait=60)       # stays: the unit menu
        game.screenshot().save(tmp_path / "menu.png")
        game.press("A", wait=30)       # Pivot, the first command
        game.press("A", wait=30)       # the ally
        game.run(120)
        game.screenshot().save(tmp_path / "pivot.png")
        print("menu:", tmp_path / "menu.png", "after:", tmp_path / "pivot.png")
        assert (game.read(lord, 0x10), game.read(lord, 0x11)) == (4, 2)


def test_reposition_shove_and_swap_commands(tmp_path):
    """Skills batch 4: the unit menu's Reposition, Shove and Swap (in this order, before Rescue), on the lord at (2, 2)
    and the ally at (3, 2), one game each; the units slide there (ticket 27)."""
    project = _bench(tmp_path, "moves", [["ITEM_SWORD_IRON"], []])
    chapters = project.load("chapters")
    friend = chapters["unitGroups"]["UnitDef_Event_PrologueAlly"][1]
    friend.update(x=3, y=2, endX=3, endY=2)
    project.save("chapters", chapters)
    project.set_game_options({**project.game_options, "skills": True})
    characters = project.load("characters")
    lord_id = chapters["unitGroups"]["UnitDef_Event_PrologueAlly"][0]["character"]
    next(c for c in characters if c["id"] == lord_id)["skills"] = ["Reposition", "Shove", "Swap"]
    project.save("characters", characters)
    out = build(project)
    expected = {0: ((2, 2), (1, 2)), 1: ((2, 2), (4, 2)), 2: ((3, 2), (2, 2))}   # command: lord's, ally's tiles
    for command, (lord_at, friend_at) in expected.items():
        with Game(out.rom_path, out.map_path) as game:
            assert game.wait_until(lambda: game.chapter() == 0 and game.phase() == "player" and game.units())
            game.run(120)
            base = game.address("gUnitArrayBlue")
            at = {(game.read(base + n * UNIT_SIZE, 0x10), game.read(base + n * UNIT_SIZE, 0x11)): base + n * UNIT_SIZE
                  for n in range(62) if game.read(base + n * UNIT_SIZE, 0)}
            lord, ally = at[(2, 2)], at[(3, 2)]
            game.move_cursor(2, 2)
            game.press("A")
            game.press("A", wait=60)       # stays: the unit menu
            if command == 0:
                game.screenshot().save(tmp_path / "menu.png")
            for _ in range(command):
                game.press("DOWN", wait=10)
            game.press("A", wait=30)       # the command
            game.press("A", wait=2)        # the ally
            game.screenshot().save(tmp_path / f"slide{command}.png")
            # ticket 27: the ally slides there on the map, set on its tile only at the end
            assert (game.read(ally, 0x10), game.read(ally, 0x11)) == (3, 2)
            game.run(120)
            game.screenshot().save(tmp_path / f"after{command}.png")
            print("menu:", tmp_path / "menu.png", "after:", tmp_path / f"after{command}.png")
            assert (game.read(lord, 0x10), game.read(lord, 0x11)) == lord_at
            assert (game.read(ally, 0x10), game.read(ally, 0x11)) == friend_at


def test_renewal_and_galeforce_on_the_map(tmp_path):
    """Skills batch 4: Renewal heals the lord at the start of turn 2; on turn 2, Galeforce (every time, even with
    Skill 0; a sword of hit 255) lets it act again after its battle won."""
    place = (BENCH_SPOTS[0][0] + 1, BENCH_SPOTS[0][1])
    project = _bench(tmp_path, "mapskills", [["ITEM_SWORD_IRON"], []], enemy_at=place)
    project.set_game_options({**project.game_options, "skills": True})
    items = project.load("items")
    next(i for i in items if i["id"] == "ITEM_SWORD_IRON").update(hit=255)
    project.save("items", items)
    characters = project.load("characters")
    lord_id = project.load("chapters")["unitGroups"]["UnitDef_Event_PrologueAlly"][0]["character"]
    next(c for c in characters if c["id"] == lord_id)["skills"] = ["Renewal", "Galeforce"]
    next(c for c in characters if c["id"] == "CHARACTER_SOLDIER_83")["bases"]["hp"] = 60
    project.save("characters", characters)
    out = build(project)
    with Game(out.rom_path, out.map_path) as game:
        attacker, _idle = _bench_units(game)
        game.write(attacker, 40, 0x17)            # Defense 40: the soldier does no damage
        game.write(attacker, 1, 0x13)             # 1 HP
        game.move_cursor(0, 0)                     # End the turn from the map menu
        game.press("A")
        game.press("UP")
        game.press("A")
        assert game.wait_until(lambda: game.turn() == 2 and game.phase() == "player", seconds=120, step=30)
        game.run(240)
        hp, max_hp = game.read(attacker, 0x13), game.read(attacker, 0x12)
        print("Renewal: 1 ->", hp, "of", max_hp)
        assert hp == min(max_hp, 1 + max_hp * 30 // 100)
        game.write(attacker, 60, 0x14)            # Strength 60: one hit kills
        game.write(attacker, 0, 0x15)             # Skill 0: Galeforce triggers all the same
        _bench_attack(game, attacker)
        assert game.wait_until(lambda: not game.units("Red"), seconds=60, step=10)
        for n in range(8):                         # the flash, then gone (ticket 23)
            game.run(30)
            game.screenshot().save(tmp_path / f"galeforce{n}.png")
        state = game.read(attacker, 0xC, width=32)
        game.screenshot().save(tmp_path / "galeforce.png")
        print("state", hex(state), "screenshot:", tmp_path / "galeforce.png")
        assert not state & 0x2                     # not grayed: it can act again


def test_galeforce_flash_after_a_battle_animation(tmp_path):
    """Ticket 23: after a kill in a battle animation, Galeforce's flash plays and ends (the unit shown again, the light
    column gone): Seth, with Galeforce and Strength 60, attacks in the prologue."""
    project = Project.create(tmp_path / "galeanim", "GaleAnim")
    project.set_game_options({**project.game_options, "skills": True})
    characters = project.load("characters")
    next(c for c in characters if c["id"] == "CHARACTER_SETH")["skills"] = ["Galeforce"]
    project.save("characters", characters)
    out = build(project)
    with Game(out.rom_path, out.map_path) as game:
        _on_map(game)
        base = game.address("gUnitArrayBlue")
        seth = next(base + n * UNIT_SIZE for n in range(20) if game.read(base + n * UNIT_SIZE, width=32)
                    and game.read(game.read(base + n * UNIT_SIZE, width=32), 4) == 2)
        game.write(seth, 60, 0x14)           # Strength 60: one hit kills
        enemy = _seth_attacks(game)
        for k in range(16):
            game.run(60)
            game.screenshot().convert("RGB").save(tmp_path / f"gale{k}.png")
        print("screenshots:", tmp_path, "enemy", enemy)
        state = game.read(seth, 0xC, width=32)
        print("state", hex(state))
        assert not state & 0x2               # not grayed: it can act again
        assert not state & 0x1               # shown again (US_HIDDEN cleared by the flash's end)


def test_vantage_and_desperation_change_the_order_of_attacks(tmp_path):
    """Skills lot 1: the soldier's class has Vantage, the lord Desperation; both under half of their HP. The soldier
    strikes first, then the lord twice in a row (its follow-up before any counter)."""
    place = (BENCH_SPOTS[0][0] + 1, BENCH_SPOTS[0][1])
    project = _bench(tmp_path, "order", [["ITEM_SWORD_IRON"], []], enemy_at=place)
    project.set_game_options({**project.game_options, "skills": True})
    items = project.load("items")
    for item in items:
        if item["id"] in ("ITEM_SWORD_IRON", "ITEM_LANCE_IRON"):
            item.update(weight=0, hit=255, might=0, crit=0)
    project.save("items", items)
    chapters = project.load("chapters")
    enemy = next(u for group in chapters["unitGroups"].values() for u in group if u.get("character") == "CHARACTER_SOLDIER_83")
    enemy["items"] = ["ITEM_LANCE_IRON"]
    project.save("chapters", chapters)
    characters = project.load("characters")
    lord_id = chapters["unitGroups"]["UnitDef_Event_PrologueAlly"][0]["character"]
    lord = next(c for c in characters if c["id"] == lord_id)
    lord["skills"] = ["Desperation"]
    lord["bases"]["spd"] = 15   # doubles the soldier
    soldier = next(c for c in characters if c["id"] == "CHARACTER_SOLDIER_83")
    soldier["bases"].update(hp=40, spd=0)
    project.save("characters", characters)
    classes = project.load("classes")
    next(c for c in classes if c["id"] == "CLASS_SOLDIER")["skills"] = ["Vantage"]
    project.save("classes", classes)
    out = build(project)
    with Game(out.rom_path, out.map_path) as game:
        attacker, _idle = _bench_units(game)
        game.write(attacker, 7, 0x13)       # 7 HP of 16: under half
        base = game.address("gUnitArrayRed")
        foe = next(base + n * UNIT_SIZE for n in range(50) if game.read(base + n * UNIT_SIZE, width=32)
                   and (game.read(base + n * UNIT_SIZE, 0x10), game.read(base + n * UNIT_SIZE, 0x11)) == place)
        game.write(foe, 10, 0x13)            # 10 HP of 40
        _bench_attack(game, attacker)
        game.run(240)
        hits = [game.read("gBattleHitArray", 4 * k, width=32) for k in range(4)]
        attributes = [h & 0x7FFFF for h in hits]
        print("hits", [hex(h) for h in hits])
        retaliate, followup = 1 << 3, 1 << 2   # BATTLE_HIT_ATTR_RETALIATE, _FOLLOWUP
        assert attributes[0] & retaliate                 # Vantage: the soldier first
        assert not attributes[1] & (retaliate | followup)
        assert attributes[2] & followup                   # Desperation: the lord again at once
        assert (hits[3] >> 19) & 0x10                     # BATTLE_HIT_INFO_END after them: no counter


def test_luna_and_sol_trigger_on_each_hit(tmp_path):
    """Skills lot 2: with 100 Skill, Luna and Sol trigger on every hit: the lord wounds a soldier whose defense would
    stop its blows (shown as the game's Pierce), and heals what it deals (as Nosferatu)."""
    place = (BENCH_SPOTS[0][0] + 1, BENCH_SPOTS[0][1])
    project = _bench(tmp_path, "procs", [["ITEM_SWORD_IRON"], []], enemy_at=place)
    project.set_game_options({**project.game_options, "skills": True})
    items = project.load("items")
    next(i for i in items if i["id"] == "ITEM_SWORD_IRON").update(weight=0, hit=255, might=5, crit=0)
    project.save("items", items)
    characters = project.load("characters")
    lord_id = project.load("chapters")["unitGroups"]["UnitDef_Event_PrologueAlly"][0]["character"]
    next(c for c in characters if c["id"] == lord_id)["skills"] = ["Luna", "Sol"]
    next(c for c in characters if c["id"] == "CHARACTER_SOLDIER_83")["bases"]["hp"] = 60
    project.save("characters", characters)
    out = build(project)
    with Game(out.rom_path, out.map_path) as game:
        attacker, _idle = _bench_units(game)
        game.write(attacker, 100, 0x15)      # Skill 100: always triggers
        game.write(attacker, 5, 0x13)        # 5 HP: room to heal
        base = game.address("gUnitArrayRed")
        foe = next(base + n * UNIT_SIZE for n in range(50) if game.read(base + n * UNIT_SIZE, width=32)
                   and (game.read(base + n * UNIT_SIZE, 0x10), game.read(base + n * UNIT_SIZE, 0x11)) == place)
        game.write(foe, 30, 0x17)            # Defense 30: no damage without Luna
        foe_hp = game.read(foe, 0x13)
        _bench_attack(game, attacker)
        assert game.wait_until(lambda: game.read(foe, 0x13) < foe_hp and game.phase() == "player", seconds=60, step=20)
        game.run(120)
        hit = game.read("gBattleHitArray", 0, width=32)
        print("hit", hex(hit), "foe hp", foe_hp, "->", game.read(foe, 0x13), "lord hp", game.read(attacker, 0x13))
        assert hit & (1 << 16) and hit & (1 << 8)   # BATTLE_HIT_ATTR_PIERCE (Luna), _HPSTEAL (Sol)
        dealt = foe_hp - game.read(foe, 0x13)
        assert dealt > 0 and game.read(attacker, 0x13) == min(16, 5 + dealt)


@pytest.mark.parametrize("skill", ["Adept", "Astra"])
def test_adept_and_astra_add_hits(tmp_path, skill):
    """Skills lot 2: with full HP, Adept gives one more hit per attack (2, then 2 in the follow-up); Astra (100 Speed:
    always) gives 5 halved hits, and the battle stops at the game's 6 hits."""
    place = (BENCH_SPOTS[0][0] + 1, BENCH_SPOTS[0][1])
    project = _bench(tmp_path, skill.lower(), [["ITEM_SWORD_IRON"], []], enemy_at=place)
    project.set_game_options({**project.game_options, "skills": True})
    items = project.load("items")
    next(i for i in items if i["id"] == "ITEM_SWORD_IRON").update(weight=0, hit=255, might=10, crit=0)
    project.save("items", items)
    characters = project.load("characters")
    lord_id = project.load("chapters")["unitGroups"]["UnitDef_Event_PrologueAlly"][0]["character"]
    next(c for c in characters if c["id"] == lord_id)["skills"] = [skill]
    next(c for c in characters if c["id"] == "CHARACTER_SOLDIER_83")["bases"]["hp"] = 60
    project.save("characters", characters)
    out = build(project)
    with Game(out.rom_path, out.map_path) as game:
        attacker, _idle = _bench_units(game)
        game.write(attacker, 30, 0x16)       # Speed 30: doubles the soldier
        if skill == "Astra":
            game.write(attacker, 100, 0x16)  # Speed 100: Astra always triggers
        _bench_attack(game, attacker)
        game.run(240)
        hits = [game.read("gBattleHitArray", 4 * k, width=32) for k in range(7)]
        print("hits", [hex(h) for h in hits])
        count = next(k for k, h in enumerate(hits) if (h >> 19) & 0x10)   # BATTLE_HIT_INFO_END
        assert count == (4 if skill == "Adept" else 6)
        assert not any(h & (1 << 3) for h in hits[:count])                 # all the lord's (no counter: unarmed)
        if skill == "Astra":
            attack = game.read("gBattleActor", 0x5A, width=16, signed=True)
            defense = game.read("gBattleTarget", 0x5C, width=16, signed=True)
            assert (hits[0] >> 24) == (attack - defense) // 2
            shown = [game.read(0x02028D82 + 2 * k) for k in range(count)]   # the actor's skill shown on each hit
            assert len(set(shown)) == 1 and shown[0]                        # Astra's number, on every hit


def test_triggered_skill_name_in_battle_animation(tmp_path):
    """Skills lot 2: a triggered skill shows its name and icon under the unit's name plate in the battle animation
    (Huichelaar's display, Skill System): Seth, with Sol and 100 Skill, attacks in the prologue. Ticket 170: Sol, which
    has no game effect, plays the game's skill flash and sound (Sure Strike's); the gauge's palette stays."""
    project = Project.create(tmp_path / "skillname", "SkillName")
    project.set_game_options({**project.game_options, "skills": True})
    characters = project.load("characters")
    next(c for c in characters if c["id"] == "CHARACTER_SETH")["skills"] = ["Sol"]
    project.save("characters", characters)
    out = build(project)
    with Game(out.rom_path, out.map_path) as game:
        _on_map(game)
        base = game.address("gUnitArrayBlue")
        seth = next(base + n * UNIT_SIZE for n in range(20) if game.read(base + n * UNIT_SIZE, width=32)
                    and game.read(game.read(base + n * UNIT_SIZE, width=32), 4) == 2)
        game.write(seth, 100, 0x15)          # Skill 100: Sol always triggers
        _seth_attacks(game)
        assert game.wait_until(lambda: game.read(0x02028D82) or game.read(0x02028D83), seconds=20, step=5)
        print("shown", [game.read(0x02028D82 + k) for k in range(16)])
        for k in range(8):
            game.run(30)
            game.screenshot().convert("RGB").save(tmp_path / f"battle{k}.png")
        print("screenshots:", tmp_path)
        assert game.read(0x02028D90)         # a round was shown
        assert game.read("gAnimRoundData", 2, width=16) & 0x800   # ANIM_ROUND_SURE_SHOT on Seth's side (right)


def test_effect_spore_status_flashes_the_attacker_in_battle_animation(tmp_path):
    """Ticket 33: Seth has Effect Spore; when the enemy's counter hits him, the status it gets (poison, silence or sleep)
    flashes the enemy (the hit's attacker) in its color in the battle animation, never Seth. 50%: tried with other seeds."""
    project = Project.create(tmp_path / "spore", "Spore")
    project.set_game_options({**project.game_options, "skills": True})
    characters = project.load("characters")
    next(c for c in characters if c["id"] == "CHARACTER_SETH")["skills"] = ["EffectSpore"]
    project.save("characters", characters)
    out = build(project)
    seen = []
    for seed in range(12):
        with Game(out.rom_path, out.map_path) as game:
            _on_map(game)
            for k in range(3):   # gRNSeeds (static in rng.c: first in its .bss, at the start of IWRAM)
                game.write(0x03000000, (0x1234 + 0x9E37 * (seed + 1) * (k + 1)) & 0xFFFF, 2 * k, width=16)
            base = game.address("gUnitArrayBlue")
            seth = next(base + n * UNIT_SIZE for n in range(20) if game.read(base + n * UNIT_SIZE, width=32)
                        and game.read(game.read(base + n * UNIT_SIZE, width=32), 4) == 2)
            game.write(seth, 0, 0x16)        # Speed 0, Luck 0: the counter hits more often
            game.write(seth, 0, 0x19)
            game.write(seth, 60, 0x12)       # 60 HP: he survives
            game.write(seth, 60, 0x13)
            _seth_attacks(game)
            statuses = [game.read(0x02028D92 + k) for k in range(7)]
            print("seed", seed, "statuses", statuses)
            hit = next((s for s in statuses if s), 0)
            if not hit:
                continue
            assert hit & 0x80 and (hit & 0x7F) in (1, 2, 3)          # on the battle's target, poison / sleep / silence
            procs = game.address("gpProcEfxStatusUnits")

            def debuff(pos):
                proc = game.read(procs + 4 * pos, width=32)
                return game.read(proc, 0x4C, width=32) if proc else 0

            assert game.wait_until(lambda: debuff(0) or debuff(1), seconds=30, step=2)
            game.screenshot().convert("RGB").save(tmp_path / f"spore{seed}.png")
            enemy_left = game.read("gpEkrBattleUnitLeft", width=32) == game.address("gBattleTarget")
            enemy, seth_side = (0, 1) if enemy_left else (1, 0)
            print("debuffs", debuff(0), debuff(1), "enemy left", enemy_left)
            assert debuff(enemy) == hit & 0x7F and debuff(seth_side) == 0
            seen.append(hit & 0x7F)
            print("screenshots:", tmp_path)
            break
    assert seen, "Effect Spore never triggered"


def test_damage_and_heal_numbers_in_battle_animation(tmp_path):
    """Ticket 169 (option battleNumbers, C-SkillSys's AnimNumber): Seth with Sol attacks in the prologue; a red "-n"
    rises over the unit hit, a green "+n" over Seth when Sol heals him."""
    project = Project.create(tmp_path / "numbers", "Numbers")
    project.set_game_options({**project.game_options, "skills": True, "battleNumbers": True})
    characters = project.load("characters")
    next(c for c in characters if c["id"] == "CHARACTER_SETH")["skills"] = ["Sol"]
    project.save("characters", characters)
    out = build(project)
    with Game(out.rom_path, out.map_path) as game:
        _on_map(game)
        base = game.address("gUnitArrayBlue")
        seth = next(base + n * UNIT_SIZE for n in range(20) if game.read(base + n * UNIT_SIZE, width=32)
                    and game.read(game.read(base + n * UNIT_SIZE, width=32), 4) == 2)
        game.write(seth, 100, 0x15)          # Skill 100: Sol always triggers
        game.write(seth, 10, 0x13)           # 10 HP: Sol has something to heal
        _seth_attacks(game)
        def drawn():   # the number's tiles (the game's MISS / NO DAMAGE text's), first row of slot 0
            return any(game.read(0x06012000 + 4 * k, width=32) for k in range(0x40))

        assert game.wait_until(drawn, seconds=30, step=2)
        for k in range(15):
            game.screenshot().convert("RGB").save(tmp_path / f"numbers{k}.png")
            game.run(8)
        print("screenshots:", tmp_path)


def test_sol_heal_shows_in_battle_animation(tmp_path):
    """Ticket 44: Seth, with Sol and 100 Skill at 10 HP, attacks in the prologue: his HP gauge rises in the battle
    animation (Nosferatu's bars: the foe's, then his), right after the foe's."""
    project = Project.create(tmp_path / "solheal", "SolHeal")
    project.set_game_options({**project.game_options, "skills": True})
    characters = project.load("characters")
    next(c for c in characters if c["id"] == "CHARACTER_SETH")["skills"] = ["Sol"]
    project.save("characters", characters)
    out = build(project)
    with Game(out.rom_path, out.map_path) as game:
        _on_map(game)
        base = game.address("gUnitArrayBlue")
        seth = next(base + n * UNIT_SIZE for n in range(20) if game.read(base + n * UNIT_SIZE, width=32)
                    and game.read(game.read(base + n * UNIT_SIZE, width=32), 4) == 2)
        game.write(seth, 100, 0x15)          # Skill 100: Sol always triggers
        game.write(seth, 10, 0x13)           # 10 HP: Sol has something to heal
        _seth_attacks(game)
        assert game.wait_until(lambda: game.read("gpEkrBattleUnitLeft", width=32), seconds=20, step=5)
        side = 0 if game.read("gpEkrBattleUnitLeft", width=32) == game.address("gBattleActor") else 1
        gauge, foe = [], []

        def healed():
            gauge.append(game.read("gEkrGaugeHp", 2 * side, width=16, signed=True))
            foe.append(game.read("gEkrGaugeHp", 2 * (1 - side), width=16, signed=True))
            return gauge[-1] > 10

        assert game.wait_until(healed, seconds=30, step=2), gauge
        game.screenshot().convert("RGB").save(tmp_path / "sol.png")
        # the foe's bar stops falling, then Seth's rises 10 frames later, as C-SkillSys (Nosferatu's wait: 0x54 frames)
        last_fall = max(k for k in range(1, len(foe)) if foe[k] < foe[k - 1])
        pause = 2 * (len(gauge) - 1 - last_fall)
        print("gauge", gauge[-5:], "foe", foe[-5:], "pause", pause, "frames; screenshot:", tmp_path)
        assert pause <= 16


def test_triggered_skill_icon_in_map_battle(tmp_path):
    """Skills lot 2: without battle animations, a triggered skill's icon shows beside the map battle box (Huichelaar's
    SPD_Map, Skill System): Seth, with Sol and 100 Skill, attacks in the prologue with animations off."""
    project = Project.create(tmp_path / "skillmap", "SkillMap")
    project.set_game_options({**project.game_options, "skills": True})
    characters = project.load("characters")
    next(c for c in characters if c["id"] == "CHARACTER_SETH")["skills"] = ["Sol"]
    project.save("characters", characters)
    out = build(project)
    with Game(out.rom_path, out.map_path) as game:
        _on_map(game)
        base = game.address("gUnitArrayBlue")
        seth = next(base + n * UNIT_SIZE for n in range(20) if game.read(base + n * UNIT_SIZE, width=32)
                    and game.read(game.read(base + n * UNIT_SIZE, width=32), 4) == 2)
        game.write(seth, 100, 0x15)          # Skill 100: Sol always triggers
        config = game.read("gPlaySt", 0x42)
        game.write("gPlaySt", (config & ~0x06) | 0x02, 0x42)   # config.animationType = OFF
        _seth_attacks(game)

        def icon_shown():
            return any(0x4060 <= game.read("gBG0TilemapBuffer", 2 * k, width=16) <= 0x4063 for k in range(32 * 20))
        assert game.wait_until(icon_shown, seconds=20, step=2)
        game.run(6)
        game.screenshot().convert("RGB").save(tmp_path / "map.png")
        print("screenshot:", tmp_path / "map.png")


def test_heal_preview_battle_speed_and_fallen_items(tmp_path):
    """Ticket 6: choosing a staff's target shows its HP before and after (screenshot). Ticket 7: an enemy phase's battle
    with L held takes clearly less time than without. Ticket 8: a fallen unit's items go to the convoy."""
    project = _bench(tmp_path, "comfort", [["ITEM_STAFF_HEAL"], ["ITEM_VULNERARY", "ITEM_ELIXIR"], []], enemy_at=(9, 2))
    project.set_game_options({"healPreview": True, "holdLBattleSpeed": True, "deadItemsToConvoy": True})
    characters = project.load("characters")
    healer_id = project.load("chapters")["unitGroups"]["UnitDef_Event_PrologueAlly"][0]["character"]
    healer = next(c for c in characters if c["id"] == healer_id)
    healer.update(**{"class": "CLASS_PRIEST", "weaponRanks": {**dict.fromkeys(healer["weaponRanks"], 0), "staff": 31}})
    project.save("characters", characters)
    chapters = project.load("chapters")
    chapters["unitGroups"]["UnitDef_Event_PrologueAlly"][0]["class"] = "CLASS_PRIEST"
    for group, units in chapters["unitGroups"].items():
        for unit in units:
            if unit.get("side") == "enemy":
                unit["items"] = ["ITEM_LANCE_IRON"]
    project.save("chapters", chapters)
    out = build(project)

    def end_turn(keys=()):
        game.move_cursor(14, 2)
        game.press("A", wait=30)
        game.press("UP", wait=15)      # End
        game.press("A", wait=30)
        start = game.frame
        while game.phase() == "player" and game.frame - start < 600:
            game.run(10, keys)
        start = game.frame
        while game.phase() != "player" and game.frame - start < 3600:
            game.run(10, keys)
        game.run(60)
        return game.frame - start

    with Game(out.rom_path, out.map_path) as game:
        priest, victim, wounded = _bench_units(game)
        game.write(wounded, 3, 0x13)                       # 3 HP left
        for offset, value in ((0x12, 60), (0x13, 60), (0x17, 5)):   # it survives two enemy phases
            game.write(victim, value, offset)
        game.move_cursor(2, 2)
        game.press("A", wait=30)
        game.move_cursor(2, 6)
        game.press("A", wait=60)                           # moves next to the wounded unit
        game.press("A", wait=30)                           # Staff
        game.press("A", wait=60)                           # Heal: the target's window
        game.screenshot().save(tmp_path / "heal.png")
        print("heal preview:", tmp_path / "heal.png")
        game.press("A", wait=30)
        assert game.wait_until(lambda: game.read(wounded, 0x13) > 3, seconds=20)
        game.run(120)
        slow = end_turn()
        fast = end_turn(["L"])
        print("enemy phase without L:", slow, "with L:", fast)
        assert fast < 0.85 * slow
        items = [game.read(victim, 0x1E + 2 * k, width=16) for k in range(2)]
        game.write(victim, 1, 0x13)                        # 1 HP, no Defense, no Speed, no Luck: it falls
        for offset in (0x16, 0x17, 0x19):
            game.write(victim, 0, offset)
        for _ in range(4):
            if game.read(victim, 0x0C, width=32) & 1 << 2:  # US_DEAD
                break
            end_turn(["L"])
        assert game.read(victim, 0x0C, width=32) & 1 << 2
        convoy = [game.read("gConvoyItemArray", 2 * k, width=16) for k in range(100)]
        assert all(item in convoy for item in items)
        assert not any(game.read(victim, 0x1E + 2 * k, width=16) for k in range(5))


def test_renewal_for_an_enemy_steal_and_canto_given(tmp_path):
    """Skills batch 4, the last checks: Renewal heals an enemy at the start of its phase (the terrain's heal runs for
    every side); Steal given to the lord (not a thief) takes the enemy's Vulnerary; Canto given to a unit on foot lets
    it move again after using an item."""
    place = (BENCH_SPOTS[0][0] + 1, BENCH_SPOTS[0][1])
    project = _bench(tmp_path, "givenskills", [[], ["ITEM_VULNERARY"]], enemy_at=place)
    project.set_game_options({**project.game_options, "skills": True})
    chapters = project.load("chapters")
    ally = chapters["unitGroups"]["UnitDef_Event_PrologueAlly"]
    lord_id, walker_id = ally[0]["character"], ally[1]["character"]
    enemy = next(u for group in chapters["unitGroups"].values() for u in group if u.get("character") == "CHARACTER_SOLDIER_83")
    enemy["items"] = ["ITEM_VULNERARY"]
    project.save("chapters", chapters)
    characters = project.load("characters")
    lord = next(c for c in characters if c["id"] == lord_id)
    lord["skills"] = ["Steal"]
    lord["bases"]["spd"] = 20
    next(c for c in characters if c["id"] == walker_id)["skills"] = ["Canto"]
    soldier = next(c for c in characters if c["id"] == "CHARACTER_SOLDIER_83")
    soldier.update(skills=["Renewal"])
    soldier["bases"].update(hp=20, spd=0)
    project.save("characters", characters)
    out = build(project)
    with Game(out.rom_path, out.map_path) as game:
        thief, walker = _bench_units(game)
        base = game.address("gUnitArrayRed")
        foe = next(base + n * UNIT_SIZE for n in range(50) if game.read(base + n * UNIT_SIZE, width=32)
                   and (game.read(base + n * UNIT_SIZE, 0x10), game.read(base + n * UNIT_SIZE, 0x11)) == place)
        vulnerary = game.read(foe, 0x1E, width=16)
        game.move_cursor(*BENCH_SPOTS[0])
        game.press("A")
        game.press("A", wait=60)       # stays
        game.screenshot().save(tmp_path / "menu.png")
        print("menu:", tmp_path / "menu.png")
        game.press("A", wait=30)       # Steal
        game.press("A", wait=60)       # the soldier
        game.press("A", wait=60)       # its Vulnerary
        assert game.wait_until(lambda: game.read(thief, 0x1E, width=16) == vulnerary, seconds=20)
        assert not game.read(foe, 0x1E, width=16)
        game.run(120)
        game.write(foe, 1, 0x13)       # 1 HP: Renewal heals 30 % of max HP at the start of the enemy phase
        game.move_cursor(14, 2)
        game.press("A", wait=30)
        game.press("UP", wait=15)      # End
        game.press("A", wait=30)
        assert game.wait_until(lambda: game.turn() == 2 and game.phase() == "player", seconds=120, step=30)
        print("enemy Renewal: 1 ->", game.read(foe, 0x13))
        assert game.read(foe, 0x13) == 1 + game.read(foe, 0x12) * 30 // 100
        game.run(120)
        game.write(walker, 5, 0x13)
        _bench_use_item(game, walker)
        state = game.read(walker, 0x0C, width=32)
        game.screenshot().save(tmp_path / "canto.png")
        print("Canto state", hex(state), "screenshot:", tmp_path / "canto.png")
        assert state & 0x40 and not state & 0x2      # cantoing, not done


def test_dance_and_supply_given_as_skills(tmp_path):
    """Ticket 46: Dance given to a unit of a class without dance animation refreshes the lord (on the map, without
    freezing the game); Supply given to it opens the convoy to a unit next to it, away from the lord (menu
    screenshots)."""
    project = _bench(tmp_path, "dance", [[], [], []])
    project.set_game_options({**project.game_options, "skills": True})
    ally = project.load("chapters")["unitGroups"]["UnitDef_Event_PrologueAlly"]
    characters = project.load("characters")
    next(c for c in characters if c["id"] == ally[1]["character"])["skills"] = ["Dance", "Supply"]
    project.save("characters", characters)
    out = build(project)
    with Game(out.rom_path, out.map_path) as game:
        lord, dancer, other = _bench_units(game)
        game.move_cursor(*BENCH_SPOTS[0])
        game.press("A")
        game.press("A", wait=60)       # stays
        game.press("UP", wait=15)      # Wait, the last command
        game.press("A", wait=60)
        assert game.read(lord, 0x0C, width=32) & 0x2
        game.move_cursor(*BENCH_SPOTS[1])
        game.press("A")
        game.press("A", wait=60)       # stays, far from the lord: Supply by its own skill
        game.screenshot().save(tmp_path / "own_menu.png")
        game.press("B", wait=30)
        game.press("B", wait=30)
        game.move_cursor(*BENCH_SPOTS[1])
        game.press("A")
        game.move_cursor(BENCH_SPOTS[0][0] + 1, BENCH_SPOTS[0][1])
        game.press("A", wait=60)       # next to the lord
        game.screenshot().save(tmp_path / "dance_menu.png")
        game.press("A", wait=30)       # Dance, the first command
        game.press("A", wait=30)       # the lord
        assert game.wait_until(lambda: not game.read(lord, 0x0C, width=32) & 0x2, seconds=20), "the lord not refreshed"
        game.run(240)                  # on the map: a class without dance frames froze the game there
        game.screenshot().save(tmp_path / "danced.png")
        game.move_cursor(*BENCH_SPOTS[2])
        game.press("A")
        game.move_cursor(BENCH_SPOTS[0][0] + 1, BENCH_SPOTS[0][1] + 1)
        game.press("A", wait=60)       # under the dancer, not next to the lord
        game.screenshot().save(tmp_path / "supply_menu.png")
        print("menus:", tmp_path)


def test_level_up_screen_with_l_held(tmp_path):
    """Ticket 21: L held through a battle animation ending in a level up: the battle goes twice as fast, the level up
    screen at its own speed (screenshots along the way)."""
    place = (BENCH_SPOTS[0][0] + 1, BENCH_SPOTS[0][1])
    project = _bench(tmp_path, "lvupl", [["ITEM_SWORD_IRON"], []], enemy_at=place)
    project.set_game_options({**project.game_options, "holdLBattleSpeed": True})
    out = build(project)
    with Game(out.rom_path, out.map_path) as game:
        attacker, _idle = _bench_units(game)
        game.write(attacker, 60, 0x14)            # Strength 60: one hit kills
        game.write(attacker, 99, 0x09)            # 99 experience: the kill levels up
        level = game.read(attacker, 0x08)
        _bench_attack(game, attacker)
        for k in range(30):
            game.run(30, ["L"])
            game.screenshot().save(tmp_path / f"lvup{k:02}.png")
        print("screenshots:", tmp_path)
        assert game.read(attacker, 0x08) == level + 1
