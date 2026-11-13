"""NIMAP2, the General MIDI instrument set of FE8 hacks (Alusq's revision of circleseverywhere's Native Instrument
Map, from FEBuilderGBA's patch SOUND_NIMAP2): 128 voices of 12 bytes in General MIDI order, pointing to the game's
own samples, waves and drum kits. Nothing new is heard: the game's instruments in the order MIDI files expect.

The table is downloaded once from FEBuilderGBA at a pinned commit (config_dir()/nimap). Its pointers are ROM
addresses: each one is named after the game's voice holding the same pointer, read from the user's ROM at the voices'
addresses (the "@ 0x..." comments of sound/voicegroups/), so the table becomes a voicegroup of the decomp
(voice_* macros, labels), written as a new voicegroupNNN at build when an imported song uses it.
"""

from __future__ import annotations

import re
import struct
import urllib.error
import urllib.request
from functools import lru_cache
from pathlib import Path

from ..config import config_dir
from . import instruments

KEY = "nimap"   # an imported song's "voicegroup" when it plays with NIMAP2
REPO = "FEBuilderGBA/FEBuilderGBA"
COMMIT = "677b39b729fd1ec2885c510782317f900f4bcef7"
URL = (f"https://raw.githubusercontent.com/{REPO}/{COMMIT}/FEBuilderGBA/bin/Debug/config/patch2/FE8U/SOUND_NIMAP2/"
       "FE8%20native%20instrument%20map%20(revised).bin")
SIZE = 128 * instruments.VOICE_SIZE
ROM_BASE = 0x08000000
LINKER_FILE = "linker_script_sound.txt"


class NimapError(Exception):
    pass


def table_path() -> Path:
    return config_dir() / "nimap" / COMMIT[:12] / "nimap2.bin"


def rom_path() -> Path:
    return config_dir() / "rom" / "baserom.gba"   # config.Settings.rom_path


def download() -> bytes:
    """The NIMAP2 table, downloaded once."""
    path = table_path()
    if path.is_file():
        return path.read_bytes()
    from ..ferepo import _ssl_context
    request = urllib.request.Request(URL, headers={"User-Agent": "FE-Maker"})
    try:
        with urllib.request.urlopen(request, timeout=30, context=_ssl_context()) as response:
            data = response.read(SIZE + 1)
    except (urllib.error.URLError, OSError) as e:
        raise NimapError("nimapUnreachable") from e
    if len(data) != SIZE:
        raise NimapError("nimapUnreachable")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return data


_VOICE_LINE = re.compile(r"^\s*(voice_\w+)\s+([^@\n]*?)\s*@\s*([0-9A-Fa-f]{8})", re.MULTILINE)
_POINTER_ARG = {"voice_directsound": 2, "voice_directsound_no_resample": 2, "voice_directsound_alt": 2,
                "voice_programmable_wave": 0, "voice_programmable_wave_alt": 0, "voice_keysplit_all": 0}


def _symbols(decomp_dir: Path, rom: bytes) -> dict[int, str]:
    """ROM address -> decomp label of the samples, waves and voicegroups the game's voices point to."""
    names: dict[int, str] = {}
    _voices, labels = instruments._bank(decomp_dir)
    for label, address in labels.items():
        names[address] = label
    for path in sorted((decomp_dir / instruments.VOICEGROUP_DIR).glob("*.s")):
        for m in _VOICE_LINE.finditer(path.read_text(encoding="utf-8")):
            arg = _POINTER_ARG.get(m.group(1))
            if arg is None:
                continue
            offset = int(m.group(3), 16) - ROM_BASE + 4
            if offset + 4 > len(rom):
                continue
            pointer = struct.unpack_from("<I", rom, offset)[0]
            names.setdefault(pointer, [a.strip() for a in m.group(2).split(",")][arg])
    return names


def _pointer(names: dict[int, str], pointer: int, starts: list[tuple[int, str]]) -> str:
    if pointer in names:
        return names[pointer]
    for start, label in starts:   # inside a voicegroup (a drum kit starting further on)
        if start <= pointer < start + 128 * instruments.VOICE_SIZE and (pointer - start) % instruments.VOICE_SIZE == 0:
            return f"{label} + {pointer - start}"
    raise NimapError(f"unknownPointer 0x{pointer:08X}")


