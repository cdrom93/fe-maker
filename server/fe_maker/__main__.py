"""Start FE Maker: python -m fe_maker [--port 8765] [--no-browser]

A launch while FE Maker already runs restarts it (to load a new version), unless a build is running:
then it only opens the running one."""

import argparse
import re
import socket
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
import webbrowser

import uvicorn


def _already_running(url: str) -> bool:
    try:
        with urllib.request.urlopen(f"{url}/api/status", timeout=1) as response:
            return response.status == 200
    except OSError:
        return False


def _port_free(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(("127.0.0.1", port)) != 0


def _listening_pid(port: int) -> int | None:
    """The process listening on the port (Windows), for servers older than /api/shutdown."""
    if sys.platform != "win32":
        return None
    out = subprocess.run(["netstat", "-ano", "-p", "tcp"], capture_output=True, text=True, errors="replace").stdout or ""
    for line in out.splitlines():
        m = re.match(rf"\s*TCP\s+127\.0\.0\.1:{port}\s+\S+\s+LISTENING\s+(\d+)", line)
        if m:
            return int(m.group(1))
    return None


def _stop_running(url: str, port: int) -> str:
    """Ask the running FE Maker to stop: "stopped", "busy" (a build runs) or "failed"."""
    request = urllib.request.Request(f"{url}/api/shutdown", method="POST", data=b"")
    try:
        with urllib.request.urlopen(request, timeout=3):
            pass
    except urllib.error.HTTPError as e:
        if e.code == 409:
            return "busy"
        if e.code not in (404, 405, 501):
            return "failed"
        # an older FE Maker without /api/shutdown: stop its process
        pid = _listening_pid(port)
        if pid is None:
            return "failed"
        subprocess.run(["taskkill", "/PID", str(pid), "/F"], capture_output=True)
    except OSError:
        pass  # the server closed the connection while stopping
    for _ in range(50):
        if _port_free(port):
            return "stopped"
        time.sleep(0.2)
    return "failed"


def main() -> None:
    parser = argparse.ArgumentParser(description="FE Maker")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--no-browser", action="store_true")
    args = parser.parse_args()

    url = f"http://127.0.0.1:{args.port}"
    if _already_running(url):
        result = _stop_running(url, args.port)
        if result != "stopped":
            print({"busy": "FE Maker is building: the running one is kept",
                   "failed": "FE Maker is already running and could not be restarted"}[result])
            if not args.no_browser:
                webbrowser.open(url)
            return
        print("FE Maker was running: restarted")
    if not args.no_browser:
        threading.Timer(1.5, webbrowser.open, args=(url,)).start()
    print(f"FE Maker: {url}")
    server = uvicorn.Server(uvicorn.Config("fe_maker.api:app", host="127.0.0.1", port=args.port))
    from .api import state

    def stop() -> None:
        server.should_exit = True

    state.stop_server = stop
    server.run()


if __name__ == "__main__":
    main()
