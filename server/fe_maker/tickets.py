"""Test feedback tickets written from the app (bug reports, ideas), with screenshots.

Stored per user, outside the repository: <config dir>/tickets/tickets.json and images/.
List the open ones with:  python -m fe_maker.tickets  [--all]
"""

from __future__ import annotations

import argparse
import base64
import binascii
import json
import re
import subprocess
import sys
import threading
import uuid
from datetime import datetime
from pathlib import Path

from .config import config_dir
from .paths import REPO_ROOT

KINDS = ("bug", "idea", "question")
PRIORITIES = ("high", "normal", "low")
STATUSES = ("open", "done", "cancelled")
PRIORITY_RANK = {p: i for i, p in enumerate(PRIORITIES)}
MAX_IMAGE_BYTES = 8 * 1024 * 1024
IMAGE_TYPES = {"image/png": "png", "image/jpeg": "jpg", "image/webp": "webp", "image/gif": "gif"}


class TicketError(Exception):
    pass


def tickets_dir() -> Path:
    return config_dir() / "tickets"


def app_version() -> str:
    """Short commit of the running code (the app is run from a git checkout), else the package version."""
    try:
        out = subprocess.run(["git", "-C", str(REPO_ROOT), "rev-parse", "--short", "HEAD"],
                             capture_output=True, text=True, timeout=5)
        if out.returncode == 0:
            return out.stdout.strip()
    except (OSError, subprocess.SubprocessError):
        pass
    return "0.1.0"


def _now() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def sort_tickets(tickets: list[dict]) -> list[dict]:
    """Open first, then by priority, then oldest first."""
    return sorted(tickets, key=lambda t: (t["status"] != "open", PRIORITY_RANK.get(t["priority"], 1), t["createdAt"]))


def _image_names(ticket: dict) -> list[str]:
    return ticket["images"] + [name for comment in ticket["comments"] for name in comment["images"]]


