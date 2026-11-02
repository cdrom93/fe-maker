import io
import json
import struct

import pytest
from PIL import Image

from fe_maker.decomp import maps, units


def _make_map(tmp_path, fog_color=(10, 20, 30)):
    """A fictional 2x1 map: one 16x16 metatile made of tile 1, using palette 0."""
    tileset = Image.new("L", (16, 8), 255)  # inverted grayscale: 255 = color index 0
    for x in range(8, 16):
        for y in range(8):
            tileset.putpixel((x, y), 255 - 17 * 3)  # tile 1, color index 3
    tileset.save(tmp_path / "ObjectType1.png")
    colors = [(0, 0, 0)] * 160
    colors[3] = (200, 100, 50)  # palette 0, color 3 (normal)
    colors[5 * 16 + 3] = fog_color  # palette 5, color 3 (fog)
    (tmp_path / "MapPalette1.pal").write_text(
        "JASC-PAL\n0100\n160\n" + "\n".join(f"{r} {g} {b}" for r, g, b in colors) + "\n", encoding="utf-8")
    config = bytearray(0x2400)
    struct.pack_into("<4H", config, 8, 1, 1, 1, 1)  # metatile 1 = four times tile 1
    config[0x2000 + 1] = 0x10  # terrain of metatile 1
    (tmp_path / "TileConfiguration1.bin").write_bytes(bytes(config))
    (tmp_path / "Map.mar").write_bytes(struct.pack("<2H", 1 << 5, 0))  # cells: metatile 1, metatile 0
    (tmp_path / "Map.json").write_text(json.dumps({"id": "Map", "width": 2, "height": 1}), encoding="utf-8")
    return maps.MapAssets([tmp_path / "ObjectType1.png"], tmp_path / "MapPalette1.pal",
                          tmp_path / "TileConfiguration1.bin", tmp_path / "Map.mar")


def test_render_map_colors_and_size(tmp_path):
    assets = _make_map(tmp_path)
    png, width, height = maps.render_map(assets)
    assert (width, height) == (2, 1)
    img = Image.open(io.BytesIO(png)).convert("RGB")
    assert img.size == (32, 16)
    assert img.getpixel((4, 4)) == (200, 100, 50)   # metatile 1: normal palette
    fog, _, _ = maps.render_map(assets, fog=True)
    assert Image.open(io.BytesIO(fog)).convert("RGB").getpixel((4, 4)) == (10, 20, 30)


def test_terrain_grid(tmp_path):
    assert maps.terrain_grid(_make_map(tmp_path)) == [[0x10, 0]]


def test_edited_unit_group_reaches_the_overlay(tmp_path, decomp_dir):
    import copy

    from fe_maker.project import Project

    project = Project.create(tmp_path / "p", "P", decomp_dir=decomp_dir)
    original = units.read_unit_groups(decomp_dir)["UnitDef_TestChapter"].units
    edited = copy.deepcopy(original)
    edited[1]["endX"], edited[1]["endY"], edited[1]["level"] = 5, 6, 7
    edited[1]["items"] = ["ITEM_TESTBLADE"]
    project.save("chapters", {"unitGroups": {"UnitDef_TestChapter": edited}})
    overlay = project.generate_overlay(decomp_dir)
    source = (overlay / "src" / "events_udefs.c").read_text(encoding="utf-8")
    rival = source.split(".charIndex = CHARACTER_TESTRIVAL,")[1].split("\n    },")[0]
    assert ".xPosition = 5," in rival and ".yPosition = 6," in rival and ".level = 7," in rival
    assert "ITEM_TESTBLADE" in rival
    # The other units of the group are untouched.
    assert source.count(".charIndex = CHARACTER_TESTHERO,\n        .classIndex = CLASS_TESTLORD,\n        .level = 1,") == 1


