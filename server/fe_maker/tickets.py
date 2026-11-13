"""Test feedback tickets written from the app (bug reports, ideas), with screenshots.

Stored per user, outside the repository: <config dir>/tickets/tickets.json and images/.
List the open ones with:  python -m fe_maker.tickets  [--all]

Each ticket is also sent to the ticket relay (relay/, a Cloudflare Worker) which writes it in the private feedback
repository: no GitHub account needed. The relay answers with the issue's number and a secret code, kept here: with
it, sync() reads back the ticket's state and the admin's replies. A ticket the relay did not get stays here, marked
with its error, to be sent again.
"""

from __future__ import annotations

import argparse
import base64
import binascii
import json
import os
import re
import subprocess
import sys
import threading
import urllib.error
import urllib.request
import uuid
import zipfile
from datetime import datetime
from io import BytesIO
from pathlib import Path

from . import __version__, activity
from .config import config_dir
from .paths import REPO_ROOT

KINDS = ("bug", "idea", "question")
PRIORITIES = ("high", "normal", "low")
STATUSES = ("open", "done", "cancelled")
PRIORITY_RANK = {p: i for i, p in enumerate(PRIORITIES)}
MAX_IMAGE_BYTES = 8 * 1024 * 1024
IMAGE_TYPES = {"image/png": "png", "image/jpeg": "jpg", "image/webp": "webp", "image/gif": "gif"}
RELAY_URL = "https://fe-maker-tickets.fe-maker.workers.dev"
RELAY_MAX_IMAGES = 4                     # the relay's limits (relay/src/index.js)
RELAY_MAX_PROJECT = 10 * 1024 * 1024
PROJECT_PARTS = ("fe-maker.json", "CREDITS.txt", "data", "assets")   # not build/ nor backups/


class TicketError(Exception):
    pass


def relay_url() -> str | None:
    """The relay, or None when sending is off (FE_MAKER_RELAY=off; another URL for a test relay)."""
    url = os.environ.get("FE_MAKER_RELAY", RELAY_URL)
    return None if url == "off" else url.rstrip("/")


def relay_call(path: str, data: dict | None = None, secret: str = "") -> dict:
    """One call to the relay (POST with `data`, else GET). Raises TicketError with the relay's code."""
    url = relay_url()
    if url is None:
        raise TicketError("relayOff")
    headers = {"Content-Type": "application/json", "User-Agent": f"FE-Maker/{app_version()}"}
    if secret:
        headers["X-Ticket-Secret"] = secret
    body = json.dumps(data).encode() if data is not None else None
    request = urllib.request.Request(url + path, data=body, headers=headers, method="POST" if body else "GET")
    try:
        from .ferepo import _ssl_context  # certifi's certificates: Windows' store can hold an expired one

        with urllib.request.urlopen(request, timeout=60, context=_ssl_context()) as response:
            return json.loads(response.read() or b"{}")
    except urllib.error.HTTPError as e:
        try:
            code = json.loads(e.read() or b"{}").get("error") or "relayError"
        except ValueError:
            code = "relayError"
        raise TicketError(code) from None
    except (OSError, ValueError):
        raise TicketError("relayUnreachable") from None


def project_zip(project_dir: Path) -> bytes:
    """The project to join to a ticket: its settings, data and assets (not its builds nor backups)."""
    out = BytesIO()
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as archive:
        for part in PROJECT_PARTS:
            path = project_dir / part
            files = [path] if path.is_file() else sorted(p for p in path.rglob("*") if p.is_file()) if path.is_dir() else []
            for file in files:
                archive.write(file, file.relative_to(project_dir).as_posix())
    data = out.getvalue()
    if len(data) > RELAY_MAX_PROJECT:
        raise TicketError("projectTooBig")
    return data


def tickets_dir() -> Path:
    return config_dir() / "tickets"


def app_version() -> str:
    """FE Maker's version, with the short commit of the running code after a "+" when run from a git checkout
    (0.1.0-prealpha.1+e2e2bab): the relay labels the issue with the version alone."""
    try:
        out = subprocess.run(["git", "-C", str(REPO_ROOT), "rev-parse", "--short", "HEAD"],
                             capture_output=True, text=True, timeout=5)
        if out.returncode == 0 and out.stdout.strip():
            return f"{__version__}+{out.stdout.strip()}"
    except (OSError, subprocess.SubprocessError):
        pass
    return __version__


