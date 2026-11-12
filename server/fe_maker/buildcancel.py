"""Cancelling the running build (ticket 40): the build registers its process (make, or `docker run`); cancel() kills it
with its children and the build raises BuildCancelled at its next step."""

from __future__ import annotations

import os
import shutil
import subprocess
import threading
from pathlib import Path

_lock = threading.Lock()
_process: subprocess.Popen | None = None
_container = ""          # Docker: the container to stop (killing `docker run` leaves it running)
_cancelled = threading.Event()


class BuildCancelled(Exception):
    pass


def reset() -> None:
    """A new build starts: forget an earlier cancel."""
    _cancelled.clear()


def requested() -> bool:
    return _cancelled.is_set()


def check() -> None:
    """Between two steps of a build: stop here if cancelled."""
    if _cancelled.is_set():
        raise BuildCancelled()


def register(process: subprocess.Popen | None, container: str = "") -> None:
    """The build's running process (None once it ended); killed at once if the build was cancelled meanwhile."""
    global _process, _container
    with _lock:
        _process, _container = process, container
    if process is not None and _cancelled.is_set():
        _kill(process, container)


def cancel() -> bool:
    """Ask the running build to stop; False when no build process runs (a build still preparing stops at its next
    step anyway)."""
    _cancelled.set()
    with _lock:
        process, container = _process, _container
    if process is None or process.poll() is not None:
        return False
    _kill(process, container)
    return True


def _kill(process: subprocess.Popen, container: str) -> None:
    if container and (docker := shutil.which("docker")):
        subprocess.run([docker, "kill", container], capture_output=True)
    if os.name == "nt":   # make's children (the compilers) too
        subprocess.run(["taskkill", "/F", "/T", "/PID", str(process.pid)], capture_output=True,
                       creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    else:
        try:
            os.killpg(process.pid, 9)
        except OSError:
            process.kill()


def forget_outputs(work: Path, since: float) -> None:
    """After a cancelled build: the files make wrote since `since` may be cut short; remove them so that the next build
    makes them again (objects, the C files' assembly, the ROM)."""
    margin = since - 2   # file times are not exact
    for path in work.rglob("*"):
        try:
            if not path.is_file() or path.stat().st_mtime < margin:
                continue
        except OSError:
            continue
        generated = path.suffix in (".o", ".gba", ".elf", ".map") or (
            path.suffix == ".s" and path.with_suffix(".c").is_file())
        if generated:
            path.unlink(missing_ok=True)
