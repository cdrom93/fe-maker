"""The assembly files' dependencies, as the decomp's scaninc tool finds them, for all files in one pass (ticket 30).

The decomp's Makefile runs `scaninc` once per assembly file (~370) every time make starts, even with nothing to
build: on Windows, starting a process is slow and that took about 19 of the 25 seconds of a build with no change.
This module does the same scan in Python (a port of scaninc's AsmFile and main, pret's tools, MIT, by YamaArashi;
CREDITS.md) and writes the result as a make file read by win.mk, make running with NODEP=1 (no scaninc)."""

from __future__ import annotations

import re
from pathlib import Path

DEPS_FILE = ".fem-asmdeps.mk"

# The Makefile's SFILES: its assembly sources (ASM_S_FILES, SRC_S_FILES, DATA_S_FILES, SOUND_S_FILES)
_GLOBS = ("asm/*.s", "data/*.s", "sound/*.s", "sound/songs/*.s", "sound/songs/mml/*.s", "sound/voicegroups/*.s")
_SRC_S = ("src/rom_header.s", "src/crt0.s", "src/m4a_1.s", "src/libagbsyscall.s")

_C_INCLUDE = re.compile(r'^[ \t]*#[ \t]*include[ \t]*"([^"\n]*)"', re.M)


def _asm_directives(text: str) -> tuple[list[str], list[str]]:
    """scaninc's AsmFile: `.include "x"` and `.incbin "x"` (or with #) at the start of a line, outside comments
    (`;` to the end of the line, `/* */`) and strings."""
    includes, incbins = [], []
    pos, size = 0, len(text)
    while pos < size:
        while pos < size and text[pos] in " \t":
            pos += 1
        if pos < size and text[pos] in ".#":
            pos += 1
            for name in ("incbin", "include"):
                if text.startswith(name, pos):
                    pos += len(name)
                    while pos < size and text[pos] in " \t":
                        pos += 1
                    if pos < size and text[pos] == '"':
                        end = text.find('"', pos + 1)
                        if end < 0:
                            end = size
                        (incbins if name == "incbin" else includes).append(text[pos + 1:end])
                        pos = end + 1
                    break
        while pos < size:   # the rest of the line
            c = text[pos]
            pos += 1
            if c == ";":
                end = text.find("\n", pos)
                pos = size if end < 0 else end + 1
                break
            if c == "/" and pos < size and text[pos] == "*":
                end = text.find("*/", pos + 1)
                pos = size if end < 0 else end + 2
            elif c == '"':
                while pos < size:
                    c = text[pos]
                    pos += 1
                    if c == '"':
                        break
                    if c == "\\":
                        pos += 1
            elif c == "\n":
                break
    return includes, incbins


def _directives(path: Path) -> tuple[list[str], list[str]]:
    text = path.read_bytes().decode("latin-1")
    if path.suffix in (".c", ".h", ".cpp"):
        return _C_INCLUDE.findall(text), []
    return _asm_directives(text)


def dependencies(work: Path, source: str, cache: dict | None = None) -> list[str]:
    """scaninc -I include -I "" <source>: the files it includes (found in include/, the working copy, then the
    including file's folder), recursively, and the files it incbins (as written)."""
    cache = {} if cache is None else cache
    found: set[str] = set()
    queue = [source]
    while queue:
        name = queue.pop(0)
        if name not in cache:
            cache[name] = _directives(work / name)
        includes, incbins = cache[name]
        folder = name.rsplit("/", 1)[0] + "/" if "/" in name else ""
        found.update(incbins)
        for include in includes:
            for prefix in ("include/", "", folder):
                path = prefix + include
                if (work / path).is_file():
                    if path not in found:
                        found.add(path)
                        queue.append(path)
                    break
    return sorted(found)


def sources(work: Path) -> list[str]:
    files = [p.relative_to(work).as_posix() for pattern in _GLOBS for p in sorted(work.glob(pattern))]
    return files + [s for s in _SRC_S if (work / s).is_file()]


def write(work: Path) -> int:
    """The make rules `x.o: deps...` of every assembly source into DEPS_FILE (rewritten only when they change);
    how many sources."""
    cache: dict = {}
    lines = []
    for source in sources(work):
        deps = dependencies(work, source, cache)
        lines.append(f"{source[:-2]}.o: {' '.join(_escape(d) for d in deps)}\n")
    text = "".join(lines)
    target = work / DEPS_FILE
    if not target.is_file() or target.read_text(encoding="utf-8") != text:
        target.write_text(text, encoding="utf-8")
    return len(lines)


def _escape(path: str) -> str:
    return path.replace(" ", "\\ ")