def _now() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def sort_tickets(tickets: list[dict]) -> list[dict]:
    """Open first, then by priority, then oldest first."""
    return sorted(tickets, key=lambda t: (t["status"] != "open", PRIORITY_RANK.get(t["priority"], 1), t["createdAt"]))


def _github_number(ticket: dict) -> None:
    """A ticket sent to the relay goes by its number on GitHub (ticket 185), the same for the tester and the admin;
    its first number stays as localNumber, which numbers the next tickets written here."""
    remote = ticket.get("remote")
    if remote and ticket["number"] != remote["number"]:
        ticket.setdefault("localNumber", ticket["number"])
        ticket["number"] = remote["number"]


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
            _github_number(ticket)
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
               context: dict | None = None, images: list[str] | None = None, trail: dict | None = None) -> dict:
        body = body.strip()
        if not body:
            raise TicketError("bodyEmpty")
        if kind not in KINDS or priority not in PRIORITIES:
            raise TicketError("badValue")
        with self._lock:
            tickets = self._read()
            number = max((t.get("localNumber", t["number"]) for t in tickets), default=0) + 1
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
                **({"trail": trail} if trail else {}),
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

    def _image_url(self, name: str) -> str:
        ext = name.rsplit(".", 1)[1]
        kind = next(k for k, v in IMAGE_TYPES.items() if v == ext)
        return f"data:{kind};base64," + base64.b64encode((self.images_dir / name).read_bytes()).decode()

    def _set(self, ticket_id: str, change) -> dict:
        with self._lock:
            tickets = self._read()
            ticket = next((t for t in tickets if t["id"] == ticket_id), None)
            if ticket is None:
                raise KeyError(ticket_id)
            change(ticket)
            self._write(tickets)
            return ticket

    def send(self, ticket_id: str, project: bytes | None = None) -> dict:
        """Sends the ticket to the relay (again, after a failure): it keeps the issue's number and secret, or the
        error. A ticket already sent is not sent twice."""
        with self._lock:
            ticket = next((t for t in self._read() if t["id"] == ticket_id), None)
        if ticket is None:
            raise KeyError(ticket_id)
        if ticket.get("remote"):
            return ticket
        trail = ticket.get("trail") or {}
        body = ticket["body"] + activity.trail_text(trail.get("server", []), trail.get("ui", []))
        data = {"body": body, "kind": ticket["kind"], "priority": ticket["priority"],
                "context": {k: v for k, v in ticket["context"].items() if k != "version"},
                "version": ticket["context"].get("version", app_version()),
                "images": [self._image_url(name) for name in ticket["images"][:RELAY_MAX_IMAGES]]}
        if project is not None:
            data["project"] = {"data": base64.b64encode(project).decode()}
        try:
            answer = relay_call("/v1/tickets", data)
        except TicketError as e:
            error = str(e)
            return self._set(ticket_id, lambda t: t.update(sendError=error))

        def sent(t: dict) -> None:
            t.pop("sendError", None)
            t["remote"] = {"number": answer["number"], "secret": answer["secret"], "sentAt": _now()}
            _github_number(t)
        return self._set(ticket_id, sent)

    def sync(self) -> list[dict]:
        """The admin's replies and the state of the tickets sent and still open (closed on GitHub: done here)."""
        with self._lock:
            sent = [t for t in self._read() if t.get("remote") and t["status"] == "open"]
        for ticket in sent:
            try:
                remote = relay_call(f"/v1/tickets/{ticket['remote']['number']}", secret=ticket["remote"]["secret"])
            except TicketError:
                continue

            def update(t: dict, remote=remote) -> None:
                t["replies"] = [{"body": c["body"], "createdAt": c["createdAt"]}
                                for c in remote.get("comments", []) if c.get("from") == "admin"]
                if remote.get("state") in ("done", "cancelled"):
                    t["status"] = remote["state"]
                    t["updatedAt"] = _now()
            self._set(ticket["id"], update)
        return self.list()

    def send_comment(self, ticket_id: str, comment_id: str) -> None:
        """A reply written here, to the relay when its ticket was sent (else it stays here only)."""
        with self._lock:
            ticket = next((t for t in self._read() if t["id"] == ticket_id), None)
        comment = next((c for c in ticket["comments"] if c["id"] == comment_id), None) if ticket else None
        if not ticket or not ticket.get("remote") or comment is None:
            return
        data = {"body": comment["body"], "images": [self._image_url(name) for name in comment["images"][:RELAY_MAX_IMAGES]]}
        try:
            relay_call(f"/v1/tickets/{ticket['remote']['number']}/comments", data, ticket["remote"]["secret"])
            sent = True
        except TicketError:
            sent = False

        def mark(t: dict) -> None:
            for c in t["comments"]:
                if c["id"] == comment_id:
                    c["sent"] = sent
        self._set(ticket_id, mark)

    def image_path(self, name: str) -> Path | None:
        if not re.fullmatch(r"[0-9a-f]{8}-\d+\.(png|jpg|webp|gif)", name):
            return None
        path = self.images_dir / name
        return path if path.is_file() else None


