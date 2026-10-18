"""Reader and writer for texts/texts.txt.

Format (see scripts/texttools/textprocess.py in the decomp):
    #0x0              explicit message index
    ## MSG_212        named message, index = previous index + 1
    <message body, possibly several lines, ending with [X]>
Bodies run until the next line starting with "#".
"""

from __future__ import annotations

import re
from dataclasses import dataclass

_MSGIDX_RE = re.compile(r"^#([0-9a-fA-Fx]+)")
_MACRO_RE = re.compile(r"^##\s*(\w+)")
_NAME_RE = re.compile(r"^(.*?)((?:\[[^\]]*\])*)$", re.DOTALL)


@dataclass
class _Message:
    index: int
    body_start: int   # line indices of the body in TextFile.lines
    body_end: int


class TextFile:
    def __init__(self, source: str):
        self.lines = source.split("\n")
        self.messages: dict[int, _Message] = {}
        self.edits: dict[int, str] = {}
        self._parse()

    def _parse(self) -> None:
        i, index = 0, -1
        while i < len(self.lines):
            line = self.lines[i].strip()
            m_idx = _MSGIDX_RE.match(line)
            m_macro = _MACRO_RE.match(line) if not m_idx else None
            if m_idx or m_macro:
                index = int(m_idx.group(1), 0) if m_idx else index + 1
                start = i + 1
                i = start
                while i < len(self.lines) and not self.lines[i].startswith("#"):
                    i += 1
                self.messages[index] = _Message(index, start, i)
            else:
                i += 1

    def raw(self, index: int) -> str:
        if index in self.edits:
            return self.edits[index]
        msg = self.messages[index]
        return "\n".join(self.lines[msg.body_start:msg.body_end]).strip("\n")

    def set_raw(self, index: int, body: str) -> None:
        if index not in self.messages:
            raise KeyError(f"Unknown message 0x{index:X}")
        if body != self.raw(index) or index in self.edits:
            self.edits[index] = body

    def _split_name(self, index: int) -> tuple[str, str]:
        """'Gilliam[.][X]' -> ('Gilliam', '[.][X]'): visible text and trailing control codes."""
        m = _NAME_RE.match(self.raw(index).strip())
        return (m.group(1), m.group(2)) if m else (self.raw(index), "[X]")

    def get_name(self, index: int) -> str:
        """Short single-line texts such as names, without their control codes."""
        return self._split_name(index)[0]

    def set_name(self, index: int, name: str) -> None:
        current, suffix = self._split_name(index)
        if current != name:
            self.set_raw(index, f"{name}{suffix or '[X]'}")

    def render(self) -> str:
        lines = list(self.lines)
        # Replace from the end so earlier line indices stay valid.
        for index in sorted(self.edits, key=lambda k: self.messages[k].body_start, reverse=True):
            msg = self.messages[index]
            lines[msg.body_start:msg.body_end] = self.edits[index].split("\n") + [""]
        return "\n".join(lines)
