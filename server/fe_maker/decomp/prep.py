"""The preparations screen before a battle, chapter by chapter (ticket 107).

The game has no setting for it (the chapters' hasPrepScreen is always false): a chapter's opening
scene calls EventScr_08591FD8 (fade out, PREP), usually at its end. A project turns it on or off per
chapter (data/chapters.json "prep", once changed); the chapters it adds have it by default.
"""

from __future__ import annotations

SCRIPT = "EventScr_08591FD8"
_LAST_OPS = ("ENDA", "NoFade", "")   # the scene's end: the call goes before


def default(chapter_index: int, chapters: dict, scene_has_it: bool) -> bool:
    """The chapter's value when the project did not change it."""
    return scene_has_it or str(chapter_index) in chapters.get("added", {})


def scene_has_it(commands: list[dict]) -> bool:
    return any(c.get("op") == "CALL" and c.get("args") == [SCRIPT] for c in commands)


def with_prep(commands: list[dict], on: bool) -> list[dict]:
    """The opening scene's commands with or without the preparations."""
    if scene_has_it(commands) == on:
        return commands
    if not on:
        return [c for c in commands if not (c.get("op") == "CALL" and c.get("args") == [SCRIPT])]
    at = len(commands)
    while at > 0 and commands[at - 1].get("op", "") in _LAST_OPS:
        at -= 1
    return commands[:at] + [{"op": "CALL", "args": [SCRIPT]}] + commands[at:]
