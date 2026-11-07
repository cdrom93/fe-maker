import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "server"))

FIXTURE_DECOMP = Path(__file__).parent / "fixtures" / "decomp"


@pytest.fixture
def decomp_dir() -> Path:
    return FIXTURE_DECOMP


@pytest.fixture(autouse=True)
def no_ticket_relay(monkeypatch):
    """Tests never send tickets to the real relay (tickets.py); test_tickets.py gives a fake one."""
    monkeypatch.setenv("FE_MAKER_RELAY", "off")
    from fe_maker import tickets

    monkeypatch.setattr(tickets, "_admin", False)   # nor ask gh whether the admin mode is on
