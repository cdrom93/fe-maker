import json
import struct

from PIL import Image

from fe_maker.decomp import maps, tileedit

# Fictional tileset made for the tests: tile 1 has a single lit pixel in its top-left corner.


def _tileset(tmp_path, monkeypatch, asymmetric=False):
    image = Image.new("L", (32, 8), 255)          # 4 tiles, inverted grayscale (255 = color 0)
    image.putpixel((8, 0), 255 - 17 * 5)           # tile 1, pixel (0, 0) = color 5
    if asymmetric:
        image.putpixel((9, 0), 255 - 17 * 7)       # pixel (1, 0) = color 7: no flip gives its quarter turn
    image.save(tmp_path / "ObjectType1.png")
    (tmp_path / "MapPalette1.pal").write_text("JASC-PAL\n0100\n16\n" + "0 0 0\n" * 16, encoding="utf-8")
    config = bytearray(0x2400)
    # Metatile 1: tile 1 top-left, empty tile 0 elsewhere; metatiles 2+ are copies of metatile 0 (free).
    struct.pack_into("<4H", config, 8, 1, 0, 0, 0)
    config[0x2000 + 1] = 0x0C
    (tmp_path / "TileConfiguration1.bin").write_bytes(bytes(config))
    (tmp_path / "Map.mar").write_bytes(struct.pack("<2H", 1 << 5, 0))
    (tmp_path / "Map.json").write_text(json.dumps({"id": "Map", "width": 2, "height": 1}), encoding="utf-8")
    assets = maps.MapAssets([tmp_path / "ObjectType1.png"], tmp_path / "MapPalette1.pal",
                            tmp_path / "TileConfiguration1.bin", tmp_path / "Map.mar")
    monkeypatch.setattr(maps, "layouts", lambda _d: {"Map": {"mar": "Map.mar", "chapters": [0], "assets": assets,
                                                            "changes": None}})
    return tileedit.Tileset(tmp_path, "Map", None)


