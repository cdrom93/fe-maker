"""The game's instruments as the browser's song preview plays them (ui/src/lib/songplayer.ts).

A song is played with a voicegroup (sound/voicegroups/voicegroupNNN.s, chosen by mid2agb's -G in songs.mk): 128
voices of 12 bytes, one per MIDI program. Voicegroups lie end to end in the ROM, and a short one (a drum kit) reads
on into the next: voices are found by address (the "@ 0x..." comments), not by file. Voice kinds: sampled
(voice_directsound, resampled to the note, or _no_resample at the sample's own rate), GB square waves, GB
programmable wave (16 bytes, 32 4-bit steps), GB noise, and voice_keysplit_all (a drum kit: the note picks the voice
of another voicegroup, played at that voice's own key). Samples are AIFF files (sound/direct_sound_samples/, named by
sound/direct_sound_data.s), sent to the browser as WAV.
"""

from __future__ import annotations

import io
import math
import re
import struct
import wave
from functools import lru_cache
from pathlib import Path

VOICEGROUP_DIR = "sound/voicegroups"
SAMPLES_FILE = "sound/direct_sound_data.s"
WAVES_FILE = "sound/programmable_wave_data.s"
VOICE_SIZE = 12

_KINDS = {"voice_directsound": "sample", "voice_directsound_alt": "sample", "voice_directsound_no_resample": "fixed",
          "voice_square_1": "square", "voice_square_1_alt": "square", "voice_square_2": "square",
          "voice_square_2_alt": "square", "voice_programmable_wave": "wave", "voice_programmable_wave_alt": "wave",
          "voice_noise": "noise", "voice_noise_alt": "noise", "voice_keysplit_all": "drums", "voice_keysplit": "split"}


class InstrumentError(Exception):
    pass


def _numbers(args: list[str]) -> list[int]:
    return [int(a, 0) for a in args]


def parse_voice(macro: str, args: list[str]) -> dict:
    """One voice line, as the preview plays it (envelope values as in the game: 0-255 sampled, 0-15 GB)."""
    kind = _KINDS.get(macro)
    if kind in ("sample", "fixed"):
        key, pan, sample = int(args[0], 0), int(args[1], 0), args[2]
        a, d, s, r = _numbers(args[3:7])
        return {"kind": kind, "key": key, "pan": pan, "sample": sample.removeprefix("DirectSoundData_"),
                "env": [a, d, s, r]}
    if kind == "square":
        values = _numbers(args)
        duty = values[1] if macro.startswith("voice_square_1") else values[0]
        return {"kind": "square", "key": 60, "pan": 0, "duty": duty & 3, "env": values[-4:]}
    if kind == "wave":
        return {"kind": "wave", "key": 60, "pan": 0, "wave": args[0], "env": _numbers(args[1:5])}
    if kind == "noise":
        values = _numbers(args)
        return {"kind": "noise", "key": values[0], "pan": values[1], "period": values[3] & 1, "env": values[4:8]}
    if kind == "drums":
        return {"kind": "drums", "group": args[0]}
    return {"kind": "none"}


_VOICE_LINE = re.compile(r"^\s*(voice_\w+)\s+([^@\n]*?)\s*@\s*([0-9A-Fa-f]{8})", re.MULTILINE)
_LABEL_LINE = re.compile(r"^(voicegroup\w+):\s*@\s*0x([0-9A-Fa-f]{8})", re.MULTILINE)


@lru_cache(maxsize=4)
def _bank(decomp_dir: Path) -> tuple[dict[int, dict], dict[str, int]]:
    """Every voice of every voicegroup by ROM address, and each voicegroup label's address."""
    voices: dict[int, dict] = {}
    labels: dict[str, int] = {}
    for path in sorted((decomp_dir / VOICEGROUP_DIR).glob("*.s")):
        text = path.read_text(encoding="utf-8")
        for m in _LABEL_LINE.finditer(text):
            labels[m.group(1)] = int(m.group(2), 16)
        for m in _VOICE_LINE.finditer(text):
            args = [a.strip() for a in m.group(2).split(",")]
            voices[int(m.group(3), 16)] = parse_voice(m.group(1), args)
    return voices, labels


def voicegroup(decomp_dir: Path, number: int, changed: dict[int, dict] | None = None) -> list[dict]:
    """The 128 voices of voicegroupNNN, a drum kit's own 128 voices inlined ("voices"); `changed`: voices by address
    the project replaces (nimap.drumfix_bank)."""
    voices, labels = _bank(decomp_dir)
    if changed:
        voices = {**voices, **changed}
    start = labels.get(f"voicegroup{number:03d}")
    if start is None:
        raise InstrumentError("unknownVoicegroup")

    def at(base: int, index: int) -> dict:
        return voices.get(base + VOICE_SIZE * index, {"kind": "none"})

    out = []
    for program in range(128):
        voice = dict(at(start, program))
        if voice["kind"] == "drums":
            base = labels.get(voice["group"])
            kit = [at(base, key) if base is not None else {"kind": "none"} for key in range(128)]
            voice["voices"] = [v if v["kind"] != "drums" else {"kind": "none"} for v in kit]
        out.append(voice)
    return out


