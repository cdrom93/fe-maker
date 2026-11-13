import base64
import io

import pytest
from PIL import Image

from fe_maker.tickets import TicketError, TicketStore


def _png_data_url() -> str:
    out = io.BytesIO()
    Image.new("RGB", (2, 2), (255, 0, 0)).save(out, "PNG")
    return "data:image/png;base64," + base64.b64encode(out.getvalue()).decode()


def test_create_list_update_delete(tmp_path):
    store = TicketStore(tmp_path)
    low = store.create("Petite idée", kind="idea", priority="low")
    bug = store.create("Plantage au tour 2", priority="high", context={"tab": "chapters"}, images=[_png_data_url()])
    assert (low["number"], bug["number"]) == (1, 2)
    assert bug["context"]["tab"] == "chapters" and bug["context"]["version"]
    assert store.image_path(bug["images"][0]).read_bytes().startswith(b"\x89PNG")
    # Open first, then by priority.
    assert [t["id"] for t in store.list()] == [bug["id"], low["id"]]
    store.update(bug["id"], {"status": "done"})
    assert [t["id"] for t in store.list()] == [low["id"], bug["id"]]
    store.delete(bug["id"])
    assert [t["id"] for t in store.list()] == [low["id"]]
    assert list((tmp_path / "images").iterdir()) == []


def test_comments_complete_a_ticket(tmp_path):
    store = TicketStore(tmp_path)
    ticket = store.create("Plantage", images=[_png_data_url()])
    first = store.add_comment(ticket["id"], "  Aussi au tour 3  ", [_png_data_url()])["comments"][0]
    assert first["body"] == "Aussi au tour 3" and first["images"] != ticket["images"] and first["version"]
    second = store.add_comment(ticket["id"], "Encore", [_png_data_url()])["comments"][1]
    store.delete_comment(ticket["id"], first["id"])
    third = store.add_comment(ticket["id"], "Et là", [_png_data_url()])["comments"][1]
    assert third["images"] != second["images"]   # a removed comment's number does not overwrite another's picture
    assert store.image_path(second["images"][0]) and store.image_path(third["images"][0])
    with pytest.raises(TicketError):
        store.add_comment(ticket["id"], "   ")
    with pytest.raises(KeyError):
        store.add_comment("nope", "x")
    with pytest.raises(KeyError):
        store.delete_comment(ticket["id"], "nope")
    store.delete(ticket["id"])
    assert list((tmp_path / "images").iterdir()) == []


def test_tickets_written_before_comments_have_none(tmp_path):
    store = TicketStore(tmp_path)
    ticket = store.create("Ancien")
    del ticket["comments"]
    store._write([ticket])
    assert store.list()[0]["comments"] == []


def test_rejects_bad_input(tmp_path):
    store = TicketStore(tmp_path)
    with pytest.raises(TicketError):
        store.create("   ")
    with pytest.raises(TicketError):
        store.create("x", kind="nope")
    with pytest.raises(TicketError):
        store.create("x", images=["data:text/html;base64,PGI+"])
    ticket = store.create("x")
    with pytest.raises(TicketError):
        store.update(ticket["id"], {"status": "nope"})
    assert store.image_path("../tickets.json") is None


