import json
import struct

from fe_maker.decomp import maps

# Fictional test data written for FE Maker. Not taken from the game.
SOURCE = """    .section .data

\t.global TestChanges_change_0
TestChanges_change_0:
\t.incbin "graphics/map/TestChanges_change_0.bin"

\t.align 2, 0
\t.global TestChanges
TestChanges:
\t.include "src/data/map/change/TestChanges.inc"
"""


def _decomp(tmp_path):
    (tmp_path / "data").mkdir()
    (tmp_path / "data" / "data_map_change.s").write_text(SOURCE, encoding="utf-8")
    (tmp_path / "src/data/map/change").mkdir(parents=True)
    changes = {"name": "TestChanges", "changes": [{"id": 0, "x": 1, "y": 2, "w": 2, "h": 1, "tiles": "TestChanges_change_0"}]}
    (tmp_path / "src/data/map/change/TestChanges.json").write_text(json.dumps(changes, indent=2), encoding="utf-8")
    (tmp_path / "graphics/map").mkdir(parents=True)
    (tmp_path / "graphics/map/TestChanges_change_0.bin").write_bytes(struct.pack("<2H", 7 << 2, 8 << 2))
    return tmp_path


def test_read_changes(tmp_path):
    d = _decomp(tmp_path)
    rel = maps.change_set_json(d, "TestChanges")
    assert rel == "src/data/map/change/TestChanges.json"
    assert maps.read_changes(d, rel) == [
        {"id": 0, "x": 1, "y": 2, "w": 2, "h": 1, "tiles": "TestChanges_change_0", "rows": [[7, 8]]}]


def test_unchanged_changes_write_nothing(tmp_path):
    d = _decomp(tmp_path)
    rel = maps.change_set_json(d, "TestChanges")
    files, source = maps.write_changes(d, rel, maps.read_changes(d, rel), SOURCE)
    assert files == {} and source == SOURCE


def test_edit_and_add_changes(tmp_path):
    d = _decomp(tmp_path)
    rel = maps.change_set_json(d, "TestChanges")
    changes = maps.read_changes(d, rel)
    changes[0]["rows"] = [[9, 8]]
    changes.append({"id": 1, "x": 0, "y": 0, "w": 1, "h": 1, "rows": [[3]]})
    files, source = maps.write_changes(d, rel, changes, SOURCE)
    assert files["graphics/map/TestChanges_change_0.bin"] == struct.pack("<2H", 9 << 2, 8 << 2)
    assert files["graphics/map/TestChanges_change_1.bin"] == struct.pack("<H", 3 << 2)
    assert '\t.global TestChanges_change_1\nTestChanges_change_1:\n\t.incbin "graphics/map/TestChanges_change_1.bin"' in source
    written = json.loads(files[rel])["changes"]
    assert [c["tiles"] for c in written] == ["TestChanges_change_0", "TestChanges_change_1"]
    assert "rows" not in written[0]


