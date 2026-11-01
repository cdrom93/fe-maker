"""Rebuild server/fe_maker/ferepo_ranged.json: the FE-Repo animations whose ranged attack casts a spell.

Run it when FE-Repo has changed: server/.venv/Scripts/python tools/scan_ranged_animations.py
Takes a few minutes: the repository's file list comes from a clone without its files, then each sword, lance and
axe script is read from GitHub (raw files, not counted in the API's 60 requests an hour). Only names are kept.
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
import tempfile
import urllib.parse
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "server"))

from fe_maker import ferepo  # noqa: E402

REPOSITORY = "https://github.com/Klokinator/FE-Repo.git"
SCRIPTS = {"sword": r"sword", "lance": r"lance|spear", "axe": r"axe"}
_MODE_RE = re.compile(r"mode\s*(\d+)", re.IGNORECASE)
_CAST_RE = re.compile(r"^C0*5$", re.IGNORECASE)


def weapon_of(name: str) -> str | None:
    """"Axe.txt", "Axe (FE8).txt": the plain script of a weapon, not "Axe_without_comment.txt" nor "Handaxe.txt"."""
    return next((w for w, names in SCRIPTS.items() if re.fullmatch(rf"(?:{names}) ?(?:\(.*\))?\.txt", name, re.IGNORECASE)), None)


def casts_at_range(script: str) -> bool:
    """FEditor's mode 5, the ranged attack, has the command that casts the spell."""
    mode = None
    for raw in script.splitlines():
        line = raw.split("#")[0].strip()
        if line.startswith("/"):
            found = _MODE_RE.search(line)
            mode = int(found.group(1)) if found else mode
        elif mode == 5 and _CAST_RE.match(line):
            return True
    return False


def script_paths() -> list[str]:
    with tempfile.TemporaryDirectory() as folder:
        subprocess.run(["git", "clone", "-q", "--depth", "1", "--filter=blob:none", "--no-checkout", REPOSITORY, folder],
                       check=True)
        listed = subprocess.run(["git", "-c", "core.quotePath=false", "ls-tree", "-r", "--name-only", "HEAD", ferepo.ANIMATIONS],
                                cwd=folder, check=True, capture_output=True, text=True, encoding="utf-8").stdout
    return [line.strip('"') for line in listed.splitlines() if weapon_of(line.strip('"').rsplit("/", 1)[-1])]


def main() -> None:
    index, _when = ferepo.load_index(refresh=True)
    animations = {ferepo.animation_path(url) for url in index.get(ferepo.ANIMATIONS, []) if url.startswith(ferepo.TREE_PREFIX)}
    paths = script_paths()
    print(len(paths), "scripts")

    def read(path: str) -> str | None:
        try:
            return ferepo.fetch_text(ferepo.URL_PREFIX + "main/" + urllib.parse.quote(path))
        except ferepo.FeRepoError as e:
            print("not read:", path, e)
            return None

    with ThreadPoolExecutor(8) as pool:
        scripts = list(pool.map(read, paths))
    if None in scripts:
        raise SystemExit("Some scripts could not be read: the list is left as it was")
    found: dict[str, set[str]] = {}
    for path, script in zip(paths, scripts):
        if casts_at_range(script):
            parts = path.split("/")
            folders = ("/".join(parts[:n]) for n in range(len(parts) - 1, 1, -1))
            animation = next((folder for folder in folders if folder in animations), None)
            if animation:
                found.setdefault(animation, set()).add(weapon_of(parts[-1]))
    result = {animation: sorted(found[animation]) for animation in sorted(found)}
    target = ROOT / "server/fe_maker" / ferepo.RANGED_FILE
    target.write_text(json.dumps(result, ensure_ascii=False, indent=0) + "\n", encoding="utf-8", newline="\n")
    print(len(result), "animations, written to", target)


if __name__ == "__main__":
    main()
