"""What FE Maker needs on this computer, checked at each start (alpha, step 6): the home page shows what is missing
with what to do about it. Each check is {"id", "ok", "detail"}; the texts are in the interface (`checks.<id>...`).
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

from .config import Settings, find_mgba
from .paths import DECOMP_DIR

DOCKER_TIMEOUT = 20


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


def run_checks(settings: Settings, decomp_dir: Path = DECOMP_DIR) -> list[dict]:
    docker_ok, docker_detail = _docker_state()
    return [
        {"id": "rom", "ok": settings.has_rom, "detail": ""},
        {"id": "decomp", "ok": (decomp_dir / "Makefile").is_file(), "detail": ""},
        {"id": "docker", "ok": docker_ok, "detail": docker_detail},
        {"id": "mgba", "ok": bool(settings.mgba_path or find_mgba()), "detail": ""},
    ]
