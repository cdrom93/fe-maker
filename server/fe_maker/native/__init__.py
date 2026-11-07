"""Native Windows build: the decomp compiled without Docker (docs/sans-docker.md).

Same steps as docker/entrypoint.sh, in Python: a working copy of the decomp kept between builds (make only redoes
what changed), the project's overlay copied over it, then the decomp's own Makefile run by make and busybox from
FE Maker's toolchain archive, with win.mk replacing the few recipes Windows cannot run as written.

The toolchain (make, busybox, Arm binutils and preprocessor, agbcc, the decomp's MIT tools) is built by
.github/workflows/toolchain.yml and downloaded on first launch, like the decomp.
"""

from __future__ import annotations

import hashlib
import io
import os
import shutil
import subprocess
import sys
import urllib.request
import zipfile
from collections.abc import Callable
from pathlib import Path

NATIVE_DIR = Path(__file__).resolve().parent
TOOLCHAIN_VERSION = "1"
TOOLCHAIN_URL = ("https://github.com/cdrom93/fe-maker/releases/download/"
                 f"toolchain-{TOOLCHAIN_VERSION}/fe-maker-toolchain-win64-{TOOLCHAIN_VERSION}.zip")
MAX_TOOLCHAIN_SIZE = 300 * 1024 * 1024
# The decomp's conversion tools, prebuilt in the archive's tools/ folder, copied where its Makefile looks for them.
DECOMP_TOOLS = ("aif2pcm", "bin2c", "gbagfx", "mid2agb", "scaninc", "textencode")
OVERLAY_RECORD = ".fe-maker-overlay"     # files the last overlay wrote, restored from the decomp at the next build
BANIM_RECORD = ".fe-maker-banim-linker"


class NativeBuildError(Exception):
    pass


def _home() -> Path:
    from ..config import config_dir

    return config_dir()


def toolchain_dir() -> Path:
    override = os.environ.get("FE_MAKER_TOOLCHAIN")
    return Path(override) if override else _home() / "toolchain" / TOOLCHAIN_VERSION


def toolchain_ready(toolchain: Path | None = None) -> bool:
    toolchain = toolchain or toolchain_dir()
    return (toolchain / "bin" / "make.exe").is_file() and (toolchain / "agbcc" / "bin" / "agbcc.exe").is_file()


def available() -> bool:
    """A native build can run here: Windows, the toolchain installed, and not turned off (FE_MAKER_BUILDER=docker)."""
    return os.name == "nt" and os.environ.get("FE_MAKER_BUILDER") != "docker" and toolchain_ready()


def install_toolchain(archive: bytes, target: Path | None = None) -> None:
    """Unpack the toolchain archive into its folder, in one move: a broken download leaves nothing behind."""
    target = target or toolchain_dir()
    temporary = target.with_name(target.name + ".download")
    shutil.rmtree(temporary, ignore_errors=True)
    temporary.mkdir(parents=True)
    root = temporary.resolve()
    try:
        with zipfile.ZipFile(io.BytesIO(archive)) as z:
            for info in z.infolist():
                path = (temporary / info.filename).resolve()
                if not path.is_relative_to(root):
                    raise NativeBuildError("badArchive")
                if info.is_dir():
                    continue
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(z.read(info))
    except zipfile.BadZipFile as e:
        raise NativeBuildError("badArchive") from e
    if not toolchain_ready(temporary):
        raise NativeBuildError("badArchive")
    shutil.rmtree(target, ignore_errors=True)
    temporary.rename(target)


def fetch_toolchain() -> None:
    from ..ferepo import _ssl_context

    request = urllib.request.Request(TOOLCHAIN_URL, headers={"User-Agent": "FE-Maker"})
    try:
        with urllib.request.urlopen(request, timeout=300, context=_ssl_context()) as response:
            archive = response.read(MAX_TOOLCHAIN_SIZE)
    except OSError as e:
        raise NativeBuildError("unreachable") from e
    install_toolchain(archive)


