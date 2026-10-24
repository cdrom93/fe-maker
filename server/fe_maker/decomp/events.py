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

from .cparse import _match_brace

_SCRIPT_RE = re.compile(r"(?:CONST_DATA\s+)?EventListScr\s+(\w+)\s*\[\s*\]\s*=\s*\{")
_IDENT_RE = re.compile(r"[A-Za-z_]\w*")

# Argument kinds: song, message, character, group (unit group), x, y, frames, background, flag, speed,
# item, number, raw. The editor shows a field for each.
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
}
# Commands the editor offers to add (the others can only be kept, moved or removed).
ADDABLE = ("Text", "Text_BG", "MUSC", "LOAD1", "ENUN", "MOVE", "CAMERA_CAHR", "CAMERA", "CUMO_AT", "CURE", "FlashCursor",
           "STAL", "DISA", "CUSA", "FADI", "FADU", "SetBackground", "ENUT", "ENUF")


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
    if "args" in c:
        return f"{c['op']}({', '.join(str(a) for a in c['args'])})"
    return c["op"]


def render_script(commands: list[dict], indent: str = "    ") -> str:
    """Script body: one command per line, blank lines kept."""
    lines = ["" if c.get("op") == "" else indent + render_command(c) for c in commands]
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
    return None


# ---------- constants offered by the editor ----------

def read_constants(header: str, prefix: str) -> list[str]:
    """Names of an enum or #define list (SONG_..., BG_...), in order."""
    return list(dict.fromkeys(re.findall(rf"\b({prefix}\w+)\b\s*(?:=|,|\s)", header)))
