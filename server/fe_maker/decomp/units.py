"""Units of each chapter: unit groups (struct UnitDefinition arrays) and where they come from.

A chapter's event group (struct ChapterEventGroup, src/events/*-eventinfo.h) names the
player units and the opening scene script. Scripts load unit groups with LOAD1/LOAD2/
LOAD3; turn-based events (TURN(...) entries) load reinforcements. Unit groups and the
paths units walk on entry (struct REDA arrays) are in src/events_udefs.c and
src/events/*-eventudefs.h.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

from .cparse import _blank_comments, _match_brace, _split_top_level, parse_fields

UNIT_SOURCES = ["src/events_udefs.c", "src/events/*-eventudefs.h"]
EVENT_SOURCES = ["src/events/*.h", "src/events_script.c", "src/events_info.c"]

ALLEGIANCE = {"FACTION_ID_BLUE": "player", "FACTION_ID_GREEN": "ally", "FACTION_ID_RED": "enemy",
              "0": "player", "1": "ally", "2": "enemy"}


@dataclass
class UnitGroup:
    name: str
    file: str
    units: list[dict] = field(default_factory=list)


def _sources(decomp_dir: Path, patterns: list[str]) -> dict[str, str]:
    out = {}
    for pattern in patterns:
        for path in sorted(decomp_dir.glob(pattern)):
            out[path.relative_to(decomp_dir).as_posix()] = _blank_comments(path.read_text(encoding="utf-8"))
    return out


def _arrays(source: str, struct_name: str) -> list[tuple[str, str]]:
    """(name, body) of every `struct <struct_name> NAME[] = { ... };`."""
    result = []
    for m in re.finditer(rf"struct\s+{struct_name}\s+(\w+)\s*\[\s*\w*\s*\]\s*=\s*\{{", source):
        open_pos = m.end() - 1
        close = _match_brace(source, open_pos)
        result.append((m.group(1), source[open_pos + 1: close]))
    return result


def _entries(body: str) -> list[str]:
    """Brace blocks of an array body: '{ .x = 1, }' -> '.x = 1,'."""
    return [part.strip()[1:-1] for part in _split_top_level(body) if part.strip().startswith("{")]


def _int(value: str | None, default: int = 0) -> int:
    try:
        return int(value.strip().rstrip("uU"), 0) if value else default
    except ValueError:
        return default


@lru_cache(maxsize=4)
def read_unit_groups(decomp_dir: Path) -> dict[str, UnitGroup]:
    sources = _sources(decomp_dir, UNIT_SOURCES)
    redas: dict[str, list[tuple[int, int]]] = {}
    for source in sources.values():
        for name, body in _arrays(source, "REDA"):
            points = []
            for entry in _entries(body):
                f = parse_fields(entry) if entry.strip() else {}
                points.append((_int(f.get("x")), _int(f.get("y"))))
            redas[name] = points

    groups: dict[str, UnitGroup] = {}
    for rel, source in sources.items():
        for name, body in _arrays(source, "UnitDefinition"):
            group = UnitGroup(name, rel)
            for entry in _entries(body):
                if not entry.strip() or re.fullmatch(r"\s*0\s*", entry):
                    continue  # terminator { 0 }
                try:
                    f = parse_fields(entry)
                except Exception:
                    continue
                x, y = _int(f.get("xPosition")), _int(f.get("yPosition"))
                path_name = f.get("redas", "").lstrip("&").strip()
                path = redas.get(path_name, [])
                items = [i.strip() for i in f.get("items", "{}").strip("{} ").split(",") if i.strip() not in ("", "0")]
                group.units.append({
                    "character": f.get("charIndex", "0"),
                    "class": f.get("classIndex", "0"),
                    "level": _int(f.get("level")),
                    "autolevel": f.get("autolevel", "0") not in ("0", "FALSE", "false"),
                    "side": ALLEGIANCE.get(f.get("allegiance", "0"), "player"),
                    "x": x,
                    "y": y,
                    # Units entering with a movement path end their move here.
                    "endX": path[-1][0] if path else x,
                    "endY": path[-1][1] if path else y,
                    "items": items,
                    "ai": f.get("ai", ""),
                    # Entry path stored as a raw address (not decompiled): the unit cannot be moved yet.
                    "fixedPath": bool(path_name) and not re.fullmatch(r"\w+", path_name),
                })
            groups[name] = group
    return groups


# ---------- writing unit groups ----------

SIDE_TO_C = {"player": "FACTION_ID_BLUE", "ally": "FACTION_ID_GREEN", "enemy": "FACTION_ID_RED"}


class UnitEditError(Exception):
    pass


def _array_body_span(clean: str, struct_name: str, name: str) -> tuple[int, int] | None:
    m = re.search(rf"struct\s+{struct_name}\s+{re.escape(name)}\s*\[\s*\w*\s*\]\s*=\s*\{{", clean)
    if not m:
        return None
    open_pos = m.end() - 1
    return open_pos + 1, _match_brace(clean, open_pos)


def _entry_spans(clean: str, start: int, end: int) -> list[tuple[int, int]]:
    """Spans of the top-level { ... } entries in an array body (terminators excluded)."""
    spans, pos = [], start
    while True:
        open_pos = clean.find("{", pos, end)
        if open_pos < 0:
            break
        close = _match_brace(clean, open_pos)
        if clean[open_pos + 1: close].strip() not in ("", "0"):
            spans.append((open_pos, close + 1))
        pos = close + 1
    return spans


def _render_unit(fields: dict[str, str], indent: str) -> str:
    inner = indent + "    "
    lines = ["{"]
    for key, value in fields.items():
        lines.append(f"{inner}.{key} = {value},")
    lines.append(f"{indent}}}")
    return "\n".join(lines)


def apply_unit_groups(sources: dict[str, str], edits: dict[str, list[dict]]) -> dict[str, str]:
    """Write edited unit groups into the decomp sources (decomp-relative path -> text).

    Only the edited fields of the edited units are re-rendered. A unit that enters
    the map along a path keeps its path; its battle position is the path's end point.
    """
    sources = dict(sources)
    for name, new_units in edits.items():
        rel = next((r for r, s in sources.items() if _array_body_span(_blank_comments(s), "UnitDefinition", name)), None)
        if rel is None:
            raise UnitEditError(f"Unit group {name} not found")
        source = sources[rel]
        clean = _blank_comments(source)
        start, end = _array_body_span(clean, "UnitDefinition", name)
        spans = _entry_spans(clean, start, end)
        if len(spans) != len(new_units):
            raise UnitEditError(f"{name}: adding or removing units is not supported yet")
        reda_moves: list[tuple[str, int, int]] = []
        out, last = [], 0
        for (s, e), unit in zip(spans, new_units):
            fields = parse_fields(clean[s + 1: e - 1])
            original = dict(fields)
            # Only touch a field whose meaning changes, so unedited units stay byte-identical.
            if fields.get("charIndex", "0") != unit["character"]:
                fields["charIndex"] = unit["character"]
            if fields.get("classIndex", "0") != unit["class"]:
                fields["classIndex"] = unit["class"]
            if _int(fields.get("level")) != int(unit["level"]):
                fields["level"] = str(int(unit["level"]))
            if "side" in unit and ALLEGIANCE.get(fields.get("allegiance", "0"), "player") != unit["side"]:
                fields["allegiance"] = SIDE_TO_C[unit["side"]]
            items = [i for i in unit.get("items", []) if i]
            if len(items) > 4:
                raise UnitEditError(f"{name}: at most 4 items per unit")
            old_items = [i.strip() for i in fields.get("items", "{}").strip("{} ").split(",") if i.strip() not in ("", "0")]
            if items != old_items:
                fields["items"] = "{ " + " ".join(f"{i}," for i in items) + " }" if items else "{ }"
            path = fields.get("redas", "").lstrip("&").strip()
            if path and not re.fullmatch(r"\w+", path):
                # Path given as a raw address (not decompiled yet): it cannot be edited.
                if (_int(fields.get("xPosition")), _int(fields.get("yPosition"))) != (int(unit["endX"]), int(unit["endY"])):
                    raise UnitEditError(f"{name}: this unit follows a movement path that cannot be edited yet")
            elif path:
                reda_moves.append((path, int(unit["endX"]), int(unit["endY"])))
            elif (_int(fields.get("xPosition")), _int(fields.get("yPosition"))) != (int(unit["endX"]), int(unit["endY"])):
                fields["xPosition"], fields["yPosition"] = str(int(unit["endX"])), str(int(unit["endY"]))
            if fields != original:
                line_start = clean.rfind("\n", 0, s) + 1
                indent = clean[line_start:s] if clean[line_start:s].strip() == "" else "    "
                out.append(source[last:s])
                out.append(_render_unit(fields, indent))
                last = e
        out.append(source[last:])
        sources[rel] = "".join(out)
        for path, x, y in reda_moves:
            sources = _move_path_end(sources, path, x, y)
    return sources



def _move_path_end(sources: dict[str, str], path: str, x: int, y: int) -> dict[str, str]:
    for rel, source in sources.items():
        clean = _blank_comments(source)
        span = _array_body_span(clean, "REDA", path)
        if span is None:
            continue
        spans = _entry_spans(clean, *span)
        if not spans:
            return sources
        s, e = spans[-1]
        fields = parse_fields(clean[s + 1: e - 1])
        if _int(fields.get("x")) == x and _int(fields.get("y")) == y:
            return sources
        fields["x"], fields["y"] = str(x), str(y)
        line_start = clean.rfind("\n", 0, s) + 1
        indent = clean[line_start:s] if clean[line_start:s].strip() == "" else "    "
        new = dict(sources)
        new[rel] = source[:s] + _render_unit(fields, indent) + source[e:]
        return new
    raise UnitEditError(f"Movement path {path} not found")


@lru_cache(maxsize=4)
def _event_sources(decomp_dir: Path) -> dict[str, str]:
    return _sources(decomp_dir, EVENT_SOURCES)


def _find_block(decomp_dir: Path, pattern: str) -> str | None:
    for source in _event_sources(decomp_dir).values():
        m = re.search(pattern, source)
        if m:
            open_pos = m.end() - 1
            return source[open_pos + 1: _match_brace(source, open_pos)]
    return None


def _script_loads(decomp_dir: Path, script: str, depth: int = 0) -> list[str]:
    """Unit groups loaded by an event script (following CALL to other scripts)."""
    body = _find_block(decomp_dir, rf"EventListScr\s+{re.escape(script)}\s*\[\s*\]\s*=\s*\{{")
    if body is None or depth > 3:
        return []
    groups = re.findall(r"\bLOAD\d?\s*\(\s*\w+\s*,\s*(\w+)\s*\)", body)
    for called in re.findall(r"\bCALL\s*\(\s*(\w+)\s*\)", body):
        groups += _script_loads(decomp_dir, called, depth + 1)
    return groups


def chapter_unit_groups(decomp_dir: Path, event_group_symbol: str) -> list[dict]:
    """[{name, origin, turn?}] for a chapter, in loading order."""
    info = _find_block(decomp_dir, rf"struct\s+ChapterEventGroup\s+{re.escape(event_group_symbol)}\s*=\s*\{{")
    if info is None:
        return []
    fields = parse_fields(info)
    result: list[dict] = []
    seen = set()

    def add(name: str, origin: str, turn: int | None = None):
        # A group may be loaded several times (players again in the opening scene): keep the first.
        if name and name not in ("NULL", "0") and name not in seen:
            seen.add(name)
            result.append({"name": name, "origin": origin, "turn": turn})

    add(fields.get("playerUnitsInNormal", ""), "players")
    for name in _script_loads(decomp_dir, fields.get("beginningSceneEvents", "")):
        add(name, "opening")
    turns = _find_block(decomp_dir, rf"EventListScr\s+{re.escape(fields.get('turnBasedEvents', '-'))}\s*\[\s*\]\s*=\s*\{{")
    for m in re.finditer(r"\bTURN\s*\(\s*[^,]+,\s*(\w+)\s*,\s*(\d+)\s*,", turns or ""):
        for name in _script_loads(decomp_dir, m.group(1)):
            add(name, "turn", int(m.group(2)))
    return result
