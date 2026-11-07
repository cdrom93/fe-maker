"""Compile the FE8 decomp: natively on Windows when FE Maker's toolchain is installed (native/), else inside the
FE Maker Docker image.

The decomp is never modified. Compilation happens in a working copy (a Docker named volume, or a folder of the
config directory for a native build); project files are applied on top of it through an overlay directory.
"""

from __future__ import annotations

import hashlib
import os
import shutil
import subprocess
import tempfile
import time
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path

from . import native
from .paths import DECOMP_DIR, DOCKER_DIR
from .rom import check_rom

IMAGE = "fe-maker-build"
# Published by .github/workflows/image.yml, so that a first build does not spend ten minutes compiling agbcc.
REGISTRY_IMAGE = "ghcr.io/cdrom93/fe-maker-build"

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
def build_lock(on_output: Callable[[str], None] | None = None, poll: float = 1.0,
               where: Path | None = None) -> Iterator[None]:
    """One build at a time per working copy, whatever program asks for it (FE Maker, a second server, playtests): two
    builds at once in one working copy mix their projects' files (ticket 57). Docker's volume is one for the whole
    computer (the lock in the temporary folder); a build without Docker locks its own working copies (`where`), so a
    program with another FE_MAKER_HOME does not wait (ticket 20). The system frees the lock when the process ends,
    even after a crash."""
    folder = where or Path(tempfile.gettempdir())
    folder.mkdir(parents=True, exist_ok=True)
    with open(folder / "fe-maker-build.lock", "a+b") as file:
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
    if not git or not (decomp_dir / ".git").exists():   # a release's download has LF endings already
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


def image_tag() -> str:
    """The image's version: the hash of what it is made from (line endings aside)."""
    digest = hashlib.sha256()
    for name in ("Dockerfile", "entrypoint.sh"):
        digest.update((DOCKER_DIR / name).read_bytes().replace(b"\r\n", b"\n"))
    return digest.hexdigest()[:12]


def ensure_image(docker: str, on_output: Callable[[str], None] | None = None) -> str:
    """The build image of this version: already here, else published, else built."""
    def run(*args: str) -> bool:
        return subprocess.run([docker, *args], capture_output=True).returncode == 0

    image = f"{IMAGE}:{image_tag()}"
    if run("image", "inspect", image):
        return image
    published = f"{REGISTRY_IMAGE}:{image_tag()}"
    if on_output:
        on_output("Getting the build tools (first time only)...\n")
    if run("pull", published) and run("tag", published, image):
        return image
    if on_output:
        on_output("Preparing the build tools (first time only, about ten minutes)...\n")
    result = subprocess.run([docker, "build", "-q", "-t", image, str(DOCKER_DIR)], capture_output=True, text=True,
                            encoding="utf-8", errors="replace")
    if result.returncode != 0:
        raise BuildError("Build failed:\n" + result.stdout[-2000:] + result.stderr[-2000:])
    return image


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
    if overlay is not None and not overlay.is_dir():
        raise BuildError(f"Overlay directory not found: {overlay}")
    if native.available():   # Windows without Docker (docs/sans-docker.md); Docker stays the fallback
        with build_lock(on_output, where=native.work_dir(bugfix).parent):
            try:
                log = native.build(rom.resolve(), out_dir, DECOMP_DIR, overlay.resolve() if overlay else None, bugfix,
                                   on_output)
            except native.NativeBuildError as e:
                raise BuildError("Build failed:\n" + str(e)) from e
        return BuildResult(rom_path=out_dir / "fireemblem8.gba", matches_original="fireemblem8.gba: OK" in log, log=log)
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

    log_lines: list[str] = []
    with build_lock(on_output):
        process = subprocess.Popen(
            [*args, ensure_image(docker, on_output)],
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
