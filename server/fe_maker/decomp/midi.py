"""Standard MIDI files read into what the browser's song preview plays (ui/src/lib/songplayer.ts).

Only what mid2agb (the decomp's MIDI converter) turns into game music is kept, grouped by MIDI channel as mid2agb
does (one game track per channel): notes, program changes, volume (CC7), pan (CC10), pitch bend and its range
(CC20, mid2agb's BENDR), tempo changes, and the loop markers "[" and "]" (text or marker events).
"""

from __future__ import annotations

import struct


class MidiError(Exception):
    pass


def _varlen(data: bytes, pos: int, signed: bool = False) -> tuple[int, int]:
    """A variable-length number, read as mid2agb does: no length limit, kept to 32 bits. The decomp's MIDI files
    use that for negative delta times (a tempo moved back to the start)."""
    value = 0
    while True:
        if pos >= len(data):
            raise MidiError("truncated")
        byte = data[pos]
        pos += 1
        value = ((value << 7) | (byte & 0x7F)) & 0xFFFFFFFF
        if not byte & 0x80:
            if signed and value & 0x80000000:
                value -= 1 << 32
            return value, pos


def read(data: bytes) -> dict:
    """{"division", "tempos": [[tick, µs per beat]], "loop": [start, end] | None, "end": tick,
    "channels": {channel: [[tick, "n", key, velocity, length] | [tick, "p", program] | [tick, "c", cc, value]
    | [tick, "b", bend -8192..8191]]}}, events sorted by tick."""
    if not data.startswith(b"MThd") or len(data) < 14:
        raise MidiError("notAMidi")
    _, tracks, division = struct.unpack(">HHH", data[8:14])
    if division & 0x8000:
        raise MidiError("smpteTime")
    pos = 8 + struct.unpack(">I", data[4:8])[0]
    tempos: list[list[int]] = []
    loop_start = loop_end = None
    end = 0
    channels: dict[int, list[list]] = {}
    for _ in range(tracks):
        if data[pos:pos + 4] != b"MTrk":
            break
        size = struct.unpack(">I", data[pos + 4:pos + 8])[0]
        pos += 8
        track_end = min(pos + size, len(data))
        tick, status = 0, 0
        playing: dict[tuple[int, int], list] = {}
        while pos < track_end:
            delta, pos = _varlen(data, pos, signed=True)
            tick = max(tick + delta, 0)
            byte = data[pos]
            if byte >= 0xF0:   # meta and system events keep the running status, as in mid2agb
                pos += 1
            elif byte & 0x80:
                status = byte
                pos += 1
            elif not status:
                raise MidiError("noStatus")
            if byte == 0xFF:
                kind = data[pos]
                length, pos = _varlen(data, pos + 1)
                body = data[pos:pos + length]
                pos += length
                if kind == 0x51 and length == 3:
                    tempos.append([tick, int.from_bytes(body, "big")])
                elif 1 <= kind <= 7:
                    text = body.decode("latin-1").strip()
                    if text in ("[", "]["):
                        loop_start = tick if loop_start is None else loop_start
                    if text in ("]", "]["):
                        loop_end = tick
                elif kind == 0x2F:
                    break
                continue
            if byte in (0xF0, 0xF7):
                length, pos = _varlen(data, pos)
                pos += length
                continue
            kind, channel = status & 0xF0, status & 0x0F
            if kind in (0xC0, 0xD0):
                a, b = data[pos], 0
                pos += 1
            else:
                a, b = data[pos], data[pos + 1]
                pos += 2
            events = channels.setdefault(channel, [])
            if kind == 0x90 and b:
                note = [tick, "n", a, b, 0]
                playing.setdefault((channel, a), []).append(note)
                events.append(note)
            elif kind in (0x80, 0x90):
                started = playing.get((channel, a))
                if started:
                    note = started.pop(0)
                    note[4] = tick - note[0]
            elif kind == 0xB0 and a in (7, 10, 20):
                events.append([tick, "c", a, b])
            elif kind == 0xC0:
                events.append([tick, "p", a])
            elif kind == 0xE0:
                events.append([tick, "b", ((b << 7) | a) - 8192])
        for started in playing.values():
            for note in started:
                note[4] = max(tick - note[0], 1)
        end = max(end, tick)
        pos = track_end
    for events in channels.values():
        events.sort(key=lambda e: e[0])
    loop = [loop_start, loop_end] if loop_start is not None and loop_end and loop_end > loop_start else None
    return {"division": division, "tempos": sorted(tempos) or [[0, 500000]], "loop": loop, "end": end,
            "channels": {c: e for c, e in sorted(channels.items()) if e}}
