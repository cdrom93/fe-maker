"""Map objects: villages, houses, chests, doors, cracked walls and snags painted on a map.

The engine finds everything from the map itself:
- the terrain of a cell says what it is (village gate, full chest, door, cracked wall...);
- visiting a village, opening a chest or a door, breaking a wall or a snag applies the map
  change whose rectangle holds the cell (GetMapChangeIdAt in src/bmtrick.c, the last one wins);
- villages, houses, chests and doors also need an entry in the chapter's location events
  (Village, House, Chest, ChestMoney, Door in src/events/*-eventinfo.h); cracked walls and
  snags become obstacles by themselves (InitMapObstacles).

So a newly painted object only needs a map change with its "after" tiles (open chest, closed
village, floor, rubble) and, for the first four kinds, a location event. The "after" tiles are
learned from the original game's changes, for each tileset: the whole change when the new object
matches one (walls also fix the shadows around them), else tile by tile.

Objects already on the original map keep their original behavior (some are only decoration);
the project can still set what a chest holds or what a village says (data/maps.json "objects").
"""

from __future__ import annotations

import re
from collections import Counter
from functools import lru_cache
from pathlib import Path

from . import dialogues, fonts, maps

# Terrain id -> object kind (include/constants/terrains.h).
KINDS = {0x03: "village", 0x05: "house", 0x06: "armory", 0x07: "vendor", 0x1E: "door", 0x21: "chest",
         0x1B: "wall", 0x33: "snag"}
CHANGE_KINDS = ("village", "door", "chest", "wall", "snag")   # change their tiles when used
EVENT_KINDS = ("village", "house", "armory", "vendor", "door", "chest")   # need a location event
SHOP_KINDS = ("armory", "vendor")
MAX_SHOP_ITEMS = 20

DEFAULTS = {
    "chest": {"item": "ITEM_VULNERARY"},
    "village": {"item": "ITEM_VULNERARY", "face": "FID_VillagerOldMan",
                "text": "Thank you for coming to our village.\nPlease, take this with you."},
    "house": {"face": "FID_VillagerWoman", "text": "Be careful out there.\nThe roads are not safe anymore."},
    "door": {},
    "armory": {"items": ["ITEM_SWORD_IRON", "ITEM_LANCE_IRON", "ITEM_AXE_IRON", "ITEM_BOW_IRON"]},
    "vendor": {"items": ["ITEM_VULNERARY", "ITEM_ANIMA_FIRE", "ITEM_LIGHT_LIGHTNING", "ITEM_STAFF_HEAL"]},
}
# Villager portraits for generated dialogues: text code -> portrait id (texts/textdefs.txt).
FACES = {"FID_VillagerOldMan": 0x59, "FID_VillagerOldWoman": 0x5F, "FID_VillagerMan1": 0x58, "FID_VillagerMan2": 0x5A,
         "FID_VillagerMan3": 0x5B, "FID_VillagerMan4": 0x5C, "FID_VillagerYoungMan": 0x5D, "FID_VillagerYoungBoy": 0x5E,
         "FID_VillagerWoman": 0x60, "FID_VillagerGirlBrownHair": 0x61, "FID_VillagerGirlBlackHair": 0x62,
         "FID_VillagerGirlYoung": 0x63}
BG_HOUSE, BG_NORMAL_VILLAGE = 0x00, 0x02  # include/constants/backgrounds.h
FIRST_FLAG = 70     # temporary event flags (1-100 are cleared each chapter); the game uses up to 28
LAST_FLAG = 100


