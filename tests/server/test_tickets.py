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
