"""Whole buildings taken from the game's own maps (ticket 41): villages, houses, shops, castles, forts...

A building is a group of touching cells whose terrain is part of a building (village gate, house,
shop, castle gate, roof, walls of a castle, church...), found on every original map drawn with the
same tile sheet. Its bounding box becomes a block the map editor paints in one click. The same
building drawn several times counts once, the most used first.
"""

from __future__ import annotations

from collections import Counter
from functools import lru_cache
from pathlib import Path

from . import maps

# include/constants/terrains.h: the key cell of a building, by what it is called in the editor.
KEY_TERRAINS = {0x03: "village", 0x04: "village", 0x05: "house", 0x06: "armory", 0x07: "vendor", 0x08: "arena",
                0x30: "arena", 0x0B: "castle", 0x1F: "castle", 0x0A: "fort", 0x24: "church", 0x38: "inn", 0x23: "gate"}
# Other cells a building is made of: roofs, the castle walls (TILE_2C), village and house walls (TILE_2E).
PART_TERRAINS = {0x22, 0x2C, 0x2E}
MAX_SIDE = 10
MAX_PIECES = 60


def _components(width: int, height: int, cells: list[int], terrain: bytes) -> list[set[tuple[int, int]]]:
    building = set(KEY_TERRAINS) | PART_TERRAINS

    def kind(x: int, y: int) -> int | None:
        m = cells[y * width + x]
        return terrain[m] if m < len(terrain) else None

    seen: set[tuple[int, int]] = set()
    found = []
    for y in range(height):
        for x in range(width):
            if (x, y) in seen or kind(x, y) not in building:
                continue
            group, stack = set(), [(x, y)]
            while stack:
                c = stack.pop()
                if c in seen or not (0 <= c[0] < width and 0 <= c[1] < height) or kind(*c) not in building:
                    continue
                seen.add(c)
                group.add(c)
                stack += [(c[0] + 1, c[1]), (c[0] - 1, c[1]), (c[0], c[1] + 1), (c[0], c[1] - 1)]
            found.append(group)
    return found


def one_building(terrains: list[int]) -> bool:
    """A single key cell with its roof or walls: two villages side by side or a row of shops are not offered
    (ticket 41), nor a key cell alone (a cut piece, like a fort one tile wide)."""
    return sum(t in KEY_TERRAINS for t in terrains) == 1 and any(t in PART_TERRAINS for t in terrains)


@lru_cache(maxsize=16)
def pieces(decomp_dir: Path, config: Path) -> tuple[dict, ...]:
    """Buildings of the original maps drawn with this tile config: {"kind", "rows", "uses", "maps"}."""
    _metatiles, terrain = maps.read_config(config)
    counts: Counter = Counter()
    kinds: dict[tuple, str] = {}
    where: dict[tuple, list[str]] = {}
    for layout_id, layout in sorted(maps.layouts(decomp_dir).items()):
        if layout["assets"].config != config:
            continue
        width, height, cells = maps.read_layout(layout["assets"].layout)
        for group in _components(width, height, cells, terrain):
            keys = [KEY_TERRAINS[terrain[cells[y * width + x]]] for x, y in group
                    if terrain[cells[y * width + x]] in KEY_TERRAINS]
            if not one_building([terrain[cells[y * width + x]] for x, y in group]):
                continue
            xs, ys = [x for x, _ in group], [y for _, y in group]
            x0, y0, x1, y1 = min(xs), min(ys), max(xs), max(ys)
            if x1 - x0 + 1 > MAX_SIDE or y1 - y0 + 1 > MAX_SIDE:
                continue
            rows = tuple(tuple(cells[y * width + x] for x in range(x0, x1 + 1)) for y in range(y0, y1 + 1))
            counts[rows] += 1
            kinds[rows] = Counter(keys).most_common(1)[0][0]
            where.setdefault(rows, [])
            if layout_id not in where[rows]:
                where[rows].append(layout_id)
    order = sorted(counts, key=lambda r: (list(KEY_TERRAINS.values()).index(kinds[r]), -counts[r], len(r) * len(r[0])))
    return tuple({"kind": kinds[r], "rows": [list(row) for row in r], "uses": counts[r], "maps": where[r][:3]}
                 for r in order[:MAX_PIECES])
