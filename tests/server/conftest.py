import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "server"))

FIXTURE_DECOMP = Path(__file__).parent / "fixtures" / "decomp"


@pytest.fixture
def decomp_dir() -> Path:
    return FIXTURE_DECOMP