def test_impassable_terrain_is_reported_only_when_new(tmp_path, decomp_dir, monkeypatch):
    from fe_maker.decomp import units
    from fe_maker.decomp.gamedata import DecompData
    from fe_maker.validation import _validate_chapter_maps

    # A fictional 15 x 10 map: metatile 0 is plains (terrain 1), metatile 1 is sea (terrain 21).
    config = bytearray(0x2400)
    config[0x2000] = 1
    config[0x2001] = 21
    (tmp_path / "Config.bin").write_bytes(bytes(config))
    (tmp_path / "Map.mar").write_bytes(bytes(15 * 10 * 2))
    (tmp_path / "Map.json").write_text(json.dumps({"id": "Map", "width": 15, "height": 10}), encoding="utf-8")
    assets = maps.MapAssets([], tmp_path / "x.pal", tmp_path / "Config.bin", tmp_path / "Map.mar")
    layout = {"mar": "Map.mar", "chapters": [0], "assets": assets, "changes": None}
    monkeypatch.setattr(maps, "layouts", lambda _d: {"Map": layout})
    groups = {0: [{"name": "UnitDef_TestChapter", "origin": "players", "turn": None}]}
    monkeypatch.setattr(units, "all_chapter_unit_groups", lambda _d: groups)
    monkeypatch.setattr(maps, "movement_costs", lambda _d: {"Foot": [-1, 1] + [-1] * 63})
    d = DecompData(decomp_dir)
    classes = [{"id": c["id"], "movement": "Foot"} for c in d.export_classes()]
    hero = units.read_unit_groups(decomp_dir)["UnitDef_TestChapter"].units[0]
    rows = [[0] * 15 for _ in range(10)]

    problems = []
    _validate_chapter_maps(problems, d, {"unitGroups": {}}, {"layouts": {"Map": {"rows": rows}}}, d.export_characters(), classes)
    assert problems == []  # the map is all plains

    rows[hero["endY"]][hero["endX"]] = 1  # sea under the units (all on the same tile in the fixture)
    _validate_chapter_maps(problems, d, {"unitGroups": {}}, {"layouts": {"Map": {"rows": rows}}}, d.export_characters(), classes)
    assert {(p.code, p.params["terrain"]) for p in problems} == {("impassableTile", 21)}
    assert problems[0].id == "UnitDef_TestChapter#0"

    # A unit moved past the edge of the (unpainted) map.
    moved = [dict(u) for u in units.read_unit_groups(decomp_dir)["UnitDef_TestChapter"].units]
    moved[1]["endX"] = 20
    problems = []
    _validate_chapter_maps(problems, d, {"unitGroups": {"UnitDef_TestChapter": moved}}, {"layouts": {}},
                           d.export_characters(), classes)
    assert [(p.id, p.code) for p in problems] == [("UnitDef_TestChapter#1", "unitOutOfMap")]


def test_terrain_effects(tmp_path):
    header = tmp_path / maps.TERRAINS_HEADER
    header.parent.mkdir(parents=True)
    header.write_text("enum {\n    TERRAIN_PLAINS = 0x01,\n    TERRAIN_FOREST = 0x0C,\n    TERRAIN_COUNT = 0x41,\n};\n")
    data = tmp_path / maps.TERRAIN_DATA_FILE
    data.parent.mkdir(parents=True)
    data.write_text(
        "CONST_DATA s8 TerrainTable_MovCost_CommonT1Normal[] = {\n    [TERRAIN_PLAINS] = 1,\n    [TERRAIN_FOREST] = 2,\n};\n"
        "CONST_DATA s8 TerrainTable_MovCost_HorseT1Normal[] = {\n    [TERRAIN_PLAINS] = 1,\n    [TERRAIN_FOREST] = 3,\n};\n"
        "CONST_DATA s8 TerrainTable_Avo_Common[] = {\n    [TERRAIN_FOREST] = 20,\n};\n"
        "CONST_DATA s8 TerrainTable_Def_Common[] = {\n    [TERRAIN_FOREST] = 1,\n};\n")
    effects = maps.terrain_effects(tmp_path)
    assert (effects["avoid"][0x0C], effects["defense"][0x0C], effects["resistance"][0x0C]) == (20, 1, 0)
    assert (effects["foot"][0x0C], effects["horse"][0x0C], effects["foot"][0]) == (2, 3, -1)


def test_a_map_without_changes_gets_a_set(tmp_path):
    d = _decomp(tmp_path)
    rel, source = maps.add_change_set("OtherMap", SOURCE)
    assert rel == "src/data/map/change/OtherMapChanges.json"
    assert '\t.global OtherMapChanges\nOtherMapChanges:\n\t.include "src/data/map/change/OtherMapChanges.inc"' in source
    files, source = maps.write_changes(d, rel, [{"id": 0, "x": 0, "y": 0, "w": 1, "h": 1, "rows": [[3]]}], source)
    assert json.loads(files[rel]) == {"name": "OtherMapChanges", "changes": [
        {"id": 0, "x": 0, "y": 0, "w": 1, "h": 1, "tiles": "OtherMapChanges_change_0"}]}
    assert files["graphics/map/OtherMapChanges_change_0.bin"] == struct.pack("<H", 3 << 2)
    assert "OtherMapChanges_change_0:" in source


def test_asset_table_grows_at_its_end():
    table = "t:\n    .word 0\n\t.word A\n\t.global Next\nNext:\n.4byte B\n"
    index, source = maps.add_asset(table, "New")
    assert index == 2 and source == "t:\n    .word 0\n\t.word A\n\t.word New\n\t.global Next\nNext:\n.4byte B\n"
