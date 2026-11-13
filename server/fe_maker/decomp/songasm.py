"""Songs written in the game's music assembly (mid2agb's output, the .s files of FE-Repo-Music) turned back into
MIDI files, so they are stored, heard and built as the project's imported MIDI songs are (music.py, midi.py).

The assembly is the m4a engine's track language (include/MPlayDef.s): waits Wnn, notes Nnn / TIE / EOT with
running status, VOICE, VOL, PAN, BEND, BENDR, MOD, LFOS, MODT, TUNE, LFODL, PRIO, XCMD, TEMPO, KEYSH, and
GOTO / PATT / PEND / FINE for loops and patterns. Each command becomes the MIDI event mid2agb turns back into it
(tools/mid2agb/agb.cpp), at 24 ticks a beat, the engine's own clock; GOTO becomes the loop markers "[" and "]".
"""

from __future__ import annotations

import ast
import operator
import re
import struct

DIVISION = 24   # the engine counts 96 clocks a whole note
MAX_TRACKS = 16
_MAX_STEPS = 400_000
_NOTE_NAMES = {"Cn": 0, "Cs": 1, "Dn": 2, "Ds": 3, "En": 4, "Fn": 5, "Fs": 6, "Gn": 7, "Gs": 8, "An": 9, "As": 10,
               "Bn": 11}
_NOTE_RE = re.compile(r"(Cn|Cs|Dn|Ds|En|Fn|Fs|Gn|Gs|An|As|Bn)(M?)(\d)")
# Commands taking values, and the MIDI controller mid2agb reads each one from (agb.cpp, PrintControllerOp).
_CONTROLLERS = {"MOD": 1, "VOL": 7, "PAN": 10, "BENDR": 20, "LFOS": 21, "MODT": 22, "TUNE": 24, "LFODL": 26,
                "PRIO": 33}
_SKIPPED = {"MEMACC": 3, "REPT": 1}   # read, not played
_OPS = {ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul}


class SongAsmError(Exception):
    pass


def _key(name: str) -> int | None:
    m = _NOTE_RE.fullmatch(name)
    if not m:
        return None
    octave = -int(m.group(3)) if m.group(2) else int(m.group(3))
    return 12 * (octave + 2) + _NOTE_NAMES[m.group(1)]


def _evaluate(text: str, names: dict[str, int]) -> int:
    """An assembler expression of numbers, known names and + - * / (integer division, as the assembler does)."""
    def value(node) -> int:
        if isinstance(node, ast.Constant) and isinstance(node.value, int):
            return node.value
        if isinstance(node, ast.Name):
            if node.id in names:
                return names[node.id]
            key = _key(node.id)
            if key is not None:
                return key
            m = re.fullmatch(r"v(\d{1,3})|gtp(\d)", node.id)
            if m:
                return int(m.group(1) or m.group(2))
            raise SongAsmError(f"unknown name {node.id}")
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.USub):
            return -value(node.operand)
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.UAdd):
            return value(node.operand)
        if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Div):
            a, b = value(node.left), value(node.right)
            if b == 0:
                raise SongAsmError("division by zero")
            return int(a / b)
        if isinstance(node, ast.BinOp) and type(node.op) in _OPS:
            return _OPS[type(node.op)](value(node.left), value(node.right))
        raise SongAsmError(f"unreadable value {text}")
    text = re.sub(r"\b0x([0-9a-fA-F]+)\b", lambda m: str(int(m.group(1), 16)), text.strip())
    try:
        return value(ast.parse(text, mode="eval").body)
    except SyntaxError as e:
        raise SongAsmError(f"unreadable value {text}") from e


def _plain_names(source: str) -> str:
    """Songs named after files with dashes ("Knight_of_the_Wind-1") have them in every label: they become
    underscores (dots too), so that "-" is only ever a minus."""
    for name in set(re.findall(r"\.global\s+(\S+)", source)):
        if not re.fullmatch(r"[A-Za-z_]\w*", name):
            source = source.replace(name, re.sub(r"\W", "_", name))
    return source


def _statements(source: str) -> tuple[list[tuple[str, list[str]]], dict[str, int], dict[str, str]]:
    """The file's .byte / .word lines in order (directive, comma-separated arguments), each label's position and
    the .equ definitions."""
    source = _plain_names(source)
    statements: list[tuple[str, list[str]]] = []
    labels: dict[str, int] = {}
    equs: dict[str, str] = {}
    for raw in source.splitlines():
        line = raw.split("@", 1)[0].strip()
        while True:
            m = re.match(r"([A-Za-z_.$][\w.$]*):\s*", line)
            if not m:
                break
            labels[m.group(1)] = len(statements)
            line = line[m.end():]
        if not line:
            continue
        m = re.match(r"\.(byte|word|equ|set)\s+(.*)$", line)
        if not m:
            continue
        directive, rest = m.groups()
        args = [a.strip() for a in rest.split(",")]
        if directive in ("equ", "set"):
            if len(args) >= 2:
                equs[args[0]] = ",".join(args[1:]).strip()
        else:
            statements.append((directive, [a for a in args if a]))
    return statements, labels, equs


