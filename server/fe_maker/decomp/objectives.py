"""Chapter objectives: what the goal window shows, and the events that actually win the chapter.

Two places must agree:
- the goal block of src/data/chapter_settings.json: window type (seize, defeat_all,
  defense, defeat_boss, special), window text, turn shown for defense maps, and the
  text of the status screen (statusObjectiveTextId, in texts/texts.txt);
- the chapter's events (src/events/*-eventinfo.h): Seize(x, y) in the location list,
  DefeatAll(script) / DefeatBoss(script) in the misc list, or a turn event setting the
  win flag. Once EVFLAG_WIN is set, the engine plays the chapter's ending scene
  (MaybeCallEndEvent, src/eventinfo.c). With defeat_all and defeat_boss, it also wins by
  itself when no enemy is left.

Only chapters written with these standard forms can be edited; the others (the tower and ruins
maps, custom scripts) are shown as they are. A defense map can also be won by defeating the boss
("orBoss": the game's "Survive for 11 turns or defeat Aias", TURN and DefeatBoss together).
"""

from __future__ import annotations

import re

from .cparse import _blank_comments, _match_brace, parse_fields
from .texts import text_size

TYPES = ("seize", "defeat_all", "defeat_boss", "defense", "area")
SEIZE_LABELS = {"throne": 417, "gate": 415}
WINDOW_TEXT = {"defense": 412, "defeat_boss": 413, "defeat_all": 414}

_SEIZE_RE = re.compile(r"^[ \t]*Seize\s*\(\s*(\d+)\s*,\s*(\d+)\s*\)[ \t]*\r?\n", re.M)
_DEFEAT_RE = re.compile(r"^[ \t]*(DefeatAll|DefeatBoss)\s*\(\s*(\w+)\s*\)[ \t]*\r?\n", re.M)
# The turn that wins a defense map: TURN(EVFLAG_WIN, script, turn, 0, FACTION_BLUE), or the same written
# with the TurnEventPlayer macro (Main_Code_Helpers.h), maybe followed by a comment.
_WIN_TURN_RE = re.compile(
    r"^[ \t]*(?:TURN\s*\(\s*EVFLAG_WIN\s*,\s*(\w+)\s*,\s*(\d+)\s*,\s*0\s*,\s*FACTION_BLUE\s*\)"
    r"|TurnEventPlayer\s*\(\s*EVFLAG_WIN\s*,\s*(\w+)\s*,\s*(\d+)\s*\))[ \t]*(?:/\*[^\n]*?\*/)?[ \t]*\r?\n", re.M)
_END_RE = re.compile(r"^([ \t]*)END_MAIN\b", re.M)
# "Reach an area": AREA(EVFLAG_WIN, script, x1, y1, x2, y2) in the misc list; the script cancels the
# event when the unit that moved there is not a player unit (or not the chosen character).
_AREA_WIN_RE = re.compile(r"^[ \t]*AREA\s*\(\s*EVFLAG_WIN\s*,[^\n]*\)[ \t]*\r?\n", re.M)
AREA_SCRIPT = "EventScr_FEM_ReachArea"
GAME_OVER_RE = re.compile(r"CauseGameOverIfLordDies|AFEV\s*\([^)]*EVFLAG_GAMEOVER")


def area_script(name: str, who: str) -> str:
    """Event of the "reach an area" objective: it only counts for the player's units, or for `who`
    (EventScr_UnTriggerIfNotFaction / EventScr_UnTriggerIfNotUnit, src/events_script_utils.c)."""
    check = (f"    SVAL(EVT_SLOT_2, {who})\n    CALL(EventScr_UnTriggerIfNotUnit)\n" if who
             else "    SVAL(EVT_SLOT_2, 0)\n    CALL(EventScr_UnTriggerIfNotFaction)\n")
    return f"CONST_DATA EventListScr {name}[] = {{\n{check}    NoFade\n    ENDA\n}};\n\n"


class ObjectiveError(Exception):
    pass


# ---------- texts ----------

def status_message(text: str) -> str:
    """Message body for an objective text typed by the user (lines separated by \\n).

    Each run of text before a control code must have an even length: the text
    compressor packs characters two by two (see texts.name_message). The original
    game pads with [.], e.g. "Guard Mansel for 13[.][LF]".
    """
    lines = [line.strip() for line in text.strip().split("\n")]
    padded = [line + ("[.]" if text_size(line) % 2 else "") for line in lines]
    return "[LF]\n".join(padded) + "[X]"


