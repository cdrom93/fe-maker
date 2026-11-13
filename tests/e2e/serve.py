"""FE Maker for the interface tests (ui/e2e, Playwright): a server on the fictional decomp (fake_decomp.py), with its
own settings folder, a stand-in ROM file (only its presence is checked before a build) and no network.

    python tests/e2e/serve.py [--port 8790] [--dir <work folder>]

The work folder (default: a temporary one) is emptied at each start: decomp/, home/, projects/. FE_MAKER_UI_DIST
picks the interface build (default ui/dist).
"""

import argparse
import os
import shutil
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parents[1] / "server"))

import fake_decomp  # noqa: E402


def prepare(work: Path) -> None:
    if work.exists():
        shutil.rmtree(work)
    decomp = fake_decomp.make(work / "decomp")
    home = work / "home"
    (home / "rom").mkdir(parents=True)
    (home / "rom" / "baserom.gba").write_bytes(b"stand-in")
    (work / "projects").mkdir()
    os.environ.update(FE_MAKER_HOME=str(home), FE_MAKER_DECOMP=str(decomp), FE_MAKER_RELAY="off",
                      FE_MAKER_BUILDER="docker",   # never the native toolchain's background first build
                      HOME=str(work / "projects"), USERPROFILE=str(work / "projects"))   # default projects folder


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=8790)
    parser.add_argument("--dir", type=Path, default=Path(tempfile.gettempdir()) / "fe-maker-e2e")
    args = parser.parse_args()
    prepare(args.dir)

    import uvicorn

    from fe_maker import api, ferepo

    def offline(*_args, **_kwargs):
        raise ferepo.FeRepoError("unreachable")

    ferepo._download = offline   # FE-Repo stays out of the tests
    print(f"FE Maker (interface tests): http://127.0.0.1:{args.port}, work folder {args.dir}", flush=True)
    uvicorn.run(api.app, host="127.0.0.1", port=args.port, log_level="warning")


if __name__ == "__main__":
    main()
