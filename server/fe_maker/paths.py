import os
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
DOCKER_DIR = REPO_ROOT / "docker"
# The commit FE Maker is written against: a release does not carry the decomp, it is downloaded at this commit.
DECOMP_COMMIT = "f2e1f060dbe5b0cc35285df5a0f6659860644a04"


def _config_dir() -> Path:
    from .config import config_dir

    return config_dir()


def _decomp_dir() -> Path:
    """The submodule in a checkout, else the copy downloaded for a release (decompfetch.py)."""
    override = os.environ.get("FE_MAKER_DECOMP")
    if override:
        return Path(override)
    submodule = REPO_ROOT / "decomp"
    return submodule if (submodule / "Makefile").is_file() else _config_dir() / "decomp"


DECOMP_DIR = _decomp_dir()