def detect(rows: list[list[int]], terrain: bytes) -> list[dict]:
    """Objects of a map: {"kind", "x", "y" (first cell), "cells": [[x, y]...]}.
    Doors are whole doors (touching door cells); stacked cracked walls are one wall (the engine
    puts one obstacle on the topmost cell); the other objects are single cells."""
    height, width = len(rows), len(rows[0]) if rows else 0

    def kind(x: int, y: int) -> str | None:
        m = rows[y][x]
        return KINDS.get(terrain[m]) if m < len(terrain) else None

    seen: set[tuple[int, int]] = set()
    objects = []
    for y in range(height):
        for x in range(width):
            k = kind(x, y)
            if not k or (x, y) in seen:
                continue
            cells = [(x, y)]
            seen.add((x, y))
            if k == "door":
                stack = [(x, y)]
                while stack:
                    cx, cy = stack.pop()
                    for nx, ny in ((cx + 1, cy), (cx - 1, cy), (cx, cy + 1), (cx, cy - 1)):
                        if 0 <= nx < width and 0 <= ny < height and (nx, ny) not in seen and kind(nx, ny) == "door":
                            seen.add((nx, ny))
                            cells.append((nx, ny))
                            stack.append((nx, ny))
            elif k == "wall":
                ny = y + 1
                while ny < height and kind(x, ny) == "wall":
                    seen.add((x, ny))
                    cells.append((x, ny))
                    ny += 1
            cells.sort(key=lambda c: (c[1], c[0]))
            objects.append({"kind": k, "x": cells[0][0], "y": cells[0][1], "cells": [list(c) for c in cells]})
    return objects


# ---------- learning the "after" tiles from the original game ----------

def _shape(cells) -> frozenset[tuple[int, int]]:
    """Cells relative to the first one (top row first)."""
    first = min(cells, key=lambda c: (c[1], c[0]))
    return frozenset((x - first[0], y - first[1]) for x, y in cells)


@lru_cache(maxsize=4)
def rules(decomp_dir: Path) -> dict[str, dict]:
    """Tile config file name -> {"templates": [...], "tiles": {metatile: metatile after}, "terrain", "pixels"}.

    A template is an original change made for a single object: its object cells ("shape",
    relative to the first one), the offset of that first cell in the rectangle, and the tiles
    before and after. "tiles" maps each object tile to its most frequent state after; tiles no
    original change uses get the state of the same picture in another tileset, when there is one."""
    result: dict[str, dict] = {}
    for layout in maps.layouts(decomp_dir).values():
        assets = layout["assets"]
        if assets.config.name not in result:
            _metatiles, terrain = maps.read_config(assets.config)
            result[assets.config.name] = {"templates": Counter(), "counts": {}, "terrain": terrain,
                                          "pixels": maps.metatile_pixels(assets)}
        if not layout["changes"]:
            continue
        width, height, cells = maps.read_layout(assets.layout)
        entry = result[assets.config.name]
        terrain = entry["terrain"]
        for c in maps.read_changes(decomp_dir, layout["changes"]):
            if c["x"] + c["w"] > width or c["y"] + c["h"] > height:
                continue
            before = [[cells[(c["y"] + j) * width + c["x"] + i] for i in range(c["w"])] for j in range(c["h"])]
            after = c["rows"]
            used = {}
            for j in range(c["h"]):
                for i in range(c["w"]):
                    b, a = before[j][i], after[j][i]
                    k = KINDS.get(terrain[b]) if b < len(terrain) else None
                    if k in CHANGE_KINDS and a != b and terrain[a] != terrain[b]:
                        used.setdefault(k, []).append((i, j))
            if len(used) != 1:
                continue  # story changes (roofs, bridges, ruined villages) or several objects at once
            kind, object_cells = next(iter(used.items()))
            if kind == "village" and terrain[after[object_cells[0][1]][object_cells[0][0]]] != 0x04:
                continue  # villages destroyed by brigands, not visited
            first = min(object_cells, key=lambda p: (p[1], p[0]))
            key = (kind, _shape(object_cells), first, tuple(map(tuple, before)), tuple(map(tuple, after)))
            entry["templates"][key] += 1
            for i, j in object_cells:
                entry["counts"].setdefault(before[j][i], Counter())[after[j][i]] += 1
    for entry in result.values():
        entry["templates"] = [
            {"kind": k[0], "shape": k[1], "first": k[2], "before": k[3], "after": k[4], "uses": n}
            for k, n in entry["templates"].most_common()]
        entry["tiles"] = {m: counts.most_common(1)[0][0] for m, counts in entry.pop("counts").items()}
    # The same picture in another tileset: its state after, if this tileset has that picture too.
    by_pixels: dict[bytes, Counter] = {}
    for entry in result.values():
        for before, after in entry["tiles"].items():
            by_pixels.setdefault(entry["pixels"][before], Counter())[entry["pixels"][after]] += 1
    for entry in result.values():
        terrain, pixels = entry["terrain"], entry["pixels"]
        index = {}
        for m in range(len(pixels) - 1, -1, -1):
            index[pixels[m], terrain[m]] = m  # first metatile with this picture and terrain
        for m, t in enumerate(terrain):
            if KINDS.get(t) in CHANGE_KINDS and m not in entry["tiles"] and pixels[m] in by_pixels:
                for after_pixels, _n in by_pixels[pixels[m]].most_common():
                    found = next((index[after_pixels, at] for at in range(256)
                                  if at != t and (after_pixels, at) in index), None)
                    if found is not None:
                        entry["tiles"][m] = found
                        break
    return result