def test_a_named_ally_takes_the_level_of_their_sheet(tmp_path, decomp_dir):
    from fe_maker.project import Project

    project = Project.create(tmp_path / "p", "P", decomp_dir=decomp_dir)
    game = units.read_unit_groups(decomp_dir)["UnitDef_TestChapter"].units

    def source():
        return (project.generate_overlay(decomp_dir) / "src" / "events_udefs.c").read_text(encoding="utf-8")

    # An added unit follows the sheet, the game's keep theirs
    project.save("chapters", {"unitGroups": {"UnitDef_TestChapter": [*game, {**game[0], "slot": None, "level": 7}]}})
    assert ".level = 7," not in source() and ".level = 10," in source()

    # A changed sheet reaches the game's units too, in groups nobody edited, but not an enemy or who levels up alone
    characters = project.load("characters")
    next(c for c in characters if c["id"] == "CHARACTER_TESTHERO")["level"] = 5
    project.save("characters", characters)
    project.save("chapters", {"unitGroups": {}})
    assert ".level = 10," not in source() and ".level = 3," in source()
    project.save("chapters", {"unitGroups": {"UnitDef_TestChapter": [game[0], game[1], {**game[2], "autolevel": True}]}})
    assert ".level = 10," in source()


def test_autolevel_is_written_on_the_game_units_only_when_it_changes(tmp_path, decomp_dir):
    from fe_maker.project import Project

    project = Project.create(tmp_path / "p", "P", decomp_dir=decomp_dir)
    game = units.read_unit_groups(decomp_dir)["UnitDef_TestChapter"].units
    project.save("chapters", {"unitGroups": {"UnitDef_TestChapter": [{**game[0], "autolevel": True}, game[1], game[2]]}})
    source = (project.generate_overlay(decomp_dir) / "src" / "events_udefs.c").read_text(encoding="utf-8")
    assert source.count(".autolevel = 1,") == 1
    assert units.read_unit_groups(project.generate_overlay(decomp_dir))["UnitDef_TestChapter"].units[0]["autolevel"] is True


def test_level_bonus_of_a_chapter():
    from fe_maker.decomp.gamedata import _set_level_bonus

    settings = [{}, {"easyModeLevelMalus": 4}]
    _set_level_bonus(settings, {"1": {"normal": 2, "hard": 30}})
    assert settings == [{}, {"easyModeLevelMalus": 4, "normalModeLevelMalus": 2, "difficultModeLevelBonus": 15}]


def test_affinity_bonuses(tmp_path):
    from fe_maker.decomp import combat

    assert combat.read_affinity_bonuses(tmp_path) == {}
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "bmreliance-data.c").write_text(
        "struct SupportBonuses gAffinityBonuses[] = {\n    {\n        .affinity = UNIT_AFFIN_FIRE,\n"
        "        .bonusAttack = 1,\n        .bonusDodge = 0,\n    },\n    { 0 },\n};\n", encoding="utf-8")
    assert combat.read_affinity_bonuses(tmp_path) == {"fire": {"attack": 1, "dodge": 0}}


def test_unit_groups_and_chapter_events(decomp_dir):
    groups = units.read_unit_groups(decomp_dir)
    test = groups["UnitDef_TestChapter"].units
    assert [u["character"] for u in test] == ["CHARACTER_TESTHERO", "CHARACTER_TESTRIVAL", "CHARACTER_TESTHERO"]
    assert test[1]["level"] == 3
    chapter = units.chapter_unit_groups(decomp_dir, "TestChapterEvents")
    assert chapter == [
        {"name": "UnitDef_TestChapter", "origin": "players", "turn": None},
        {"name": "UnitDef_TestEnemies", "origin": "opening", "turn": None},
        {"name": "UnitDef_TestReinforcements", "origin": "turn", "turn": 3},
    ]


def _udefs(decomp_dir):
    rel = "src/events_udefs.c"
    return rel, {rel: (decomp_dir / rel).read_text(encoding="utf-8")}


def _reread(tmp_path, sources):
    for rel, text in sources.items():
        (tmp_path / rel).parent.mkdir(parents=True, exist_ok=True)
        (tmp_path / rel).write_text(text, encoding="utf-8")
    units.read_unit_groups.cache_clear()
    return units.read_unit_groups(tmp_path)


def test_add_remove_and_reorder_units(tmp_path, decomp_dir):
    import copy

    original = units.read_unit_groups(decomp_dir)["UnitDef_TestChapter"].units
    assert [u["slot"] for u in original] == [0, 1, 2]
    rel, sources = _udefs(decomp_dir)
    edited = copy.deepcopy([original[2], original[0]])  # remove the rival, reorder
    new = copy.deepcopy(original[1]) | {"slot": None, "copyOf": 1, "endX": 4, "endY": 2}
    edited.append(new)
    out = units.apply_unit_groups(sources, {"UnitDef_TestChapter": edited})
    groups = _reread(tmp_path, out)
    result = groups["UnitDef_TestChapter"].units
    assert [(u["character"], u["class"], u["level"]) for u in result] == [
        ("CHARACTER_TESTHERO", "CLASS_TESTKNIGHT", 10),
        ("CHARACTER_TESTHERO", "CLASS_TESTLORD", 1),
        ("CHARACTER_TESTRIVAL", "CLASS_TESTLORD", 3),
    ]
    assert (result[2]["endX"], result[2]["endY"]) == (4, 2)
    assert "{ 0 }" in out[rel]


