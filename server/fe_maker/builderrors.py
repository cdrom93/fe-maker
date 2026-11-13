"""Build errors said plainly (spec, section 4, alpha): the known failures of a build are recognized in its error and
log, and given back as a kind and the data in question; the interface words them (locales "build.why.*") above the
raw log, which stays foldable.

Kinds: problems (the project's own errors, listed), decompMismatch (a decomp file is not the one FE Maker reads),
text (textencode: a line of texts/texts.txt, with its message number), code (compiler or assembler error in a file,
with the part of the project that file holds and whether FE Maker wrote it), undefined (a symbol nobody defines),
romFull (the game is too big), missingFile (make has no rule for a file), image (gbagfx), locked (a file in use),
diskFull.
"""

from __future__ import annotations

import re
from pathlib import Path

# Which part of the project a decomp file holds (the first matching prefix), for "code" errors.
AREAS = (
    ("src/data_characters", "characters"), ("include/constants/characters", "characters"),
    ("src/data_classes", "classes"), ("include/constants/classes", "classes"), ("src/classchg", "classes"),
    ("src/data_item", "items"), ("include/constants/items", "items"), ("data/data_item_icon", "items"),
    ("src/events", "events"), ("src/eventinfo", "events"), ("src/data_battlequotes", "events"),
    ("include/EAstdlib", "events"), ("src/data/chapter_settings", "chapters"), ("data/const_data_chapter_maps", "maps"),
    ("data/data_map_change", "maps"), ("data/maps", "maps"), ("texts/", "texts"),
    ("data/data_portrait", "portraits"), ("include/portrait_pointer", "portraits"), ("graphics/portrait", "portraits"),
    ("src/banim", "animations"), ("data/banim", "animations"), ("graphics/banim", "animations"),
    ("include/banim", "animations"), ("sound/", "music"), ("songs.mk", "music"), ("src/skill", "skills"),
    ("include/skills", "skills"),
)
_DECOMP_ERRORS = ("CParseError", "CombatTableError", "ConvoyError", "GameDataError", "MapError", "TweakError")
# "src/data_items.c:2950: syntax error before `;'" (agbcc, gcc 2.95: no "error:"), "data/x.s:680: Error: bad
# instruction" (as); warnings and make's own "Makefile:240:" lines are not errors.
_CODE_RE = re.compile(r"^((?:src|include|data|asm|sound|graphics|texts)/[^\s:]+):(\d+)(?::\d+)?: (?!warning)"
                      r"(?:fatal )?(?:error: |Error: )?(.*)$")


def area(path: str) -> str | None:
    return next((name for prefix, name in AREAS if path.startswith(prefix)), None)


def _text_message(line: int, texts: Path | None) -> str | None:
    """The message a line of texts/texts.txt belongs to ("0x914", or its name)."""
    if texts is None or not texts.is_file():
        return None
    lines = texts.read_text(encoding="utf-8", errors="replace").splitlines()[:line]
    for text in reversed(lines):
        m = re.match(r"^(?:#(0x[0-9A-Fa-f]+)|## (\w+))", text)
        if m:
            return m.group(1) or m.group(2)
    return None


def explain(error: str, log: list[str] | None = None, overlay: Path | None = None, decomp: Path | None = None) -> dict | None:
    """{"kind", **data} for a known failure, else None."""
    error = error or ""
    if error.startswith("Fix these problems before building: "):
        return {"kind": "problems", "problems": error.split(": ", 1)[1].split("; ")}
    name = error.split(":", 1)[0]
    if name in _DECOMP_ERRORS or "not found in this version of the decomp" in error:
        return {"kind": "decompMismatch", "detail": error.split(": ", 1)[-1]}
    lines = [line.rstrip() for line in [*(log or []), *error.splitlines()]]
    for line in lines:
        m = re.search(r"No space left on device|There is not enough space on the disk", line)
        if m:
            return {"kind": "diskFull"}
        m = re.search(r"region [`']?\w+'? overflowed by (\d+) bytes|will not fit in region", line)
        if m:
            return {"kind": "romFull", "bytes": int(m.group(1)) if m.group(1) else None}
    for line in lines:
        m = re.search(r"^error: line (\d+): (.*)$", line)
        if m:
            n = int(m.group(1))
            texts = next((p for p in (overlay and overlay / "texts/texts.txt", decomp and decomp / "texts/texts.txt")
                          if p and p.is_file()), None)
            return {"kind": "text", "line": n, "message": m.group(2), "text": _text_message(n, texts)}
        m = _CODE_RE.search(line)
        if m:
            path = m.group(1)
            written = bool(overlay and (overlay / path).is_file())
            return {"kind": "code", "file": path, "line": int(m.group(2)), "message": m.group(3).strip(),
                    "area": area(path), "written": written}
        m = re.search(r"undefined reference to [`']([^'`]+)'", line)
        if m:
            return {"kind": "undefined", "symbol": m.group(1)}
        m = re.search(r"No rule to make target [`']([^'`]+)'(?:, needed by [`']([^'`]+)')?", line)
        if m:
            return {"kind": "missingFile", "file": m.group(1), "area": area(m.group(2) or m.group(1))}
        m = re.search(r"gbagfx\S*:?\s*(.*)", line)
        if m and ("error" in line.lower() or ".png" in line):
            return {"kind": "image", "message": m.group(1).strip()}
        m = re.search(r"(?:Permission denied|Access is denied|being used by another process)", line)
        if m:
            path = re.search(r"([\w./\\:-]+\.(?:gba|elf|o|s|c|png|bin|lz))", line)
            return {"kind": "locked", "file": path.group(1) if path else ""}
    return None
