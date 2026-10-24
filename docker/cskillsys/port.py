"""Port FE8U C-SkillSys (https://github.com/FireEmblemUniverse/fe8u-cskillsys, MIT) onto a ROM built
from the decomp by FE Maker (prototype, ticket 27).

C-SkillSys is written for the original ROM: its C code links against FE-CLib-Mokha's reference
(symbol addresses of the original game, generated from the decomp's ELF), and its Event Assembler
files patch the game at fixed offsets (ORG $17e34, BL(0x16B28), PROTECT ..., #define ... 0x59D1F0).
FE Maker's ROM has the same engine code, moved: each address of the original game is translated to
the same symbol + offset in our build, read from both ELF files (the original game built from the
unmodified decomp, and the project's build).

Usage (in the fe-maker-cskillsys image):
    python3 port.py vanilla.elf ours.elf <C-SkillSys tree> [vanilla.gba]
rewrites the tree in place (a copy) and prints every translation.
"""

from __future__ import annotations

import bisect
import re
import sys
from pathlib import Path

ROM = 0x08000000
ROM_END = 0x0A000000
FREE_MIN = 0x1000   # a gap this long after a label of size 0 is free space
# Where C-SkillSys gets its free space in our ROM: after 16 MB (the decomp's ROM is 16 MB at most
# while FE Maker keeps to the original data sizes; checked by the build).
FREE_SPACE = {"FreeSpaceCommon": 0x1000000, "FreeSpaceFont": 0x10E0000, "FreeSpaceDEMO": 0x1200000}


class PortError(Exception):
    pass


def elf_symbols(path: Path) -> list[tuple[int, int, str, bool]]:
    """ROM symbols of an ELF: (address without the thumb bit, size, name, is a function)."""
    from elftools.elf.elffile import ELFFile
    from elftools.elf.sections import SymbolTableSection

    out = []
    with open(path, "rb") as f:
        table = ELFFile(f).get_section_by_name(".symtab")
        if not isinstance(table, SymbolTableSection):
            raise PortError(f"{path}: no symbol table")
        for sym in table.iter_symbols():
            name, value = sym.name, sym.entry.st_value
            if not name or "$" in name or "." in name or not ROM <= value < ROM_END:
                continue
            out.append((value & ~1, sym.entry.st_size, name, sym.entry.st_info.type == "STT_FUNC"))
    return out


