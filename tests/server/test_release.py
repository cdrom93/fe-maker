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
    assert found["toolchain"] == {"id": "toolchain", "ok": False, "detail": "", "download": None} and "docker" not in found
    started = []
    monkeypatch.setattr(native, "toolchain_ready", lambda toolchain=None: True)
    monkeypatch.setattr(native, "start_warmup", lambda rom, decomp: started.append(rom))
    monkeypatch.setattr(native, "warmup_state", lambda: "running")
    settings = Settings(mgba_path="mgba")
    monkeypatch.setattr(Settings, "has_rom", property(lambda self: True))
    (tmp_path / "Makefile").write_text("")
    found = {c["id"]: c for c in checks.run_checks(settings, tmp_path)}
    assert found["firstBuild"] == {"id": "firstBuild", "ok": False, "detail": "running", "progress": 0.0} and started


def test_the_installers_python_finds_fe_maker_and_its_dependencies(tmp_path):
    spec = importlib.util.spec_from_file_location("make_installer", ROOT / "tools/make_installer.py")
    installer = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(installer)
    lines = installer.pth("311").splitlines()
    assert lines[0] == "python311.zip" and r"..\server" in lines and "import site" in lines
    assert installer.numeric("0.1.0-prealpha.41") == "0.1.0.41" and installer.numeric("1.2.0") == "1.2.0.0"
    assert installer.numeric("0.43") == "0.43.0.0"
    needed = installer.dependencies()
    assert any(d.startswith("fastapi") for d in needed) and not any(d.startswith("pytest") for d in needed)
    # an update of an installed FE Maker installs the same list with its own Python, an update from the zip the .venv's
    (tmp_path / "server").mkdir()
    (tmp_path / "server" / "pyproject.toml").write_text((ROOT / "server/pyproject.toml").read_text(encoding="utf-8"))
    from fe_maker import update
    assert update.pip_command(tmp_path)[-2:] == ["-e", str(tmp_path / "server")]
    (tmp_path / "python").mkdir()
    (tmp_path / "python" / "python.exe").write_bytes(b"")
    command = update.pip_command(tmp_path)
    assert command[0] == str(tmp_path / "python" / "python.exe") and command[-len(needed):] == needed


def test_downloads_run_in_the_background_with_their_progress(monkeypatch):
    import threading

    from fe_maker import downloads

    class Response(io.BytesIO):
        headers = {"Content-Length": "600000"}

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

    monkeypatch.setattr(downloads.urllib.request, "urlopen", lambda *a, **k: Response(b"x" * 600000))
    release = threading.Event()
    got = {}

    def run():
        got["data"] = downloads.get("https://example.org/a.zip", 10**7, 5)
        release.wait(5)

    downloads.start("test-a", run, ValueError)
    downloads.start("test-a", lambda: got.setdefault("twice", True), ValueError)   # already running: not started again
    for _ in range(100):
        if downloads.state("test-a")["received"] == 600000:
            break
        threading.Event().wait(0.02)
    assert downloads.state("test-a") == {"state": "running", "received": 600000, "total": 600000, "error": ""}
    release.set()
    for _ in range(100):
        if downloads.state("test-a")["state"] != "running":
            break
        threading.Event().wait(0.02)
    assert downloads.state("test-a")["state"] == "done" and len(got["data"]) == 600000 and "twice" not in got

    def broken():
        raise ValueError("badArchive")

    downloads.start("test-b", broken, ValueError)
    for _ in range(100):
        if downloads.state("test-b")["state"] != "running":
            break
        threading.Event().wait(0.02)
    assert downloads.state("test-b")["error"] == "badArchive" and downloads.state("test-c") is None


@pytest.mark.skipif(not __import__("fe_maker.mgbafetch").mgbafetch.available(), reason="Windows' tar")
def test_mgba_is_unpacked_with_windows_tar(tmp_path):
    from fe_maker import mgbafetch

    with pytest.raises(mgbafetch.MgbaFetchError):
        mgbafetch.install(b"not an archive", tmp_path / "mgba")
    assert not (tmp_path / "mgba").exists() and not (tmp_path / "mgba.download").exists()
    archive = _zip({"mGBA-1-win64/mGBA.exe": "exe", "mGBA-1-win64/portable.ini": ""})   # tar reads zip too
    exe = mgbafetch.install(archive, tmp_path / "mgba")
    assert exe == tmp_path / "mgba" / "mGBA-1-win64" / "mGBA.exe" and exe.read_text() == "exe"
