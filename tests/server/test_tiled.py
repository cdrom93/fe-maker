import base64
import struct
import zlib

import pytest

from fe_maker.decomp import tiled


def test_map_and_changes_round_trip():
    rows = [[0, 1, 2, 3], [4, 5, 6, 7], [8, 9, 10, 11]]
    changes = [{"id": 2, "x": 1, "y": 1, "w": 2, "h": 1, "rows": [[40, 41]]}]
    text = tiled.write_tmx(rows, changes, "map-tiles.png", (512, 1024), 32, {"TileConfig": "TileConfiguration1"})
    back = tiled.read_tmx(text)
    assert back["rows"] == rows
    assert [{k: c[k] for k in ("id", "x", "y", "w", "h", "rows")} for c in back["changes"]] == changes
    assert back["properties"]["TileConfig"] == "TileConfiguration1"


def _tmx(layers: str, width=3, height=2, firstgid=1) -> str:
    return (f'<map orientation="orthogonal" width="{width}" height="{height}" tilewidth="16" tileheight="16">'
            f'<tileset firstgid="{firstgid}" name="t"/>{layers}</map>')


def test_tiled_encodings_flips_and_changes_without_id():
    gids = [11, 12, 13, 14, 15, 16 | 0x80000000]   # last one flipped: the flip is dropped
    raw = base64.b64encode(zlib.compress(struct.pack("<6I", *gids))).decode()
    change = '<layer name="Door"><data encoding="csv">0,0,0,\n0,30,31</data></layer>'
    text = _tmx(f'<layer name="Main"><data encoding="base64" compression="zlib">{raw}</data></layer>{change}', firstgid=11)
    back = tiled.read_tmx(text)
    assert back["rows"] == [[0, 1, 2], [3, 4, 5]]
    # the change covers the cells its layer fills, and gets the first free id
    assert back["changes"][0] | {"name": ""} == {"id": 1, "x": 1, "y": 1, "w": 2, "h": 1, "rows": [[19, 20]], "name": ""}


def test_changes_keep_the_map_where_their_layer_is_empty():
    change = '<layer name="C"><properties><property name="ID" value="0x5"/></properties>' \
             '<data encoding="csv">7,0,8,\n0,0,0</data></layer>'
    back = tiled.read_tmx(_tmx(f'<layer name="Main"><data encoding="csv">1,2,3,4,5,6</data></layer>{change}'))
    assert back["changes"][0]["id"] == 5
    assert back["changes"][0]["rows"] == [[6, 1, 7]]


@pytest.mark.parametrize("text, code", [
    ("not xml", "notTmx"),
    (_tmx('<layer name="Main"><data encoding="csv">1,2</data></layer>'), "badLayerSize"),
    (_tmx('<layer name="Main"><data encoding="csv">1,2,3,4,5,99999</data></layer>'), "tileOutOfRange"),
])
def test_bad_files(text, code):
    with pytest.raises(tiled.TiledError, match=code):
        tiled.read_tmx(text)