def voice_lines(table: bytes, decomp_dir: Path, rom: bytes) -> list[str]:
    """The 128 voices of the table as the decomp's voice macros."""
    if len(table) != SIZE:
        raise NimapError("badTable")
    names = _symbols(decomp_dir, rom)
    starts = sorted((a, label) for a, label in names.items() if label.startswith("voicegroup"))
    lines = []
    for i in range(128):
        b = table[instruments.VOICE_SIZE * i: instruments.VOICE_SIZE * (i + 1)]
        kind, key, pan = b[0], b[1], (b[3] & 0x7F if b[3] & 0x80 else 0)
        pointer = struct.unpack_from("<I", b, 4)[0]
        a, d, s, r = b[8:12]
        if kind in (0, 8, 16):
            macro = {0: "voice_directsound", 8: "voice_directsound_no_resample", 16: "voice_directsound_alt"}[kind]
            lines.append(f"{macro} {key}, {pan}, {_pointer(names, pointer, starts)}, {a}, {d}, {s}, {r}")
        elif kind in (1, 9):
            lines.append(f"voice_square_1{'_alt' if kind == 9 else ''} {b[3]}, {b[4] & 3}, {a}, {d}, {s}, {r}")
        elif kind in (2, 10):
            lines.append(f"voice_square_2{'_alt' if kind == 10 else ''} {b[4] & 3}, {a}, {d}, {s}, {r}")
        elif kind in (3, 11):
            lines.append(f"voice_programmable_wave{'_alt' if kind == 11 else ''} {_pointer(names, pointer, starts)}, "
                         f"{a}, {d}, {s}, {r}")
        elif kind in (4, 12):
            lines.append(f"voice_noise{'_alt' if kind == 12 else ''} {key}, {pan}, {b[3] & 0x7F}, {b[4] & 1}, "
                         f"{a}, {d}, {s}, {r}")
        elif kind == 0x80:
            lines.append(f"voice_keysplit_all {_pointer(names, pointer, starts)}")
        else:
            raise NimapError(f"unknownVoice {kind}")
    return lines


def voicegroup_source(lines: list[str], number: int) -> str:
    body = "".join(f"\t{line}\n" for line in lines)
    return (f'\t.include "asm/macros/music_voice.inc"\n\n\t.section .rodata\n\n\t.align 4\n'
            f"\t@ FE Maker: NIMAP2 (General MIDI order, the game's instruments; Alusq, after circleseverywhere)\n"
            f"\t.global voicegroup{number:03d}\nvoicegroup{number:03d}:\n{body}")


@lru_cache(maxsize=2)
def _cached_lines(decomp_dir: Path, table_mtime: float, rom_mtime: float) -> tuple[str, ...]:
    return tuple(voice_lines(table_path().read_bytes(), decomp_dir, rom_path().read_bytes()))


def lines(decomp_dir: Path) -> list[str]:
    """NIMAP2's voices for this decomp: downloaded, then named with the user's ROM."""
    download()
    if not rom_path().is_file():
        raise NimapError("noRom")
    return list(_cached_lines(decomp_dir, table_path().stat().st_mtime, rom_path().stat().st_mtime))


def number(decomp_dir: Path) -> int:
    """The voicegroup number NIMAP2 takes at build: the one after the game's last."""
    return max(instruments.voicegroup_numbers(decomp_dir), default=-1) + 1


def build_files(decomp_dir: Path, linker: str) -> tuple[dict[str, str], str]:
    """The voicegroup file and the sound linker script (given as it stands) with its line."""
    n = number(decomp_dir)
    rel = f"{instruments.VOICEGROUP_DIR}/voicegroup{n:03d}.s"
    previous = f"{instruments.VOICEGROUP_DIR}/voicegroup{n - 1:03d}.o(.rodata);\n"
    if previous not in linker:
        raise NimapError("noVoicegroupLine")
    linker = linker.replace(previous, previous + f"{instruments.VOICEGROUP_DIR}/voicegroup{n:03d}.o(.rodata);\n", 1)
    return {rel: voicegroup_source(lines(decomp_dir), n)}, linker


def voices(decomp_dir: Path) -> list[dict]:
    """NIMAP2's 128 voices as the song preview plays them (instruments.voicegroup's format)."""
    bank, labels = instruments._bank(decomp_dir)
    out = []
    for line in lines(decomp_dir):
        macro, _, rest = line.partition(" ")
        voice = instruments.parse_voice(macro, [a.strip() for a in rest.split(",")])
        if voice["kind"] == "drums":
            label, _, offset = voice["group"].partition(" + ")
            base = labels.get(label)
            kit = [bank.get(base + int(offset or 0) + instruments.VOICE_SIZE * k, {"kind": "none"}) if base is not None
                   else {"kind": "none"} for k in range(128)]
            voice["voices"] = [v if v["kind"] != "drums" else {"kind": "none"} for v in kit]
        out.append(voice)
    return out
