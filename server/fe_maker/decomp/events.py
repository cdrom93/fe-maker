"""Event scripts (EventListScr in src/events/*-eventscript.h) as lists of commands for the visual editor.

A script is a list of event macros (include/EAstdlib.h, include/EA_Standard_Library/*.h), one per
line: MUSC(SONG_TENSION), LOAD1(1, UnitDef_Event_Ch1Enemy), ENUN, Text_BG(BG_GRASS_PLAINS, 0x92A)...
FE Maker reads each into {"op": name, "args": [raw C expressions]} (no "args" for a bare macro), keeps
comments ({"op": "#", "text"}) and blank lines ({"op": ""}), and writes an edited script back one
command per line. Commands the editor knows (COMMANDS) get forms; the others stay as they are.

Project data: data/dialogues.json "scripts": {script name: [commands]} (only edited scripts).
"""

from __future__ import annotations

import re

from . import unitstats
from .cparse import _match_brace

_SCRIPT_RE = re.compile(r"(?:CONST_DATA\s+)?EventListScr\s+(\w+)\s*\[\s*\]\s*=\s*\{")
_IDENT_RE = re.compile(r"[A-Za-z_]\w*")

# Argument kinds: song, message, character, group (unit group), x, y, frames, background, flag, speed,
# item, number, stat, amount (a signed number), chapter, raw, slot (a memory slot of the event engine, EVT_SLOT_0 to
# EVT_SLOT_D), label (a LABEL number of the script), script (another script, for CALL). The editor shows a field for each.
#
# Conditions: a check (CHECK_x) puts its result in slot C, then a branch (BEQ, BNE...) jumps to a LABEL of
# the script when its two slots compare; the game writes "if alive" as CHECK_ALIVE(x), BEQ(n, EVT_SLOT_C,
# EVT_SLOT_0), ..., LABEL(n).
COMMANDS: dict[str, list[tuple[str, str]]] = {
    "MUSC": [("song", "song")],
    "MUSS": [("song", "song")],
    "MURE": [("speed", "number")],
    "MUSI": [],
    "MUNO": [],
    "Text": [("message", "message")],
    "Text_BG": [("background", "background"), ("message", "message")],
    "TEXTSTART": [],
    "TEXTSHOW": [("message", "message")],
    "TEXTEND": [],
    "REMA": [],
    "BACG": [("background", "background")],
    "FADI": [("speed", "number")],
    "FADU": [("speed", "number")],
    "FAWI": [("speed", "number")],
    "FAWU": [("speed", "number")],
    "LOAD1": [("flag", "number"), ("group", "group")],
    "LOAD2": [("flag", "number"), ("group", "group")],
    "LOAD3": [("flag", "number"), ("group", "group")],
    "ENUN": [],
    "MOVE": [("speed", "number"), ("character", "character"), ("x", "x"), ("y", "y")],
    "CUMO_AT": [("x", "x"), ("y", "y")],
    "CUMO_CHAR": [("character", "character")],
    "CURE": [],
    "FlashCursor": [("character", "character"), ("frames", "frames")],
    "STAL": [("frames", "frames")],
    "STAL2": [("frames", "frames")],
    "STAL3": [("frames", "frames")],
    "DISA": [("character", "character")],
    "KILL": [("character", "character")],
    "CUSE": [("character", "character")],
    "REMU": [("character", "character")],
    "REVEAL": [("character", "character")],
    "TILECHANGE": [("change", "mapChange")],
    "TILEREVERT": [("change", "mapChange")],
    "WEA1": [("weather", "weather")],   # FE Maker's macro, added to the build when a script uses it
    "VCWF": [("vision", "number")],
    "SOUN": [("sound", "song")],
    "WARP_IN": [("x", "x"), ("y", "y")],
    "WARP_OUT": [("x", "x"), ("y", "y")],
    "SetHP": [("character", "character"), ("hp", "number")],   # the editor's: SVAL + SET_HP
    "SetAI": [("character", "character"), ("ai", "ai")],   # the editor's: SVAL + CHAI
    # Screen tint (the editor's): red, green, blue in % of the normal colors, written as EvtColorFadeSetup on every
    # palette; the first tint of a script archives the palettes (STARTFADE), going back to normal ends it (ENDFADE).
    "ScreenTint": [("speed", "number"), ("red", "percent"), ("green", "percent"), ("blue", "percent")],
    "ScreenNormal": [("speed", "number")],
    # Counters: 8 per chapter (0-7), each 0 to 15; COUNTER_CHECK puts the value in slot C.
    "COUNTER_SET": [("counter", "counter"), ("value", "number")],
    "COUNTER_INC": [("counter", "counter")],
    "COUNTER_DEC": [("counter", "counter")],
    "COUNTER_CHECK": [("counter", "counter")],
    "CUSA": [("character", "character")],
    "CUSN": [("character", "character")],
    "ENUT": [("flag", "flag")],
    "ENUF": [("flag", "flag")],
    "MUSCMID": [("song", "song")],
    "MUSCSLOW": [("song", "song")],
    "SetBackground": [("background", "background")],
    "TEXTCONT": [],
    "CAMERA": [("x", "x"), ("y", "y")],
    "CAMERA2": [("x", "x"), ("y", "y")],
    "CAMERA_CAHR": [("character", "character")],
    "CLEA": [],
    "CLEE": [],
    "CLEN": [],
    "NoFade": [],
    "ENDA": [],
    "CHECK_ALIVE": [("character", "character")],
    "CHECK_EXISTS": [("character", "character")],
    "CHECK_DEPLOYED": [("character", "character")],
    "CHECK_EVENTID": [("flag", "flag")],
    "CHECK_TURNS": [],
    "CHECK_HARD": [],
    "CHECK_MODE": [],
    "CHECK_ENEMIES": [],
    "CHECK_MONEY": [],
    "CHECK_ACTIVE": [],
    "CHECK_AT": [("x", "x"), ("y", "y")],
    "SVAL": [("slot", "slot"), ("value", "number")],
    "LABEL": [("label", "label")],
    "GOTO": [("label", "label")],
    "CALL": [("script", "script")],
    "GiveItem": [("character", "character"), ("item", "item")],   # the editor's: written as two commands (render_command)
    "MNC2": [("chapter", "chapter")],
    "ChangeStat": [("character", "character"), ("stat", "stat"), ("amount", "amount")],   # the editor's too (unitstats.py)
    # skills batch 3 (the editor's): written as slots + ASMC(FemSkillEvent) (skills.py), only with the skills option
    "GiveSkill": [("character", "character"), ("skill", "skill")],
    "RemoveSkill": [("character", "character"), ("skill", "skill")],
    **{op: [("label", "label"), ("left", "slot"), ("right", "slot")] for op in ("BEQ", "BNE", "BGE", "BGT", "BLE", "BLT")},
}
# Commands the editor offers to add (the others can only be kept, moved or removed).
ADDABLE = ("Text", "Text_BG", "MUSC", "LOAD1", "ENUN", "MOVE", "CAMERA_CAHR", "CAMERA", "CUMO_AT", "CURE", "FlashCursor",
           "STAL", "DISA", "CUSA", "FADI", "FADU", "SetBackground", "ENUT", "ENUF",
           "CHECK_ALIVE", "CHECK_EXISTS", "CHECK_DEPLOYED", "CHECK_EVENTID", "CHECK_TURNS", "CHECK_HARD", "CHECK_ENEMIES",
           "GiveItem", "ChangeStat", "MNC2", "CHECK_MONEY", "CHECK_ACTIVE",
           "SVAL", "BEQ", "BNE", "BGE", "BLT", "LABEL", "GOTO", "CALL",
           "TILECHANGE", "TILEREVERT", "WEA1", "VCWF", "SOUN", "WARP_IN", "WARP_OUT", "CUSN", "CUSE", "KILL", "REMU", "REVEAL",
           "SetHP", "SetAI", "ScreenTint", "ScreenNormal", "COUNTER_SET", "COUNTER_INC", "COUNTER_DEC",
           "GiveSkill", "RemoveSkill")
