"""Dialogues: game messages (texts/texts.txt) as steps an editor can show and change.

A message is text and control codes (texts/textdefs.txt). A conversation opens a speaker slot
([OpenMidLeft]...), loads a portrait in it ([LoadFace][FID_Eirika]), then the speaker of the slot
talks; [LF] goes to the next line, [A] waits for a button press, [X] ends the message. Runs of
printable text must have an even length in bytes (two characters per symbol, see
texts.name_message): the game pads them with [.], which FE Maker removes when reading and puts
back when writing.

Steps:
- {"kind": "face", "pos": "MidLeft", "face": "FID_Eirika"}: a portrait appears in a slot;
- {"kind": "clear", "pos": ...}: the portrait leaves;
- {"kind": "move", "pos": ..., "to": "Right"}: the portrait moves to another slot;
- {"kind": "say", "pos": ... or None, "text": ..., "wait": bool}: the speaker of the slot talks.
  In the text, "\\n" is a new line, a blank line waits for a button and opens a new box, and the
  other codes stay as they are ([ToggleSmile], [ToggleMouthMove]...). "wait": the last box waits
  for a button press;
- {"kind": "code", "code": "CloseSpeechSlow", "pos": ...}: any other code between lines.
"""

from __future__ import annotations

import re

from .fonts import char_byte
from .texts import pad_text

# A message made for an event script (data/dialogues.json "quotes" of kind "scene", by their "key"):
# a script argument "new:<key>" becomes the new message's id at build time.
SCENE_MESSAGE = "new:"

POSITIONS = ("FarFarLeft", "FarLeft", "MidLeft", "Left", "Right", "MidRight", "FarRight", "FarFarRight")
_TOKEN_RE = re.compile(r"\[([^\]]*)\]")
# Codes that are printable characters (>= 0x20 in texts/textdefs.txt): they count in a text run.
PRINTABLE_CODES = {"LQuote", "RQuote", "DashedLine"}
PADDING = "."


class DialogueError(Exception):
    pass


def tokens(raw: str) -> list[tuple[str, str]]:
    """("text", "...") and ("code", "Name") items; file line breaks do not count."""
    raw = raw.replace("\r", "").replace("\n", "")
    out: list[tuple[str, str]] = []
    pos = 0
    for m in _TOKEN_RE.finditer(raw):
        if m.start() > pos:
            out.append(("text", raw[pos:m.start()]))
        out.append(("code", m.group(1)))
        pos = m.end()
    if pos < len(raw):
        out.append(("text", raw[pos:]))
    return out


def _open(code: str) -> str | None:
    return code[4:] if code.startswith("Open") and code[4:] in POSITIONS else None


def _move(code: str) -> str | None:
    return code[4:] if code.startswith("Move") and code[4:] in POSITIONS else None


def parse(raw: str) -> list[dict]:
    """Steps of a message (see the module docstring). [X] (end) is implicit."""
    items = [t for t in tokens(raw) if not (t[0] == "code" and t[1] == PADDING)]
    if items and items[-1] == ("code", "X"):
        items = items[:-1]
    steps: list[dict] = []
    pos: str | None = None
    opened = False   # the slot was just opened: the next line starts with [Open...]
    i = 0
    while i < len(items):
        kind, value = items[i]
        if kind == "code" and _open(value):
            pos = _open(value)
            nxt = items[i + 1] if i + 1 < len(items) else None
            if nxt == ("code", "LoadFace") and i + 2 < len(items) and items[i + 2][0] == "code":
                steps.append({"kind": "face", "pos": pos, "face": items[i + 2][1]})
                i += 3
                continue
            if nxt == ("code", "ClearFace"):
                steps.append({"kind": "clear", "pos": pos})
                i += 2
                continue
            if nxt and nxt[0] == "code" and _move(nxt[1]):
                steps.append({"kind": "move", "pos": pos, "to": _move(nxt[1])})
                pos = _move(nxt[1])
                i += 2
                continue
            i += 1
            # A slot opened before its text: the text that follows is a line of this speaker.
            if not nxt or (nxt[0] == "code" and (_open(nxt[1]) or nxt[1] in ("LoadFace", "ClearFace"))):
                steps.append({"kind": "code", "code": value, "pos": pos})
            else:
                opened = True
            continue
        if kind == "code" and not _starts_line(items, i):
            step = {"kind": "code", "code": value, "pos": pos}
            if opened:
                step["open"] = True  # [Open...] then a code alone (an expression: [CloseEyes]...)
                opened = False
            steps.append(step)
            i += 1
            continue
        # A line: everything up to the next slot change.
        j = i
        while j < len(items) and not (items[j][0] == "code" and _open(items[j][1])):
            j += 1
        steps.extend(_say(items[i:j], pos, opened))
        opened = False
        i = j
    return steps


