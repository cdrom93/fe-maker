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
    path, data, _ = calls[0]
    assert data["body"] == "Broken map" and data["context"] == {"tab": "Maps"} and data["version"]
    assert data["images"][0].startswith("data:image/png;base64,") and data["project"] == {"data": "emlw"}
    assert store.send(ticket["id"]) == sent and len(calls) == 1      # never sent twice
    with_comment = store.add_comment(ticket["id"], "More")
    store.send_comment(ticket["id"], with_comment["comments"][-1]["id"])
    assert calls[-1][0] == "/v1/tickets/12/comments" and calls[-1][2] == "s" * 32
    assert store.list()[0]["comments"][-1]["sent"] is True
    synced = store.sync()[0]
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