def test_remove_all_units_keeps_the_terminator(tmp_path, decomp_dir):
    _, sources = _udefs(decomp_dir)
    out = units.apply_unit_groups(sources, {"UnitDef_TestChapter": []})
    assert _reread(tmp_path, out)["UnitDef_TestChapter"].units == []


def test_unchanged_units_with_slots_are_byte_identical(decomp_dir):
    rel, sources = _udefs(decomp_dir)
    group = units.read_unit_groups(decomp_dir)["UnitDef_TestChapter"].units
    assert units.apply_unit_groups(sources, {"UnitDef_TestChapter": group})[rel] == sources[rel]


def test_parse_ai_expands_macros():
    macros = {"AttackInRangeAI": [0x00, 0x03], "NeverMoveAI": [0x03, 0x03, 0x04, 0x20]}
    assert units.parse_ai("{AttackInRangeAI, 0x9}", macros) == [0x00, 0x03, 0x09, 0x00]
    assert units.parse_ai("{NeverMoveAI}", macros) == [0x03, 0x03, 0x04, 0x20]
    assert units.parse_ai("{0x6, 0x3, 0x0, 0x0}", macros) == [0x06, 0x03, 0x00, 0x00]
    assert units.parse_ai("", macros) == [0, 0, 0, 0]


def test_edit_unit_ai(tmp_path, decomp_dir):
    import copy

    group = copy.deepcopy(units.read_unit_groups(decomp_dir)["UnitDef_TestChapter"].units)
    assert group[0]["ai"] == [0, 0, 0, 0]
    group[0]["ai"] = [0x00, 0x03, 0x09, 0x20]
    rel, sources = _udefs(decomp_dir)
    out = units.apply_unit_groups(sources, {"UnitDef_TestChapter": group})
    assert ".ai = {0x0, 0x3, 0x9, 0x20}," in out[rel]
    assert _reread(tmp_path, out)["UnitDef_TestChapter"].units[0]["ai"] == [0x00, 0x03, 0x09, 0x20]
    # Projects saved before the AI was editable keep the original text.
    group[0]["ai"] = "{0x0, 0x0}"
    assert units.apply_unit_groups(sources, {"UnitDef_TestChapter": group})[rel] == sources[rel]


def test_reinforcements_of_a_cleared_chapter_keep_their_events(monkeypatch, decomp_dir):
    from fe_maker.decomp.gamedata import DecompData

    d = DecompData(decomp_dir)
    added = []
    monkeypatch.setattr(d, "_add_turn_event", lambda name, meta: added.append((name, meta)))
    monkeypatch.setattr(d, "_chapter_event_symbol", lambda _c: "Group")
    monkeypatch.setattr("fe_maker.decomp.gamedata.maps.chapter_settings", lambda _d: [{}])
    monkeypatch.setattr(units, "chapter_unit_groups", lambda _d, _s: [
        {"name": "Empty", "origin": "turn", "turn": 3}, {"name": "Full", "origin": "turn", "turn": 3},
        {"name": "Opening", "origin": "opening", "turn": None}])
    d._apply_group_turns({"cleared": [0], "unitGroups": {"Empty": [], "Full": [{"side": "enemy"}], "Opening": [{}]},
                          "groupTurns": {"Full": {"chapter": 0, "turn": 5}}})
    assert added == [("Full", {"chapter": 0, "turn": 5, "phase": "enemy"})]