def _starts_line(items: list[tuple[str, str]], i: int) -> bool:
    """Is there any text from here to the next slot change? (else these are loose codes)"""
    for kind, value in items[i:]:
        if kind == "code" and _open(value):
            return False
        if kind == "text" or (kind == "code" and value in PRINTABLE_CODES):
            return True
    return False


def _say(items: list[tuple[str, str]], pos: str | None, opened: bool = True) -> list[dict]:
    # The line ends with its last [A] when only codes follow it ([CloseSpeechSlow]...: loose codes);
    # without such an [A], codes after the last text are loose codes.
    last = max(k for k, (kind, value) in enumerate(items) if kind == "text" or value in PRINTABLE_CODES)
    end = next((k for k in range(len(items) - 1, last, -1) if items[k] == ("code", "A")), None)
    wait = end is not None
    if wait:
        body, tail = items[:end], items[end + 1:]
    else:
        body, tail = items[: last + 1], items[last + 1:]
    text = ""
    k = 0
    while k < len(body):
        kind, value = body[k]
        if kind == "text":
            text += value
        elif value == "A" and k + 1 < len(body) and body[k + 1] == ("code", "LF"):
            text += "\n\n"
            k += 1
        elif value == "LF" and k > 0 and body[k - 1] == ("code", "LF"):
            text += "[LF]"   # an empty line, without waiting (a blank line waits for a button)
        elif value == "LF":
            text += "\n"
        else:
            text += f"[{value}]"
        k += 1
    steps = [{"kind": "say", "pos": pos, "text": text, "wait": wait, "open": opened}]
    steps += [{"kind": "code", "code": value, "pos": pos} for _kind, value in tail]  # only codes after the last text
    return steps


def _pad(run: str) -> str:
    """Text run padded to an even number of bytes."""
    return pad_text(run)


# ---------- layout: lines that fit in the box ----------

TALK_WIDTH = 208     # widest line of a conversation: the box is 28 tiles at most, with its border (src/scene.c)
BATTLE_WIDTH = 144   # battle quotes and last words: the battle screen's box is 20 tiles wide (PutTalkBubble)
BOX_LINES = 2        # lines of a box; the game scrolls the text up for a third line
PRINTABLE_BYTES = {"LQuote": 0x93, "RQuote": 0x94, "DashedLine": 0x7F}


def line_width(line: str, widths: dict[int, int]) -> int:
    """Width in pixels of a line in the talk font (codes take no room)."""
    total = 0
    for kind, value in tokens(line):
        if kind == "text":
            total += sum(widths.get(char_byte(ch) or -1, 0) for ch in value)
        elif value in PRINTABLE_BYTES:
            total += widths.get(PRINTABLE_BYTES[value], 0)
    return total


def _split_word(word: str, widths: dict[int, int], max_width: int) -> list[str]:
    """A word wider than the box, cut between characters (never inside a [code])."""
    parts: list[str] = []
    current = ""
    for kind, value in tokens(word):
        pieces = list(value) if kind == "text" else [f"[{value}]"]
        for piece in pieces:
            if current and line_width(current + piece, widths) > max_width:
                parts.append(current)
                current = ""
            current += piece
    return [*parts, current] if current else parts


