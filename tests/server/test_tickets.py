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
