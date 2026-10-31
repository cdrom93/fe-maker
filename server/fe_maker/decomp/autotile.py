"""Terrain brushes whose tiles join by themselves, learned from the game's own maps.

For one tile sheet, every original map drawn with it tells two things: which tile a terrain uses for a given
shape of its neighbors (a river's bend, a cliff's end), and which tiles really touch each other. Painting a
terrain then picks, for the cells painted and those around them, the tiles that fit best: nothing here knows
what a river is.
"""

from __future__ import annotations

import io
import random
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

from PIL import Image

from . import maps, pieces

# Clockwise from the top; the even ones are the four sides.
AROUND = ((0, -1), (1, -1), (1, 0), (1, 1), (0, 1), (-1, 1), (-1, 0), (-1, -1))
SIDES = 0b01010101
# Terrains that are objects rather than ground: bridges, doors, chests, throne, ballistae, pillars, stairs, snags.
NOT_GROUND = (set(pieces.KEY_TERRAINS) | pieces.PART_TERRAINS
              | {0x00, 0x13, 0x14, 0x1C, 0x1D, 0x1E, 0x1F, 0x20, 0x21, 0x27, 0x28, 0x29, 0x2D, 0x33, 0x34, 0x39})
MIN_CELLS = 10
SIDE_STEPS = ((1, 0), (0, 1), (-1, 0), (0, -1))    # right, below, left, above
BORDER = tuple((dx, dy) for dx in range(-2, 3) for dy in range(-2, 3))
ATTEMPTS = 3
MIN_USES = 3      # tiles the game uses once or twice are not picked for the ground around a stroke
MAX_RETRIES = 300
KEEP_KIND = 400
FILL_SHARE = 0.25     # share of a map's empty cells that "fill" turns into another ground
FILL_PATCH = 9        # largest patch of ground it lays
FILL_TRIES = 60
ROAD = 0x02           # a patch of road leads nowhere


@dataclass
class Model:
    terrain: bytes
    tiles: dict[int, Counter] = field(default_factory=lambda: defaultdict(Counter))    # terrain -> tile
    shape: dict[tuple, Counter] = field(default_factory=lambda: defaultdict(Counter))  # (terrain, 8 neighbors) -> tile
    sides: dict[tuple, Counter] = field(default_factory=lambda: defaultdict(Counter))  # (terrain, 4 neighbors) -> tile
    right: Counter = field(default_factory=Counter)                                    # (left tile, right tile)
    below: Counter = field(default_factory=Counter)                                    # (upper tile, lower tile)
    links: list = field(default_factory=list)
    borders: list = field(default_factory=list)                                        # by tile

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
        if not model.borders:
            sheet = Image.open(io.BytesIO(maps.render_tileset(layout["assets"]))).convert("RGB")
            model.borders = [_borders(sheet, tile) for tile in range(len(terrain))]
        width, height, cells = maps.read_layout(layout["assets"].layout)
        study(model, [cells[y * width:(y + 1) * width] for y in range(height)])
    return model


def brushes(model: Model) -> list[dict]:
    """The ground terrains of this tile sheet, the most used first: {"terrain", "tile"}."""
    grounds = [(sum(c.values()), kind) for kind, c in model.tiles.items() if kind not in NOT_GROUND]
    return [{"terrain": kind, "tile": model.tiles[kind].most_common(1)[0][0]}
            for cells, kind in sorted(grounds, reverse=True) if cells >= MIN_CELLS]


def _material(r: int, g: int, b: int) -> str:
    """What a piece of a tile's border looks like: only what must carry on across a join."""
    if b > r + 12 and b >= g:
        return "w"    # water
    if r + g + b < 200:
        return "d"    # dark: rock, shadow
    if g > r + 8:
        return "g"    # grass
    if r > 170 and g > 150:
        return "s"    # sand, road, bright rock
    return "e"        # earth


