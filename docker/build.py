"""Build the FE8 decomp inside the FE Maker Docker image.

Usage: python docker/build.py --rom PATH/TO/fe8.gba [--out build]

Phase 0 helper: builds the untouched decomp submodule. The submodule is
mounted read-only; compilation happens in a working copy kept in a Docker
named volume.
"""

import argparse
import hashlib
import shutil
import subprocess
import sys
from pathlib import Path

FE8_US_SHA1 = "c25b145e37456171ada4b0d440bf88a19f4d509f"
IMAGE = "fe-maker-build"
WORK_VOLUME = "fe-maker-work"

REPO_ROOT = Path(__file__).resolve().parent.parent
DOCKER_DIR = REPO_ROOT / "docker"
DECOMP_DIR = REPO_ROOT / "decomp"

DOCKER_FALLBACKS = [
    r"C:\Program Files\Docker\Docker\resources\bin\docker.exe",
    "/usr/local/bin/docker",
    "/Applications/Docker.app/Contents/Resources/bin/docker",
]


def find_docker() -> str:
    found = shutil.which("docker")
    if found:
        return found
    for candidate in DOCKER_FALLBACKS:
        if Path(candidate).exists():
            return candidate
    sys.exit("Docker not found. Install Docker Desktop and start it.")


def sha1_of(path: Path) -> str:
    h = hashlib.sha1()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def ensure_lf_checkout() -> None:
    """Git for Windows converts text files to CRLF by default, which breaks
    the Linux build. Force the submodule checkout to keep LF line endings."""
    git = shutil.which("git")
    if not git:
        return
    def git_config(key: str) -> str:
        result = subprocess.run([git, "-C", str(DECOMP_DIR), "config", "--get", key], capture_output=True, text=True)
        return result.stdout.strip()
    if git_config("core.autocrlf") == "false" and git_config("core.eol") == "lf":
        return
    print("Configuring decomp checkout to use LF line endings...")
    subprocess.run([git, "-C", str(DECOMP_DIR), "config", "core.autocrlf", "false"], check=True)
    subprocess.run([git, "-C", str(DECOMP_DIR), "config", "core.eol", "lf"], check=True)
    subprocess.run([git, "-C", str(DECOMP_DIR), "rm", "-r", "-q", "--cached", "."], check=True)
    subprocess.run([git, "-C", str(DECOMP_DIR), "reset", "-q", "--hard"], check=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rom", required=True, type=Path, help="Fire Emblem: The Sacred Stones (US) ROM")
    parser.add_argument("--out", default=REPO_ROOT / "build", type=Path, help="output directory")
    args = parser.parse_args()

    rom = args.rom.resolve()
    if not rom.is_file():
        sys.exit(f"ROM not found: {rom}")
    if sha1_of(rom) != FE8_US_SHA1:
        sys.exit("This ROM is not Fire Emblem: The Sacred Stones (US). Expected SHA1 " + FE8_US_SHA1)
    if not (DECOMP_DIR / "Makefile").is_file():
        sys.exit("Decomp submodule missing. Run: git submodule update --init")
    ensure_lf_checkout()

    out = args.out.resolve()
    out.mkdir(parents=True, exist_ok=True)
    docker = find_docker()

    subprocess.run([docker, "build", "-t", IMAGE, str(DOCKER_DIR)], check=True)
    subprocess.run(
        [
            docker, "run", "--rm",
            "-v", f"{DECOMP_DIR}:/src:ro",
            "-v", f"{rom}:/rom/baserom.gba:ro",
            "-v", f"{WORK_VOLUME}:/work",
            "-v", f"{out}:/out",
            IMAGE,
        ],
        check=True,
    )


if __name__ == "__main__":
    main()
