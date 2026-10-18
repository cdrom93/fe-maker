"""Start FE Maker: python -m fe_maker [--port 8765] [--no-browser]"""

import argparse
import threading
import webbrowser

import uvicorn


def main() -> None:
    parser = argparse.ArgumentParser(description="FE Maker")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--no-browser", action="store_true")
    args = parser.parse_args()

    url = f"http://127.0.0.1:{args.port}"
    if not args.no_browser:
        threading.Timer(1.5, webbrowser.open, args=(url,)).start()
    print(f"FE Maker: {url}")
    uvicorn.run("fe_maker.api:app", host="127.0.0.1", port=args.port)


if __name__ == "__main__":
    main()
