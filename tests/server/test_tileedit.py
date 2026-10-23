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