# Terrain an object gets once used (most frequent in the original changes).
USED_TERRAIN = {"chest": (0x20,), "village": (0x04,), "door": (0x17, 0x02, 0x01), "wall": (0x17, 0x02, 0x01, 0x1C),
                "snag": (0x01, 0x02, 0x17, 0x1C)}
SIMILAR_KINDS = ("chest", "village")  # used state looks like the tile (open chest, closed gate)


def _guess_tile(m: int, kind: str, rows: list[list[int]], x: int, y: int, rule: dict) -> int | None:
    """Used state of a tile no original change shows: the most similar tile of the used terrain
    (chests, villages), or the ground next to it (doors, walls, snags)."""
    terrain, pixels = rule["terrain"], rule["pixels"]
    targets = USED_TERRAIN[kind]
    if kind in SIMILAR_KINDS:
        candidates = [c for c in range(len(terrain)) if terrain[c] in targets]
        if not candidates:
            return None
        return max(candidates, key=lambda c: sum(a == b for a, b in zip(pixels[c], pixels[m])))
    for t in targets:
        for nx, ny in ((x, y + 1), (x, y - 1), (x - 1, y), (x + 1, y)):
            if 0 <= ny < len(rows) and 0 <= nx < len(rows[0]) and terrain[rows[ny][nx]] == t:
                return rows[ny][nx]
    return None


def after_change(obj: dict, rows: list[list[int]], rule: dict | None) -> dict | None:
    """Map change {x, y, w, h, rows} putting the object in its used state, or None if unknown."""
    if not rule:
        return None
    rule = {"templates": [], "tiles": {}, **rule}
    height, width = len(rows), len(rows[0])
    shape = _shape(obj["cells"])
    best = None
    for t in rule["templates"]:
        if t["kind"] != obj["kind"] or t["shape"] != shape:
            continue
        x0, y0 = obj["x"] - t["first"][0], obj["y"] - t["first"][1]
        h, w = len(t["before"]), len(t["before"][0])
        if x0 < 0 or y0 < 0 or x0 + w > width or y0 + h > height:
            continue
        changed = [(i, j) for j in range(h) for i in range(w) if t["before"][j][i] != t["after"][j][i]]
        if any(rows[y0 + j][x0 + i] != t["before"][j][i] for i, j in changed):
            continue
        score = (len(changed), t["uses"])
        if best is None or score > best[0]:
            # Cells the original change left alone keep the painted tile.
            after = [[t["after"][j][i] if (i, j) in changed else rows[y0 + j][x0 + i] for i in range(w)] for j in range(h)]
            best = (score, {"x": x0, "y": y0, "w": w, "h": h, "rows": after})
    if best:
        return best[1]
    # Tile by tile, over the object's cells only.
    xs = [c[0] for c in obj["cells"]]
    ys = [c[1] for c in obj["cells"]]
    x0, y0, w, h = min(xs), min(ys), max(xs) - min(xs) + 1, max(ys) - min(ys) + 1
    after = [[rows[y0 + j][x0 + i] for i in range(w)] for j in range(h)]
    for x, y in obj["cells"]:
        m = rule["tiles"].get(rows[y][x])
        if m is None:
            m = _guess_tile(rows[y][x], obj["kind"], rows, x, y, rule)
        if m is None:
            return None
        after[y - y0][x - x0] = m
    return {"x": x0, "y": y0, "w": w, "h": h, "rows": after}


# ---------- objects of a map, as the project sees them ----------

