"""Local-only tests that need the user's ROM and Docker. Never run in public CI.

Run with:  FE_MAKER_ROM=path/to/fe8.gba python -m pytest tests/local -s
"""

import os
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "server"))

from fe_maker import ups  # noqa: E402
from fe_maker.project import Project  # noqa: E402

ROM = os.environ.get("FE_MAKER_ROM")
pytestmark = pytest.mark.skipif(not ROM, reason="set FE_MAKER_ROM to run tests that need the ROM")


def test_unmodified_project_rebuilds_original_rom(tmp_path):
    project = Project.create(tmp_path / "vanilla", "Vanilla")
    out = project.build(Path(ROM), on_output=lambda line: print(line, end=""))
    assert out.matches_original
    assert out.rom_path.read_bytes() == Path(ROM).read_bytes()


def test_test_build_starting_on_map(tmp_path):
    project = Project.create(tmp_path / "quick", "Quick")
    assert project.test_options["start"] == "map"
    out = project.build(Path(ROM), on_output=lambda line: print(line, end=""), for_test=True)
    assert out.patch_path is None
    assert out.rom_path.read_bytes() != Path(ROM).read_bytes()


def test_modified_project_and_patch(tmp_path):
    project = Project.create(tmp_path / "modded", "Modded")
    chars = project.load("characters")
    eirika = next(c for c in chars if c["id"] == "CHARACTER_EIRIKA")
    eirika["name"] = "Erika"
    eirika["bases"]["hp"] = 20
    eirika["class"] = "CLASS_CAVALIER_F"
    eirika["weaponRanks"]["lance"] = "D"
    eirika["abilities"] = ["female", "lock4", "canto"]
    eirika["affinity"] = "fire"
    problems = [p for p in project.save("characters", chars) if p.severity == "error"]
    assert problems == []
    items = project.load("items")
    iron = next(i for i in items if i["id"] == "ITEM_SWORD_IRON")
    iron["might"] = 9
    iron["reservedFor"] = {"characters": ["CHARACTER_SETH"], "classes": ["CLASS_THIEF"]}
    project.save("items", items)

    classes = project.load("classes")
    thief = next(c for c in classes if c["id"] == "CLASS_THIEF")
    thief["maxes"]["spd"] = 30
    thief["movement"] = "Fly"
    thief["promotions"] = ["CLASS_ASSASSIN", "CLASS_HERO"]
    project.save("classes", classes)
    combat = project.load("combat")
    combat["triangle"][0]["hit"] = -20
    combat["effectiveness"]["ItemEffectiveness_Horse"].append("CLASS_THIEF")
    project.save("combat", combat)
    import copy

    from fe_maker.decomp import units

    group = copy.deepcopy(units.read_unit_groups(project.decomp_dir)["UnitDef_Event_PrologueEnemy"].units)
    group[0]["endX"], group[0]["level"], group[0]["items"] = 11, 9, ["ITEM_AXE_STEEL", "ITEM_VULNERARY"]
    # Remove the second enemy and add a copy of the third one.
    group = [group[0], group[2], dict(group[2], slot=None, copyOf=2, endX=12, endY=9)]
    objectives = {
        "0": {"type": "seize", "seize": [{"x": 4, "y": 3}], "seizeLabel": "throne", "turns": 0,
              "statusText": "Seize the old fort"},
        "2": {"type": "defense", "seize": [], "seizeLabel": "throne", "turns": 8, "statusText": "Survive 8 turns"},
    }
    project.save("chapters", {"unitGroups": {"UnitDef_Event_PrologueEnemy": group}, "objectives": objectives})
    from fe_maker.decomp import maps

    width, height, cells = maps.read_layout(maps.layouts(project.decomp_dir)["PrologueMap"]["assets"].layout)
    rows = [cells[y * width: (y + 1) * width] for y in range(height)]
    rows[0][0] = rows[0][1]  # paint one cell
    rows = [row + [row[-1]] for row in rows]  # one more column
    known = maps.layouts(project.decomp_dir)["Ch2Map"]
    changes = maps.read_changes(project.decomp_dir, known["changes"])
    changes[0]["rows"][0][0] = changes[0]["rows"][0][1]  # edit a change
    changes.append({"id": 99, "x": 0, "y": 0, "w": 1, "h": 1, "rows": [[changes[0]["rows"][0][0]]]})  # and add one
    project.save("maps", {"layouts": {"PrologueMap": {"rows": rows}}, "changes": {"Ch2Map": changes}})
    assert [p for p in project.validate() if p.severity == "error"] == []

    out = project.build(Path(ROM), on_output=lambda line: print(line, end=""))
    built = out.rom_path.read_bytes()
    assert not out.matches_original
    assert ups.apply(Path(ROM).read_bytes(), out.patch_path.read_bytes()) == built


