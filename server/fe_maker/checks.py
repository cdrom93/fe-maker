"""What FE Maker needs on this computer, checked at each start (alpha, step 6): the home page shows what is missing
with what to do about it. Each check is {"id", "ok", "detail"}; the texts are in the interface (`checks.<id>...`).
"""

from __future__ import annotations

import os
import shutil
import subprocess
import time
from pathlib import Path

from .config import Settings, find_mgba
from .paths import DECOMP_DIR

DOCKER_TIMEOUT = 20
DOCKER_STARTUP = 180   # seconds Docker Desktop may take to start before it is reported stopped again
_docker_started_at: float | None = None


def _docker_state() -> tuple[bool, str]:
    """(usable, detail): detail is "missing", "stopped" (Docker Desktop not started, or virtualization off in the
    BIOS: it then never starts) or the server's version."""
    docker = shutil.which("docker")
    if docker is None:
        return False, "missing"
    try:
        result = subprocess.run([docker, "version", "--format", "{{.Server.Version}}"], capture_output=True, text=True,
                                timeout=DOCKER_TIMEOUT)
    except (OSError, subprocess.TimeoutExpired):
        return False, "stopped"
    return (True, result.stdout.strip()) if result.returncode == 0 and result.stdout.strip() else (False, "stopped")


def docker_desktop() -> Path | None:
    """Docker Desktop's program on Windows, if installed."""
    for base in (os.environ.get("ProgramFiles"), os.environ.get("ProgramW6432")):
        if base and (exe := Path(base) / "Docker" / "Docker" / "Docker Desktop.exe").is_file():
            return exe
    return None


def start_docker() -> bool:
    """Start Docker Desktop when Docker is installed but does not answer (ticket 146), detached from FE Maker.
    True if it was launched."""
    global _docker_started_at
    exe = docker_desktop()
    if exe is None or _docker_state() != (False, "stopped"):
        return False
    flags = getattr(subprocess, "DETACHED_PROCESS", 0) | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
    try:
        subprocess.Popen([str(exe)], creationflags=flags, close_fds=True)
    except OSError:
        return False
    _docker_started_at = time.monotonic()
    return True


def run_checks(settings: Settings, decomp_dir: Path = DECOMP_DIR) -> list[dict]:
    docker_ok, docker_detail = _docker_state()
    if docker_detail == "stopped" and _docker_started_at is not None and time.monotonic() - _docker_started_at < DOCKER_STARTUP:
        docker_detail = "starting"
    return [
        {"id": "rom", "ok": settings.has_rom, "detail": ""},
        {"id": "decomp", "ok": (decomp_dir / "Makefile").is_file(), "detail": ""},
        {"id": "docker", "ok": docker_ok, "detail": docker_detail},
        {"id": "mgba", "ok": bool(settings.mgba_path or find_mgba()), "detail": ""},
    ]