def _covered(obj: dict, changes: list[dict], terrain: bytes) -> int | None:
    """Id of the change the engine applies when the object is used (the last one holding its cell),
    if that change puts the object in its used state. A village painted inside the rectangle of
    another village's change would else close (or ruin) the wrong village. A change the project
    marks "manual" (its tiles drawn by hand for the object) always counts."""
    found = None
    x, y = obj["x"], obj["y"]
    for c in changes:
        if c["x"] <= x < c["x"] + c["w"] and c["y"] <= y < c["y"] + c["h"]:
            found = c
    if found is None:
        return None
    if found.get("manual"):
        return found["id"]   # drawn by hand for an object (ticket 19): it counts whatever its tiles
    try:
        after = found["rows"][y - found["y"]][x - found["x"]]
    except (IndexError, KeyError):
        return None
    return found["id"] if after < len(terrain) and terrain[after] in USED_TERRAIN[obj["kind"]] else None


def map_objects(decomp_dir: Path, layout_id: str, rows: list[list[int]], changes: list[dict] | None,
                settings: dict | None = None, terrain: bytes | None = None,
                assets: maps.MapAssets | None = None) -> list[dict]:
    """Objects of a layout with what the build will do for them.

    Each object: kind, x, y, cells, "new" (not on the original map), "change" (id of the change
    used, None if none), "auto" (the change FE Maker adds, for new objects without one),
    "noAfter" (new object whose used state is unknown for this tileset). `terrain` replaces the
    tileset's terrains when the project added metatiles (tileedit.py); `assets`: the layout drawn
    with another tile sheet (ticket 21), whose objects are new where the terrain changed."""
    layout = maps.layouts(decomp_dir)[layout_id]
    original = layout["assets"]
    assets = assets or original
    if terrain is None:
        _metatiles, terrain = maps.read_config(assets.config)
    width, height, cells = maps.read_layout(original.layout)
    rule = rules(decomp_dir).get(assets.config.name)
    original_terrain = maps.read_config(original.config)[1] if assets.config != original.config else None

    def changed(x: int, y: int) -> bool:
        if x >= width or y >= height:
            return True
        if original_terrain is None:
            return cells[y * width + x] != rows[y][x]
        before, now = cells[y * width + x], rows[y][x]
        return (original_terrain[before] if before < len(original_terrain) else None) != \
            (terrain[now] if now < len(terrain) else None)

    settings = settings or {}
    objects = detect(rows, terrain)
    changes = list(changes or [])
    next_id = max((c["id"] for c in changes), default=-1) + 1
    for obj in objects:
        obj["new"] = any(changed(x, y) for x, y in obj["cells"])
        obj["change"] = _covered(obj, changes, terrain) if obj["kind"] in CHANGE_KINDS else None
        obj["auto"] = None
        obj["noAfter"] = False
        off = settings.get(f"{obj['x']},{obj['y']}", {}).get("off", False)
        if obj["kind"] in CHANGE_KINDS and obj["new"] and obj["change"] is None and not off:
            change = after_change(obj, rows, rule)
            if change is None:
                obj["noAfter"] = True
            elif layout["changes"] and next_id <= maps.MAX_CHANGE_ID:
                obj["auto"] = {"id": next_id, **change}
                obj["change"] = next_id
                next_id += 1
    return objects


# ---------- location events ----------

_EVENT_RE = re.compile(
    r"^[ \t]*(Chest|ChestMoney|Door_|Door|Village|House|Armory|Vendor|SecretShop)"
    r"\s*\(([^()\n]*(?:\([^()\n]*\)[^()\n]*)*)\)[ \t]*\r?\n", re.M)


def _args(text: str) -> list[str]:
    out, depth, cur = [], 0, ""
    for ch in text:
        if ch == "," and depth == 0:
            out.append(cur.strip())
            cur = ""
            continue
        depth += ch == "("
        depth -= ch == ")"
        cur += ch
    out.append(cur.strip())
    return out


def _int(value: str) -> int | None:
    try:
        return int(value, 0)
    except ValueError:
        return None