READY_MARK = ".fe-maker-ready"   # in the working copy, after a first successful build
_warmup: dict = {"thread": None, "error": ""}


def warmed_up() -> bool:
    return (work_dir(False) / READY_MARK).is_file()


def warmup_state() -> str:
    """"done", "running", "failed" or "" (not started) for the first build made in the background."""
    if warmed_up():
        return "done"
    thread = _warmup["thread"]
    if thread is not None and thread.is_alive():
        return "running"
    return "failed" if _warmup["error"] else ""


def start_warmup(rom: Path, decomp: Path) -> None:
    """The first build takes ~8 minutes (thousands of files): make it right after installation, in the background,
    from the untouched decomp, so that the user's first test only rebuilds what the project changed. Stopped midway
    (FE Maker closed), the next launch carries on from what make already built."""
    import threading

    if warmup_state() in ("done", "running") or not available():
        return

    def run() -> None:
        from ..builder import BuildError
        from ..builder import build as full_build

        _warmup["error"] = ""
        out = _home() / "work" / "first-build"
        try:
            full_build(rom, out)
        except (BuildError, OSError) as e:
            _warmup["error"] = str(e)[-2000:]

    _warmup["thread"] = threading.Thread(target=run, name="fe-maker-first-build", daemon=True)
    _warmup["thread"].start()


def work_dir(bugfix: bool) -> Path:
    """The working copy, one per compiler flags (make does not notice a change of flags), like the Docker volumes."""
    return _home() / "work" / ("decomp-bugfix" if bugfix else "decomp")


def _same(a: Path, b: Path) -> bool:
    if a.stat().st_size != b.stat().st_size:
        return False
    with open(a, "rb") as fa, open(b, "rb") as fb:
        while True:
            chunk = fa.read(1 << 20)
            if chunk != fb.read(1 << 20):
                return False
            if not chunk:
                return True


def _copy_if_changed(src: Path, dst: Path, check_content: bool) -> bool:
    """Copy when missing or different; the copy gets a fresh time, so make rebuilds what depends on it."""
    if dst.is_file():
        if src.stat().st_size == dst.stat().st_size and not check_content and src.stat().st_mtime <= dst.stat().st_mtime:
            return False
        if _same(src, dst):
            return False
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(src, dst)
    return True


def _files(root: Path) -> list[Path]:
    found = []
    for folder, dirs, names in os.walk(root):
        dirs[:] = [d for d in dirs if d != ".git"]
        found.extend(Path(folder, name).relative_to(root) for name in names if name != ".git")
    return found


def sync(decomp: Path, work: Path, overlay: Path | None) -> int:
    """Like `rsync --checksum` of the decomp then of the overlay (entrypoint.sh): only files whose content differs
    are copied. A decomp file is compared by content only when it may differ: newer than its copy, or written by the
    previous project's overlay. Returns how many files were copied."""
    work.mkdir(parents=True, exist_ok=True)
    record = work / OVERLAY_RECORD
    previous = set(record.read_text(encoding="utf-8").splitlines()) if record.is_file() else set()
    overlay_files = set(_files(overlay)) if overlay is not None else set()
    copied = 0
    for relative in _files(decomp):
        if relative in overlay_files:
            continue
        copied += _copy_if_changed(decomp / relative, work / relative, relative.as_posix() in previous)
    for relative in overlay_files:
        copied += _copy_if_changed(overlay / relative, work / relative, True)
    for name in previous:   # a file only the previous project added (an imported song, animation...)
        if Path(name) not in overlay_files and not (decomp / name).exists():
            (work / name).unlink(missing_ok=True)
    record.write_text("\n".join(sorted(p.as_posix() for p in overlay_files)), encoding="utf-8")
    return copied


