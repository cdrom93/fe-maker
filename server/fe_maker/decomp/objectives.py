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

Only chapters written with these standard forms can be edited; the others (escort,
areas, custom scripts) are shown as they are.
"""

from __future__ import annotations

import re

from .cparse import _blank_comments, _match_brace, parse_fields

TYPES = ("seize", "defeat_all", "defeat_boss", "defense")
SEIZE_LABELS = {"throne": 417, "gate": 415}
WINDOW_TEXT = {"defense": 412, "defeat_boss": 413, "defeat_all": 414}

_SEIZE_RE = re.compile(r"^[ \t]*Seize\s*\(\s*(\d+)\s*,\s*(\d+)\s*\)[ \t]*\r?\n", re.M)
_DEFEAT_RE = re.compile(r"^[ \t]*(DefeatAll|DefeatBoss)\s*\(\s*(\w+)\s*\)[ \t]*\r?\n", re.M)
_WIN_TURN_RE = re.compile(
    r"^[ \t]*TURN\s*\(\s*EVFLAG_WIN\s*,\s*(\w+)\s*,\s*(\d+)\s*,\s*0\s*,\s*FACTION_BLUE\s*\)[ \t]*\r?\n", re.M)
_END_RE = re.compile(r"^([ \t]*)END_MAIN\b", re.M)


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
    padded = [line + ("[.]" if len(line.encode("utf-8")) % 2 else "") for line in lines]
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
    win_turns = _WIN_TURN_RE.findall(turn)
    objective["seize"] = seize
    if win_turns:
        objective["turns"] = int(win_turns[0][1]) - 1
    # Any other way of setting the win flag is a custom objective.
    win_flag_uses = sum(body.count("EVFLAG_WIN") for body in (location, misc, turn))
    standard = {
        "seize": bool(seize) and not defeats and not win_turns and win_flag_uses == 0,
        "defeat_all": [d[0] for d in defeats] == ["DefeatAll"] and not seize and not win_turns and win_flag_uses == 0,
        "defeat_boss": [d[0] for d in defeats] == ["DefeatBoss"] and not seize and not win_turns and win_flag_uses == 0,
        "defense": len(win_turns) == 1 and not seize and not defeats and win_flag_uses == 1,
    }
    if goal.get("protectCharacterIndex", 0):
        objective["reason"] = "escort"
    elif not standard.get(objective["type"], False):
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

    group = event_group(sources, symbol)
    sources = dict(sources)
    misc_name = group.get("miscBasedEvents", "")
    defeats = _DEFEAT_RE.findall(_body(sources, misc_name))
    ending = defeats[0][1] if defeats else group.get("endingSceneEvents", "")
    if kind != "seize" and not re.fullmatch(r"\w+", ending or ""):
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
    rewrite(misc_name, _DEFEAT_RE,
            [f"{'DefeatAll' if kind == 'defeat_all' else 'DefeatBoss'}({ending})"] if kind in ("defeat_all", "defeat_boss") else [],
            at_start=True)
    rewrite(group.get("turnBasedEvents", ""), _WIN_TURN_RE,
            [f"TURN(EVFLAG_WIN, {ending}, {turns + 1}, 0, FACTION_BLUE)"] if kind == "defense" else [])

    goal["windowDataType"] = kind
    if kind == "seize":
        goal["windowTextId"] = SEIZE_LABELS.get(new.get("seizeLabel", "throne"), 417)
    else:
        goal["windowTextId"] = WINDOW_TEXT[kind]
    goal["windowEndTurnNumber"] = turns + 1 if kind == "defense" else 0
    return sources