def test_tickets_go_to_the_relay_and_come_back_with_replies(tmp_path, monkeypatch):
    from fe_maker import tickets

    calls = []

    def relay(path, data=None, secret=""):
        calls.append((path, data, secret))
        if path == "/v1/tickets":
            return {"number": 12, "secret": "s" * 32}
        if path == "/v1/tickets/12":
            return {"number": 12, "state": "done", "comments": [
                {"from": "admin", "body": "Fixed.", "createdAt": "2026-11-07T12:00:00Z"},
                {"from": "tester", "body": "Mine", "createdAt": "2026-11-07T12:01:00Z"}]}
        return {"ok": True}

    store = TicketStore(tmp_path)
    ticket = store.create("Broken map", context={"tab": "Maps"}, images=[_png_data_url()])
    # the relay is off: the ticket stays here, with its error
    assert store.send(ticket["id"])["sendError"] == "relayOff"
    monkeypatch.setattr(tickets, "relay_call", relay)
    sent = store.send(ticket["id"], project=b"zip")
    assert sent["remote"]["number"] == 12 and "sendError" not in sent
    # ticket 185: it now goes by its GitHub number; the next ticket written here follows the local ones
    assert (sent["number"], sent["localNumber"]) == (12, 1) and store.create("Next")["number"] == 2
    path, data, _ = calls[0]
    assert data["body"] == "Broken map" and data["context"] == {"tab": "Maps"} and data["version"]
    assert data["images"][0].startswith("data:image/png;base64,") and data["project"] == {"data": "emlw"}
    assert store.send(ticket["id"]) == sent and len(calls) == 1      # never sent twice
    with_comment = store.add_comment(ticket["id"], "More")
    store.send_comment(ticket["id"], with_comment["comments"][-1]["id"])
    assert calls[-1][0] == "/v1/tickets/12/comments" and calls[-1][2] == "s" * 32
    assert next(x for x in store.list() if x["id"] == ticket["id"])["comments"][-1]["sent"] is True
    synced = next(x for x in store.sync() if x["id"] == ticket["id"])
    assert synced["status"] == "done" and synced["replies"] == [{"body": "Fixed.", "createdAt": "2026-11-07T12:00:00Z"}]


def test_project_joined_without_its_builds(tmp_path):
    import zipfile
    from io import BytesIO

    from fe_maker.tickets import project_zip

    (tmp_path / "data").mkdir()
    (tmp_path / "data" / "characters.json").write_text("[]")
    (tmp_path / "fe-maker.json").write_text("{}")
    (tmp_path / "build").mkdir()
    (tmp_path / "build" / "game.gba").write_bytes(b"rom")
    names = zipfile.ZipFile(BytesIO(project_zip(tmp_path))).namelist()
    assert sorted(names) == ["data/characters.json", "fe-maker.json"]


ISSUE_BODY = """Plantage au tour 2
avec deux lignes

| | |
|---|---|
| tab | Cartes |
| version | 0.1.0-prealpha.1+abc1234 |

![Capture 1](https://github.com/cdrom93/fe-maker-feedback/blob/main/uploads/2026-11/ab12-1.png?raw=true)

[Projet joint](https://github.com/cdrom93/fe-maker-feedback/blob/main/uploads/2026-11/ab12-project.zip?raw=true)

<!-- fem:secret=""" + "0" * 64 + " -->"


def test_admin_mode_reads_answers_and_closes_through_gh(monkeypatch):
    import json

    from fe_maker import tickets

    calls = []
    labels = [{"name": "bug"}, {"name": "priority:high"}, {"name": "v0.1.0-prealpha.1"}]
    issue = {"number": 5, "body": ISSUE_BODY, "labels": labels,
             "createdAt": "2026-11-07T12:00:00Z", "state": "CLOSED", "stateReason": "NOT_PLANNED", "url": "u",
             "comments": [{"body": "Merci\n\n<!-- fem:tester -->", "createdAt": "c1"}, {"body": "Corrigé", "createdAt": "c2"}]}

    def gh(*args, stdin=None):
        calls.append((args, stdin))
        if args[:2] == ("issue", "list"):
            return json.dumps([issue])
        if args[0] == "api" and args[-1].endswith(".png") and "-X" not in args:
            return json.dumps({"content": base64.b64encode(b"PNG").decode(), "sha": "s"})
        return ""

    monkeypatch.setattr(tickets, "_gh", gh)
    [found] = tickets.admin_tickets(include_closed=True)
    assert found["body"] == "Plantage au tour 2\navec deux lignes"
    assert found["context"] == {"tab": "Cartes", "version": "0.1.0-prealpha.1+abc1234"}
    assert found["images"] == ["uploads/2026-11/ab12-1.png"] and found["project"] == "uploads/2026-11/ab12-project.zip"
    assert (found["kind"], found["priority"], found["status"]) == ("bug", "high", "cancelled")
    assert found["version"] == "0.1.0-prealpha.1"
    assert [(c["from"], c["body"]) for c in found["comments"]] == [("tester", "Merci"), ("admin", "Corrigé")]

    tickets.admin_reply(5, "C'est réglé", [_png_data_url()])
    upload, comment = calls[-2], calls[-1]
    assert upload[0][:3] == ("api", "-X", "PUT") and json.loads(upload[1])["content"]
    assert comment[0][:3] == ("issue", "comment", "5") and comment[1].startswith("C'est réglé\n\n![Capture 1](")
    tickets.admin_set_status(5, "done")
    assert calls[-1][0][:2] == ("issue", "close") and "completed" in calls[-1][0]
    assert tickets.admin_file("uploads/2026-11/ab12-1.png") == b"PNG"
    with pytest.raises(tickets.AdminError):
        tickets.admin_file("../secrets.txt")


