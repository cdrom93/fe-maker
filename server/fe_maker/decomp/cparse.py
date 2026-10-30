"""Minimal parser for the designated-initializer arrays used by the decomp.

Handles arrays shaped like:

    CONST_DATA struct CharacterData gCharacterData[] = {
        [CHARACTER_EIRIKA - 1] = {
            .nameTextId = 0x212,
            .baseRanks = {
                [ITYPE_SWORD] = WPN_EXP_E,
            },
        },
        ...
    };

Field values are kept as raw C expressions. Entries that are not modified are
written back byte for byte, so an unmodified project rebuilds the original ROM.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field


class CParseError(Exception):
    pass


@dataclass
class Entry:
    key: str                      # e.g. "CHARACTER_EIRIKA - 1"
    fields: dict[str, str]        # field name -> raw C expression
    start: int                    # span of the whole "[key] = {...}," text
    end: int
    indent: str = "    "
    original_fields: dict[str, str] = field(default_factory=dict)


@dataclass
class ParsedArray:
    source: str
    entries: list[Entry]

    def by_key(self) -> dict[str, Entry]:
        return {e.key: e for e in self.entries}


_COMMENT_RE = re.compile(r"//[^\n]*|/\*.*?\*/", re.DOTALL)


def _blank_comments(text: str) -> str:
    """Replace comments by spaces, keeping offsets unchanged."""
    return _COMMENT_RE.sub(lambda m: re.sub(r"[^\n]", " ", m.group(0)), text)


def _match_brace(text: str, open_pos: int) -> int:
    """Return the index of the brace closing the one at open_pos."""
    depth = 0
    for i in range(open_pos, len(text)):
        c = text[i]
        if c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                return i
    raise CParseError("Unbalanced braces")


def _split_top_level(body: str) -> list[str]:
    """Split on commas that are not nested in braces or parentheses."""
    parts, depth, current = [], 0, []
    for c in body:
        if c in "{(":
            depth += 1
        elif c in "})":
            depth -= 1
        if c == "," and depth == 0:
            parts.append("".join(current))
            current = []
        else:
            current.append(c)
    parts.append("".join(current))
    return [p.strip() for p in parts if p.strip()]


def parse_fields(body: str) -> dict[str, str]:
    fields: dict[str, str] = {}
    for part in _split_top_level(body):
        m = re.match(r"\.(\w+)\s*=\s*(.+)$", part, re.DOTALL)
        if not m:
            raise CParseError(f"Unexpected initializer: {part[:60]!r}")
        fields[m.group(1)] = " ".join(m.group(2).split())
    return fields


def parse_array(source: str, array_name: str) -> ParsedArray:
    clean = _blank_comments(source)
    m = re.search(rf"\b{re.escape(array_name)}\s*\[\s*\]\s*=\s*\{{", clean)
    if not m:
        raise CParseError(f"Array {array_name} not found")
    array_open = m.end() - 1
    array_close = _match_brace(clean, array_open)

    entries: list[Entry] = []
    entry_re = re.compile(r"\[([^\]]+)\]\s*=\s*\{")
    pos = array_open + 1
    while True:
        em = entry_re.search(clean, pos, array_close)
        if not em:
            break
        body_open = em.end() - 1
        body_close = _match_brace(clean, body_open)
        end = body_close + 1
        if end < array_close and clean[end] == ",":
            end += 1
        line_start = clean.rfind("\n", 0, em.start()) + 1
        indent = clean[line_start:em.start()]
        fields = parse_fields(clean[body_open + 1:body_close])
        entries.append(Entry(
            key=" ".join(em.group(1).split()),
            fields=fields,
            start=em.start(),
            end=end,
            indent=indent if indent.strip() == "" else "    ",
            original_fields=dict(fields),
        ))
        pos = end
    return ParsedArray(source=source, entries=entries)


def render_entry(entry: Entry) -> str:
    inner = entry.indent + ("\t" if "\t" in entry.indent else "    ")
    lines = [f"[{entry.key}] = {{"]
    for name, value in entry.fields.items():
        lines.append(f"{inner}.{name} = {value},")
    lines.append(f"{entry.indent}}},")
    return "\n".join(lines)


def render_array(parsed: ParsedArray) -> str:
    """Rebuild the source, re-rendering only the entries whose fields changed."""
    out, last = [], 0
    for entry in parsed.entries:
        out.append(parsed.source[last:entry.start])
        if entry.start == entry.end:   # an entry added at the end of the array (start: the line of its "};")
            out.append(entry.indent + render_entry(entry) + "\n")
        elif entry.fields == entry.original_fields:
            out.append(parsed.source[entry.start:entry.end])
        else:
            out.append(render_entry(entry))
        last = entry.end
    out.append(parsed.source[last:])
    return "".join(out)


def parse_int(value: str) -> int:
    """Parse a plain C integer literal (decimal, hex, optional sign)."""
    return int(value.strip().rstrip("uUlL"), 0)


def parse_designated_list(value: str) -> dict[str, str]:
    """Parse '{ [ITYPE_SWORD] = WPN_EXP_E, }' into {'ITYPE_SWORD': 'WPN_EXP_E'}."""
    value = value.strip()
    if not (value.startswith("{") and value.endswith("}")):
        raise CParseError(f"Not a brace list: {value!r}")
    result = {}
    for part in _split_top_level(value[1:-1]):
        m = re.match(r"\[\s*(\w+)\s*\]\s*=\s*(.+)$", part)
        if not m:
            raise CParseError(f"Unexpected list item: {part!r}")
        result[m.group(1)] = m.group(2).strip()
    return result


def render_designated_list(items: dict[str, str]) -> str:
    if not items:
        return "{ }"
    return "{ " + " ".join(f"[{k}] = {v}," for k, v in items.items()) + " }"