def voicegroup_numbers(decomp_dir: Path) -> list[int]:
    return sorted(int(m.group(1)) for p in (decomp_dir / VOICEGROUP_DIR).glob("voicegroup*.s")
                  if (m := re.fullmatch(r"voicegroup(\d+)\.s", p.name)))


def _labelled_files(decomp_dir: Path, rel: str, directive: str) -> dict[str, str]:
    text = (decomp_dir / rel).read_text(encoding="utf-8")
    return {m.group(1): m.group(2) for m in
            re.finditer(rf"^\s*(\w+):[^\n]*\n\s*{directive}\s+\"([^\"]+)\"", text, re.MULTILINE)}


@lru_cache(maxsize=4)
def _sample_files(decomp_dir: Path) -> dict[str, str]:
    return {label.removeprefix("DirectSoundData_"): path.removesuffix(".bin") + ".aif"
            for label, path in _labelled_files(decomp_dir, SAMPLES_FILE, ".incbin").items()}


def _extended(raw: bytes) -> float:
    """An AIFF 80-bit float (the sample rate)."""
    exponent, mantissa = struct.unpack(">HQ", raw)
    if not mantissa:
        return 0.0
    return math.ldexp(mantissa, (exponent & 0x7FFF) - 16383 - 63) * (-1 if exponent & 0x8000 else 1)


def read_aif(data: bytes) -> dict:
    """{"rate", "bits", "frames", "loop": start frame or None, "pcm": signed bytes} of a mono AIFF (as aif2pcm)."""
    if data[:4] != b"FORM" or data[8:12] not in (b"AIFF", b"AIFC"):
        raise InstrumentError("notAnAif")
    pos, info, markers, loop_id, pcm = 12, None, {}, None, b""
    while pos + 8 <= len(data):
        name, size = data[pos:pos + 4], struct.unpack(">I", data[pos + 4:pos + 8])[0]
        body = data[pos + 8:pos + 8 + size]
        if name == b"COMM":
            channels, frames, bits = struct.unpack(">HIH", body[:8])
            info = {"rate": _extended(body[8:18]), "bits": bits, "frames": frames}
        elif name == b"MARK":
            count, p = struct.unpack(">H", body[:2])[0], 2
            for _ in range(count):
                marker, position, length = struct.unpack(">HIB", body[p:p + 7])
                markers[marker] = position
                p += 7 + length + (1 - length % 2)   # pascal string padded to an even size
        elif name == b"INST" and len(body) >= 14:
            mode, begin = struct.unpack(">HH", body[8:12])
            if mode:
                loop_id = begin
        elif name == b"SSND":
            offset = struct.unpack(">I", body[:4])[0]
            pcm = body[8 + offset:]
        pos += 8 + size + (size & 1)
    if info is None:
        raise InstrumentError("notAnAif")
    if info["bits"] == 16:   # kept as 8-bit, as aif2pcm does
        pcm = bytes(pcm[i] for i in range(0, len(pcm) - 1, 2))
    info["pcm"] = pcm[:info["frames"]]
    info["loop"] = markers.get(loop_id) if loop_id is not None else None
    return info


def sample_info(decomp_dir: Path, name: str) -> dict:
    files = _sample_files(decomp_dir)
    if name not in files or not (decomp_dir / files[name]).is_file():
        raise InstrumentError("unknownSample")
    return read_aif((decomp_dir / files[name]).read_bytes())


def to_wav(info: dict) -> bytes:
    """8-bit WAV (unsigned samples) at the sample's own rate."""
    out = io.BytesIO()
    with wave.open(out, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(1)
        w.setframerate(max(3000, round(info["rate"])))
        w.writeframes(bytes((b + 128) & 0xFF for b in info["pcm"]))
    return out.getvalue()


@lru_cache(maxsize=4)
def waves(decomp_dir: Path) -> dict[str, list[int]]:
    """GB programmable waves: 32 steps of 0-15 each."""
    out = {}
    for label, rel in _labelled_files(decomp_dir, WAVES_FILE, ".incbin").items():
        path = decomp_dir / rel
        if path.is_file():
            out[label] = [n for b in path.read_bytes()[:16] for n in (b >> 4, b & 15)]
    return out
