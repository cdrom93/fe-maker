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

from .fonts import char_byte

_MSGIDX_RE = re.compile(r"^#([0-9a-fA-Fx]+)")
_MACRO_RE = re.compile(r"^##\s*(\w+)")
_NAME_RE = re.compile(r"^(.*?)((?:\[[^\]]*\])*)$", re.DOTALL)


def name_message(name: str) -> str:
    """Message body for a short name.

    The text compressor packs printable characters two by two
    (scripts/texttools/textprocess.py). With an odd number of bytes, the last
    character would be packed with the [X] terminator, which the game then
    misses and keeps reading the next message (seen in game: "Rapieros enH-e3
    Sord"). The original game pads such names with [.], e.g. "Gilliam[.][X]".
    """
    padding = "[.]" if text_size(name) % 2 else ""
    return f"{name}{padding}[X]"


def text_size(text: str) -> int:
    """Bytes of printable text in the game: one per character of the game's code page (accented
    letters too, written as codes by TextFile.render), else its UTF-8 bytes."""
    return sum(1 if char_byte(ch) is not None else len(ch.encode("utf-8")) for ch in text)


_SPECIAL_RE = re.compile(r"[^\x00-\x7F]")


def special_chars(body: str) -> set[str]:
    """Non-ASCII characters of a message that the game's code page has (they become text codes)."""
    return {ch for ch in _SPECIAL_RE.findall(body) if char_byte(ch) is not None}


def encode_special(body: str) -> str:
    """é -> [é]: the code, defined in textdefs.txt with the character's byte (see fonts.py)."""
    return _SPECIAL_RE.sub(lambda m: f"[{m.group(0)}]" if char_byte(m.group(0)) is not None else m.group(0), body)


def textdefs_with(textdefs: str, chars: set[str]) -> str:
    """texts/textdefs.txt with a code for each character (its byte in the game's code page)."""
    lines = [f"[{ch}] = 0x{char_byte(ch):02X}" for ch in sorted(chars)]
    return textdefs.rstrip("\n") + "\n\n// FE Maker: accented letters\n" + "\n".join(lines) + "\n"


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
        self.added: dict[int, str] = {}  # new messages, after the last one
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

    def add(self, body: str) -> int:
        """New message at the end of the file; returns its index."""
        index = max([*self.messages, *self.added, -1]) + 1
        self.added[index] = body
        return index

    def raw(self, index: int) -> str:
        if index in self.added:
            return self.added[index]
        if index in self.edits:
            return self.edits[index]
        msg = self.messages[index]
        return "\n".join(self.lines[msg.body_start:msg.body_end]).strip("\n")

    def set_raw(self, index: int, body: str) -> None:
        if index in self.added:
            self.added[index] = body
            return
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
        current, _suffix = self._split_name(index)
        if current != name:
            self.set_raw(index, name_message(name))

    def special_chars(self) -> set[str]:
        """Accented letters of the edited and added messages (they need codes in textdefs.txt)."""
        return set().union(*(special_chars(b) for b in [*self.edits.values(), *self.added.values()]))

    def render(self) -> str:
        lines = list(self.lines)
        # Replace from the end so earlier line indices stay valid.
        for index in sorted(self.edits, key=lambda k: self.messages[k].body_start, reverse=True):
            msg = self.messages[index]
            lines[msg.body_start:msg.body_end] = encode_special(self.edits[index]).split("\n") + [""]
        text = "\n".join(lines)
        if self.added:
            text = text.rstrip("\n") + "\n\n" + "".join(
                f"## MSG_{index:03X}\n{encode_special(body)}\n\n" for index, body in sorted(self.added.items()))
        return text
