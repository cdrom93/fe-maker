"""The Windows package of a release (alpha, step 4): a zip with the compiled interface, the server, the build image's
sources and the launchers. No Node needed to run it; no decomp and no ROM inside: the decomp is downloaded at the
first launch (server/fe_maker/decompfetch.py).

    cd ui && npm ci && npm run build && cd ..
    python tools/make_release.py        ->  dist/fe-maker-<version>.zip
"""

from __future__ import annotations

import re
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FILES = ["LICENSE", "README.md", "CREDITS.md", "CHANGELOG.md", "docs/guide.md", "docs/guide.en.md",
         "server/pyproject.toml", "docker/Dockerfile", "docker/entrypoint.sh", "tools/lancer-fe-maker.bat",
         "tools/start-fe-maker.sh"]
TREES = ["server/fe_maker", "ui/dist"]
FORBIDDEN = re.compile(r"\.(gba|sav|ups)$|^(decomp|rom)/", re.IGNORECASE)


def package_files(root: Path = ROOT) -> list[Path]:
    """Paths relative to `root`; a compiled file or anything from the game stops the release."""
    found = [Path(f) for f in FILES]
    for tree in TREES:
        found += [p.relative_to(root) for p in sorted((root / tree).rglob("*"))
                  if p.is_file() and "__pycache__" not in p.parts]
    bad = [p for p in found if FORBIDDEN.search(p.as_posix())]
    if bad:
        raise SystemExit(f"Refusing to package: {bad}")
    return found


def version(root: Path = ROOT) -> str:
    return re.search(r'__version__ = "([^"]+)"', (root / "server/fe_maker/__init__.py").read_text(encoding="utf-8")).group(1)


def main() -> None:
    if not (ROOT / "ui/dist/index.html").is_file():
        sys.exit("Build the interface first: cd ui && npm ci && npm run build")
    target = ROOT / "dist" / f"fe-maker-{version()}.zip"
    target.parent.mkdir(exist_ok=True)
    with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as z:
        for path in package_files():
            # launchers at the top of the package
            name = path.name if path.parent == Path("tools") else path.as_posix()
            z.write(ROOT / path, f"fe-maker/{name}")
    print(target)


if __name__ == "__main__":
    main()
