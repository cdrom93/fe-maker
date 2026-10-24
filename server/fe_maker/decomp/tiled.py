"""Maps to and from Tiled (https://www.mapeditor.org), ticket 25.

FE Maker writes a .tmx the way the FE community lays out its Tiled maps (tmx2ea, from the FE8 Skill
System, CC0): a layer named "Main" holds the map, one more layer per map change, with an "ID"
property; a change covers the cells its layer fills (its rectangle is computed from them). A tile's
gid is its metatile number + 1 (gid 0: no tile), with the tileset sheet as the Tiled tileset: one
16 x 16 tile per metatile, 32 columns (maps.TILESET_COLUMNS).

Reading accepts what Tiled writes: CSV or base64 layers (uncompressed, zlib or gzip), the flip bits
of gids (ignored: the game cannot flip a metatile), any firstgid, "Main" as layer name or property.
"""

from __future__ import annotations

import base64
import gzip
import struct
import xml.etree.ElementTree as ET
import zlib

TILE = 16
FLIP_BITS = 0xE0000000
MAX_METATILES = 1024


class TiledError(Exception):
    pass


def _esc(text: str) -> str:
    return text.replace("&", "&amp;").replace('"', "&quot;").replace("<", "&lt;")


def _csv(rows: list[list[int]]) -> str:
    return ",\n".join(",".join(str(gid) for gid in row) for row in rows)


def write_tmx(rows: list[list[int]], changes: list[dict], image: str, image_size: tuple[int, int], columns: int,
              properties: dict[str, str] | None = None) -> str:
    """A .tmx of the map and its changes; `image`: the tileset sheet next to it."""
    height, width = len(rows), len(rows[0])
    count = columns * (image_size[1] // TILE)
    props = "".join(f'   <property name="{_esc(k)}" value="{_esc(str(v))}"/>\n' for k, v in (properties or {}).items())
    out = [
        '<?xml version="1.0" encoding="UTF-8"?>\n',
        f'<map version="1.10" tiledversion="1.10.2" orientation="orthogonal" renderorder="right-down" '
        f'width="{width}" height="{height}" tilewidth="{TILE}" tileheight="{TILE}" infinite="0" '
        f'nextlayerid="{len(changes) + 2}" nextobjectid="1">\n',
        f' <tileset firstgid="1" name="tiles" tilewidth="{TILE}" tileheight="{TILE}" tilecount="{count}" columns="{columns}">\n',
        f'  <image source="{_esc(image)}" width="{image_size[0]}" height="{image_size[1]}"/>\n',
        ' </tileset>\n',
        f' <layer id="1" name="Main" width="{width}" height="{height}">\n',
        f'  <properties>\n   <property name="Main" value=""/>\n{props}  </properties>\n',
        f'  <data encoding="csv">\n{_csv([[m + 1 for m in row] for row in rows])}\n  </data>\n',
        ' </layer>\n',
    ]
    for k, c in enumerate(changes):
        grid = [[0] * width for _ in range(height)]
        for j, row in enumerate(c["rows"]):
            for i, m in enumerate(row):
                if 0 <= c["y"] + j < height and 0 <= c["x"] + i < width:
                    grid[c["y"] + j][c["x"] + i] = m + 1
        out += [
            f' <layer id="{k + 2}" name="Change {c["id"]}" width="{width}" height="{height}">\n',
            f'  <properties>\n   <property name="ID" type="int" value="{c["id"]}"/>\n  </properties>\n',
            f'  <data encoding="csv">\n{_csv(grid)}\n  </data>\n',
            ' </layer>\n',
        ]
    out.append('</map>\n')
    return "".join(out)


def _layer_gids(layer: ET.Element, width: int, height: int) -> list[int]:
    data = layer.find("data")
    if data is None:
        raise TiledError("layerWithoutData")
    encoding = data.get("encoding")
    if encoding == "csv":
        gids = [int(v) for v in (data.text or "").replace("\n", "").split(",") if v.strip()]
    elif encoding == "base64":
        raw = base64.b64decode((data.text or "").strip())
        compression = data.get("compression")
        if compression == "zlib":
            raw = zlib.decompress(raw)
        elif compression == "gzip":
            raw = gzip.decompress(raw)
        elif compression:
            raise TiledError("unsupportedCompression")
        gids = list(struct.unpack(f"<{len(raw) // 4}I", raw))
    elif encoding is None:
        gids = [int(t.get("gid", "0")) for t in data.findall("tile")]
    else:
        raise TiledError("unsupportedEncoding")
    if len(gids) != width * height:
        raise TiledError("badLayerSize")
    return [g & ~FLIP_BITS for g in gids]


def _props(element: ET.Element) -> dict[str, str]:
    props = element.find("properties")
    return {p.get("name", ""): p.get("value", p.text or "") for p in props.findall("property")} if props is not None else {}


def read_tmx(text: str) -> dict:
    """The map and changes of a .tmx: {"rows", "changes": [{"id", "x", "y", "w", "h", "rows"}], "properties"}.
    A change's cells its layer leaves empty keep the map's tile."""
    try:
        root = ET.fromstring(text)
    except ET.ParseError as e:
        raise TiledError("notTmx") from e
    if root.tag != "map":
        raise TiledError("notTmx")
    if root.get("orientation", "orthogonal") != "orthogonal" or root.get("infinite") == "1":
        raise TiledError("unsupportedMap")
    width, height = int(root.get("width", "0")), int(root.get("height", "0"))
    tileset = root.find("tileset")
    first = int(tileset.get("firstgid", "1")) if tileset is not None else 1
    layers = root.findall("layer")
    if not layers:
        raise TiledError("noLayer")
    main = next((la for la in layers if la.get("name") == "Main" or "Main" in _props(la)), layers[0])

    def metatile(gid: int) -> int:
        m = gid - first
        if not 0 <= m < MAX_METATILES:
            raise TiledError("tileOutOfRange")
        return m

    gids = _layer_gids(main, width, height)
    rows = [[metatile(g) if g else 0 for g in gids[y * width:(y + 1) * width]] for y in range(height)]
    changes, used = [], set()
    for layer in layers:
        if layer is main:
            continue
        cells = _layer_gids(layer, width, height)
        filled = [(i % width, i // width) for i, g in enumerate(cells) if g]
        if not filled:
            continue
        x0, x1 = min(x for x, _ in filled), max(x for x, _ in filled)
        y0, y1 = min(y for _, y in filled), max(y for _, y in filled)
        props = _props(layer)
        try:
            cid = int(props["ID"], 0) if "ID" in props else None
        except ValueError:
            cid = None
        tiles = [[metatile(cells[y * width + x]) if cells[y * width + x] else rows[y][x] for x in range(x0, x1 + 1)]
                 for y in range(y0, y1 + 1)]
        changes.append({"id": cid, "x": x0, "y": y0, "w": x1 - x0 + 1, "h": y1 - y0 + 1, "rows": tiles,
                        "name": layer.get("name", "")})
    # Changes without an ID get the first free ones (tmx2ea does the same, from 1)
    used = {c["id"] for c in changes if c["id"] is not None}
    free = (n for n in range(1, 256) if n not in used)
    for c in changes:
        if c["id"] is None:
            c["id"] = next(free)
    return {"rows": rows, "changes": changes, "properties": _props(main)}
