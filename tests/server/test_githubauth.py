"""The optional GitHub sign-in of the tickets (githubauth.py), with a fake GitHub."""

import pytest

from fe_maker import githubauth, tickets
from fe_maker.tickets import TicketStore


@pytest.fixture
def github(tmp_path, monkeypatch):
    monkeypatch.setattr(githubauth, "config_dir", lambda: tmp_path)
    monkeypatch.setattr(githubauth, "CLIENT_ID", "client")
    monkeypatch.delenv("FE_MAKER_GITHUB_CLIENT_ID", raising=False)
    answers = {"token": [{"error": "authorization_pending"}, {"error": "slow_down", "interval": 10},
                         {"access_token": "gho_secret"}]}

    def call(url, data=None, token=""):
        if url == githubauth.DEVICE_URL:
            assert data == {"client_id": "client", "scope": ""}
            return {"device_code": "dev", "user_code": "ABCD-1234", "verification_uri": "https://github.com/login/device",
                    "interval": 5, "expires_in": 900}
        if url == githubauth.TOKEN_URL:
            assert data["device_code"] == "dev"
            return answers["token"].pop(0)
        assert url == githubauth.USER_URL and token == "gho_secret"
        return {"login": "known-member"}

    monkeypatch.setattr(githubauth, "_call", call)
    githubauth._pending.clear()
    return tmp_path


def test_device_flow_signs_in_and_out(github):
    assert githubauth.account() is None
    assert githubauth.start()["userCode"] == "ABCD-1234"
    assert githubauth.poll() == {"state": "pending", "interval": 5}
    assert githubauth.poll() == {"state": "pending", "interval": 10}
    assert githubauth.poll() == {"state": "done", "login": "known-member"}
    assert githubauth.account() == {"login": "known-member", "token": "gho_secret"}
    assert githubauth.poll() == {"state": "expired"}
    githubauth.sign_out()
    assert githubauth.account() is None


def test_not_offered_without_a_client_id(github, monkeypatch):
    monkeypatch.setattr(githubauth, "CLIENT_ID", "")
    with pytest.raises(githubauth.GithubAuthError, match="githubUnavailable"):
        githubauth.start()


def test_a_signed_in_testers_token_goes_to_the_relay_only(github, tmp_path, monkeypatch):
    sent = []
    monkeypatch.setattr(tickets, "relay_call",
                        lambda path, data=None, secret="": sent.append(data) or {"number": 3, "secret": "s"})
    store = TicketStore(tmp_path / "tickets")
    first = store.create("Anonymous")
    store.send(first["id"])
    githubauth.start()
    for _ in range(3):
        githubauth.poll()
    second = store.create("Signed")
    store.send(second["id"])
    assert "githubToken" not in sent[0] and sent[1]["githubToken"] == "gho_secret"
    assert "gho_secret" not in (tmp_path / "tickets").joinpath("tickets.json").read_text(encoding="utf-8")