def wrap_line(line: str, widths: dict[int, int], max_width: int) -> list[str]:
    """A line cut between words so that each part fits in `max_width` pixels."""
    out: list[str] = []
    current = ""
    for word in line.split(" "):
        candidate = f"{current} {word}" if current else word
        if line_width(candidate, widths) <= max_width:
            current = candidate
            continue
        if current:
            out.append(current)
        parts = _split_word(word, widths, max_width) if line_width(word, widths) > max_width else [word]
        out += parts[:-1]
        current = parts[-1] if parts else ""
    if current or not out:
        out.append(current)
    return out


def layout(text: str, widths: dict[int, int], max_width: int = TALK_WIDTH) -> str:
    """Text of a line laid out for the game: lines too wide for the box are cut between words, and
    a box that gets more than two lines that way is split into boxes of two lines (a button press
    between them). Lines that fit are kept as written."""
    boxes: list[str] = []
    for box in text.split("\n\n"):
        lines: list[str] = []
        wrapped = False
        for line in box.split("\n"):
            if line_width(line, widths) <= max_width:
                lines.append(line)
            else:
                wrapped = True
                lines += wrap_line(line, widths, max_width)
        if wrapped and len(lines) > BOX_LINES:
            boxes += ["\n".join(lines[k:k + BOX_LINES]) for k in range(0, len(lines), BOX_LINES)]
        else:
            boxes.append("\n".join(lines))
    return "\n\n".join(boxes)


def layout_steps(steps: list[dict], widths: dict[int, int], max_width: int = TALK_WIDTH) -> list[dict]:
    return [{**s, "text": layout(s.get("text", ""), widths, max_width)} if s.get("kind") == "say" else s for s in steps]


def _text_runs(text: str) -> str:
    """Text of a line in game codes, each run of characters padded."""
    out = ""
    run = ""

    def flush() -> None:
        nonlocal out, run
        if run:
            out += _pad(run)
            run = ""

    for kind, value in tokens(text.replace("\n\n", "\x00").replace("\n", "\x01")):
        if kind == "text":
            for part in re.split(r"([\x00\x01])", value):
                if part == "\x00":
                    flush()
                    out += "[A][LF]\n"
                elif part == "\x01":
                    flush()
                    out += "[LF]\n"
                else:
                    run += part
        elif value in PRINTABLE_CODES:
            run += f"[{value}]"
        else:
            flush()
            out += f"[{value}]"
    flush()
    return out


def render(steps: list[dict]) -> str:
    """Message body (ending with [X]) of a list of steps."""
    out = ""
    current: str | None = None
    for s in steps:
        kind = s.get("kind")
        pos = s.get("pos")
        if pos is not None and pos not in POSITIONS:
            raise DialogueError(f"Unknown position {pos}")
        if kind == "face":
            out += f"[Open{pos}][LoadFace][{s['face']}]\n"
            current = pos
        elif kind == "clear":
            out += f"[Open{pos}][ClearFace]\n"
            current = pos
        elif kind == "move":
            if s.get("to") not in POSITIONS:
                raise DialogueError(f"Unknown position {s.get('to')}")
            out += f"[Open{pos}][Move{s['to']}]\n"
            current = s["to"]
        elif kind == "say":
            # Lines start by opening their speaker's slot ("open": False keeps a line that does not).
            if pos is not None and (s.get("open", True) or pos != current):
                out += f"[Open{pos}]"
                current = pos
            out += _text_runs(s.get("text", "")) + ("[A]" if s.get("wait") else "") + "\n"
        elif kind == "code":
            if s.get("open") and pos is not None:
                out += f"[Open{pos}]"
                current = pos
            if _open(s["code"]):
                current = _open(s["code"])
            out += f"[{s['code']}]"
        else:
            raise DialogueError(f"Unknown step {kind}")
    return out.rstrip("\n") + "[X]"