def test_a_moved_unit_no_longer_walks_in():
    source = """CONST_DATA struct REDA REDAs_Test[] = {
    { .x = 2, .y = 3 },
};
CONST_DATA struct UnitDefinition UnitDef_Test[] = {
    { .charIndex = CHARACTER_TESTHERO, .level = 1, .xPosition = 9, .yPosition = 9, .redaCount = 1, .redas = REDAs_Test },
    { 0 },
};
"""
    sources = {"a.h": source}
    unit = {"slot": 0, "character": "CHARACTER_TESTHERO", "class": "0", "level": 1, "items": [], "endX": 2, "endY": 3}
    assert units.apply_unit_groups(sources, {"UnitDef_Test": [unit]}) == sources   # still at the end of its path
    moved = units.apply_unit_groups(sources, {"UnitDef_Test": [{**unit, "endX": 4}]})["a.h"]
    assert ".xPosition = 4" in moved and ".yPosition = 3" in moved and ".redas" not in moved.split("UnitDefinition")[1]


def test_cutscene_groups(decomp_dir):
    units._event_sources.cache_clear()
    assert units.chapter_unit_groups(decomp_dir, "TestCutsceneChapterEvents") == [
        {"name": "UnitDef_TestChapter", "origin": "players", "turn": None},
        {"name": "UnitDef_TestCutsceneActors", "origin": "cutscene", "turn": None},
        {"name": "UnitDef_TestEnemies", "origin": "opening", "turn": None},
    ]


def test_named_character_class_comes_from_the_character_sheet(tmp_path, decomp_dir):
    import copy

    rel, sources = _udefs(decomp_dir)
    group = copy.deepcopy(units.read_unit_groups(decomp_dir)["UnitDef_TestChapter"].units)
    group[0]["class"] = "CLASS_TESTKNIGHT"  # ignored: CHARACTER_TESTHERO's class is set on its sheet
    assert units.apply_unit_groups(sources, {"UnitDef_TestChapter": group})[rel] == sources[rel]
    group[0]["character"] = "0x80"  # a generic unit keeps a class chosen in the chapter
    group[0]["class"] = "CLASS_TESTKNIGHT"
    group[1]["character"] = "CHARACTER_TESTHERO"  # becomes a named character: the game uses its class
    out = _reread(tmp_path, units.apply_unit_groups(sources, {"UnitDef_TestChapter": group}))["UnitDef_TestChapter"].units
    assert (out[0]["character"], out[0]["class"]) == ("0x80", "CLASS_TESTKNIGHT")
    assert (out[1]["character"], out[1]["class"]) == ("CHARACTER_TESTHERO", "0")


def test_layout_encoding_round_trip(tmp_path):
    assets = _make_map(tmp_path)
    mar, info = maps.encode_layout("Map", 2, 1, [1, 0])
    assert mar == assets.layout.read_bytes() and info == assets.layout.with_suffix(".json").read_text(encoding="utf-8")