def test_admin_endpoints_need_the_admin_mode():
    from fastapi import HTTPException

    from fe_maker import api

    assert api.admin_state() == {"available": False}
    with pytest.raises(HTTPException) as refused:
        api.admin_tickets()
    assert refused.value.status_code == 403


def test_the_admin_closing_a_sent_ticket_closes_its_issue(tmp_path, monkeypatch):
    """The admin's Done / Cancel / Reopen on a ticket sent follows on GitHub; a tester's stays on their PC."""
    from fe_maker import api, tickets

    store = TicketStore(tmp_path)
    ticket = store.create("Sent one")
    store._set(ticket["id"], lambda t: t.update(remote={"number": 7, "secret": "s" * 32, "sentAt": "x"}))
    monkeypatch.setattr(api, "tickets", store)
    calls = []
    monkeypatch.setattr(tickets, "admin_set_status", lambda number, status: calls.append((number, status)))
    assert api.update_ticket(ticket["id"], {"status": "done"})["status"] == "done" and calls == []   # a tester
    monkeypatch.setattr(tickets, "_admin", True)
    api.update_ticket(ticket["id"], {"status": "open"})
    api.update_ticket(ticket["id"], {"priority": "high"})
    assert calls == [(7, "open")]


def test_the_last_actions_and_errors_go_with_a_sent_ticket(tmp_path, monkeypatch):
    """Spec, section 4, automatic tests point 3: activity.py notes the writing requests and the failures; a ticket
    keeps them and sends them folded at the end of its text."""
    from fe_maker import activity, tickets

    activity.clear()
    activity.request("GET", "/api/characters", 200)            # reading: not told
    activity.request("PUT", "/api/characters/eirika", 200)
    activity.request("GET", "/api/maps/3", 500)
    activity.request("POST", "/api/tickets", 200)               # the ticket itself: not told
    activity.error("build failed: code")
    recent = activity.recent()
    assert [e.split(" ", 1)[1] for e in recent] == ["PUT /api/characters/eirika -> 200", "GET /api/maps/3 -> 500",
                                                    "ERROR build failed: code"]
    calls = []
    monkeypatch.setattr(tickets, "relay_call", lambda path, data=None, secret="": calls.append(data) or
                        {"number": 3, "secret": "s" * 32})
    store = TicketStore(tmp_path)
    ticket = store.create("Crash", trail={"server": recent, "ui": ["10:00:00 tab maps"]})
    store.send(ticket["id"])
    body = calls[0]["body"]
    assert body.startswith("Crash\n\n<details>") and "[server]" in body and "[ui] 10:00:00 tab maps" in body
    assert "trail" not in store.create("Plain")


def test_the_testers_name_is_kept_and_joined_to_the_tickets(tmp_path, monkeypatch):
    """The optional name of the Ticket panel: kept in the settings, joined to each ticket as context "tester"."""
    from fe_maker import api
    from fe_maker.config import Settings

    monkeypatch.setattr(api, "tickets", TicketStore(tmp_path))
    monkeypatch.setattr(api.state, "settings", Settings())
    monkeypatch.setattr(api.state, "project", None)
    monkeypatch.setattr(Settings, "save", lambda self: None)
    ticket = api.create_ticket(api.TicketIn(body="Anonymous", send=False))
    assert "tester" not in ticket["context"]
    assert api.update_settings(api.SettingsIn(testerName="  Some   one  "))["testerName"] == "Some one"
    ticket = api.create_ticket(api.TicketIn(body="Signed", send=False))
    assert ticket["context"]["tester"] == "Some one"
