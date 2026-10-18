"""Build the FE8 decomp inside the FE Maker Docker image.

Usage: python docker/build.py --rom PATH/TO/fe8.gba [--out build] [--overlay DIR] [--bugfix]
"""

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "server"))

from fe_maker.builder import BuildError, build  # noqa: E402
from fe_maker.rom import InvalidRomError  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rom", required=True, type=Path, help="Fire Emblem: The Sacred Stones (US) ROM")
    parser.add_argument("--out", default=REPO_ROOT / "build", type=Path, help="output directory")
    parser.add_argument("--overlay", type=Path, help="directory of files copied over the decomp sources before building")
    parser.add_argument("--bugfix", action="store_true", help="enable the decomp's BUGFIX blocks")
    args = parser.parse_args()

    try:
        result = build(args.rom, args.out, args.overlay, args.bugfix, on_output=lambda line: print(line, end=""))
    except (BuildError, InvalidRomError) as e:
        sys.exit(str(e))
    print(f"ROM: {result.rom_path}")


if __name__ == "__main__":
    main()
