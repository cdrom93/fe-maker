"""Compile the FE8 decomp inside the FE Maker Docker image.

The decomp submodule is mounted read-only. Compilation happens in a working
copy kept in a Docker named volume; project files are applied on top of it
through an overlay directory.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
import time
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path

from .paths import DECOMP_DIR, DOCKER_DIR
from .rom import check_rom

IMAGE = "fe-maker-build"

DOCKER_FALLBACKS = [
    r"C:\Program Files\Docker\Docker\resources\bin\docker.exe",
    "/usr/local/bin/docker",
    "/Applications/Docker.app/Contents/Resources/bin/docker",
]


class BuildError(Exception):
    pass


@dataclass
class BuildResult:
    rom_path: Path
    matches_original: bool
    log: str


def _try_lock(file) -> bool:
    try:
        if os.name == "nt":
            import msvcrt

            msvcrt.locking(file.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl

            fcntl.flock(file, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        return False
    return True


@contextmanager
def build_lock(on_output: Callable[[str], None] | None = None, poll: float = 1.0) -> Iterator[None]:
    """One build at a time on this computer, whatever program asks for it (FE Maker, a second server, playtests): they
    share the working copy of the Docker volume, and two builds at once mix their projects' files (ticket 57). The
    system frees the lock when the process ends, even after a crash."""
    with open(Path(tempfile.gettempdir()) / "fe-maker-build.lock", "a+b") as file:
        waited = False
        while not _try_lock(file):
            if not waited and on_output:
                on_output("[fe-maker] Another build is running, waiting for it...\n")
            waited = True
            time.sleep(poll)
        try:
            yield
        finally:
            if os.name == "nt":
                import msvcrt

                file.seek(0)
                msvcrt.locking(file.fileno(), msvcrt.LK_UNLCK, 1)


def find_docker() -> str:
    found = shutil.which("docker")
    if found:
        return found
    for candidate in DOCKER_FALLBACKS:
        if Path(candidate).exists():
            return candidate
    raise BuildError("Docker not found. Install Docker Desktop and start it.")


def ensure_lf_checkout(decomp_dir: Path = DECOMP_DIR) -> None:
    """Git for Windows converts text files to CRLF by default, which breaks
    the Linux build. Force the submodule checkout to keep LF line endings."""
    git = shutil.which("git")
    if not git:
        return

    def git_config(key: str) -> str:
        result = subprocess.run([git, "-C", str(decomp_dir), "config", "--get", key], capture_output=True, text=True)
        return result.stdout.strip()

    if git_config("core.autocrlf") == "false" and git_config("core.eol") == "lf":
        return
    subprocess.run([git, "-C", str(decomp_dir), "config", "core.autocrlf", "false"], check=True)
    subprocess.run([git, "-C", str(decomp_dir), "config", "core.eol", "lf"], check=True)
    subprocess.run([git, "-C", str(decomp_dir), "rm", "-r", "-q", "--cached", "."], check=True)
    subprocess.run([git, "-C", str(decomp_dir), "reset", "-q", "--hard"], check=True)


def build(
    rom: Path,
    out_dir: Path,
    overlay: Path | None = None,
    bugfix: bool = False,
    on_output: Callable[[str], None] | None = None,
) -> BuildResult:
    """Build the ROM and copy it to out_dir/fireemblem8.gba."""
    check_rom(rom)
    if not (DECOMP_DIR / "Makefile").is_file():
        raise BuildError("Decomp submodule missing. Run: git submodule update --init")
    ensure_lf_checkout()

    out_dir = out_dir.resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    docker = find_docker()

    # Separate caches: make does not notice a change of compiler flags.
    volume = "fe-maker-work-bugfix" if bugfix else "fe-maker-work"
    args = [
        docker, "run", "--rm",
        "-e", f"FE_MAKER_BUGFIX={1 if bugfix else 0}",
        "-v", f"{DECOMP_DIR}:/src:ro",
        "-v", f"{rom.resolve()}:/rom/baserom.gba:ro",
        "-v", f"{volume}:/work",
        "-v", f"{out_dir}:/out",
    ]
    if overlay is not None:
        overlay = overlay.resolve()
        if not overlay.is_dir():
            raise BuildError(f"Overlay directory not found: {overlay}")
        args += ["-v", f"{overlay}:/overlay:ro"]
    args.append(IMAGE)

    log_lines: list[str] = []
    with build_lock(on_output):
        for command in ([docker, "build", "-q", "-t", IMAGE, str(DOCKER_DIR)], args):
            process = subprocess.Popen(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
            )
            assert process.stdout is not None
            for line in process.stdout:
                log_lines.append(line)
                if on_output:
                    on_output(line)
            if process.wait() != 0:
                raise BuildError("Build failed:\n" + "".join(log_lines[-40:]))

    log = "".join(log_lines)
    return BuildResult(
        rom_path=out_dir / "fireemblem8.gba",
        matches_original="fireemblem8.gba: OK" in log,
        log=log,
    )