class TicketStore:
    def __init__(self, root: Path | None = None):
        self.root = root or tickets_dir()
        self._lock = threading.Lock()

    @property
    def file(self) -> Path:
        return self.root / "tickets.json"

    @property
    def images_dir(self) -> Path:
        return self.root / "images"

    def _read(self) -> list[dict]:
        if not self.file.is_file():
            return []
        tickets = json.loads(self.file.read_text(encoding="utf-8"))
        for ticket in tickets:
            ticket.setdefault("comments", [])   # tickets written before comments existed
        return tickets

    def _write(self, tickets: list[dict]) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        tmp = self.file.with_suffix(".tmp")
        tmp.write_text(json.dumps(tickets, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        tmp.replace(self.file)

    def list(self) -> list[dict]:
        with self._lock:
            return sort_tickets(self._read())

    def create(self, body: str, kind: str = "bug", priority: str = "normal",
               context: dict | None = None, images: list[str] | None = None) -> dict:
        body = body.strip()
        if not body:
            raise TicketError("bodyEmpty")
        if kind not in KINDS or priority not in PRIORITIES:
            raise TicketError("badValue")
        with self._lock:
            tickets = self._read()
            number = max((t["number"] for t in tickets), default=0) + 1
            ticket_id = uuid.uuid4().hex[:8]
            ticket = {
                "id": ticket_id,
                "number": number,
                "kind": kind,
                "priority": priority,
                "status": "open",
                "body": body,
                "context": {**(context or {}), "version": app_version()},
                "images": [self._save_image(ticket_id, i, data) for i, data in enumerate(images or [])],
                "comments": [],
                "createdAt": _now(),
                "updatedAt": _now(),
            }
            tickets.append(ticket)
            self._write(tickets)
            return ticket

    def _save_image(self, ticket_id: str, index: int, data_url: str) -> str:
        m = re.fullmatch(r"data:(image/[\w+.-]+);base64,(.+)", data_url, re.S)
        if not m or m.group(1) not in IMAGE_TYPES:
            raise TicketError("badImage")
        try:
            raw = base64.b64decode(m.group(2), validate=True)
        except binascii.Error:
            raise TicketError("badImage") from None
        if len(raw) > MAX_IMAGE_BYTES:
            raise TicketError("imageTooBig")
        self.images_dir.mkdir(parents=True, exist_ok=True)
        name = f"{ticket_id}-{index + 1}.{IMAGE_TYPES[m.group(1)]}"
        (self.images_dir / name).write_bytes(raw)
        return name

    def update(self, ticket_id: str, changes: dict) -> dict:
        with self._lock:
            tickets = self._read()
            ticket = next((t for t in tickets if t["id"] == ticket_id), None)
            if ticket is None:
                raise KeyError(ticket_id)
            if "body" in changes:
                body = str(changes["body"]).strip()
                if not body:
                    raise TicketError("bodyEmpty")
                ticket["body"] = body
            for key, allowed in (("status", STATUSES), ("priority", PRIORITIES), ("kind", KINDS)):
                if key in changes:
                    if changes[key] not in allowed:
                        raise TicketError("badValue")
                    ticket[key] = changes[key]
            ticket["updatedAt"] = _now()
            self._write(tickets)
            return ticket

    def add_comment(self, ticket_id: str, body: str, images: list[str] | None = None) -> dict:
        """A reply that completes the ticket, with its own screenshots; the ticket stays as it was written."""
        body = body.strip()
        if not body:
            raise TicketError("bodyEmpty")
        with self._lock:
            tickets = self._read()
            ticket = next((t for t in tickets if t["id"] == ticket_id), None)
            if ticket is None:
                raise KeyError(ticket_id)
            taken = [int(name.split("-")[1].split(".")[0]) for name in _image_names(ticket)]
            first = max(taken, default=0)   # a comment removed frees its numbers: never reuse a name still on disk
            ticket["comments"].append({
                "id": uuid.uuid4().hex[:8],
                "body": body,
                "images": [self._save_image(ticket_id, first + i, data) for i, data in enumerate(images or [])],
                "version": app_version(),
                "createdAt": _now(),
            })
            ticket["updatedAt"] = _now()
            self._write(tickets)
            return ticket

    def delete_comment(self, ticket_id: str, comment_id: str) -> dict:
        with self._lock:
            tickets = self._read()
            ticket = next((t for t in tickets if t["id"] == ticket_id), None)
            comment = next((c for c in ticket["comments"] if c["id"] == comment_id), None) if ticket else None
            if comment is None:
                raise KeyError(comment_id)
            for name in comment["images"]:
                (self.images_dir / name).unlink(missing_ok=True)
            ticket["comments"].remove(comment)
            ticket["updatedAt"] = _now()
            self._write(tickets)
            return ticket

    def delete(self, ticket_id: str) -> None:
        with self._lock:
            tickets = self._read()
            ticket = next((t for t in tickets if t["id"] == ticket_id), None)
            if ticket is None:
                raise KeyError(ticket_id)
            for name in _image_names(ticket):
                (self.images_dir / name).unlink(missing_ok=True)
            self._write([t for t in tickets if t["id"] != ticket_id])

    def image_path(self, name: str) -> Path | None:
        if not re.fullmatch(r"[0-9a-f]{8}-\d+\.(png|jpg|webp|gif)", name):
            return None
        path = self.images_dir / name
        return path if path.is_file() else None


def main() -> None:
    parser = argparse.ArgumentParser(description="List FE Maker feedback tickets")
    parser.add_argument("--all", action="store_true", help="include done and cancelled tickets")
    args = parser.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")  # tickets are written in French
    store = TicketStore()
    tickets = [t for t in store.list() if args.all or t["status"] == "open"]
    if not tickets:
        print("No open ticket." if not args.all else "No ticket.")
        return
    for t in tickets:
        ctx = t.get("context", {})
        where = " / ".join(str(ctx[k]) for k in ("project", "tab", "record", "detail") if ctx.get(k))
        print(f"#{t['number']} [{t['id']}] {t['kind']} · {t['priority']} · {t['status']} · {t['createdAt']}"
              f" · {ctx.get('version', '?')}" + (f" · {where}" if where else ""))
        for line in t["body"].splitlines():
            print(f"    {line}")
        for name in t["images"]:
            print(f"    image: {store.images_dir / name}")
        for comment in t["comments"]:
            print(f"    --- comment · {comment['createdAt']} · {comment['version']}")
            for line in comment["body"].splitlines():
                print(f"    {line}")
            for name in comment["images"]:
                print(f"    image: {store.images_dir / name}")
        print()


if __name__ == "__main__":
    main()
