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
AI_HELPERS = "include/EA_Standard_Library/AI_Helpers.h"
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
def ai_macros(decomp_dir: Path) -> dict[str, list[int]]:
    """AI macros of the EA standard library (DefaultAI = 0x00,0x00...), used in unit definitions."""
    path = decomp_dir / AI_HELPERS
    if not path.is_file():
        return {}
    macros = {}
    for name, value in re.findall(r"#define\s+(\w+)\s+((?:0x[0-9A-Fa-f]+|\d+)(?:\s*,\s*(?:0x[0-9A-Fa-f]+|\d+))*)",
                                  path.read_text(encoding="utf-8")):
        macros[name] = [int(v, 0) for v in value.split(",")]
    return macros


def parse_ai(raw: str, macros: dict[str, list[int]]) -> list[int]:
    """The 4 AI bytes of a unit: action, movement, target/recovery settings, flags (0x20: guard its tile)."""
    values: list[int] = []
    for token in (t.strip() for t in raw.strip().strip("{}").split(",")):
        if not token:
            continue
        if token in macros:
            values += macros[token]
        else:
            try:
                values.append(int(token.rstrip("uU"), 0))
            except ValueError:
                raise UnitEditError(f"Unknown AI value: {token}") from None
    return (values + [0, 0, 0, 0])[:4]


def is_named_character(char_index: str) -> bool:
    """Characters with a CHARACTER_ constant have a sheet; generic units use raw numbers (0x80...)."""
    return char_index.startswith("CHARACTER_")


def render_ai(ai: list[int]) -> str:
    return "{" + ", ".join(hex(v) for v in ai) + "}"