class Translator:
    """Original-game address -> our build's address, through the symbol holding it."""

    def __init__(self, vanilla: list[tuple[int, int, str, bool]], ours: list[tuple[int, int, str, bool]],
                 vanilla_rom: bytes = b""):
        self.vanilla = sorted(vanilla)
        self.starts = [s[0] for s in self.vanilla]
        # start of the next symbol at another address, for each symbol
        self.next_start = [ROM_END] * len(self.vanilla)
        following = ROM_END
        for k in range(len(self.vanilla) - 1, -1, -1):
            self.next_start[k] = following
            if k and self.starts[k - 1] != self.starts[k]:
                following = self.starts[k]
        self.start_of = {name: start for start, _z, name, _f in self.vanilla}
        self.ours = {name: (addr, size) for addr, size, name, _f in ours}
        # Free space of the original ROM: a label of size 0 followed by a long run of 0x00 or 0xFF
        # (the padding before data at fixed addresses, like banim_number at 0x08C00000). Patches put
        # there stay where they are, as long as our build's data does not reach them.
        self.free: list[tuple[int, int, str]] = []
        for k, (start, size, name, _f) in enumerate(self.vanilla):
            nxt = self.next_start[k]
            if size or nxt - start < FREE_MIN or not vanilla_rom:
                continue
            # the padding starts after the label's data: look for the run of filler bytes before nxt
            body = vanilla_rom[start - ROM:nxt - ROM]
            filler = body[-1:] if body[-1:] in (bytes([0]), bytes([0xFF])) else b""
            run = len(body) - len(body.rstrip(filler)) if filler else 0
            if run >= FREE_MIN:
                self.free.append((nxt - run, nxt, name))
        self.log: list[str] = []
        self.conflicts: list[str] = []

    def holder(self, addr: int) -> tuple[int, int, str] | None:
        """The original symbol holding the address: the closest one starting at or before it whose
        size reaches it (a symbol of size 0 holds up to the next one), preferring those our build
        has too. Small labels inside a function (jump tables, literal pools) do not hide it."""
        i = bisect.bisect_right(self.starts, addr) - 1
        candidates = []
        for k in range(i, max(-1, i - 400), -1):
            start, size, name, _f = self.vanilla[k]
            if addr - start > 0x10000:
                break
            nxt = self.next_start[k]
            if addr < start + (size or nxt - start):
                candidates.append((start, size, name))
        if not candidates:
            return None
        closest = max(c[0] for c in candidates)
        found = [c for c in candidates if c[2] in self.ours]
        same = [c for c in found if c[0] == closest]
        return (same or found or candidates)[0]

    def translate(self, addr: int, where: str = "") -> int:
        """`addr`: an absolute ROM address (0x08......) or a ROM offset; returns the same kind."""
        absolute = addr >= ROM
        full = addr if absolute else addr + ROM
        thumb = full & 1
        for start, end, name in self.free:
            if start <= full < end:
                if name in self.ours and full < self.ours[name][0] + (start - self.start_of[name]):
                    self.conflicts.append(f"{where}: {addr:#x} is free space of the original game that this build uses")
                return addr
        hold = self.holder(full & ~1)
        if hold is None:
            self.conflicts.append(f"{where}: {addr:#x} is in no symbol of the original game")
            return addr
        start, size, name = hold
        if name not in self.ours:
            self.conflicts.append(f"{where}: {addr:#x} is in {name}, missing from this build")
            return addr
        new_start, new_size = self.ours[name]
        offset = (full & ~1) - start
        if offset and size and new_size != size:
            self.conflicts.append(f"{where}: {addr:#x} is {name}+{offset:#x}, and {name} changed size "
                                  f"({size:#x} -> {new_size:#x}): FE Maker rewrites it")
        new = new_start + offset + thumb
        if new != full:
            self.log.append(f"{where}: {addr:#x} ({name}+{offset:#x}) -> {new if absolute else new - ROM:#x}")
        return new if absolute else new - ROM

    def translate_end(self, end: int, where: str = "") -> int:
        """The end (excluded) of a range: the end of a function is often after its alignment
        padding, held by no symbol; the last bytes held before it give the move."""
        absolute = end >= ROM
        full = end if absolute else end + ROM
        for back in (1, 2, 3, 4):
            hold = self.holder((full - back) & ~1)
            if hold and hold[2] in self.ours:
                new = self.ours[hold[2]][0] + (full - hold[0])
                return new if absolute else new - ROM
        return self.translate(end - 1, where) + 1

    def ref_source(self, reference: str) -> str:
        """FE-CLib-Mokha's reference (fireemblem8.ref.s) with our build's addresses."""
        def line(m: re.Match) -> str:
            kind, value, name = m.group(1), int(m.group(2), 16), m.group(3)
            if not ROM <= value < ROM_END:
                return m.group(0)   # RAM: FE Maker does not move it
            return f"{kind} 0x{self.translate(value, 'ref ' + name):08X}, {name}"
        return re.sub(r"^(fun|dat) 0x([0-9A-Fa-f]+), (\w+)$", line, reference, flags=re.M)

    def sym_source(self, sym: str) -> str:
        """The same for fireemblem8.sym (address name per line, used to protect hooked functions)."""
        def line(m: re.Match) -> str:
            value = int(m.group(1), 16)
            if not ROM <= value < ROM_END:
                return m.group(0)
            return f"{self.translate(value, 'sym ' + m.group(2)):08X} {m.group(2)}"
        return re.sub(r"^([0-9A-Fa-f]{8}) (\w+)$", line, sym, flags=re.M)