def _prepare(work: Path, toolchain: Path, rom: Path) -> None:
    # (Songs a project imported, song<n>_fem_<key>.mid, are removed by sync() with the project's other added files:
    # the Makefile builds every .mid it finds, and songs.mk has no rule for them without that project.)
    # data_banim.o depends on the objects its linker script lists, not on the script: rebuild it when it changes.
    banim_sum = hashlib.sha1((work / "linker_script_banim.txt").read_bytes()).hexdigest()
    record = work / BANIM_RECORD
    if not record.is_file() or record.read_text().strip() != banim_sum:
        (work / "data/banim/data_banim.o").unlink(missing_ok=True)
        record.write_text(banim_sum)
    shutil.copytree(toolchain / "agbcc", work / "tools/agbcc", dirs_exist_ok=True)
    for tool in DECOMP_TOOLS:
        _copy_if_changed(toolchain / "tools" / f"{tool}.exe", work / "tools" / tool / f"{tool}.exe", False)
    _copy_if_changed(rom, work / "baserom.gba", True)


def _quoted(path: Path | str) -> str:
    return '"' + str(path).replace("\\", "/") + '"'


def make_command(toolchain: Path, bugfix: bool) -> list[str]:
    cpp = "arm-none-eabi-cpp" + (" -DBUGFIX=1" if bugfix else "")
    return [
        str(toolchain / "bin" / "make.exe"), f"-j{os.cpu_count() or 4}",
        "-f", "Makefile", "-f", str(NATIVE_DIR / "win.mk").replace("\\", "/"),
        f"FEM_NATIVE={_quoted(NATIVE_DIR)}", f"PYTHON={_quoted(sys.executable)}", f"CPP={cpp}",
        "fireemblem8.gba",
    ]


def build(rom: Path, out_dir: Path, decomp: Path, overlay: Path | None = None, bugfix: bool = False,
          on_output: Callable[[str], None] | None = None) -> str:
    """Build the ROM into out_dir (fireemblem8.gba, .map, .elf) and return the log; raise NativeBuildError."""
    toolchain = toolchain_dir()
    work = work_dir(bugfix)
    log: list[str] = []

    def say(line: str) -> None:
        log.append(line)
        if on_output:
            on_output(line)

    say("[fe-maker] Syncing decomp into working copy...\n")
    sync(decomp, work, overlay)
    _prepare(work, toolchain, rom)
    if bugfix:
        say("[fe-maker] BUGFIX enabled\n")
    say("[fe-maker] Building ROM...\n")
    env = {**os.environ, "PATH": str(toolchain / "bin") + os.pathsep + os.environ.get("PATH", "")}
    for attempt in range(2):
        # Windows sometimes holds a file just written (the antivirus): `sed -i` then fails with "Permission denied", or
        # an assembly file is left half written. make starts again from the failed targets: one more try.
        if attempt:
            say("[fe-maker] Build failed, trying once more (a file may have been locked by Windows)...\n")
        process = subprocess.Popen(make_command(toolchain, bugfix), cwd=work, env=env, stdout=subprocess.PIPE,
                                   stderr=subprocess.STDOUT, text=True, encoding="utf-8", errors="replace",
                                   creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        assert process.stdout is not None
        for line in process.stdout:
            say(line)
        if process.wait() == 0:
            break
    else:
        raise NativeBuildError("".join(log[-40:]))
    rom_out = work / "fireemblem8.gba"
    expected = (work / "checksum.sha1").read_text().split()[0]
    if hashlib.sha1(rom_out.read_bytes()).hexdigest() == expected:
        say("fireemblem8.gba: OK\n")
    else:
        say("[fe-maker] Checksum differs from the original game (expected once the project is modified).\n")
    out_dir.mkdir(parents=True, exist_ok=True)
    for name in ("fireemblem8.gba", "fireemblem8.map", "fireemblem8.elf"):
        shutil.copyfile(work / name, out_dir / name)
    (work / READY_MARK).touch()
    say("[fe-maker] Done\n")
    return "".join(log)