# Weather change during a chapter (EV_CMD_CHANGEWEATHER has no macro in the decomp).
MACROS_FILE = "include/EAstdlib.h"
WEATHER_MACRO = "#define WEA1(weather) _EvtArg0(EV_CMD_CHANGEWEATHER, 2, 0, (weather)),\n"
# Memories, the player's past choices: permanent event flags the game does not use (saved with the game, flags up to
# 300), named in data/dialogues.json "memories" [{flag, name}]; scripts hold their number (ENUT, ENUF, CHECK_EVENTID).
MEMORY_FLAGS = (240, 300)
_SLOT_RE = re.compile(r"EVT_SLOT_[0-9A-D]|0x[0-9A-Da-d]|1[0-3]|[0-9]")
_LABEL_RE = re.compile(r"0x[0-9A-Fa-f]+|\d+")


class EventError(Exception):
    pass


def _split_args(text: str) -> list[str]:
    out, depth, cur = [], 0, ""
    for ch in text:
        if ch in "([{":
            depth += 1
        elif ch in ")]}":
            depth -= 1
        if ch == "," and depth == 0:
            out.append(cur.strip())
            cur = ""
        else:
            cur += ch
    if cur.strip():
        out.append(cur.strip())
    return out


def parse_script(body: str) -> list[dict]:
    """Commands of a script body (between its braces)."""
    out: list[dict] = []
    i, n = 0, len(body)
    newlines = 0
    while i < n:
        ch = body[i]
        if ch == "\n":
            newlines += 1
            i += 1
            continue
        if ch.isspace():
            i += 1
            continue
        if newlines >= 2 and out:
            out.append({"op": ""})   # a blank line between commands
        newlines = 0
        if body.startswith("/*", i):
            end = body.find("*/", i + 2)
            end = n if end < 0 else end + 2
            out.append({"op": "#", "text": body[i:end]})
            i = end
            continue
        if body.startswith("//", i):
            end = body.find("\n", i)
            end = n if end < 0 else end
            out.append({"op": "#", "text": body[i:end]})
            i = end
            continue
        m = _IDENT_RE.match(body, i)
        if not m:
            raise EventError(f"Cannot read the script near: {body[i:i + 30]!r}")
        op = m.group(0)
        i = m.end()
        j = i
        while j < n and body[j] in " \t":
            j += 1
        if j < n and body[j] == "(":
            depth, k = 0, j
            while k < n:
                if body[k] == "(":
                    depth += 1
                elif body[k] == ")":
                    depth -= 1
                    if depth == 0:
                        break
                k += 1
            if k >= n:
                raise EventError(f"Unclosed parenthesis after {op}")
            out.append({"op": op, "args": _split_args(body[j + 1:k])})
            i = k + 1
        else:
            out.append({"op": op})
    return out


