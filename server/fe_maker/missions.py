"""Missions for the testers (spec, section 4, alpha, automatic tests point 4): for each version, a few tasks drawn
from the CHANGELOG's themes, each with three questions about how it felt. They are shown in the Ticket panel; the
answers go out as a ticket (kind "idea") that names the mission. missions.json is keyed by version prefix: a new
version series gets its own list, written from its CHANGELOG (CLAUDE.md).
"""

from __future__ import annotations

import json
from pathlib import Path

from . import __version__

FILE = Path(__file__).with_name("missions.json")


def for_version(version: str = __version__, path: Path = FILE) -> list[dict]:
    """The missions of the longest version prefix matching `version` ("0.1.0-prealpha" for "0.1.0-prealpha.19")."""
    data = json.loads(path.read_text(encoding="utf-8"))
    keys = [k for k in data if version.startswith(k)]
    return data[max(keys, key=len)] if keys else []


def localized(missions: list[dict], language: str) -> list[dict]:
    def pick(text: dict) -> str:
        return text.get(language) or text.get("en") or next(iter(text.values()), "")
    return [{"id": m["id"], "theme": m.get("theme", ""), "title": pick(m["title"]), "task": pick(m["task"]),
             "questions": [pick(q) for q in m["questions"]]} for m in missions]


def ticket_body(mission: dict, answers: list[str]) -> str:
    """The ticket a mission's answers make (the mission localized, as the tester read it)."""
    lines = [f"Mission « {mission['title']} » ({mission['id']})", "", mission["task"]]
    for question, answer in zip(mission["questions"], answers):
        lines += ["", f"**{question}**", answer.strip() or "-"]
    return "\n".join(lines)
