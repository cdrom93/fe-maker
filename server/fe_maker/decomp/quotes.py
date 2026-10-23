"""Battle quotes and death quotes (src/data_battlequotes.c).

- gBattleTalkList: when pidA fights pidB in a chapter, the message is shown once (its flag is set).
  pidA = 0 (CHAR_EVT_PLAYER_LEADER) or pidB = 0 means "anyone": the game writes a boss quote as two
  entries, {0, boss} and {boss, 0}, so it plays whoever starts the fight. Chapter 0xFF: any chapter.
  Bosses share the flag EVFLAG_BATTLE_QUOTES; other quotes use temporary flags.
- gDefeatTalkList: a character's last words in a chapter (0xFF: any chapter, used for the playable
  characters); the entry of a boss also sets EVFLAG_DEFEAT_BOSS (see objectives.py).

New quotes (project data/dialogues.json "quotes") get a new message and new entries, added before
the end of the lists.
"""

from __future__ import annotations

from .cparse import _blank_comments, parse_fields
from .units import _array_body_span, _entry_spans, _indent_at, _render_unit

FILE = "src/data_battlequotes.c"
BATTLE = ("BattleTalkExtEnt", "gBattleTalkList")
DEATH = ("DefeatTalkEnt", "gDefeatTalkList")
ANY_CHAPTER = 0xFF
LEADER = "CHAR_EVT_PLAYER_LEADER"   # 0: anyone
FIRST_FLAG = 50                     # temporary flags for new quotes (map objects use 70+)


def _int(value: str, constants: dict[str, int]) -> int | None:
    value = value.strip()
    if value in constants:
        return constants[value]
    try:
        return int(value, 0)
    except ValueError:
        return None


def _entries(source: str, array: tuple[str, str], key: str) -> list[tuple[tuple[int, int], dict[str, str]]]:
    clean = _blank_comments(source)
    span = _array_body_span(clean, *array)
    if span is None:
        return []
    out = []
    for s, e in _entry_spans(clean, *span):
        fields = parse_fields(clean[s + 1: e - 1])
        if fields.get(key, "").strip().lower() in ("0xffff", "-1"):
            continue  # terminator
        out.append(((s, e), fields))
    return out


def read_quotes(source: str, constants: dict[str, int]) -> dict[str, list[dict]]:
    """{"battle": [{a, b, chapter, flag, msg}], "death": [{a, chapter, route, flag, msg}]}; a / b are
    character constants ("" = anyone), chapter an index (ANY_CHAPTER = any)."""
    battle = []
    for _span, f in _entries(source, BATTLE, "pidA"):
        a, b = f.get("pidA", "0").strip(), f.get("pidB", "0").strip()
        battle.append({"a": "" if a in ("0", LEADER) else a, "b": "" if b in ("0", LEADER) else b,
                       "chapter": _int(f.get("chapter", "0"), constants), "flag": f.get("flag", "0").strip(),
                       "msg": _int(f.get("msg", "0"), constants) or 0})
    death = []
    for _span, f in _entries(source, DEATH, "pid"):
        death.append({"a": f.get("pid", "").strip(), "chapter": _int(f.get("chapter", "0"), constants),
                      "route": f.get("route", "").strip(), "flag": f.get("flag", "0").strip(),
                      "msg": _int(f.get("msg", "0"), constants) or 0})
    return {"battle": battle, "death": death}


def _chapter_name(index: int, constants: dict[str, int]) -> str:
    if index == ANY_CHAPTER:
        return "0xFF"
    return next((name for name, value in constants.items() if value == index), f"0x{index:02X}")


def _insert(source: str, array: tuple[str, str], key: str, fields_list: list[dict[str, str]], first: bool = False) -> str:
    """Entries added before the terminator of an array, or before its first entry with `first` (the
    game uses the first entry that matches: a chapter's entry must come before an every-chapter one)."""
    clean = _blank_comments(source)
    start, end = _array_body_span(clean, *array)
    spans = _entry_spans(clean, start, end)
    term = spans[0][0] if first and spans else None
    for s, e in ([] if first else spans):
        if parse_fields(clean[s + 1: e - 1]).get(key, "").strip().lower() in ("0xffff", "-1"):
            term = s
    if term is None:
        raise ValueError(f"{array[1]}: end of list not found")
    indent = _indent_at(clean, term)
    block = "".join(_render_unit(fields, indent) + ",\n" + indent for fields in fields_list)
    return source[:term] + block + source[term:]


def add_battle_quote(source: str, constants: dict[str, int], chapter: int, a: str, b: str, msg: int, flag: int) -> str:
    """A quote shown once when `a` fights `b` (b "" = anyone), whoever starts the fight."""
    common = {"chapter": _chapter_name(chapter, constants), "flag": f"0x{flag:04X}", "msg": f"0x{msg:04X}"}
    first = {"pidA": a, "pidB": b or LEADER, **common}
    second = {"pidA": b or LEADER, "pidB": a, **common}
    return _insert(source, BATTLE, "pidA", [first, second])


def set_death_flag(source: str, constants: dict[str, int], chapter: int, a: str, flag: str) -> str:
    """The flag set when `a` dies in a chapter (EVFLAG_GAMEOVER: the game is lost): its entry for the
    chapter, or a new entry without words."""
    clean = _blank_comments(source)
    for (s, e), f in _entries(source, DEATH, "pid"):
        if f.get("pid", "").strip() == a and _int(f.get("chapter", "0"), constants) == chapter:
            if f.get("flag", "").strip() == flag:
                return source
            f["flag"] = flag
            return source[:s] + _render_unit(f, _indent_at(clean, s)) + source[e:]
    # Keep the character's every-chapter last words, if any.
    words = next((_int(f.get("msg", "0"), constants) or 0 for _span, f in _entries(source, DEATH, "pid")
                  if f.get("pid", "").strip() == a and _int(f.get("chapter", "0"), constants) == ANY_CHAPTER), 0)
    fields = {"pid": a, "route": "CHAPTER_MODE_ANY", "chapter": _chapter_name(chapter, constants), "flag": flag,
              "msg": f"0x{words:04X}"}
    return _insert(source, DEATH, "pid", [fields], first=True)


def add_death_quote(source: str, constants: dict[str, int], chapter: int, a: str, msg: int) -> str:
    """Last words of `a` in a chapter: the message of its entry when it has one without words (a boss
    set by FE Maker), else a new entry."""
    clean = _blank_comments(source)
    for (s, e), f in _entries(source, DEATH, "pid"):
        if f.get("pid", "").strip() == a and _int(f.get("chapter", "0"), constants) == chapter \
                and (_int(f.get("msg", "0"), constants) or 0) == 0:
            f["msg"] = f"0x{msg:04X}"
            return source[:s] + _render_unit(f, _indent_at(clean, s)) + source[e:]
    fields = {"pid": a, "route": "CHAPTER_MODE_ANY", "chapter": _chapter_name(chapter, constants), "msg": f"0x{msg:04X}"}
    return _insert(source, DEATH, "pid", [fields], first=chapter != ANY_CHAPTER)
