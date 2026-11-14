"""Missions for the testers (missions.py, missions.json)."""

import json

from fe_maker import __version__, missions


def test_this_version_has_missions_in_both_languages():
    found = missions.for_version(__version__)
    assert len(found) >= 3
    assert len({m["id"] for m in found}) == len(found)
    for m in found:
        assert len(m["questions"]) == 3
        for text in (m["title"], m["task"], *m["questions"]):
            assert text["fr"].strip() and text["en"].strip()


def test_longest_prefix_and_answers_as_a_ticket(tmp_path):
    path = tmp_path / "missions.json"
    one = {"id": "a", "title": {"fr": "Titre", "en": "Title"}, "task": {"fr": "Tâche", "en": "Task"},
           "questions": [{"fr": "Q1", "en": "Q1"}, {"fr": "Q2", "en": "Q2"}, {"fr": "Q3", "en": "Q3"}]}
    path.write_text(json.dumps({"0.1.0": [], "0.1.0-alpha": [one]}), encoding="utf-8")
    assert missions.for_version("0.1.0-alpha.3", path) == [one]
    assert missions.for_version("0.2.0", path) == [] and missions.for_version("0.1.01", path) == []
    path.write_text(json.dumps({"0": [one]}), encoding="utf-8")   # the 0.N versions, the old 0.1.0-prealpha.N too
    assert missions.for_version("0.43", path) == [one] == missions.for_version("0.1.0-prealpha.42", path)
    assert missions.for_version("1.0", path) == []
    mission = missions.localized([one], "fr")[0]
    assert mission["title"] == "Titre" and mission["questions"] == ["Q1", "Q2", "Q3"]
    body = missions.ticket_body(mission, ["Bien", "", "Oui"])
    assert body.startswith("Mission « Titre » (a)") and "**Q2**\n-" in body and body.endswith("Oui")