FEEDBACK_REPO = "cdrom93/fe-maker-feedback"   # where the relay writes (relay/wrangler.toml)

# ---------- admin mode: the testers' tickets, read and answered through the admin's own gh login ----------
# No token is typed or kept by FE Maker: the gh CLI holds it, and the mode only shows to whoever can write to the
# feedback repository. Admin replies are plain comments: the relay hands every comment without the tester mark back
# to the tester as a reply.

UPLOAD_LINK = re.compile(r"^\s*!?\[[^\]]*\]\(https://github\.com/[^/]+/[^/]+/blob/main/(uploads/[\w./-]+)\?raw=true\)\s*$")
MARKS = re.compile(r"<!-- fem:[^>]*-->")
_admin: bool | None = None


class AdminError(Exception):
    pass


def _gh(*args: str, stdin: str | None = None) -> str:
    try:
        out = subprocess.run(["gh", *args], capture_output=True, text=True, encoding="utf-8", input=stdin, timeout=60)
    except (OSError, subprocess.SubprocessError) as e:
        raise AdminError(str(e)) from e
    if out.returncode != 0:
        raise AdminError(out.stderr.strip() or "gh failed")
    return out.stdout


def admin_available() -> bool:
    """gh is installed, logged in and may write to the feedback repository (checked once per run)."""
    global _admin
    if _admin is None:
        try:
            _admin = _gh("api", f"repos/{FEEDBACK_REPO}", "--jq", ".permissions.push").strip() == "true"
        except AdminError:
            _admin = False
    return _admin


def _split(text: str) -> dict:
    """An issue or comment body written by the relay: the text, its context table, screenshots and project."""
    lines, context, images, project = [], {}, [], ""
    for line in MARKS.sub("", text or "").splitlines():
        link = UPLOAD_LINK.match(line)
        if link:
            if link.group(1).endswith(".zip"):
                project = link.group(1)
            else:
                images.append(link.group(1))
        elif line.startswith("|"):
            cells = [c.strip() for c in line.strip("|").split("|")]
            if len(cells) == 2 and cells[0] and not set(cells[0]) <= {"-"}:
                context[cells[0]] = cells[1]
        else:
            lines.append(line)
    return {"body": "\n".join(lines).strip(), "context": context, "images": images, "project": project}


def _issue(issue: dict) -> dict:
    labels = [label["name"] for label in issue.get("labels", [])]
    state = "open" if issue["state"] == "OPEN" else "cancelled" if issue.get("stateReason") == "NOT_PLANNED" else "done"
    parts = _split(issue.get("body") or "")
    return {
        "number": issue["number"],
        "kind": next((k for k in ("bug", "idea", "question") if k in labels), "bug"),
        "priority": next((x.split(":", 1)[1] for x in labels if x.startswith("priority:")), "normal"),
        "version": next((x[1:] for x in labels if x.startswith("v") and x[1:2].isdigit()), parts["context"].get("version", "")),
        "status": state,
        "createdAt": issue["createdAt"],
        "url": issue.get("url", ""),
        **parts,
        "comments": [
            {"from": "tester" if "<!-- fem:tester -->" in (c.get("body") or "") else "admin", "createdAt": c["createdAt"],
             **{k: v for k, v in _split(c.get("body") or "").items() if k in ("body", "images")}}
            for c in issue.get("comments", [])
        ],
    }


