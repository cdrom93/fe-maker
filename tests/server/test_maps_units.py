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