def _names(equs: dict[str, str]) -> dict[str, int]:
    """Values of the song's .equ names, the volume read as the engine's maximum (the song keeps its own as the
    imported song's volume)."""
    names = {"c_v": 64, "mxv": 127}
    for name, text in equs.items():
        if name.endswith("_mvl"):
            names[name] = 127
        elif name.endswith("_grp"):
            names[name] = 0
    for _ in range(3):
        for name, text in equs.items():
            if name not in names:
                try:
                    names[name] = _evaluate(text, names)
                except SongAsmError:
                    pass
    return names


def song_volume(source: str) -> int:
    """The song's master volume (its _mvl), 127 when it has none."""
    _, _, equs = _statements(source)
    for name, text in equs.items():
        if name.endswith("_mvl"):
            try:
                return max(0, min(127, _evaluate(text, {})))
            except SongAsmError:
                break
    return 127


def _header(statements, labels, source: str) -> list[str]:
    """The song's track labels, read from its header (`.global song`, then .byte counts and .word pointers)."""
    m = re.search(r"\.global\s+(\w+)", source)
    names = [m.group(1)] if m and m.group(1) in labels else []
    names += [n for n in labels if n not in names]
    for name in names:
        tracks = []
        for directive, args in statements[labels[name]:]:
            if directive == "word":
                tracks += [a for a in args if a in labels and not a.endswith("_grp")]
            elif tracks:
                break
        if tracks:
            return tracks[:MAX_TRACKS]
    raise SongAsmError("noTracks")