def _borders(sheet: Image.Image, tile: int) -> tuple[str, str, str, str]:
    """The materials along a tile's right, lower, left and upper borders, each cut in four."""
    x0, y0 = (tile % maps.TILESET_COLUMNS) * 16, (tile // maps.TILESET_COLUMNS) * 16

    def strip(cells: list[tuple[int, int]]) -> str:
        out = ""
        for piece in range(4):
            colors = [sheet.getpixel((x0 + x, y0 + y)) for x, y in cells[piece * 4:(piece + 1) * 4]]
            out += _material(*(sum(c[i] for c in colors) // 4 for i in range(3)))
        return out

    return (strip([(15, i) for i in range(16)]), strip([(i, 15) for i in range(16)]),
            strip([(0, i) for i in range(16)]), strip([(i, 0) for i in range(16)]))


def _links(model: Model) -> list[dict[int, int]]:
    """For each side (right, below, left, above), the tiles that can stand there, as a bit set: the tiles the game draws
    there, and those whose facing border shows the same materials."""
    if not model.links:
        links: list[dict[int, int]] = [defaultdict(int) for _ in SIDE_STEPS]
        for (a, b) in model.right:
            links[0][a] |= 1 << b
            links[2][b] |= 1 << a
        for (a, b) in model.below:
            links[1][a] |= 1 << b
            links[3][b] |= 1 << a
        used = [tile for tiles in model.tiles.values() for tile in tiles if tile < len(model.borders)]
        for side in range(4):
            facing: dict[str, int] = defaultdict(int)
            for tile in used:
                facing[model.borders[tile][(side + 2) % 4]] |= 1 << tile
            for tile in used:
                links[side][tile] |= facing[model.borders[tile][side]]
        model.links = links
    return model.links


def _weights(model: Model, rows: list[list[int]], x: int, y: int, wanted: int) -> dict[int, float]:
    """How much each tile suits a cell: how often the game uses it, and for this shape of neighbors above all."""
    key = _key(model, rows, x, y)
    shape, sides = model.shape.get((wanted, key), Counter()), model.sides.get((wanted, key & SIDES), Counter())
    weights = {}
    for kind, tiles in model.tiles.items():
        if kind in NOT_GROUND and kind != wanted:
            continue
        for tile, uses in tiles.items():
            weights[tile] = (uses ** 0.5) * (1 + 40 * shape[tile] + 8 * sides[tile]) * (KEEP_KIND if kind == wanted else 1)
    return weights


def _spread(model: Model, width: int, cells: dict, fixed: dict, start: list) -> bool:
    """Keep in each cell only the tiles that can touch what its neighbors may still hold. False: a cell has none left."""
    links = _links(model)
    queue = list(start)
    while queue:
        cx, cy = queue.pop()
        here = cells[cx, cy]
        for side, (dx, dy) in enumerate(SIDE_STEPS):
            spot = (cx + dx, cy + dy)
            if spot not in cells:
                continue
            allowed = 0
            rest = here
            while rest:
                low = rest & -rest
                allowed |= links[side].get(low.bit_length() - 1, 0)
                rest ^= low
            kept = cells[spot] & allowed
            if kept != cells[spot]:
                if not kept:
                    return False
                cells[spot] = kept
                queue.append(spot)
    return True


def _solve(model: Model, rows: list[list[int]], region: dict, weights: dict, rng: random.Random) -> dict | None:
    """Wave function collapse: settle the most constrained cell, spread what follows, go back on a dead end."""
    links = _links(model)
    cells = dict(region)
    start = []
    for (x, y) in cells:
        for side, (dx, dy) in enumerate(SIDE_STEPS):
            nx, ny = x + dx, y + dy
            if (nx, ny) in cells or not (0 <= ny < len(rows) and 0 <= nx < len(rows[ny])):
                continue
            # a tile outside the region stays: what it can touch on the side of this cell
            seen = links[(side + 2) % 4].get(rows[ny][nx])
            if seen is not None:
                cells[x, y] &= seen
        if not cells[x, y]:
            return None
        start.append((x, y))
    if not _spread(model, 0, cells, {}, start):
        return None
    trail = []
    tries = 0
    while True:
        open_cells = [(bin(mask).count("1"), c) for c, mask in cells.items() if mask & (mask - 1)]
        if not open_cells:
            return {c: mask.bit_length() - 1 for c, mask in cells.items()}
        _, cell = min(open_cells)
        choices = [i for i in range(cells[cell].bit_length()) if cells[cell] >> i & 1]
        scores = [weights[cell].get(i, 0.001) ** 3 for i in choices]   # mostly the best, with some variety
        tile = rng.choices(choices, scores)[0]
        trail.append((dict(cells), cell, tile))
        cells[cell] = 1 << tile
        while not _spread(model, 0, cells, {}, [cell]):
            tries += 1
            if tries > MAX_RETRIES or not trail:
                return None
            cells, cell, tile = trail.pop()
            cells[cell] &= ~(1 << tile)
            if not cells[cell]:
                if not trail:
                    return None
                cells, cell, tile = trail.pop()
                cells[cell] &= ~(1 << tile)
                if not cells[cell]:
                    return None


def paint(model: Model, rows: list[list[int]], cells: list[tuple[int, int]]) -> list[list[int]]:
    """Rows where the painted cells, which already hold their terrain, are joined with what is around them.

    Every two tiles side by side in the result are tiles the game draws side by side. The cells around may change
    tile, within their terrain first, then to any ground (a slope around a peak) when that is not enough.
    """
    return _join(model, rows, cells) or [list(row) for row in rows]


def _join(model: Model, rows: list[list[int]], cells: list[tuple[int, int]],
          kept: frozenset | set = frozenset(), only: set | None = None) -> list[list[int]] | None:
    """`paint`, leaving the `kept` cells alone and using only the terrains `only` around the cells; None when the cells
    cannot be joined."""
    out = [list(row) for row in rows]
    painted = {(x, y) for x, y in cells if 0 <= y < len(out) and 0 <= x < len(out[y])}
    # the middle of a big area keeps the tile it was filled with: only its border has something to join
    painted = {(x, y) for x, y in painted if any((x + dx, y + dy) not in painted and 0 <= y + dy < len(out)
                                                 and 0 <= x + dx < len(out[y + dy]) for dx, dy in BORDER)}
    if not painted:
        return out
    ground = 0
    of_kind: dict[int, int] = {}
    for kind, tiles in model.tiles.items():
        for tile in tiles:
            of_kind[kind] = of_kind.get(kind, 0) | 1 << tile
            if kind not in NOT_GROUND and tiles[tile] >= MIN_USES and (only is None or kind in only):
                ground |= 1 << tile
    # a patch of a fill stays away from water, even as the shore of its own terrain
    dry = sum(1 << tile for tile, sides in enumerate(model.borders) if not any("w" in side for side in sides))
    rng = random.Random(0)
    for ring, loose in ((1, False), (2, False), (1, True), (2, True), (3, True), (4, True)):
        if only is not None and ring > 2:
            return None             # the patch would spread far past its cells
        near = {(x + dx, y + dy) for x, y in painted for dx in range(-ring, ring + 1) for dy in range(-ring, ring + 1)}
        near = {(x, y) for x, y in near if 0 <= y < len(out) and 0 <= x < len(out[y])}
        kinds = {c: model.kind(out[c[1]][c[0]]) for c in near}
        weights = {(x, y): _weights(model, out, x, y, kinds[x, y]) for x, y in near}
        region = {}
        for c in near:
            if c in kept or (kinds[c] in NOT_GROUND and c not in painted):
                continue                    # buildings and the like stay as they are
            region[c] = (of_kind.get(kinds[c], 0) if c in painted or not loose else ground) or ground
            if only is not None and model.borders:
                region[c] &= dry
        for _ in range(ATTEMPTS):
            found = _solve(model, out, region, weights, rng)
            if found:
                for (x, y), tile in found.items():
                    out[y][x] = tile
                return out
    return None


def _fill_grounds(model: Model, empty: int, costs: list[int]) -> list[tuple[int, int]]:
    """Grounds to lay on `empty` cells, (terrain, how much the game uses it): those a unit on foot can cross, so that a
    filled map stays open, and that the game's maps draw next to the empty terrain."""
    meets: Counter = Counter()
    for pairs in (model.right, model.below):
        for (a, b), uses in pairs.items():
            kinds = {model.kind(a), model.kind(b)}
            if empty in kinds:
                meets[(kinds - {empty} or {empty}).pop()] += uses
    return [(kind, sum(model.tiles[kind].values())) for kind in model.tiles
            if kind not in (empty, ROAD) and kind not in NOT_GROUND and meets[kind] >= MIN_CELLS
            and kind < len(costs) and costs[kind] > 0]


def fill(model: Model, rows: list[list[int]], costs: list[int], keep: list[tuple[int, int]] = (),
         seed: int | None = None) -> list[list[int]]:
    """Rows where the empty space gets patches of other grounds, joined to what is around them.

    Empty cells are those of the map's most common terrain; everything else stays as it is, with the `keep` cells (map
    objects and changes, drawn over the rows) and a free cell around it, so that what the user built keeps its approaches.
    `costs`: the cost of each terrain on foot (-1: impassable).
    """
    out = [list(row) for row in rows]
    height, width = len(out), len(out[0]) if out else 0
    counts = Counter(model.kind(tile) for row in out for tile in row)
    if not counts:
        return out
    empty = counts.most_common(1)[0][0]
    kept = {(x, y) for y in range(height) for x in range(width) if model.kind(out[y][x]) != empty} | set(map(tuple, keep))
    grounds = _fill_grounds(model, empty, costs)
    if not grounds:
        return out
    only = {empty} | {g[0] for g in grounds}     # no water or house comes up around a patch
    rng = random.Random(seed)
    free = {(x, y) for y in range(height) for x in range(width)
            if not any((x + dx, y + dy) in kept for dx in (-1, 0, 1) for dy in (-1, 0, 1))}
    left = int((height * width - len(kept)) * FILL_SHARE)
    for _ in range(FILL_TRIES):
        if left <= 0 or not free:
            break
        kind = rng.choices([g[0] for g in grounds], [g[1] ** 0.5 for g in grounds])[0]
        patch = {rng.choice(sorted(free))}
        size = rng.randint(2, FILL_PATCH)
        while len(patch) < size:
            around = sorted({(x + dx, y + dy) for x, y in patch for dx, dy in SIDE_STEPS} & free - patch)
            if not around:
                break
            patch.add(rng.choice(around))
        tile = model.tiles[kind].most_common(1)[0][0]
        laid = [list(row) for row in out]
        for x, y in patch:
            laid[y][x] = tile
        joined = _join(model, laid, sorted(patch), kept, only)
        if joined:
            out = joined
            left -= len(patch)
        free -= {(x + dx, y + dy) for x, y in patch for dx in (-1, 0, 1) for dy in (-1, 0, 1)}
    return out
    return out
