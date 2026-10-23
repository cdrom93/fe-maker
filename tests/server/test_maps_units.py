import io
import json
import struct

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
    monkeypatch.setattr(maps, "layouts", lambda _d: {"Map": {"mar": rel, "chapters": [0], "assets": assets}})
    project = Project.create(tmp_path / "p", "P", decomp_dir=decomp)
    assert project.load("maps") == {"layouts": {}}
    project.save("maps", {"layouts": {"Map": {"rows": [[1, 0]]}}})
    assert not (project.generate_overlay(decomp) / rel).exists()  # unchanged: nothing written
    project.save("maps", {"layouts": {"Map": {"rows": [[0, 1]]}}})
    overlay = project.generate_overlay(decomp)
    assert (overlay / rel).read_bytes() == struct.pack("<2H", 0, 1 << 5)
    assert not (overlay / rel).with_suffix(".json").exists()  # same size