@lru_cache(maxsize=4)
def read_unit_groups(decomp_dir: Path) -> dict[str, UnitGroup]:
    macros = ai_macros(decomp_dir)
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
            slot = -1
            for entry in _entries(body):
                if not entry.strip() or re.fullmatch(r"\s*0\s*", entry):
                    continue  # terminator { 0 }
                slot += 1
                try:
                    f = parse_fields(entry)
                except Exception:
                    continue
                x, y = _int(f.get("xPosition")), _int(f.get("yPosition"))
                path_name = f.get("redas", "").lstrip("&").strip()
                path = redas.get(path_name, [])
                items = [i.strip() for i in f.get("items", "{}").strip("{} ").split(",") if i.strip() not in ("", "0")]
                group.units.append({
                    # Position in the original array: identifies the unit once units are added or removed.
                    "slot": slot,
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
                    "ai": parse_ai(f.get("ai", ""), macros),
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


def apply_unit_groups(sources: dict[str, str], edits: dict[str, list[dict]],
                      macros: dict[str, list[int]] | None = None) -> dict[str, str]:
    """Write edited unit groups into the decomp sources (decomp-relative path -> text).

    Each unit's "slot" is its position in the original array. A new unit has "slot": None
    and "copyOf": the slot of the unit it was copied from; it inherits that unit's other
    fields (such as its AI) but not its movement path. When the units keep their order
    and none is added or removed, only the edited fields of the edited units are
    re-rendered, so unedited units stay byte-identical. A unit that enters the map
    along a path keeps it until it is moved: it then appears at its place, since the
    game corrupts its memory when a path cannot be walked (ticket 108).
    """
    sources = dict(sources)
    path_ends = _path_ends(sources)
    for name, new_units in edits.items():
        rel = next((r for r, s in sources.items() if _array_body_span(_blank_comments(s), "UnitDefinition", name)), None)
        if rel is None:
            raise UnitEditError(f"Unit group {name} not found")
        source = sources[rel]
        clean = _blank_comments(source)
        start, end = _array_body_span(clean, "UnitDefinition", name)
        spans = _entry_spans(clean, start, end)
        # Projects saved before units could be added or removed have no "slot": units were in order.
        slots = [u["slot"] if "slot" in u else i for i, u in enumerate(new_units)]
        kept = [s for s in slots if s is not None]
        if any(not 0 <= s < len(spans) for s in kept):
            raise UnitEditError(f"{name}: unknown unit")
        if len(set(kept)) != len(kept):
            raise UnitEditError(f"{name}: a unit appears twice")

        rendered: list[str | None] = []  # None: the original text is kept
        for slot, unit in zip(slots, new_units):
            if slot is None:
                fields = _new_unit_fields(clean, spans, unit, name)
                original = {}
            else:
                s, e = spans[slot]
                fields = parse_fields(clean[s + 1: e - 1])
                original = dict(fields)
            _apply_unit_fields(fields, unit, name, path_ends, is_new=slot is None, macros=macros or {})
            rendered.append(None if fields == original else _render_unit(fields, INDENT_MARK))

        if slots == list(range(len(spans))):
            # Same units in the same order: replace only the edited entries.
            out, last = [], 0
            for (s, e), text in zip(spans, rendered):
                if text is not None:
                    out.append(source[last:s])
                    out.append(text.replace(INDENT_MARK, _indent_at(clean, s)))
                    last = e
            out.append(source[last:])
            sources[rel] = "".join(out)
        else:
            sources[rel] = _rewrite_array(source, clean, start, end, spans, slots, rendered)
    return sources


INDENT_MARK = "\x00indent\x00"


def _indent_at(clean: str, pos: int) -> str:
    line_start = clean.rfind("\n", 0, pos) + 1
    return clean[line_start:pos] if clean[line_start:pos].strip() == "" else "    "


def _new_unit_fields(clean: str, spans: list[tuple[int, int]], unit: dict, name: str) -> dict[str, str]:
    """Fields of a new unit: those of the unit it was copied from, without its movement path."""
    template = unit.get("copyOf")
    if template is None:
        return {"charIndex": "0", "classIndex": "0", "allegiance": "FACTION_ID_BLUE", "level": "1"}
    if not 0 <= template < len(spans):
        raise UnitEditError(f"{name}: unknown unit {template}")
    s, e = spans[template]
    fields = parse_fields(clean[s + 1: e - 1])
    fields.pop("redaCount", None)
    fields.pop("redas", None)
    return fields


def _apply_unit_fields(fields: dict[str, str], unit: dict, name: str, path_ends: dict[str, tuple[int, int]], is_new: bool,
                       macros: dict[str, list[int]]) -> None:
    """Update the parsed fields of a unit. Only fields whose meaning changes are touched."""
    character_changed = fields.get("charIndex", "0") != unit["character"]
    if character_changed:
        fields["charIndex"] = unit["character"]
    if is_named_character(unit["character"]):
        # A named character's class comes from its character sheet (the only source of
        # truth; class changes there are carried to unit definitions by gamedata). Class 0
        # makes the game use the character's class (UnitInitFromDefinition, src/bmunit.c).
        if character_changed:
            fields["classIndex"] = "0"
    elif fields.get("classIndex", "0") != unit["class"]:
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
    # Projects saved before the AI was editable store it as the original C text.
    ai = unit.get("ai")
    if isinstance(ai, list) and parse_ai(fields.get("ai", ""), macros) != [int(v) for v in ai]:
        if len(ai) != 4 or not all(0 <= int(v) <= 255 for v in ai):
            raise UnitEditError(f"{name}: invalid AI {ai}")
        fields["ai"] = render_ai([int(v) for v in ai])
    position = (int(unit["endX"]), int(unit["endY"]))
    path = fields.get("redas", "").lstrip("&").strip()
    if path and not re.fullmatch(r"\w+", path):
        # Path given as a raw address (not decompiled yet): it cannot be edited.
        if (_int(fields.get("xPosition")), _int(fields.get("yPosition"))) != position:
            raise UnitEditError(f"{name}: this unit follows a movement path that cannot be edited yet")
    elif path:
        if path not in path_ends:
            raise UnitEditError(f"Movement path {path} not found")
        if path_ends[path] != position:
            fields["xPosition"], fields["yPosition"] = str(position[0]), str(position[1])
            fields.pop("redaCount", None)
            fields.pop("redas", None)
    elif is_new or (_int(fields.get("xPosition")), _int(fields.get("yPosition"))) != position:
        fields["xPosition"], fields["yPosition"] = str(position[0]), str(position[1])


def _rewrite_array(source: str, clean: str, start: int, end: int, spans: list[tuple[int, int]],
                   slots: list[int | None], rendered: list[str | None]) -> str:
    """Rewrite the entries of a unit array whose units were added, removed or reordered."""
    terminator = re.compile(r"\{\s*0?\s*\}").search(clean, spans[-1][1] if spans else start, end)
    if terminator is None:
        raise UnitEditError("Unit group without its { 0 } terminator")
    indent = _indent_at(clean, spans[0][0] if spans else terminator.start())
    entries = []
    for slot, text in zip(slots, rendered):
        if text is None:
            s, e = spans[slot]
            entries.append(source[s:e])
        else:
            entries.append(text.replace(INDENT_MARK, indent))
    body = "".join(f"\n{indent}{entry}," for entry in entries)
    return source[:start] + body + "\n" + indent + source[terminator.start():]


NEW_GROUPS_FILE = "src/events_udefs.c"   # new groups are added at its end (it includes the class constants)


def render_new_group(name: str, new_units: list[dict], macros: dict[str, list[int]] | None = None) -> str:
    """C array of a group made in the project (reinforcements): each unit from default fields."""
    entries = []
    for unit in new_units:
        fields = {"charIndex": "0", "classIndex": "0", "allegiance": "FACTION_ID_RED", "level": "1"}
        _apply_unit_fields(fields, unit, name, {}, is_new=True, macros=macros or {})
        if unit.get("autolevel"):
            fields["autolevel"] = "1"
        entries.append(_render_unit(fields, "    "))
    body = "".join(f"    {entry},\n" for entry in entries)
    return f"\nCONST_DATA struct UnitDefinition {name}[] = {{\n{body}    {{ 0 }},\n}};\n"


def _path_ends(sources: dict[str, str]) -> dict[str, tuple[int, int]]:
    """Where each entry path ends."""
    ends: dict[str, tuple[int, int]] = {}
    for source in sources.values():
        for name, body in _arrays(_blank_comments(source), "REDA"):
            entries = [e for e in _entries(body) if e.strip()]
            if entries:
                f = parse_fields(entries[-1])
                ends[name] = (_int(f.get("x")), _int(f.get("y")))
    return ends


def place_at_destination(sources: dict[str, str], group: str) -> dict[str, str]:
    """Units of a group appear directly where their entry path ends, without walking in."""
    redas = _path_ends(sources)
    sources = dict(sources)
    for rel, source in sources.items():
        clean = _blank_comments(source)
        span = _array_body_span(clean, "UnitDefinition", group)
        if span is None:
            continue
        out, last = [], 0
        for s, e in _entry_spans(clean, *span):
            fields = parse_fields(clean[s + 1: e - 1])
            path = fields.get("redas", "").lstrip("&").strip()
            if path not in redas:
                continue
            fields["xPosition"], fields["yPosition"] = (str(v) for v in redas[path])
            fields.pop("redaCount", None)
            fields.pop("redas", None)
            out += [source[last:s], _render_unit(fields, _indent_at(clean, s))]
            last = e
        sources[rel] = "".join(out) + source[last:]
        return sources
    raise UnitEditError(f"Unit group {group} not found")


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


_SCRIPT_STEP = re.compile(r"\b(?:LOAD\d?\s*\(\s*\w+\s*,\s*(?P<load>\w+)\s*\)|(?P<loma>LOMA)\s*\(|CALL\s*\(\s*(?P<call>\w+)\s*\))")


def _script_steps(decomp_dir: Path, script: str, depth: int = 0) -> list[tuple[str, str]]:
    """("load", group) and ("map", "") steps of an event script, in order, CALLed scripts inlined.
    A "map" step (LOMA) switches to another map: cutscenes are often played on other maps."""
    body = _find_block(decomp_dir, rf"EventListScr\s+{re.escape(script)}\s*\[\s*\]\s*=\s*\{{")
    if body is None or depth > 3:
        return []
    steps: list[tuple[str, str]] = []
    for m in _SCRIPT_STEP.finditer(body):
        if m.group("load"):
            steps.append(("load", m.group("load")))
        elif m.group("loma"):
            steps.append(("map", ""))
        else:
            steps += _script_steps(decomp_dir, m.group("call"), depth + 1)
    return steps


def _script_loads(decomp_dir: Path, script: str) -> list[tuple[str, bool]]:
    """(group, in_cutscene) for the unit groups a script loads. Groups loaded before the
    script's last map change only appear in a cutscene: the battle starts on the map
    loaded last, and the units loaded before are cleared with the old map."""
    steps = _script_steps(decomp_dir, script)
    last_map = max((i for i, (kind, _) in enumerate(steps) if kind == "map"), default=-1)
    return [(name, i < last_map) for i, (kind, name) in enumerate(steps) if kind == "load"]


def chapter_unit_groups(decomp_dir: Path, event_group_symbol: str) -> list[dict]:
    """[{name, origin, turn}] for a chapter, in loading order. origin: "players" (the
    chapter's player units), "opening" (loaded by the opening scene), "cutscene" (only
    seen in a cutscene, before the battle) or "turn" (reinforcements on a given turn)."""
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
    for name, in_cutscene in _script_loads(decomp_dir, fields.get("beginningSceneEvents", "")):
        add(name, "cutscene" if in_cutscene else "opening")
    turns = _find_block(decomp_dir, rf"EventListScr\s+{re.escape(fields.get('turnBasedEvents', '-'))}\s*\[\s*\]\s*=\s*\{{")
    for m in re.finditer(r"\bTURN\s*\(\s*[^,]+,\s*(\w+)\s*,\s*(\d+)\s*,", turns or ""):
        for name, in_cutscene in _script_loads(decomp_dir, m.group(1)):
            add(name, "cutscene" if in_cutscene else "turn", int(m.group(2)))
    return result


@lru_cache(maxsize=4)
def all_chapter_unit_groups(decomp_dir: Path) -> dict[int, list[dict]]:
    """Chapter index -> chapter_unit_groups(), for every chapter with events (cached: used by validation)."""
    from . import maps

    table = maps.asset_table(decomp_dir)
    result = {}
    for i, chapter in enumerate(maps.chapter_settings(decomp_dir)):
        index = chapter.get("mapEventDataId", 0)
        if 0 < index < len(table) and table[index]:
            result[i] = chapter_unit_groups(decomp_dir, table[index])
    return result