# Event Assembler places that hold ROM offsets: ORG x, PROTECT x y, BL(x), B(x), jumpToHack(x),
# POIN x, WORD/POIN of absolute pointers, and #define NAME x with a ROM-sized value.
HEX = r"(?:\$|0x)[0-9A-Fa-f]+"
# The second number of PROTECT is an end (excluded): its last byte is translated.
PROTECT_END = re.compile(rf"(\bPROTECT\s+{HEX}\s+)({HEX})")
EVENT_PATTERNS = [
    re.compile(rf"(\bORG\s+)({HEX})"),
    re.compile(rf"(\bPROTECT\s+)({HEX})"),
    PROTECT_END,
    re.compile(rf"(\b(?:BL|B|BLH|jumpToHack|callHack_r[0-9]|SHORT_BL)\s*\(\s*)({HEX})"),
    re.compile(rf"(#define\s+\w+\s+)({HEX})(?=\s*(?://.*)?$)", re.M),
    re.compile(rf"(\b(?:POIN|WORD)\s+(?:{HEX}\s+)*)((?:\$|0x)0?8[0-9A-Fa-f]{{6}})\b"),
]


def _value(text: str) -> int:
    return int(text[1:], 16) if text.startswith("$") else int(text, 16)


def _rom_like(value: int) -> bool:
    """A ROM offset or address worth translating (not a small constant)."""
    return 0x200 <= value < 0x1000000 or ROM + 0x200 <= value < ROM + 0x1000000


def port_event_text(text: str, tr: Translator, where: str) -> str:
    for pattern in EVENT_PATTERNS:
        def sub(m: re.Match, end: bool = pattern is PROTECT_END) -> str:
            raw = m.group(2)
            value = _value(raw)
            if not _rom_like(value):
                return m.group(0)
            new = tr.translate_end(value, where) if end else tr.translate(value, where)
            return m.group(1) + (f"${new:X}" if raw.startswith("$") else f"0x{new:X}")
        text = pattern.sub(sub, text)
    return text


def port_memmap(text: str) -> str:
    """Free space of include/configs/config-memmap.h moved after our ROM's 16 MB."""
    for name, value in FREE_SPACE.items():
        text = re.sub(rf"(#define {name}\s+)0x[0-9A-Fa-f]+", lambda m, v=value: f"{m.group(1)}0x{v:X}", text)
    return text


def port_tree(root: Path, tr: Translator) -> None:
    for path in sorted(root.rglob("*")):
        if not path.is_file() or path.suffix.lower() not in (".event", ".txt"):
            continue
        if "Texts" in path.parts or "EfxAnim" in path.parts:
            continue
        text = path.read_text(encoding="utf-8", errors="surrogateescape")
        new = port_event_text(text, tr, str(path.relative_to(root)))
        if new != text:
            path.write_text(new, encoding="utf-8", errors="surrogateescape", newline="")
    memmap = root / "include/configs/config-memmap.h"
    memmap.write_text(port_memmap(memmap.read_text(encoding="utf-8")), encoding="utf-8", newline="")
    ref_dir = root / "Tools/FE-CLib-Mokha/reference"
    for name, fn in (("fireemblem8.ref.s", tr.ref_source), ("fireemblem8.sym", tr.sym_source)):
        path = ref_dir / name
        path.write_text(fn(path.read_text(encoding="utf-8")), encoding="utf-8", newline="")


def main(args: list[str]) -> int:
    vanilla, ours, root = Path(args[0]), Path(args[1]), Path(args[2])
    rom = Path(args[3]).read_bytes() if len(args) > 3 else b""
    tr = Translator(elf_symbols(vanilla), elf_symbols(ours), rom)
    port_tree(root, tr)
    print("\n".join(tr.log))
    print(f"[port] {len(tr.log)} addresses moved, {len(tr.conflicts)} conflicts")
    for c in tr.conflicts:
        print("[conflict]", c)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