def test_tileset_sheet_and_duplicates(tmp_path):
    assets = _make_map(tmp_path)
    sheet = Image.open(io.BytesIO(maps.render_tileset(assets))).convert("RGB")
    assert sheet.size == (maps.TILESET_COLUMNS * 16, 1024 // maps.TILESET_COLUMNS * 16)
    assert sheet.getpixel((16 + 4, 4)) == (200, 100, 50)  # metatile 1
    duplicates = maps.duplicate_metatiles(assets)
    assert duplicates[:3] == [False, False, True]  # metatiles 2+ are copies of the empty metatile 0
    assert sum(not d for d in duplicates) == 2


def test_painted_layout_reaches_the_overlay(tmp_path, decomp_dir, monkeypatch):
    import shutil

    from fe_maker.project import Project

    decomp = tmp_path / "decomp"
    shutil.copytree(decomp_dir, decomp)
    layout_dir = decomp / "graphics" / "map" / "layout"
    layout_dir.mkdir(parents=True)
    assets = _make_map(layout_dir)
    rel = "graphics/map/layout/Map.mar"
    # The fixture decomp has no chapters: point the layout table at the fictional map.
    monkeypatch.setattr(maps, "layouts", lambda _d: {"Map": {"mar": rel, "chapters": [0], "assets": assets, "changes": None}})
    monkeypatch.setattr("fe_maker.decomp.gamedata.DecompData._chapter_groups", lambda _s, _c: [])
    project = Project.create(tmp_path / "p", "P", decomp_dir=decomp)
    assert project.load("maps") == {"layouts": {}, "changes": {}, "objects": {}}
    project.save("maps", {"layouts": {"Map": {"rows": [[1, 0]]}}})
    assert not (project.generate_overlay(decomp) / rel).exists()  # unchanged: nothing written
    project.save("maps", {"layouts": {"Map": {"rows": [[0, 1]]}}})
    overlay = project.generate_overlay(decomp)
    assert (overlay / rel).read_bytes() == struct.pack("<2H", 0, 1 << 5)
    assert not (overlay / rel).with_suffix(".json").exists()  # same size


def test_render_new_group():
    from fe_maker.decomp import units

    unit = {"slot": None, "character": "0x80", "class": "CLASS_FIGHTER", "level": 3, "autolevel": True, "side": "enemy",
            "x": 5, "y": 6, "endX": 5, "endY": 6, "items": ["ITEM_AXE_IRON"], "ai": [0, 0, 0, 0]}
    text = units.render_new_group("UnitDef_FEM_2_0", [unit])
    assert text.startswith("\nCONST_DATA struct UnitDefinition UnitDef_FEM_2_0[] = {")
    assert ".classIndex = CLASS_FIGHTER," in text and ".allegiance = FACTION_ID_RED," in text
    assert ".xPosition = 5," in text and ".yPosition = 6," in text and ".autolevel = 1," in text
    assert text.rstrip().endswith("{ 0 },\n};")


def _decomp_with_two_palettes(tmp_path, decomp_dir):
    """The fixture decomp plus two fictional chapters on the same tileset, with two palettes."""
    import shutil

    decomp = tmp_path / "decomp"
    shutil.copytree(decomp_dir, decomp)
    folder = decomp / "graphics" / "map"
    folder.mkdir(parents=True)
    _make_map(folder)
    shutil.copy(folder / "MapPalette1.pal", folder / "MapPalette2.pal")
    shutil.copy(folder / "Map.mar", folder / "Map2.mar")
    symbols = ["ObjectType1", "MapPalette1", "MapPalette2", "TileConfiguration1", "Map", "Map2"]
    (decomp / "data" / "data_8B363C.s").write_text(
        "gChapterDataAssetTable:\n\t.word 0\n" + "".join(f"\t.word {s}\n" for s in symbols), encoding="utf-8")
    (decomp / "data" / "const_data_chapter_maps.s").write_text(
        "".join(f'{s}:\n\t.incbin "graphics/map/{s}.bin.lz"\n' for s in symbols), encoding="utf-8")
    (decomp / "src" / "data").mkdir(parents=True, exist_ok=True)
    chapters = [{"internalName": f"C{i}", "map": {"obj1Id": 1, "obj2Id": 0, "paletteId": 2 + i, "tileConfigId": 4,
                                                  "mainLayerId": 5 + i, "changeLayerId": 0}} for i in range(2)]
    (decomp / maps.CHAPTER_SETTINGS_FILE).write_text(json.dumps({"chapters": chapters}, indent=2), encoding="utf-8")
    return decomp


def test_another_palette_of_the_tileset(tmp_path, decomp_dir):
    """Ticket 16: a map takes another palette its tileset has in the game."""
    from fe_maker.decomp.gamedata import DecompData, GameDataError

    decomp = _decomp_with_two_palettes(tmp_path, decomp_dir)
    assets = maps.layouts(decomp)["Map"]["assets"]
    assert [p["id"] for p in maps.palette_choices(decomp, assets)] == ["MapPalette1", "MapPalette2"]
    assert maps.palette_symbol(decomp, assets.palette) == "MapPalette1"
    assert maps.with_palette(decomp, assets, "MapPalette2").palette.name == "MapPalette2.pal"
    assert maps.with_palette(decomp, assets, "Unknown") == assets
    d = DecompData(decomp)
    d.apply_maps({"palettes": {"Map": "MapPalette2"}})
    settings = json.loads(d.changed_files()[maps.CHAPTER_SETTINGS_FILE])
    assert [c["map"]["paletteId"] for c in settings["chapters"]] == [3, 3]
    with pytest.raises(GameDataError):
        DecompData(decomp).apply_maps({"palettes": {"Map": "TileConfiguration1"}})


def test_palette_problem(tmp_path, decomp_dir):
    from fe_maker.validation import _validate_maps

    decomp = _decomp_with_two_palettes(tmp_path, decomp_dir)
    problems = []
    _validate_maps(problems, {"palettes": {"Map": "MapPalette2"}}, decomp)
    assert not problems
    _validate_maps(problems, {"palettes": {"Map": "Map2"}}, decomp)
    assert [p.code for p in problems] == ["paletteNotForTileset"]


def test_item_drop_is_written_only_when_it_changes(tmp_path, decomp_dir):
    from fe_maker.project import Project

    project = Project.create(tmp_path / "p", "P", decomp_dir=decomp_dir)
    game = units.read_unit_groups(decomp_dir)["UnitDef_TestChapter"].units
    assert not game[0]["itemDrop"]
    legacy = {k: v for k, v in game[1].items() if k != "itemDrop"}    # saved before this option
    project.save("chapters", {"unitGroups": {"UnitDef_TestChapter": [{**game[0], "itemDrop": True}, legacy, game[2]]}})
    overlay = project.generate_overlay(decomp_dir)
    assert (overlay / "src" / "events_udefs.c").read_text(encoding="utf-8").count(".itemDrop = 1,") == 1
    assert units.read_unit_groups(overlay)["UnitDef_TestChapter"].units[0]["itemDrop"] is True


def test_average_stats():
    from fe_maker.decomp.averagestats import average_stats

    cls = {"abilities": [], "bases": {"hp": 18, "pow": 5}, "maxes": {"hp": 60, "pow": 7},
           "growths": {"hp": 100, "pow": 50}}
    hero = {"level": 2, "bases": {"hp": 2, "lck": 3}, "growths": {"hp": 50, "pow": 100, "lck": 40}}
    fixed = average_stats(hero, cls, 9, False, "enemy", 1)
    assert fixed == {"hp": 20, "pow": 5, "skl": 0, "spd": 0, "def": 0, "res": 0, "lck": 3}
    average = average_stats(hero, cls, 6, True, "player", 1)    # 4 levels with the sheet's growths, capped by the class
    assert (average["hp"], average["pow"], average["lck"]) == (22, 7, 5)
    generic = average_stats(None, cls, 5, True, "enemy", 0x80)    # 4 levels with the class's growths
    assert (generic["hp"], generic["pow"]) == (22, 7)
    promoted = average_stats(None, {**cls, "abilities": ["promoted"]}, 1, True, "enemy", 0x80)
    assert promoted["hp"] == 27
    assert average_stats(None, {**cls, "abilities": ["boss"]}, 5, True, "enemy", 0x80)["hp"] == 18


def test_map_with_a_change():
    change = {"x": 1, "y": 1, "rows": [[7, 8], [9, 9]]}
    assert maps.with_change((3, 2, [0] * 6), change) == (3, 2, [0, 0, 0, 0, 7, 8])


def test_imported_icon_takes_a_free_place_in_the_palette():
    import io

    import pytest
    from PIL import Image

    from fe_maker import ferepo
    from fe_maker.decomp import itemicons
    from fe_maker.decomp.mapsprites import MapSpriteError

    assert itemicons.free_slots(["a/item_icon_sword.png", "a/item_icon_unused_0.png"]) == [1]
    palette = [(0, 0, 0), (255, 0, 0), (0, 255, 0)] + [(9, 9, 9)] * 13
    picture = Image.new("RGBA", (16, 16), (0, 0, 0, 0))
    picture.putpixel((3, 4), (250, 10, 10, 255))
    data = io.BytesIO()
    picture.save(data, format="PNG")
    converted = Image.open(io.BytesIO(itemicons.convert(data.getvalue(), palette)))
    assert converted.mode == "P" and converted.getpixel((3, 4)) == 1 and converted.getpixel((0, 0)) == 0
    data = io.BytesIO()
    Image.new("RGBA", (32, 16)).save(data, format="PNG")
    with pytest.raises(MapSpriteError):
        itemicons.convert(data.getvalue(), palette)
    entry = ferepo.describe(ferepo.URL_PREFIX + "main/Item%20Icons/Axes/%7B2WB,%20Hanakko%7D%20Dark%20Axe.png")
    assert (entry["name"], entry["authors"]) == ("Dark Axe", ["2WB", "Hanakko"])


def test_weather_battle_background_and_camera_of_a_chapter():
    from fe_maker.decomp.gamedata import _set_chapter_look

    settings = [{"initialWeather": "fine", "battleTileSet": 0, "initialPosX": 1, "initialPosY": 0}, {}]
    _set_chapter_look(settings, {"weather": {"0": "rain", "1": "acid"}, "battleBg": {"0": 99}, "camera": {"0": [5, 70]}})
    assert settings == [{"initialWeather": "rain", "battleTileSet": 0x14, "initialPosX": 5, "initialPosY": 63}, {}]
