"""The downloads started from the home page (the decomp, the build tools, mGBA: checks.py), each in a thread of its
own with its progress, so that several run at once and the page shows how far each one is (ticket 81).

A job is {"state": "running" | "done" | "error", "received", "total" (bytes; 0 when unknown), "error" (a code)}.
"""

from __future__ import annotations

import threading
import urllib.request
from collections.abc import Callable

CHUNK = 256 * 1024

_jobs: dict[str, dict] = {}
_lock = threading.Lock()
_current = threading.local()   # the job of the thread running it, for get()


def start(kind: str, run: Callable[[], None], error_type: type[Exception]) -> None:
    """Run `run` in the background as the job `kind`, unless it already runs; `error_type`'s message is its error
    code (the interface's `checks.error.<code>`)."""
    with _lock:
        if _jobs.get(kind, {}).get("state") == "running":
            return
        job = {"state": "running", "received": 0, "total": 0, "error": ""}
        _jobs[kind] = job

    def work() -> None:
        _current.job = job
        try:
            run()
            job["state"] = "done"
        except error_type as e:
            job.update(state="error", error=str(e) or "unreachable")
        except OSError:
            job.update(state="error", error="unreachable")
        except Exception:   # never a silent stop: the page shows a failure
            job.update(state="error", error="failed")

    threading.Thread(target=work, name=f"download-{kind}", daemon=True).start()


def state(kind: str) -> dict | None:
    job = _jobs.get(kind)
    return dict(job) if job else None


def get(url: str, limit: int, timeout: int, context=None) -> bytes:
    """The file at `url` (at most `limit` bytes), its progress counted in the calling thread's job."""
    job = getattr(_current, "job", None)
    request = urllib.request.Request(url, headers={"User-Agent": "FE-Maker"})
    with urllib.request.urlopen(request, timeout=timeout, context=context) as response:
        if job is not None:
            job["total"] = int(response.headers.get("Content-Length") or 0)
        parts: list[bytes] = []
        size = 0
        while size < limit:
            chunk = response.read(min(CHUNK, limit - size))
            if not chunk:
                break
            parts.append(chunk)
            size += len(chunk)
            if job is not None:
                job["received"] = size
    return b"".join(parts)