def render_command(c: dict) -> str:
    if c.get("op") == "#":
        return c.get("text", "")
    if c.get("op") == "GiveItem":
        character, item = c["args"]
        return f"SVAL(EVT_SLOT_3, {item})\n    GIVEITEMTO({character})"
    if c.get("op") == "SetHP":
        character, hp = c["args"]
        return f"SVAL(EVT_SLOT_1, {hp})\n    SET_HP({character})"
    if c.get("op") == "SetAI":
        character, ai = c["args"]
        return f"SVAL(EVT_SLOT_1, {ai})\n    CHAI({character})"
    if c.get("op") == "ScreenTint":
        speed, *rgb = c["args"]
        return f"EvtColorFadeSetup(0x0, 0x20, {speed}, {', '.join(str(min(int(v), 200) * 256 // 100) for v in rgb)})"
    if c.get("op") == "ScreenNormal":
        return f"EvtColorFadeSetup(0x0, 0x20, {c['args'][0]}, 256, 256, 256)\n    ENDFADE"
    if c.get("op") == "ChangeStat":
        character, stat, amount = c["args"]
        return (f"SVAL(EVT_SLOT_1, {character})\n    SVAL(EVT_SLOT_2, {unitstats.STATS.index(stat)})\n"
                f"    SVAL(EVT_SLOT_3, {int(amount)})\n    ASMC({unitstats.FUNCTION})")
    if c.get("op") in ("GiveSkill", "RemoveSkill"):
        character, skill = c["args"]
        return (f"#ifdef SKILLS_FEM_EVENTS\n    SVAL(EVT_SLOT_1, {character})\n    SVAL(EVT_SLOT_2, SKILL_FEM_{skill})\n"
                f"    SVAL(EVT_SLOT_3, {1 if c['op'] == 'GiveSkill' else 0})\n    ASMC(FemSkillEvent)\n#endif")
    if "args" in c:
        return f"{c['op']}({', '.join(str(a) for a in c['args'])})"
    return c["op"]