def same_message(a: str, b: str) -> bool:
    """Same codes and text, whatever the line breaks of the file and the [.] padding."""
    def norm(raw: str) -> list[tuple[str, str]]:
        return [t for t in tokens(raw) if t != ("code", PADDING)]
    return norm(a) == norm(b)


# ---------- messages used by a chapter ----------

_SCRIPT_RE = re.compile(r"EventListScr\s+(\w+)\s*\[\s*\]\s*=\s*\{(.*?)\n\};", re.S)
_MESSAGE_RE = re.compile(r"\b(?:Text|TEXTSHOW|TEXTCONT)\s*\(\s*(0x[0-9A-Fa-f]+|\d+)\s*\)"
                         r"|\bText_BG\s*\(\s*\w+\s*,\s*(0x[0-9A-Fa-f]+|\d+)\s*\)")


def script_messages(source: str) -> list[tuple[str, list[int]]]:
    """(script name, message ids in order) of each event script of a file that shows messages."""
    out = []
    for name, body in _SCRIPT_RE.findall(source):
        ids = []
        for a, b in _MESSAGE_RE.findall(body):
            value = int(a or b, 0)
            if value not in ids:
                ids.append(value)
        if ids:
            out.append((name, ids))
    return out


TEXT_DEFS_FILE = "texts/textdefs.txt"


def read_faces(textdefs: str) -> dict[str, int]:
    """Portrait codes of the texts: FID_Eirika -> portrait id ([FID_Eirika] = 0x02, 0x01: id 2)."""
    out = {}
    for name, low, high in re.findall(r"^\[(FID_\w+)\]\s*=\s*(0x[0-9A-Fa-f]+|\d+)\s*,\s*(0x[0-9A-Fa-f]+|\d+)",
                                      textdefs, re.M):
        if name != "FID_Active":
            out[name] = int(low, 0) | ((int(high, 0) - 1) << 8)
    return out


_LIST_ENTRY_RE = re.compile(r"^[ \t]*(\w+)\s*\(([^\n]*)\)[ \t]*$", re.M)


def scene_triggers(group: dict[str, str], lists: dict[str, str], scripts: set[str]) -> dict[str, dict]:
    """What starts each event script of a chapter: {"kind": beginning, ending, turn, talk, village,
    house, area, other, ...params}. `group`: fields of the chapter event group; `lists`: list name ->
    body; `scripts`: names of the chapter's scripts."""
    out: dict[str, dict] = {}
    for field, kind in (("beginningSceneEvents", "beginning"), ("endingSceneEvents", "ending")):
        if group.get(field) in scripts:
            out[group[field]] = {"kind": kind}
    for field in ("turnBasedEvents", "characterBasedEvents", "locationBasedEvents", "miscBasedEvents"):
        for macro, args in _LIST_ENTRY_RE.findall(lists.get(group.get(field, ""), "")):
            parts = [a.strip() for a in args.split(",")]
            script = next((a for a in parts if a in scripts), None)
            if script is None or script in out:
                continue
            k = parts.index(script)
            rest = parts[k + 1:]
            if macro == "TURN" and rest:
                out[script] = {"kind": "turn", "turn": rest[0], "faction": rest[2] if len(rest) > 2 else ""}
            elif macro in ("CHAR", "CHAR_", "CharacterEventBothWays") and len(rest) >= 2:
                out[script] = {"kind": "talk", "a": rest[0], "b": rest[1]}
            elif macro in ("Village", "House") and len(rest) >= 2:
                out[script] = {"kind": macro.lower(), "x": rest[0], "y": rest[1]}
            elif macro == "AREA":
                out[script] = {"kind": "area", "area": ", ".join(rest)}
            elif macro in ("DefeatAll", "DefeatBoss"):
                out[script] = {"kind": "ending"}
            else:
                out[script] = {"kind": "other"}
    return out


