"""Terrain brushes whose tiles join by themselves, learned from the game's own maps.

For one tile sheet, every original map drawn with it tells two things: which tile a terrain uses for a given
shape of its neighbors (a river's bend, a cliff's end), and which tiles really touch each other. Painting a
terrain then picks, for the cells painted and those around them, the tiles that fit best: nothing here knows
what a river is.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

from . import maps, pieces

# Clockwise from the top; the even ones are the four sides.
AROUND = ((0, -1), (1, -1), (1, 0), (1, 1), (0, 1), (-1, 1), (-1, 0), (-1, -1))
SIDES = 0b01010101
# Terrains that are objects rather than ground: bridges, doors, chests, throne, ballistae, pillars, stairs, snags.
NOT_GROUND = (set(pieces.KEY_TERRAINS) | pieces.PART_TERRAINS
              | {0x00, 0x13, 0x14, 0x1C, 0x1D, 0x1E, 0x1F, 0x20, 0x21, 0x27, 0x28, 0x29, 0x2D, 0x33, 0x34, 0x39})
MIN_CELLS = 10
SWEEPS = 3
KEEP_BONUS = 0.4


@dataclass
class Model:
    terrain: bytes
    tiles: dict[int, Counter] = field(default_factory=lambda: defaultdict(Counter))    # terrain -> tile
    shape: dict[tuple, Counter] = field(default_factory=lambda: defaultdict(Counter))  # (terrain, 8 neighbors) -> tile
    sides: dict[tuple, Counter] = field(default_factory=lambda: defaultdict(Counter))  # (terrain, 4 neighbors) -> tile
    right: Counter = field(default_factory=Counter)                                    # (left tile, right tile)
    below: Counter = field(default_factory=Counter)                                    # (upper tile, lower tile)

    def kind(self, tile: int) -> int:
        return self.terrain[tile] if tile < len(self.terrain) else 0


def _key(model: Model, rows: list[list[int]], x: int, y: int) -> int:
    """One bit per neighbor of the same terrain; past the edge of the map counts as the same."""
    kind = model.kind(rows[y][x])
    key = 0
    for bit, (dx, dy) in enumerate(AROUND):
        nx, ny = x + dx, y + dy
        if not (0 <= ny < len(rows) and 0 <= nx < len(rows[ny])) or model.kind(rows[ny][nx]) == kind:
            key |= 1 << bit
    return key


def study(model: Model, rows: list[list[int]]) -> None:
    for y, row in enumerate(rows):
        for x, tile in enumerate(row):
            kind, key = model.kind(tile), _key(model, rows, x, y)
            model.tiles[kind][tile] += 1
            model.shape[kind, key][tile] += 1
            model.sides[kind, key & SIDES][tile] += 1
            if x + 1 < len(row):
                model.right[tile, row[x + 1]] += 1
            if y + 1 < len(rows):
                model.below[tile, rows[y + 1][x]] += 1


@lru_cache(maxsize=16)
def learn(decomp_dir: Path, config: Path) -> Model:
    _metatiles, terrain = maps.read_config(config)
    model = Model(terrain)
    for layout in maps.layouts(decomp_dir).values():
        if layout["assets"].config != config:
            continue
        width, height, cells = maps.read_layout(layout["assets"].layout)
        study(model, [cells[y * width:(y + 1) * width] for y in range(height)])
    return model


def brushes(model: Model) -> list[dict]:
    """The ground terrains of this tile sheet, the most used first: {"terrain", "tile"}."""
    grounds = [(sum(c.values()), kind) for kind, c in model.tiles.items() if kind not in NOT_GROUND]
    return [{"terrain": kind, "tile": model.tiles[kind].most_common(1)[0][0]}
            for cells, kind in sorted(grounds, reverse=True) if cells >= MIN_CELLS]


def _touches(model: Model, rows: list[list[int]], x: int, y: int, tile: int) -> float:
    """How well a tile fits the four tiles around it: pairs the game draws add up, pairs it never draws count against."""
    score = 0.0
    pairs = ((-1, 0, model.right, False), (1, 0, model.right, True), (0, -1, model.below, False), (0, 1, model.below, True))
    for dx, dy, table, after in pairs:
        nx, ny = x + dx, y + dy
        if 0 <= ny < len(rows) and 0 <= nx < len(rows[ny]):
            score += 1.0 if table[(tile, rows[ny][nx]) if after else (rows[ny][nx], tile)] else -1.0
    return score


def _choose(model: Model, rows: list[list[int]], x: int, y: int, keep: bool) -> int:
    current = rows[y][x]
    kind, key = model.kind(current), _key(model, rows, x, y)
    shape, sides = model.shape.get((kind, key), Counter()), model.sides.get((kind, key & SIDES), Counter())
    candidates = set(shape) | set(sides) | ({current} if keep else set())
    if not candidates:
        candidates = {tile for tile, _ in model.tiles[kind].most_common(30)} or {current}
    shapes, side_total = sum(shape.values()) or 1, sum(sides.values()) or 1

    def score(tile: int) -> float:
        fit = 3 * shape[tile] / shapes + 1.5 * sides[tile] / side_total + _touches(model, rows, x, y, tile)
        return fit + (KEEP_BONUS if keep and tile == current else 0)

    return max(sorted(candidates), key=score)


def paint(model: Model, rows: list[list[int]], cells: list[tuple[int, int]]) -> list[list[int]]:
    """Rows where the painted cells, which already hold their terrain, and the cells around them are joined."""
    out = [list(row) for row in rows]
    painted = {(x, y) for x, y in cells if 0 <= y < len(out) and 0 <= x < len(out[y])}
    around = {(x + dx, y + dy) for x, y in painted for dx, dy in AROUND} - painted
    around = {(x, y) for x, y in around if 0 <= y < len(out) and 0 <= x < len(out[y])}
    for _ in range(SWEEPS):
        changed = False
        for keep, group in ((False, painted), (True, around)):
            for x, y in sorted(group, key=lambda c: (c[1], c[0])):
                tile = _choose(model, out, x, y, keep)
                changed = changed or tile != out[y][x]
                out[y][x] = tile
        if not changed:
            break
    return out