def render_script(commands: list[dict], indent: str = "    ") -> str:
    """Script body: one command per line, blank lines kept."""
    lines, tinted = [], False
    for c in commands:
        if c.get("op") == "ScreenTint" and not tinted:
            lines.append(indent + "STARTFADE")
        tinted = (tinted or c.get("op") == "ScreenTint") and c.get("op") != "ScreenNormal"
        lines.append("" if c.get("op") == "" else indent + render_command(c))
    return "\n" + "\n".join(lines) + "\n"


def find_scripts(source: str) -> dict[str, tuple[int, int]]:
    """Script name -> (body start, body end) in a source file."""
    out = {}
    for m in _SCRIPT_RE.finditer(source):
        open_pos = m.end() - 1
        out[m.group(1)] = (open_pos + 1, _match_brace(source, open_pos))
    return out


def same_commands(a: list[dict], b: list[dict]) -> bool:
    """Same commands and arguments (blank lines and spacing aside)."""
    def norm(cs: list[dict]) -> list:
        return [(c["op"], [re.sub(r"\s+", "", str(x)) for x in c.get("args", [])] if "args" in c else None,
                 c.get("text")) for c in cs if c.get("op") != ""]
    return norm(a) == norm(b)


def validate_command(c: dict) -> str | None:
    """Problem code for a command the editor knows, else None."""
    if not isinstance(c, dict) or not isinstance(c.get("op"), str):
        return "badCommand"
    op = c["op"]
    if op in ("", "#"):
        return None
    if not _IDENT_RE.fullmatch(op):
        return "badCommand"
    spec = COMMANDS.get(op)
    if spec is None:
        return None
    args = c.get("args")
    if spec and (not isinstance(args, list) or len(args) != len(spec)):
        return "badArguments"
    if not spec and args:
        return "badArguments"
    if any(not str(a).strip() or any(ch in str(a) for ch in ";{}") for a in (args or [])):
        return "badArguments"
    patterns = {"slot": _SLOT_RE, "label": _LABEL_RE, "script": re.compile(f"{_IDENT_RE.pattern}|{_LABEL_RE.pattern}"),
                "stat": re.compile("|".join(unitstats.STATS)), "amount": re.compile(r"[+-]?\d{1,2}"),
                "weather": re.compile(r"WEATHER_[A-Z]+"), "ai": _LABEL_RE, "mapChange": re.compile(r"\d{1,3}"),
                "percent": re.compile(r"\d{1,3}"), "counter": re.compile(r"[0-7]"),
                "skill": re.compile(r"[A-Za-z][A-Za-z0-9]*")}
    if any(kind in patterns and not patterns[kind].fullmatch(str(a).strip()) for (_n, kind), a in zip(spec, args or [])):
        return "badArguments"
    return None


# ---------- constants offered by the editor ----------

def read_constants(header: str, prefix: str) -> list[str]:
    """Names of an enum or #define list (SONG_..., BG_...), in order."""
    return list(dict.fromkeys(re.findall(rf"\b({prefix}\w+)\b\s*(?:=|,|\s)", header)))