def with_trigger(source: str, script: str, change: dict) -> str:
    """The event lists of `source` where `script` starts as `change` says: "turn", "faction", "a", "b"."""
    def edit(found: re.Match) -> str:
        args = [a.strip() for a in found[3].split(",")]
        k = args.index(script)
        if found[2] == "TURN":
            if "turn" in change:
                start, end, turn = int(args[k + 1], 0), int(args[k + 2], 0), int(change["turn"], 0)
                args[k + 1] = str(turn)
                # one turn stays one turn; a range ("from turn 1 on") keeps its end, 0 meaning no end
                args[k + 2] = str(turn if end == start else 0 if end == 0 else max(end, turn))
            if change.get("faction"):
                args[k + 3] = change["faction"]
        else:
            args[k + 1] = change.get("a") or args[k + 1]
            args[k + 2] = change.get("b") or args[k + 2]
        return f"{found[1]}{found[2]}({', '.join(args)})"

    entry = rf"^([ \t]*)(TURN|CHAR_?|CharacterEventBothWays)\(([^\n]*\b{re.escape(script)}\b[^\n]*)\)"
    return re.sub(entry, edit, source, flags=re.M)


def without_scene(source: str, script: str) -> str:
    """`source` where nothing starts `script`: its lines in the event lists and the calls to it are gone."""
    return re.sub(rf"^[ \t]*\w+\([^\n]*\b{re.escape(script)}\b[^\n]*\)[ \t]*\n", "", source, flags=re.M)


def without_lost_messages(scripts: dict, quotes: list[dict]) -> dict:
    """`scripts` without the commands that show a project message which no longer exists (ticket 104)."""
    keys = {f"{SCENE_MESSAGE}{q['key']}" for q in quotes if q.get("key")}

    def lost(command: dict) -> bool:
        return any(isinstance(a, str) and a.startswith(SCENE_MESSAGE) and a not in keys for a in command.get("args") or [])

    return {name: [c for c in commands if not lost(c)] if isinstance(commands, list) else commands
            for name, commands in scripts.items()}


SCENE_ORDER = ("beginning", "turn", "talk", "village", "house", "area", "other", "battle", "death", "ending", "tutorial")


# ---------- new conversations ("Talk" on the map) ----------

TALK_FIRST_FLAG = 40   # temporary flags for new conversations (quotes use 50+, map objects 70+)
RECRUIT_MUSIC = 0x30   # the song of the game's recruitment conversations (MUSS(0x30))


FACTIONS = {"player": "FACTION_BLUE", "enemy": "FACTION_RED", "ally": "FACTION_GREEN"}


def scene_script(name: str, message: int) -> str:
    """Event script showing a message (a scene at the start of a turn)."""
    lines = ["TEXTSTART", f"TEXTSHOW(0x{message:X})", "TEXTEND", "REMA", "NoFade", "ENDA"]
    body = "".join(f"    {line}\n" for line in lines)
    return f"CONST_DATA EventListScr {name}[] = {{\n{body}}};\n\n"


def talk_script(name: str, message: int, recruit: str | None) -> str:
    """Event script of a conversation started with "Talk", as the game writes them
    (EventScr_Ch2_Talk_RossGarcia): the message, then `recruit` joins the player's army."""
    lines = ["STAL(33)", "TEXTSTART", f"TEXTSHOW(0x{message:X})", "TEXTEND", "REMA"]
    if recruit:
        lines = [f"MUSS(0x{RECRUIT_MUSIC:X})"] + lines + ["MURE(0x2)", f"CUSA({recruit})"]
    lines += ["NoFade", "ENDA"]
    body = "".join(f"    {line}\n" for line in lines)
    return f"CONST_DATA EventListScr {name}[] = {{\n{body}}};\n\n"
