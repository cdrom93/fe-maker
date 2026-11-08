"""Ticket 30: each build's duration kept, most recent first."""

from fe_maker import builder, buildtimes
from fe_maker.project import _timing


def test_builds_are_recorded_most_recent_first(tmp_path, monkeypatch):
    monkeypatch.setattr(buildtimes, "config_dir", lambda: tmp_path)
    assert buildtimes.recent() == []
    buildtimes.record("a", 61.24, True, False, 12, 300)
    entry = buildtimes.record("b", 8.0, False, True, 1, 20)
    assert entry["seconds"] == 8.0 and entry["test"] and not entry["native"]
    assert [e["project"] for e in buildtimes.recent()] == ["b", "a"]
    assert buildtimes.recent()[1]["seconds"] == 61.2
    for n in range(buildtimes.KEEP):
        buildtimes.record(str(n), 1, True, True, 0, 0)
    assert len(buildtimes.recent()) == buildtimes.KEEP


def test_a_damaged_history_is_ignored(tmp_path, monkeypatch):
    monkeypatch.setattr(buildtimes, "config_dir", lambda: tmp_path)
    (tmp_path / "build-times.json").write_text("{not json", encoding="utf-8")
    assert buildtimes.recent() == []
    buildtimes.record("a", 1, True, True, 0, 0)
    assert len(buildtimes.recent()) == 1


def test_the_c_files_compiled_are_counted_from_the_log():
    log = ("arm-none-eabi-cpp src/a.c | iconv | tools/agbcc/bin/agbcc.exe -O2 -o src/a.s\n"
           "arm-none-eabi-as -o src/a.o src/a.s\n"
           "arm-none-eabi-cpp src/b.c | iconv | tools/agbcc/bin/agbcc -O2 -o src/b.s\n")
    result = builder.BuildResult(rom_path=None, matches_original=False, log=log, seconds=3.5, native=True)
    assert _timing(result) == {"seconds": 3.5, "native": True, "compiled": 2}