def _lit(ts, m):
    """(x, y) of the lit pixel of metatile m."""
    for k, entry in enumerate(ts.metatiles[m]):
        px = ts._entry_pixels(entry)
        if 5 in px:
            i = px.index(5)
            return (k % 2) * 8 + i % 8, (k // 2) * 8 + i // 8
    return None


def test_mirrors_only_add_metatiles(tmp_path, monkeypatch):
    ts = _tileset(tmp_path, monkeypatch)
    assert _lit(ts, 1) == (0, 0)
    [[h]] = ts.transform_block([[1]], "h")
    [[v]] = ts.transform_block([[1]], "v")
    [[half]] = ts.transform_block([[1]], "180")
    assert (_lit(ts, h), _lit(ts, v), _lit(ts, half)) == ((15, 0), (0, 15), (15, 15))
    assert ts.edits["tiles"] == {}                      # the same tiles, flipped
    assert ts.terrain[h] == 0x0C                        # the terrain goes with the picture
    assert ts.transform_block([[1]], "h") == [[h]]      # done once


def test_quarter_turns_add_tiles(tmp_path, monkeypatch):
    ts = _tileset(tmp_path, monkeypatch)
    [[cw]] = ts.transform_block([[1]], "cw")
    [[ccw]] = ts.transform_block([[1]], "ccw")
    assert _lit(ts, cw) == (15, 0) and _lit(ts, ccw) == (0, 15)
    # A corner pixel turned is a flipped corner pixel: the existing tile is reused.
    assert ts.edits["tiles"] == {}


def test_turned_block_and_files(tmp_path, monkeypatch):
    ts = _tileset(tmp_path, monkeypatch, asymmetric=True)
    rows = ts.transform_block([[1, 0]], "cw")
    assert len(rows) == 2 and len(rows[0]) == 1 and rows[1][0] == 0   # 2 x 1 block -> 1 x 2
    assert len(ts.edits["tiles"]) == 1
    files = ts.files()
    assert set(files) == {"TileConfiguration1.bin", "ObjectType1.png"}
    (tmp_path / "out.png").write_bytes(files["ObjectType1.png"])
    written = Image.open(tmp_path / "out.png")
    assert written.mode == "L" and written.size == (32, 8)
    new = int(next(iter(ts.edits["tiles"])))
    assert list(maps._tiles([tmp_path / "out.png"])[new].tobytes()) == ts.edits["tiles"][str(new)]
    assert maps._tiles([tmp_path / "out.png"])[1].tobytes() == maps._tiles(ts.assets.tileset)[1].tobytes()


def test_no_edit_writes_nothing(tmp_path, monkeypatch):
    assert _tileset(tmp_path, monkeypatch).files() == {}


def test_copy_with_another_terrain(tmp_path, monkeypatch):
    ts = _tileset(tmp_path, monkeypatch)
    [[copy]] = ts.with_terrain([[1]], 0x15)
    assert copy != 1 and ts.metatiles[copy] == ts.metatiles[1] and ts.terrain[copy] == 0x15
    assert ts.terrain[1] == 0x0C                       # the original tile keeps its terrain
    assert ts.with_terrain([[1]], 0x15) == [[copy]]    # done once
    assert ts.with_terrain([[1]], 0x0C) == [[1]]       # same terrain: the tile itself


def test_existing_turned_metatile_is_reused(tmp_path, monkeypatch):
    """Ticket 18: the tileset already has the mirrored picture, drawn with another tile."""
    _tileset(tmp_path, monkeypatch)
    image = Image.open(tmp_path / "ObjectType1.png")
    image.putpixel((16 + 7, 0), 255 - 17 * 5)       # tile 2, pixel (7, 0) = color 5
    image.save(tmp_path / "ObjectType1.png")
    config = bytearray((tmp_path / "TileConfiguration1.bin").read_bytes())
    struct.pack_into("<4H", config, 16, 0, 2, 0, 0)  # metatile 2: tile 2 top-right
    config[0x2000 + 2] = 0x0C
    (tmp_path / "TileConfiguration1.bin").write_bytes(bytes(config))
    ts = tileedit.Tileset(tmp_path, "Map", None)
    assert ts.transform_block([[1]], "h") == [[2]] and ts.edits["metatiles"] == {}
    # Another terrain is another metatile.
    ts.terrain[2] = 0x01
    ts._pictures = None
    assert ts.transform_block([[1]], "h") != [[2]]


def test_similar_tile_of_the_game_is_offered(tmp_path, monkeypatch):
    """Ticket 18: the game draws its turned tiles again (light from the same side): a near copy is offered."""
    _tileset(tmp_path, monkeypatch)
    image = Image.open(tmp_path / "ObjectType1.png")
    image.putpixel((16 + 7, 0), 255 - 17 * 5)       # tile 2: the mirrored pixel, and one more
    image.putpixel((16 + 6, 0), 255 - 17 * 6)
    image.save(tmp_path / "ObjectType1.png")
    config = bytearray((tmp_path / "TileConfiguration1.bin").read_bytes())
    struct.pack_into("<4H", config, 16, 0, 2, 0, 0)
    config[0x2000 + 2] = 0x0C
    (tmp_path / "TileConfiguration1.bin").write_bytes(bytes(config))
    ts = tileedit.Tileset(tmp_path, "Map", None)
    [[h]] = ts.transform_block([[1]], "h")
    assert h != 2 and str(h) in ts.edits["metatiles"]
    assert ts.similar_original(h) == 2
    assert ts.similar_original(1) is None          # only added metatiles get an offer


def _config(path, terrains):
    """A fictional tile config: metatile m drawn with tile m everywhere (all different), its terrain."""
    config = bytearray(0x2400)
    for m, t in enumerate(terrains):
        struct.pack_into("<4H", config, 8 * m, m, m, m, m)
        config[0x2000 + m] = t
    for m in range(len(terrains), 0x400):      # unused slots: copies of one filler metatile
        struct.pack_into("<4H", config, 8 * m, 0x3FF, 0x3FF, 0x3FF, 0x3FF)
    path.write_bytes(bytes(config))


def test_map_drawn_with_another_tile_sheet(tmp_path, monkeypatch):
    plains, forest, village = 0x01, 0x0C, 0x03
    _config(tmp_path / "A.bin", [plains, forest, village])
    _config(tmp_path / "B.bin", [plains, plains, forest, forest])
    (tmp_path / "Other.mar").write_bytes(b"".join(struct.pack("<H", m << 5) for m in [1, 1, 1, 2, 3, 3]))
    (tmp_path / "Other.json").write_text(json.dumps({"id": "Other", "width": 6, "height": 1}), encoding="utf-8")
    a = maps.MapAssets([tmp_path / "A.png"], tmp_path / "A.pal", tmp_path / "A.bin", tmp_path / "Map.mar")
    b = maps.MapAssets([tmp_path / "B.png"], tmp_path / "B.pal", tmp_path / "B.bin", tmp_path / "Other.mar")
    monkeypatch.setattr(maps, "layouts", lambda _d: {
        "Map": {"chapters": [0], "assets": a, "changes": None}, "Other": {"chapters": [1], "assets": b, "changes": None}})
    terrain_a = maps.read_config(a.config)[1]
    # Each tile becomes sheet B's most used tile of its terrain; B has no village: its most used tile.
    grids, missing = maps.convert_by_terrain(tmp_path, terrain_a, b, [[[0, 1, 2]], [[1], [0]]])
    assert grids == [[[1, 3, 1]], [[3], [1]]] and missing == [village]