def status_text(raw: str) -> str:
    """Readable text of a message: 'Seize the castle[LF]\\ngate[X]' -> 'Seize the castle\\ngate'."""
    text = raw.replace("[LF]\n", "\n").replace("[LF]", "\n")
    return re.sub(r"\[[^\]]*\]", "", text).strip()


# ---------- events ----------

def _block(sources: dict[str, str], pattern: str) -> tuple[str, int, int] | None:
    """(file, body start, body end) of the first block matching `pattern` (ending with '{')."""
    for rel, source in sources.items():
        m = re.search(pattern, _blank_comments(source))
        if m:
            open_pos = m.end() - 1
            return rel, open_pos + 1, _match_brace(_blank_comments(source), open_pos)
    return None


def event_group(sources: dict[str, str], symbol: str) -> dict[str, str]:
    found = _block(sources, rf"struct\s+ChapterEventGroup\s+{re.escape(symbol)}\s*=\s*\{{")
    if found is None:
        raise ObjectiveError(f"Chapter event group {symbol} not found")
    rel, start, end = found
    return parse_fields(_blank_comments(sources[rel])[start:end])


def _list(sources: dict[str, str], name: str) -> tuple[str, int, int] | None:
    return _block(sources, rf"EventListScr\s+{re.escape(name)}\s*\[\s*\]\s*=\s*\{{")


def _body(sources: dict[str, str], name: str) -> str:
    found = _list(sources, name)
    return sources[found[0]][found[1]:found[2]] if found else ""


def read_objective(goal: dict, sources: dict[str, str], symbol: str | None, texts) -> dict:
    """Objective of a chapter, from its goal settings and its events."""
    status_id = goal.get("statusObjectiveTextId", 0)
    try:
        status = status_text(texts.raw(status_id)) if status_id else ""
    except KeyError:
        status = ""
    objective = {
        "type": goal.get("windowDataType", "special"),
        "seize": [],
        "seizeLabel": "gate" if goal.get("windowTextId") in (415, 416) else "throne",
        "turns": max(0, goal.get("windowEndTurnNumber", 0) - 1),
        "statusText": status,
        "area": None,
        "areaWho": "",
        "orBoss": False,
        "editable": False,
        "reason": "",
    }
    if symbol is None:
        objective["reason"] = "noEvents"
        return objective
    try:
        group = event_group(sources, symbol)
    except ObjectiveError:
        objective["reason"] = "noEvents"
        return objective
    location = _body(sources, group.get("locationBasedEvents", ""))
    misc = _body(sources, group.get("miscBasedEvents", ""))
    turn = _body(sources, group.get("turnBasedEvents", ""))
    seize = [{"x": int(x), "y": int(y)} for x, y in _SEIZE_RE.findall(location)]
    defeats = _DEFEAT_RE.findall(misc)
    win_turns = [(a or c, int(b or d)) for a, b, c, d in _WIN_TURN_RE.findall(turn)]
    objective["seize"] = seize
    if win_turns:
        objective["turns"] = win_turns[0][1] - 1
    # Any other way of setting the win flag is a custom objective.
    win_flag_uses = sum(body.count("EVFLAG_WIN") for body in (location, misc, turn))
    standard = {
        "seize": bool(seize) and not defeats and not win_turns and win_flag_uses == 0,
        "defeat_all": [d[0] for d in defeats] == ["DefeatAll"] and not seize and not win_turns and win_flag_uses == 0,
        "defeat_boss": [d[0] for d in defeats] == ["DefeatBoss"] and not seize and not win_turns and win_flag_uses == 0,
        "defense": len(win_turns) == 1 and not seize and [d[0] for d in defeats] in ([], ["DefeatBoss"])
        and win_flag_uses == 1,
    }
    objective["orBoss"] = objective["type"] == "defense" and bool(defeats)
    if not standard.get(objective["type"], False):
        objective["reason"] = "custom"
    else:
        objective["editable"] = True
    return objective