def test_painted_objects_build(tmp_path):
    """New chest, village, house and door on a map: FE Maker adds their map changes, location
    events, village scripts and texts, and the decomp still builds."""
    from fe_maker.decomp import mapobjects, maps

    project = Project.create(tmp_path / "objects", "Objects")
    layout = maps.layouts(project.decomp_dir)["Ch5Map"]
    width, height, cells = maps.read_layout(layout["assets"].layout)
    rows = [cells[y * width: (y + 1) * width] for y in range(height)]
    _metatiles, terrain = maps.read_config(layout["assets"].config)
    rule = mapobjects.rules(project.decomp_dir)[layout["assets"].config.name]
    tile = {t: next(m for m in rule["tiles"] if terrain[m] == t) for t in (0x21, 0x03, 0x1E)}
    for t in (0x05, 0x06):
        tile[t] = next(m for m in range(len(terrain)) if terrain[m] == t)
    for t, (x, y) in ((0x21, (1, 1)), (0x03, (3, 2)), (0x05, (5, 2)), (0x1E, (7, 1)), (0x06, (9, 2))):
        rows[y][x] = tile[t]
    objects = {"3,2": {"item": "ITEM_ELIXIR", "face": "FID_VillagerGirlYoung", "text": "Take this elixir, please."},
               "1,1": {"gold": 3000}, "9,2": {"items": ["ITEM_SWORD_SILVER", "ITEM_LANCE_SILVER"], "secret": True}}
    project.save("maps", {"layouts": {"Ch5Map": {"rows": rows}}, "objects": {"Ch5Map": objects}})
    assert [p for p in project.validate() if p.severity == "error"] == []
    found = mapobjects.map_objects(project.decomp_dir, "Ch5Map", rows, maps.read_changes(project.decomp_dir, layout["changes"]))
    assert all(o["auto"] for o in found if o["new"] and o["kind"] in mapobjects.CHANGE_KINDS)

    out = project.build(Path(ROM), on_output=lambda line: print(line, end=""))
    assert not out.matches_original


def test_turned_tiles_build(tmp_path):
    """A village block turned a quarter turn (new 8x8 tiles) and mirrored, painted on a map: the tile
    config and the tileset image are rewritten and the decomp still builds."""
    from fe_maker.decomp import maps, tileedit

    project = Project.create(tmp_path / "turned", "Turned")
    layout = maps.layouts(project.decomp_dir)["Ch2Map"]
    width, height, cells = maps.read_layout(layout["assets"].layout)
    rows = [cells[y * width: (y + 1) * width] for y in range(height)]
    tileset = tileedit.Tileset(project.decomp_dir, "Ch2Map", None)
    block = [row[3:6] for row in rows[0:3]]
    turned = tileset.transform_block(block, "cw")
    mirrored = tileset.transform_block(block, "h")
    assert tileset.edits["tiles"] and tileset.edits["metatiles"]
    for j in range(3):
        rows[6 + j][12:15] = turned[j]
        rows[10 + j][12:15] = mirrored[j]
    project.save("maps", {"layouts": {"Ch2Map": {"rows": rows}}, "tilesets": {tileset.name: tileset.edits}})
    assert [p for p in project.validate() if p.severity == "error"] == []

    out = project.build(Path(ROM), on_output=lambda line: print(line, end=""))
    assert not out.matches_original


