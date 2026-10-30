"""Where units can go and strike on a chapter's map (chapter editor: the picked unit's range, the enemies' danger zone).

Like the game's movement map, without the other units in the way: it shows what a unit could reach on empty ground.
"""

from __future__ import annotations

import heapq

NOT_WEAPONS = {"item", "staff", "dance"}


def movement(terrain: list[list[int]], costs: list[int], mov: int, x: int, y: int) -> set[tuple[int, int]]:
    """Cells within `mov` points of (x, y); a cost below 1 is impassable."""
    height, width = len(terrain), len(terrain[0]) if terrain else 0
    if not (0 <= x < width and 0 <= y < height):
        return set()
    best = {(x, y): 0}
    todo = [(0, x, y)]
    while todo:
        spent, cx, cy = heapq.heappop(todo)
        if spent > best[(cx, cy)]:
            continue
        for nx, ny in ((cx + 1, cy), (cx - 1, cy), (cx, cy + 1), (cx, cy - 1)):
            if 0 <= nx < width and 0 <= ny < height:
                t = terrain[ny][nx]
                cost = costs[t] if t < len(costs) else -1
                total = spent + cost
                if cost > 0 and total <= mov and total < best.get((nx, ny), mov + 1):
                    best[(nx, ny)] = total
                    heapq.heappush(todo, (total, nx, ny))
    return set(best)


def strikes(cells: set[tuple[int, int]], ranges: list[tuple[int, int]], width: int, height: int) -> set[tuple[int, int]]:
    """Cells a weapon of `ranges` (min, max) reaches from `cells`."""
    found = set()
    for low, high in set(ranges):
        offsets = [(dx, dy) for dx in range(-high, high + 1) for dy in range(-high, high + 1)
                   if low <= abs(dx) + abs(dy) <= high]
        for x, y in cells:
            found |= {(x + dx, y + dy) for dx, dy in offsets if 0 <= x + dx < width and 0 <= y + dy < height}
    return found


def weapon_ranges(item_ids: list[str], items: list[dict]) -> list[tuple[int, int]]:
    by_id = {it["id"]: it for it in items}
    found = []
    for item in item_ids:
        it = by_id.get(item)
        if it is not None and it.get("weaponType") not in NOT_WEAPONS and it["range"]["max"] > 0:
            found.append((max(it["range"]["min"], 1), it["range"]["max"]))
    return found
