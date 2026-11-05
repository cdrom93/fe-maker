import threading
import time

from fe_maker.builder import build_lock


def test_a_second_build_waits_for_the_first():
    order, said = [], []

    def second():
        with build_lock(said.append, poll=0.01):
            order.append("second")

    with build_lock():
        thread = threading.Thread(target=second)
        thread.start()
        time.sleep(0.1)
        order.append("first done")
    thread.join(timeout=5)
    assert order == ["first done", "second"]
    assert "waiting" in said[0]


def test_the_build_bar_guesses_from_the_last_build(tmp_path, monkeypatch):
    from fe_maker import api

    monkeypatch.setenv("FE_MAKER_HOME", str(tmp_path))
    assert api.expected_build_lines() == api.FIRST_BUILD_LINES
    (tmp_path / "build-lines.txt").write_text("42", encoding="utf-8")
    assert api.expected_build_lines() == 42
