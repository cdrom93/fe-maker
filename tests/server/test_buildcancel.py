import os
import subprocess
import sys
import time

import pytest

from fe_maker import buildcancel


def test_cancel_kills_the_running_process_and_stops_the_build():
    buildcancel.reset()
    process = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)"],
                               start_new_session=os.name != "nt")
    buildcancel.register(process)
    try:
        buildcancel.check()   # not cancelled yet
        assert buildcancel.cancel()
        assert process.wait(timeout=20) != 0
        with pytest.raises(buildcancel.BuildCancelled):
            buildcancel.check()
    finally:
        buildcancel.register(None)
        buildcancel.reset()
        if process.poll() is None:
            process.kill()


def test_a_process_started_after_the_cancel_is_killed_at_once():
    buildcancel.reset()
    buildcancel.cancel()   # nothing runs yet: the build stops at its next step
    process = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)"],
                               start_new_session=os.name != "nt")
    try:
        buildcancel.register(process)
        assert process.wait(timeout=20) != 0
    finally:
        buildcancel.register(None)
        buildcancel.reset()
        if process.poll() is None:
            process.kill()


def test_forget_outputs_removes_what_make_wrote_during_the_build(tmp_path):
    old = time.time() - 3600
    files = {name: tmp_path / name for name in ("src/a.c", "src/a.s", "src/a.o", "asm/b.s", "asm/b.o", "src/c.o",
                                                 "fireemblem8.gba")}
    for path in files.values():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("x")
    os.utime(files["src/c.o"], (old, old))   # made by an earlier build: kept
    buildcancel.forget_outputs(tmp_path, time.time() - 60)
    kept = {name for name, path in files.items() if path.exists()}
    assert kept == {"src/a.c", "asm/b.s", "src/c.o"}   # sources stay; the C file's assembly and the objects go