def _play(statements, labels, start: int, names: dict[str, int]) -> dict:
    """One track run from its label: {"events": [(tick, order, bytes)], "end", "loop": (start, end) | None}."""
    events: list[tuple[int, int, bytes]] = []
    times: dict[int, int] = {}
    stack: list[int] = []
    tick, pos, steps = 0, start, 0
    command, key, velocity, length = "", 60, 127, 0
    transpose = 0
    notes: list[list[int]] = []   # [start, key, velocity, end]
    ties: dict[int, list[int]] = {}
    loop = None

    def note(k: int, at: int, duration: int | None) -> None:
        k = max(0, min(127, k + transpose))
        notes.append([at, k, max(1, min(127, velocity)), at + (duration or 0)])
        if duration is None:
            ties.setdefault(k, notes[-1])

    while pos < len(statements):
        steps += 1
        if steps > _MAX_STEPS:
            raise SongAsmError("tooLong")
        times.setdefault(pos, tick)
        directive, args = statements[pos]
        pos += 1
        if directive == "word":
            continue
        if not args:
            continue
        spaced = re.fullmatch(r"([A-Z][A-Z0-9]*)\s+(\S.*)", args[0])   # "MOD 0": mid2agb writes some without a comma
        if spaced:
            args = [spaced.group(1), spaced.group(2), *args[1:]]
        head = args[0].replace(" ", "")
        if re.fullmatch(r"W\d\d", head):
            tick += int(head[1:])
            continue
        if head == "FINE":
            break
        if head in ("GOTO", "PATT"):
            target = statements[pos][1][0] if pos < len(statements) and statements[pos][0] == "word" else ""
            pos += 1
            if target not in labels:   # a few songs jump to a label they lost: the track stops there
                break
            if head == "PATT":
                if len(stack) > 8:
                    raise SongAsmError("patternDepth")
                stack.append(pos)
                pos = labels[target]
                continue
            loop_start = times.get(labels[target])
            if loop_start is not None and tick > loop_start:
                loop = (loop_start, tick)
            break
        if head == "PEND":
            if stack:
                pos = stack.pop()
            continue
        values = args
        if head in ("TEMPO", "KEYSH", "PRIO"):   # below VOICE (0xbd): the engine keeps the running status as it was
            value = _evaluate(args[1], names) if len(args) > 1 else 0
            if head == "TEMPO":
                events.append((tick, -1, b"T" + struct.pack(">I", max(1, 60_000_000 // max(1, 2 * value)))))
            elif head == "KEYSH":
                transpose = value
            else:
                events.append((tick, 1, bytes([0xB0, _CONTROLLERS["PRIO"], max(0, min(127, value))])))
            continue
        if re.fullmatch(r"N\d\d|TIE|EOT|[A-Z]{3,6}", head):
            command = head
            values = args[1:]
        if command in _SKIPPED:
            continue
        if re.fullmatch(r"N\d\d", command) or command in ("TIE", "EOT"):
            numbers = [_evaluate(v, names) for v in values]
            if numbers:
                key = numbers[0]
            if len(numbers) > 1:
                velocity = numbers[1]
            extra = numbers[2] if len(numbers) > 2 else 0
            if command == "EOT":
                k = max(0, min(127, (numbers[0] if numbers else key) + transpose))
                if not numbers and ties:
                    k = next(reversed(ties))
                if k in ties:
                    ties.pop(k)[3] = tick
            elif command == "TIE":
                note(key, tick, None)
            else:
                length = int(command[1:]) + extra
                note(key, tick, length)
            continue
        if not values:
            continue
        value = _evaluate(values[0], names)
        if command == "VOICE":
            events.append((tick, 1, bytes([0xC0, value & 0x7F])))
        elif command in _CONTROLLERS:
            events.append((tick, 1, bytes([0xB0, _CONTROLLERS[command], max(0, min(127, value))])))
        elif command == "BEND":
            events.append((tick, 1, bytes([0xE0, 0, max(0, min(127, value))])))
        elif command == "XCMD" and len(values) > 1:
            kind = {"xIECV": 8, "xIECL": 9}.get(values[0].strip())
            if kind is not None:
                events.append((tick, 1, bytes([0xB0, 30, kind])))
                events.append((tick, 1, bytes([0xB0, 29, max(0, min(127, _evaluate(values[1], names)))])))
    for tied in ties.values():
        tied[3] = tick
    # A key struck again before its note ends ends it there: MIDI cannot tell overlapping notes of one key apart.
    last: dict[int, list[int]] = {}
    for n in sorted(notes, key=lambda n: n[0]):
        if n[1] in last and last[n[1]][3] > n[0]:
            last[n[1]][3] = n[0]
        last[n[1]] = n
    for start, k, v, stop in notes:
        if stop > start:
            events.append((start, 1, bytes([0x90, k, v])))
            events.append((stop, 0, bytes([0x80, k, 0])))
    end = max([tick, *(e[0] for e in events)])
    return {"events": events, "end": end, "loop": loop}


def _varlen(value: int) -> bytes:
    out = [value & 0x7F]
    value >>= 7
    while value:
        out.append(0x80 | (value & 0x7F))
        value >>= 7
    return bytes(reversed(out))


def _track(events: list[tuple[int, bytes]], end: int) -> bytes:
    body, last = b"", 0
    for tick, data in events:
        body += _varlen(tick - last) + data
        last = tick
    body += _varlen(max(0, end - last)) + b"\xff\x2f\x00"
    return b"MTrk" + struct.pack(">I", len(body)) + body


def to_midi(source: str) -> bytes:
    """The song as a standard MIDI file (format 1): a conductor track (tempos, loop markers), then one track per
    song track on its own channel, as mid2agb reads them back."""
    statements, labels, equs = _statements(source)
    names = _names(equs)
    tracks = [_play(statements, labels, labels[label], names)
              for label in _header(statements, labels, _plain_names(source))]
    if not any(any(e[2][0] == 0x90 for e in t["events"]) for t in tracks):
        raise SongAsmError("noNotes")
    end = max(t["end"] for t in tracks)
    loop = next((t["loop"] for t in tracks if t["loop"]), None)
    conductor: list[tuple[int, int, bytes]] = []
    for t in tracks:
        conductor += [e for e in t["events"] if e[1] == -1]
        t["events"] = [e for e in t["events"] if e[1] != -1]
    if not conductor:
        conductor.append((0, -1, b"T" + struct.pack(">I", 500000)))
    meta = [(tick, b"\xff\x51\x03" + data[2:]) for tick, _, data in sorted(conductor)]
    if loop:
        meta += [(loop[0], b"\xff\x06\x01["), (loop[1], b"\xff\x06\x01]")]
        end = max(end, loop[1])
    out = [_track(sorted(meta, key=lambda e: e[0]), end)]
    for channel, t in enumerate(tracks):
        events = sorted(t["events"], key=lambda e: (e[0], e[1]))
        out.append(_track([(tick, bytes([data[0] | channel]) + data[1:]) for tick, _, data in events], end))
    return b"MThd" + struct.pack(">IHHH", 6, 1, len(out), DIVISION) + b"".join(out)