def apply_objective(goal: dict, sources: dict[str, str], symbol: str, current: dict, new: dict) -> dict[str, str]:
    """Rewrite the goal settings (in place) and the chapter's events for a new objective.
    `current` is read_objective's result; only standard objectives can be changed."""
    if not current["editable"]:
        raise ObjectiveError(f"{symbol}: this objective is scripted by the original game and cannot be edited")
    kind = new["type"]
    if kind not in TYPES:
        raise ObjectiveError(f"Unknown objective type {kind}")
    if kind == "seize" and not new.get("seize"):
        raise ObjectiveError("A seize objective needs a tile")
    turns = int(new.get("turns", 0))
    if kind == "defense" and not 1 <= turns <= 99:
        raise ObjectiveError("A defense objective needs a number of turns between 1 and 99")
    area = new.get("area") or {}
    if kind == "area" and not all(isinstance(area.get(k), int) and 0 <= area[k] < 64 for k in ("x1", "y1", "x2", "y2")):
        raise ObjectiveError("A \"reach an area\" objective needs an area")

    group = event_group(sources, symbol)
    sources = dict(sources)
    misc_name = group.get("miscBasedEvents", "")
    defeats = _DEFEAT_RE.findall(_body(sources, misc_name))
    ending = defeats[0][1] if defeats else group.get("endingSceneEvents", "")
    if kind not in ("seize", "area") and not re.fullmatch(r"\w+", ending or ""):
        raise ObjectiveError(f"{symbol}: no ending scene to play")

    def rewrite(list_name: str, pattern: re.Pattern, lines: list[str], at_start: bool = False):
        found = _list(sources, list_name)
        if found is None:
            if lines:
                raise ObjectiveError(f"{symbol}: event list {list_name} not found")
            return
        rel, start, end = found
        body = pattern.sub("", sources[rel][start:end])
        if lines:
            m = _END_RE.search(body)
            indent = m.group(1) if m else "    "
            block = "".join(f"{indent}{line}\n" for line in lines)
            if at_start:
                first = body.index("\n") + 1 if "\n" in body else 0
                body = body[:first] + block + body[first:]
            elif m:
                body = body[: m.start()] + block + body[m.start():]
            else:
                body += block
        sources[rel] = sources[rel][:start] + body + sources[rel][end:]

    rewrite(group.get("locationBasedEvents", ""), _SEIZE_RE,
            [f"Seize({int(t['x'])}, {int(t['y'])})" for t in new.get("seize", [])] if kind == "seize" else [])
    by_boss = kind == "defeat_boss" or (kind == "defense" and bool(new.get("orBoss")))
    rewrite(misc_name, _DEFEAT_RE,
            [f"{'DefeatAll' if kind == 'defeat_all' else 'DefeatBoss'}({ending})"]
            if kind == "defeat_all" or by_boss else [],
            at_start=True)
    rewrite(group.get("turnBasedEvents", ""), _WIN_TURN_RE,
            [f"TURN(EVFLAG_WIN, {ending}, {turns + 1}, 0, FACTION_BLUE)"] if kind == "defense" else [])
    area_name = f"{AREA_SCRIPT}_{symbol}"
    rewrite(misc_name, _AREA_WIN_RE,
            [f"AREA(EVFLAG_WIN, {area_name}, {area['x1']}, {area['y1']}, {area['x2']}, {area['y2']})"]
            if kind == "area" else [], at_start=True)
    if kind == "area":
        rel, start, _end = _list(sources, misc_name)
        declaration = sources[rel].rfind("\n", 0, start) + 1
        script = area_script(area_name, new.get("areaWho") or "")
        sources[rel] = sources[rel][:declaration] + script + sources[rel][declaration:]

    goal["windowDataType"] = "seize" if kind == "area" else kind
    if kind == "area":
        goal["windowTextId"] = 0  # a message added by DecompData.apply_objective
    elif kind == "seize":
        goal["windowTextId"] = SEIZE_LABELS.get(new.get("seizeLabel", "throne"), 417)
    else:
        goal["windowTextId"] = WINDOW_TEXT[kind]
    goal["windowEndTurnNumber"] = turns + 1 if kind == "defense" else 0
    return sources


# ---------- boss (defeat boss objective) ----------

DEFEAT_TALK_FILE = "src/data_battlequotes.c"
CHAPTERS_HEADER = "include/constants/chapters.h"
_DEFEAT_TALK_ARRAY = ("DefeatTalkEnt", "gDefeatTalkList")


def ensure_game_over(sources: dict[str, str], symbol: str) -> dict[str, str]:
    """The misc list of a chapter ends the game when EVFLAG_GAMEOVER is set (a protected character
    died): CauseGameOverIfLordDies, added if missing."""
    group = event_group(sources, symbol)
    found = _list(sources, group.get("miscBasedEvents", ""))
    if found is None:
        raise ObjectiveError(f"{symbol}: no misc event list")
    rel, start, end = found
    body = sources[rel][start:end]
    if GAME_OVER_RE.search(body):
        return sources
    m = _END_RE.search(body)
    indent = m.group(1) if m else "    "
    body = body[: m.start()] + f"{indent}CauseGameOverIfLordDies\n" + body[m.start():] if m else body
    return {**sources, rel: sources[rel][:start] + body + sources[rel][end:]}