def admin_tickets(include_closed: bool = False) -> list[dict]:
    fields = "number,body,labels,createdAt,state,stateReason,comments,url"
    issues = json.loads(_gh("issue", "list", "-R", FEEDBACK_REPO, "--state", "all" if include_closed else "open",
                            "--limit", "200", "--json", fields))
    return sorted((_issue(i) for i in issues), key=lambda i: -i["number"])


def _upload(data_url: str, name: str) -> str:
    """A screenshot of an admin reply, into the repository's uploads/ folder like the relay's."""
    m = re.match(r"^data:image/(png|jpeg|webp|gif);base64,(.+)$", data_url, re.S)
    if not m:
        raise AdminError("badImage")
    path = f"uploads/{datetime.now().strftime('%Y-%m')}/{name}.{'jpg' if m.group(1) == 'jpeg' else m.group(1)}"
    _gh("api", "-X", "PUT", f"repos/{FEEDBACK_REPO}/contents/{path}", "--input", "-",
        stdin=json.dumps({"message": f"Screenshot {name}", "content": m.group(2)}))
    return path


def admin_reply(number: int, body: str, images: list[str] | None = None) -> None:
    key = uuid.uuid4().hex[:6]
    paths = [_upload(src, f"{number}-{key}-{i + 1}") for i, src in enumerate(images or [])]
    links = [f"\n![Capture {i + 1}](https://github.com/{FEEDBACK_REPO}/blob/main/{p}?raw=true)" for i, p in enumerate(paths)]
    _gh("issue", "comment", str(number), "-R", FEEDBACK_REPO, "--body-file", "-", stdin="\n".join([body.strip(), *links]))


def admin_set_status(number: int, status: str) -> None:
    if status == "open":
        _gh("issue", "reopen", str(number), "-R", FEEDBACK_REPO)
    else:
        _gh("issue", "close", str(number), "-R", FEEDBACK_REPO, "--reason",
            "not planned" if status == "cancelled" else "completed")


def admin_file(path: str) -> bytes:
    """A file of the repository's uploads/ folder (screenshots, projects), through the git blob for big ones."""
    if not re.fullmatch(r"uploads/[\w.-]+/[\w.-]+", path) or ".." in path:
        raise AdminError("notFound")
    info = json.loads(_gh("api", f"repos/{FEEDBACK_REPO}/contents/{path}"))
    content = info.get("content") or json.loads(_gh("api", f"repos/{FEEDBACK_REPO}/git/blobs/{info['sha']}"))["content"]
    return base64.b64decode(content)


def print_remote(include_closed: bool = False) -> None:
    """The tickets the relay wrote, read with the admin's gh login."""
    try:
        issues = admin_tickets(include_closed)
    except AdminError as e:
        print(e, file=sys.stderr)
        sys.exit(1)
    if not issues:
        print("No ticket.")
    for issue in reversed(issues):
        print(f"#{issue['number']} {issue['status']} · {issue['kind']} · {issue['priority']} · v{issue['version']} · "
              f"{issue['createdAt']}")
        for line in issue["body"].splitlines():
            print(f"    {line}")
        for name in issue["images"] + ([issue["project"]] if issue["project"] else []):
            print(f"    [{name}]")
        for comment in issue["comments"]:
            print(f"    --- {comment['from']} · {comment['createdAt']}")
            for line in comment["body"].splitlines():
                print(f"    {line}")
        print()


def main() -> None:
    parser = argparse.ArgumentParser(description="List FE Maker feedback tickets")
    parser.add_argument("--all", action="store_true", help="include done and cancelled tickets")
    parser.add_argument("--remote", action="store_true",
                        help="the testers' tickets: issues of the feedback repository (admin, through the gh CLI)")
    args = parser.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")  # tickets are written in French
    if args.remote:
        print_remote(args.all)
        return
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