def read_location_events(body: str) -> list[dict]:
    """Village, house, chest and door events of a location list: kind, x, y, span in `body`, and
    what they give (chest item or gold, script of a village or house)."""
    out = []
    for m in _EVENT_RE.finditer(body):
        macro, args = m.group(1), _args(m.group(2))
        event = {"span": (m.start(), m.end()), "macro": macro}
        if macro in ("Chest", "ChestMoney") and len(args) == 3:
            event.update(kind="chest", x=_int(args[1]), y=_int(args[2]))
            if macro == "Chest":
                event["item"] = args[0]
            else:
                event["gold"] = _int(args[0])
        elif macro in ("Door", "Door_") and len(args) >= 2:
            event.update(kind="door", x=_int(args[0]), y=_int(args[1]))
        elif macro in ("Village", "House") and len(args) == 4:
            event.update(kind=macro.lower(), x=_int(args[2]), y=_int(args[3]), script=args[1])
        elif macro in ("Armory", "Vendor", "SecretShop") and len(args) == 3:
            event.update(kind="secret" if macro == "SecretShop" else macro.lower(), x=_int(args[1]), y=_int(args[2]),
                         shop=args[0])
        else:
            continue
        if event["x"] is not None and event["y"] is not None:
            out.append(event)
    return out


def event_matches(event_kind: str, object_kind: str | None) -> bool:
    """A secret shop (member card) can stand on an armory or a vendor."""
    return event_kind == object_kind or (event_kind == "secret" and object_kind in SHOP_KINDS)


SHOP_LIST_FILE = "src/events_shoplist.c"


def read_shop_lists(source: str) -> dict[str, list[str]]:
    """Shop item lists of the game (src/events_shoplist.c): name -> items."""
    out = {}
    for name, body in re.findall(r"u16\s+(\w+)\s*\[\s*\]\s*=\s*\{(.*?)\};", source, re.S):
        out[name] = [w for w in re.findall(r"\b(ITEM_\w+|0x[0-9A-Fa-f]+|\d+)\b", body) if w not in ("ITEM_NONE", "0")]
    return out


def shop_list(name: str, items: list[str]) -> str:
    body = "".join(f"    {item},\n" for item in items[:MAX_SHOP_ITEMS])
    return f"CONST_DATA u16 {name}[] = {{\n{body}    ITEM_NONE,\n}};\n\n"


def dialogue_message(face: str, text: str, widths: dict[int, int] | None = None) -> str:
    """Message body of a villager talking: their portrait, then the text cut to the box's width with
    the game's font (`widths`, see fonts.py), two lines per box."""
    widths = widths or dict(fonts._FALLBACK)
    lines = []
    for paragraph in text.strip().split("\n"):
        lines += dialogues.wrap_line(paragraph.strip(), widths, dialogues.TALK_WIDTH)
    boxes = ["\n".join(lines[k:k + dialogues.BOX_LINES]) for k in range(0, len(lines), dialogues.BOX_LINES)]
    return dialogues.render([{"kind": "face", "pos": "MidLeft", "face": face},
                             {"kind": "say", "pos": "MidLeft", "text": "\n\n".join(boxes), "wait": True}])


def village_script(name: str, message: int, item: str | None, gold: int | None, house: bool = False) -> str:
    # Backgrounds by number (include/constants/backgrounds.h is not included by every eventinfo file).
    background = BG_HOUSE if house else BG_NORMAL_VILLAGE
    lines = ["MUSI", f"Text_BG(0x{background:X}, 0x{message:X})", "MUNO",
             "CALL(EventScr_RemoveBGIfNeeded)"]
    if gold:
        lines += [f"SVAL(EVT_SLOT_3, {int(gold)})", "GIVEITEMTOMAIN(CHAR_EVT_PLAYER_LEADER)"]
    elif item:
        lines += [f"SVAL(EVT_SLOT_3, {item})", "GIVEITEMTO(CHAR_EVT_ACTIVE_UNIT)"]
    lines += ["NoFade", "ENDA"]
    body = "".join(f"    {line}\n" for line in lines)
    return f"CONST_DATA EventListScr {name}[] = {{\n{body}}};\n\n"


def used_flags(sources: list[str]) -> set[int]:
    return {int(n) for s in sources for n in re.findall(r"EVFLAG_TMP\(\s*(\d+)\s*\)", s)}