def clear_events(sources: dict[str, str], symbol: str) -> dict[str, str]:
    """The event lists of a chapter emptied of everything but its objective and the game over check (chapters the
    project clears, newchapter.py); no tutorial either."""
    group = event_group(sources, symbol)
    sources = dict(sources)
    keep = (_DEFEAT_RE, _SEIZE_RE, _WIN_TURN_RE, _AREA_WIN_RE, GAME_OVER_RE)
    for field in ("turnBasedEvents", "characterBasedEvents", "locationBasedEvents", "miscBasedEvents",
                  "specialEventsWhenUnitSelected", "specialEventsWhenDestSelected", "specialEventsAfterUnitMoved"):
        found = _list(sources, group.get(field, ""))
        if found is None:
            continue
        rel, start, end = found
        lines = [line for line in sources[rel][start:end].split("\n")
                 if _END_RE.search(line) or any(p.search(line + "\n") for p in keep)]
        sources[rel] = sources[rel][:start] + "\n" + "\n".join(lines) + "\n" + sources[rel][end:]
    found = _block(sources, rf"EventListScr\s*\*\s*{re.escape(group.get('tutorialEvents', '-'))}\s*\[\s*\]\s*=\s*\{{")
    if found is not None:
        rel, start, end = found
        sources[rel] = sources[rel][:start] + "\n    NULL\n" + sources[rel][end:]
    return sources


def chapter_constants(header: str) -> dict[str, int]:
    """CHAPTER_L_PROLOGUE -> 0... from include/constants/chapters.h."""
    return {name: int(value, 0) for name, value in re.findall(r"\b(CHAPTER_\w+)\s*=\s*(0x[0-9A-Fa-f]+|\d+)", header)}


def _defeat_talks(source: str, constants: dict[str, int]):
    """(span, fields, chapter index) of each death quote entry (terminator excluded)."""
    from .units import _array_body_span, _entry_spans

    clean = _blank_comments(source)
    span = _array_body_span(clean, *_DEFEAT_TALK_ARRAY)
    if span is None:
        return clean, []
    out = []
    for s, e in _entry_spans(clean, *span):
        fields = parse_fields(clean[s + 1: e - 1])
        if fields.get("pid", "").strip() in ("-1", "0xFFFF", "0xffff"):
            continue  # terminator
        chapter = fields.get("chapter", "")
        index = constants.get(chapter, None)
        if index is None:
            try:
                index = int(chapter, 0)
            except ValueError:
                index = -1
        out.append(((s, e), fields, index))
    return clean, out


def read_bosses(source: str, constants: dict[str, int]) -> dict[int, list[str]]:
    """Chapter index -> characters whose defeat sets the "boss defeated" flag (gDefeatTalkList).
    The engine does not use the Boss ability for this: the death quote entry does it."""
    bosses: dict[int, list[str]] = {}
    for _span, fields, index in _defeat_talks(source, constants)[1]:
        if fields.get("flag", "").strip() == "EVFLAG_DEFEAT_BOSS":
            bosses.setdefault(index, []).append(fields.get("pid", ""))
    return bosses


def set_boss(source: str, constants: dict[str, int], chapter_index: int, pid: str) -> str:
    """Make `pid` the boss of a chapter: change its death quote entry, or add one.
    A new or changed entry has no quote (msg 0): the previous boss's last words would not fit."""
    from .units import _indent_at, _render_unit

    clean, talks = _defeat_talks(source, constants)
    mine = [(span, f) for span, f, index in talks if index == chapter_index and f.get("flag", "").strip() == "EVFLAG_DEFEAT_BOSS"]
    if len(mine) > 1:
        raise ObjectiveError("This chapter has several bosses (one per route): not editable yet")
    if mine:
        (s, e), fields = mine[0]
        if fields.get("pid") == pid:
            return source
        fields["pid"] = pid
        fields["msg"] = "0x0000"
        fields.pop("event", None)
        return source[:s] + _render_unit(fields, _indent_at(clean, s)) + source[e:]
    chapter_name = next((name for name, value in constants.items() if value == chapter_index), f"0x{chapter_index:02X}")
    fields = {"pid": pid, "route": "CHAPTER_MODE_ANY", "chapter": chapter_name, "flag": "EVFLAG_DEFEAT_BOSS", "msg": "0x0000"}
    # Insert before the terminator, after the last entry.
    from .units import _array_body_span

    body_start, body_end = _array_body_span(clean, *_DEFEAT_TALK_ARRAY)
    terminator = clean.rfind("{", body_start, clean.rfind(".pid", body_start, body_end))
    indent = _indent_at(clean, terminator)
    entry = _render_unit(fields, indent) + ",\n" + indent
    return source[:terminator] + entry + source[terminator:]