def test_edited_dialogue_build(tmp_path):
    """A prologue conversation changed through steps (new line, new portrait, removed line) still builds."""
    from fe_maker.decomp import dialogues
    from fe_maker.decomp.gamedata import DecompData

    project = Project.create(tmp_path / "talk", "Talk")
    decomp = DecompData(project.decomp_dir)
    message = decomp.chapter_dialogues(0)[0]["messages"][0]
    steps = dialogues.parse(decomp.texts.raw(message))
    says = [i for i, s in enumerate(steps) if s["kind"] == "say"]
    steps[says[0]]["text"] = "A new first line.\nWritten in FE Maker.\n\nAnd a second box!"
    del steps[says[-1]]
    steps.insert(0, {"kind": "face", "pos": "FarLeft", "face": "FID_Franz"})
    steps.insert(1, {"kind": "say", "pos": "FarLeft", "text": "Franz is here too.", "wait": True})
    say = [{"kind": "face", "pos": "MidLeft", "face": "FID_ONeill"},
           {"kind": "say", "pos": "MidLeft", "text": "New quote!", "wait": True}]
    new_quotes = [{"kind": "battle", "chapter": 0, "a": "CHARACTER_ONEILL", "b": "CHARACTER_SETH", "steps": say},
                  {"kind": "death", "chapter": 255, "a": "CHARACTER_FRANZ", "steps": say},
                  {"kind": "talk", "chapter": 2, "a": "CHARACTER_EIRIKA", "b": "CHARACTER_GARCIA", "recruit": True,
                   "both": True, "steps": say},
                  {"kind": "turn", "chapter": 2, "a": "CHARACTER_EIRIKA", "turn": 2, "phase": "enemy", "steps": say}]
    project.save("dialogues", {"messages": {str(message): steps}, "quotes": new_quotes})
    assert [p for p in project.validate() if p.severity == "error"] == []

    out = project.build(Path(ROM), on_output=lambda line: print(line, end=""))
    assert not out.matches_original


def test_reinforcements_build(tmp_path):
    """A group made in the project arrives at the start of an enemy turn; the decomp still builds."""
    project = Project.create(tmp_path / "reinf", "Reinf")
    unit = {"slot": None, "character": "0x80", "class": "CLASS_FIGHTER", "level": 3, "autolevel": True, "side": "enemy",
            "x": 5, "y": 5, "endX": 5, "endY": 5, "items": ["ITEM_AXE_IRON"], "ai": [0, 0, 0, 0]}
    project.save("chapters", {"unitGroups": {"UnitDef_FEM_2_0": [unit, dict(unit, x=6, endX=6)]},
                              "newGroups": {"UnitDef_FEM_2_0": {"chapter": 2, "turn": 3, "phase": "enemy"}}, "objectives": {}})
    assert [p for p in project.validate() if p.severity == "error"] == []
    out = project.build(Path(ROM), on_output=lambda line: print(line, end=""))
    assert not out.matches_original


def test_area_and_protect_objective_build(tmp_path):
    """Chapter 2 won by reaching an area with Eirika, while Ross must survive; the decomp still builds."""
    project = Project.create(tmp_path / "area", "Area")
    objectives = {"2": {"type": "area", "seize": [], "seizeLabel": "throne", "turns": 0, "statusText": "Reach the hills",
                        "area": {"x1": 0, "y1": 0, "x2": 3, "y2": 3}, "areaWho": "CHARACTER_EIRIKA",
                        "protect": "CHARACTER_ROSS"}}
    project.save("chapters", {"unitGroups": {}, "objectives": objectives})
    assert [p for p in project.validate() if p.severity == "error"] == []
    out = project.build(Path(ROM), on_output=lambda line: print(line, end=""))
    assert not out.matches_original


