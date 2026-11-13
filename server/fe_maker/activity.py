"""The last actions and errors of this run (spec, section 4, alpha, automatic tests point 3): what the user changed
(the API's writing requests), what failed (server errors, refused requests, failed builds), kept in memory only and
joined to a ticket when the user leaves it ticked, so a ticket says by itself what led to the problem.
"""

from __future__ import annotations

import collections
import threading
import time

MAX_ENTRIES = 40
_entries: collections.deque[str] = collections.deque(maxlen=MAX_ENTRIES)
_lock = threading.Lock()
# Requests too frequent or too private to tell: polling, the ticket itself, file contents.
_QUIET = ("/api/tickets", "/api/project/build/cancel", "/api/emulator/", "/api/shutdown")


def note(text: str) -> None:
    with _lock:
        _entries.append(f"{time.strftime('%H:%M:%S')} {text[:300]}")


def request(method: str, path: str, status: int) -> None:
    """A request worth telling: any that failed, and the writing ones (POST, PUT, PATCH, DELETE) of the API."""
    if not path.startswith("/api/") or path.startswith(_QUIET):
        return
    if status >= 400 or method != "GET":
        note(f"{method} {path} -> {status}")


def error(text: str) -> None:
    note(f"ERROR {text}")


def recent() -> list[str]:
    with _lock:
        return list(_entries)


def clear() -> None:
    with _lock:
        _entries.clear()


def trail_text(server: list[str], client: list[str]) -> str:
    """The section a sent ticket gets at the end of its text (folded on GitHub)."""
    lines = [*(f"[server] {e}" for e in server), *(f"[ui] {e}" for e in client)]
    if not lines:
        return ""
    body = "\n".join(line.replace("```", "'''") for line in lines)
    return f"\n\n<details><summary>Last actions and errors</summary>\n\n```\n{body}\n```\n</details>"
