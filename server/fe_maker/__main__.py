"""Start FE Maker: python -m fe_maker [--port 8765] [--no-browser]"""

import argparse
import threading
import urllib.request
import webbrowser

import uvicorn


def _already_running(url: str) -> bool:
    try:
        with urllib.request.urlopen(f"{url}/api/status", timeout=1) as response:
            return response.status == 200
    except OSError:
        return False


def main() -> None:
    parser = argparse.ArgumentParser(description="FE Maker")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--no-browser", action="store_true")
    args = parser.parse_args()

    url = f"http://127.0.0.1:{args.port}"
    if _already_running(url):
        # A second launch (shortcut clicked twice...) just opens the running instance.
        print(f"FE Maker is already running: {url}")
        if not args.no_browser:
            webbrowser.open(url)
        return
    if not args.no_browser:
        threading.Timer(1.5, webbrowser.open, args=(url,)).start()
    print(f"FE Maker: {url}")
    uvicorn.run("fe_maker.api:app", host="127.0.0.1", port=args.port)


if __name__ == "__main__":
    main()
