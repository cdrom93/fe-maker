"""Optional GitHub sign-in of a tester, so their tickets say who wrote them (spec, section 4, ideas of 13/11).

GitHub's device flow: FE Maker shows a short code, the tester types it on github.com/login/device, and FE Maker gets
a token with no scope (it only proves the account). No secret is needed in FE Maker, only the public client id of
FE Maker's OAuth App. The token is kept in the config folder and sent with each ticket; the ticket relay asks GitHub
whose it is and writes that login on the issue itself, so it cannot be made up (relay/src/index.js, githubLogin).
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.parse
import urllib.request

from .config import config_dir

# The public client id of FE Maker's OAuth App (device flow enabled). Empty: the sign-in is not offered.
CLIENT_ID = ""
DEVICE_URL = "https://github.com/login/device/code"
TOKEN_URL = "https://github.com/login/oauth/access_token"
USER_URL = "https://api.github.com/user"


class GithubAuthError(Exception):
    pass


def client_id() -> str:
    return os.environ.get("FE_MAKER_GITHUB_CLIENT_ID", CLIENT_ID)


def _file():
    return config_dir() / "github.json"


def _call(url: str, data: dict | None = None, token: str = "") -> dict:
    headers = {"Accept": "application/json", "User-Agent": "FE-Maker"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    body = urllib.parse.urlencode(data).encode() if data is not None else None
    request = urllib.request.Request(url, data=body, headers=headers, method="POST" if body else "GET")
    try:
        from .ferepo import _ssl_context

        with urllib.request.urlopen(request, timeout=30, context=_ssl_context()) as response:
            return json.loads(response.read() or b"{}")
    except urllib.error.HTTPError as e:
        raise GithubAuthError("githubRefused") from e
    except (OSError, ValueError) as e:
        raise GithubAuthError("githubUnreachable") from e


def account() -> dict | None:
    """The signed-in account: {"login", "token"}, or None."""
    try:
        data = json.loads(_file().read_text(encoding="utf-8"))
        return data if data.get("login") and data.get("token") else None
    except (OSError, ValueError):
        return None


def sign_out() -> None:
    _file().unlink(missing_ok=True)


_pending: dict = {}   # the device code being confirmed on github.com (one at a time)


def start() -> dict:
    """A code for the tester to type on GitHub: {"userCode", "verificationUri", "interval", "expiresIn"}."""
    if not client_id():
        raise GithubAuthError("githubUnavailable")
    answer = _call(DEVICE_URL, {"client_id": client_id(), "scope": ""})
    if "device_code" not in answer:
        raise GithubAuthError("githubRefused")
    _pending.clear()
    _pending.update(answer)
    return {"userCode": answer["user_code"], "verificationUri": answer["verification_uri"],
            "interval": int(answer.get("interval", 5)), "expiresIn": int(answer.get("expires_in", 900))}


def poll() -> dict:
    """Whether the tester confirmed the code: {"state": "pending" | "done" | "expired" | "denied", "login"?, "interval"?}."""
    if not _pending:
        return {"state": "expired"}
    answer = _call(TOKEN_URL, {"client_id": client_id(), "device_code": _pending["device_code"],
                               "grant_type": "urn:ietf:params:oauth:grant-type:device_code"})
    error = answer.get("error")
    if error in ("authorization_pending", "slow_down"):
        if error == "slow_down":
            _pending["interval"] = int(answer.get("interval", int(_pending.get("interval", 5)) + 5))
        return {"state": "pending", "interval": int(_pending.get("interval", 5))}
    if error or not answer.get("access_token"):
        _pending.clear()
        return {"state": "denied" if error == "access_denied" else "expired"}
    token = answer["access_token"]
    login = _call(USER_URL, token=token).get("login", "")
    _pending.clear()
    if not login:
        return {"state": "expired"}
    path = _file()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"login": login, "token": token}), encoding="utf-8")
    return {"state": "done", "login": login}