def test_features_of_24_october_build(tmp_path):
    """Accented and too-long dialogue lines, a new support pair, a replaced and a new portrait, another
    palette and tile sheet for a map, convoy openers and chapters: the decomp still builds."""
    from fe_maker.decomp import dialogues, maps, portraits
    from fe_maker.decomp.gamedata import DecompData

    project = Project.create(tmp_path / "day24", "Day 24")
    decomp = DecompData(project.decomp_dir)
    message = decomp.chapter_dialogues(0)[0]["messages"][0]
    steps = dialogues.parse(decomp.texts.raw(message))
    say = next(s for s in steps if s["kind"] == "say")
    say["text"] = "Élodie, ça va ? Où êtes-vous allés ce matin, après la très longue bataille du château ?"
    talk = [{"kind": "face", "pos": "MidLeft", "face": "FID_New173"},
            {"kind": "say", "pos": "MidLeft", "text": "Un nouveau portrait, avec des accents : é è à ç.", "wait": True}]
    pair = {"a": "CHARACTER_FRANZ", "b": "CHARACTER_ROSS", "base": 20, "growth": 3}
    support = {"kind": "support", "a": "CHARACTER_FRANZ", "b": "CHARACTER_ROSS", "rank": 1, "steps": talk}
    pairs = decomp.original_supports() + [pair]
    project.save("dialogues", {"messages": {str(message): steps}, "quotes": [support],
                               "supports": [{k: p[k] for k in ("a", "b", "base", "growth")} for p in pairs]})

    # Portraits: Seth's sheet replaces Gilliam's (4) and becomes a new portrait (173) for Ross.
    sheet = portraits.to_sheet(project.decomp_dir, portraits.portrait_name(project.decomp_dir, 3))
    (project.root / "assets" / "portraits").mkdir(parents=True, exist_ok=True)
    for pid in (4, 173):
        sheet.save(project.root / "assets" / "portraits" / f"{pid}.png")
    project.save("portraits", {str(pid): {"file": f"portraits/{pid}.png", **portraits.detect(sheet)} for pid in (4, 173)})
    characters = decomp.export_characters()
    for ch in characters:
        if ch["id"] == "CHARACTER_ROSS":
            ch["portraitId"] = 173
        if ch["id"] in ("CHARACTER_SETH", "CHARACTER_FRANZ"):
            ch["convoyAccess"] = True
    project.save("characters", characters)

    # The prologue map with tile sheet 4 (redrawn by terrain) and the chapter 2 map with another palette.
    layout = maps.layouts(project.decomp_dir)["PrologueMap"]
    width, height, cells = maps.read_layout(layout["assets"].layout)
    rows = [cells[y * width:(y + 1) * width] for y in range(height)]
    target = maps.with_base(project.decomp_dir, layout["assets"], "TileConfiguration4")
    grids, _missing = maps.convert_by_terrain(project.decomp_dir, maps.read_config(layout["assets"].config)[1], target, [rows])
    ch2 = maps.chapter_map_assets(project.decomp_dir, maps.chapter_settings(project.decomp_dir)[2])
    own = maps.palette_symbol(project.decomp_dir, ch2.palette)
    other = [p["id"] for p in maps.palette_choices(project.decomp_dir, ch2) if p["id"] != own]
    project.save("maps", {"layouts": {"PrologueMap": {"rows": grids[0]}}, "bases": {"PrologueMap": "TileConfiguration4"},
                          "palettes": {ch2.layout.stem: other[0]} if other else {}})
    project.save("chapters", {"unitGroups": {}, "objectives": {}, "convoy": {"0": True, "2": False}})

    assert [p for p in project.validate() if p.severity == "error"] == []
    out = project.build(Path(ROM), on_output=lambda line: print(line, end=""))
    assert not out.matches_original
