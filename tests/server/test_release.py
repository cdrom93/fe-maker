import importlib.util
import io
import zipfile
from pathlib import Path

import pytest

from fe_maker import builder, decompfetch

ROOT = Path(__file__).resolve().parents[2]


def _zip(files: dict[str, str]) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as z:
        for name, text in files.items():
            z.writestr(name, text)
    return buffer.getvalue()


def test_the_archive_top_folder_becomes_the_decomp(tmp_path):
    target = tmp_path / "decomp"
    decompfetch.extract(_zip({"fireemblem8u-abc/Makefile": "all:", "fireemblem8u-abc/src/a.c": "int a;"}), target)
    assert (target / "src/a.c").read_text() == "int a;"
    assert not (tmp_path / "decomp.download").exists()


def test_a_bad_download_keeps_what_was_there(tmp_path):
    target = tmp_path / "decomp"
    target.mkdir()
    (target / "Makefile").write_text("old")
    with pytest.raises(decompfetch.DecompFetchError):
        decompfetch.extract(_zip({"top/other.txt": ""}), target)
    with pytest.raises(decompfetch.DecompFetchError):
        decompfetch.extract(b"not a zip", target)
    with pytest.raises(decompfetch.DecompFetchError):
        decompfetch.extract(_zip({"top/../../evil": "", "top/Makefile": ""}), target)
    assert (target / "Makefile").read_text() == "old"


def test_the_image_tag_ignores_line_endings(tmp_path, monkeypatch):
    for name in ("Dockerfile", "entrypoint.sh"):
        (tmp_path / name).write_bytes(b"line\r\nline\r\n")
    monkeypatch.setattr(builder, "DOCKER_DIR", tmp_path)
    crlf = builder.image_tag()
    for name in ("Dockerfile", "entrypoint.sh"):
        (tmp_path / name).write_bytes(b"line\nline\n")
    assert builder.image_tag() == crlf


def test_the_package_refuses_game_files():
    spec = importlib.util.spec_from_file_location("make_release", ROOT / "tools/make_release.py")
    release = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(release)
    assert release.FORBIDDEN.search("rom/game.gba") and release.FORBIDDEN.search("decomp/src/a.c")
    assert release.FORBIDDEN.search("x/patch.ups") and not release.FORBIDDEN.search("server/fe_maker/decomp/maps.py")


def test_a_checkout_has_everything_but_the_rom(monkeypatch, tmp_path):
    from fe_maker import checks
    from fe_maker.config import Settings

    monkeypatch.setattr(checks, "_docker_state", lambda: (False, "stopped"))
    monkeypatch.setattr(checks, "_windows", lambda: False)
    monkeypatch.setenv("FE_MAKER_HOME", str(tmp_path))
    found = {c["id"]: c for c in checks.run_checks(Settings(mgba_path="mgba"), tmp_path)}
    assert not found["rom"]["ok"] and not found["decomp"]["ok"] and found["mgba"]["ok"]
    assert found["docker"] == {"id": "docker", "ok": False, "detail": "stopped"}


def test_a_stopped_docker_desktop_is_started(monkeypatch, tmp_path):
    from fe_maker import checks
    from fe_maker.config import Settings

    exe = tmp_path / "Docker" / "Docker" / "Docker Desktop.exe"
    exe.parent.mkdir(parents=True)
    exe.write_bytes(b"")
    launched = []
    monkeypatch.setenv("ProgramFiles", str(tmp_path))
    monkeypatch.setattr(checks, "_docker_state", lambda: (False, "stopped"))
    monkeypatch.setattr(checks.subprocess, "Popen", lambda args, **kw: launched.append(args))
    monkeypatch.setattr(checks, "_docker_started_at", None)
    monkeypatch.setattr(checks, "_windows", lambda: False)
    monkeypatch.setattr(checks.native, "available", lambda: False)
    assert checks.start_docker() and launched == [[str(exe)]]
    found = {c["id"]: c for c in checks.run_checks(Settings(mgba_path="mgba"), tmp_path)}
    assert found["docker"]["detail"] == "starting"
    monkeypatch.setattr(checks, "_docker_state", lambda: (True, "27.0"))
    assert not checks.start_docker()


def test_docker_desktop_is_left_alone_when_builds_run_without_it(monkeypatch, tmp_path):
    from fe_maker import checks

    exe = tmp_path / "Docker" / "Docker" / "Docker Desktop.exe"
    exe.parent.mkdir(parents=True)
    exe.write_bytes(b"")
    launched = []
    monkeypatch.setenv("ProgramFiles", str(tmp_path))
    monkeypatch.setattr(checks, "_docker_state", lambda: (False, "stopped"))
    monkeypatch.setattr(checks.subprocess, "Popen", lambda args, **kw: launched.append(args))
    monkeypatch.setattr(checks.native, "available", lambda: True)
    assert not checks.start_docker() and launched == []


def test_windows_asks_for_the_toolchain_then_builds_once_in_the_background(monkeypatch, tmp_path):
    from fe_maker import checks, native
    from fe_maker.config import Settings

    monkeypatch.setattr(checks, "_windows", lambda: True)
    monkeypatch.setattr(checks, "_docker_state", lambda: (False, "missing"))
    monkeypatch.setenv("FE_MAKER_TOOLCHAIN", str(tmp_path / "toolchain"))
    monkeypatch.delenv("FE_MAKER_BUILDER", raising=False)
    found = {c["id"]: c for c in checks.run_checks(Settings(mgba_path="mgba"), tmp_path)}
    assert found["toolchain"] == {"id": "toolchain", "ok": False, "detail": ""} and "docker" not in found
    started = []
    monkeypatch.setattr(native, "toolchain_ready", lambda toolchain=None: True)
    monkeypatch.setattr(native, "start_warmup", lambda rom, decomp: started.append(rom))
    monkeypatch.setattr(native, "warmup_state", lambda: "running")
    settings = Settings(mgba_path="mgba")
    monkeypatch.setattr(Settings, "has_rom", property(lambda self: True))
    (tmp_path / "Makefile").write_text("")
    found = {c["id"]: c for c in checks.run_checks(settings, tmp_path)}
    assert found["firstBuild"] == {"id": "firstBuild", "ok": False, "detail": "running"} and started
