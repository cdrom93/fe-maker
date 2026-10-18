"""FE Maker projects: a folder with readable JSON data (see CAHIER_DES_CHARGES.md, section 3)."""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from . import builder, ups
from .decomp.gamedata import DecompData
from .decomp.tweaks import START_MODES, TweakError, apply_test_tweaks
from .paths import DECOMP_DIR
from .validation import Problem, validate

FORMAT_VERSION = 1
PROJECT_FILE = "fe-maker.json"
DATA_FILES = ("characters", "items")
DEFAULT_TEST_OPTIONS = {"start": "map"}  # see decomp/tweaks.py START_MODES

PROJECT_GITIGNORE = "build/\n*.gba\n"
CREDITS_HEADER = "Credits\n=======\n\nMade with FE Maker, on the Fire Emblem: The Sacred Stones decompilation\n(https://github.com/FireEmblemUniverse/fireemblem8u).\n"


class ProjectError(Exception):
    pass


def decomp_commit() -> str | None:
    git = shutil.which("git")
    if not git:
        return None
    result = subprocess.run([git, "-C", str(DECOMP_DIR), "rev-parse", "HEAD"], capture_output=True, text=True)
    return result.stdout.strip() or None


def slugify(name: str) -> str:
    slug = re.sub(r"[^A-Za-z0-9_-]+", "-", name).strip("-").lower()
    return slug or "project"


@dataclass
class BuildOutput:
    rom_path: Path
    patch_path: Path | None
    matches_original: bool


class Project:
    def __init__(self, root: Path):
        self.root = root
        meta_path = root / PROJECT_FILE
        if not meta_path.is_file():
            raise ProjectError(f"Not an FE Maker project: {root}")
        self.meta = json.loads(meta_path.read_text(encoding="utf-8"))

    # ---------- creation ----------

    @classmethod
    def create(cls, root: Path, name: str, author: str = "", decomp_dir: Path = DECOMP_DIR) -> Project:
        if root.exists() and any(root.iterdir()):
            raise ProjectError(f"Folder is not empty: {root}")
        data = DecompData(decomp_dir)
        (root / "data").mkdir(parents=True)
        (root / "assets").mkdir()
        meta = {
            "formatVersion": FORMAT_VERSION,
            "name": name,
            "author": author,
            "version": "0.1.0",
            "decompCommit": decomp_commit(),
            "bugfix": False,  # decomp BUGFIX blocks do not all compile yet (see docs/audit-decomp.md)
        }
        (root / PROJECT_FILE).write_text(json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8")
        _write_json(root / "data" / "characters.json", data.export_characters())
        _write_json(root / "data" / "items.json", data.export_items())
        (root / "CREDITS.txt").write_text(CREDITS_HEADER, encoding="utf-8")
        (root / ".gitignore").write_text(PROJECT_GITIGNORE, encoding="utf-8")
        return cls(root)

    # ---------- data ----------

    @property
    def name(self) -> str:
        return self.meta["name"]

    def load(self, kind: str) -> list[dict]:
        if kind not in DATA_FILES:
            raise ProjectError(f"Unknown data type {kind}")
        return json.loads((self.root / "data" / f"{kind}.json").read_text(encoding="utf-8"))

    def save(self, kind: str, records: list[dict]) -> list[Problem]:
        if kind not in DATA_FILES:
            raise ProjectError(f"Unknown data type {kind}")
        _write_json(self.root / "data" / f"{kind}.json", records)
        return self.validate()

    def validate(self) -> list[Problem]:
        return validate(self.load("characters"), self.load("items"), DecompData(DECOMP_DIR))

    # ---------- build ----------

    @property
    def test_options(self) -> dict:
        """Options applied only to "Test" builds, never to the exported patch."""
        stored = dict(self.meta.get("testOptions", {}))
        if "skipIntro" in stored:  # option name used before "start" existed
            stored.setdefault("start", "menu" if stored.pop("skipIntro") else "normal")
        return {**DEFAULT_TEST_OPTIONS, **{k: v for k, v in stored.items() if k in DEFAULT_TEST_OPTIONS}}

    def set_test_options(self, options: dict) -> None:
        start = options.get("start", self.test_options["start"])
        if start not in START_MODES:
            raise ProjectError(f"Unknown start mode: {start}")
        self.meta["testOptions"] = {"start": start}
        (self.root / PROJECT_FILE).write_text(json.dumps(self.meta, indent=2, ensure_ascii=False), encoding="utf-8")

    def generate_overlay(self, decomp_dir: Path = DECOMP_DIR, for_test: bool = False) -> Path:
        """Write the decomp files changed by this project into build/overlay."""
        data = DecompData(decomp_dir)
        data.apply_characters(self.load("characters"))
        data.apply_items(self.load("items"))
        files = data.changed_files()
        if for_test:
            files = apply_test_tweaks(decomp_dir, self.test_options, files)
        overlay = self.root / "build" / "overlay"
        if overlay.exists():
            shutil.rmtree(overlay)
        overlay.mkdir(parents=True)
        for rel, content in files.items():
            path = overlay / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            with open(path, "w", encoding="utf-8", newline="\n") as f:
                f.write(content)
        return overlay

    def build(self, rom: Path, on_output: Callable[[str], None] | None = None, for_test: bool = False) -> BuildOutput:
        """Build the game. A test build applies the test options and makes no patch."""
        errors = [p for p in self.validate() if p.severity == "error"]
        if errors:
            raise ProjectError("Fix these problems before building: " + "; ".join(p.message for p in errors))
        try:
            overlay = self.generate_overlay(for_test=for_test)
        except TweakError as e:
            raise ProjectError(str(e)) from e
        out_dir = self.root / "build"
        result = builder.build(rom, out_dir, overlay, bugfix=self.meta.get("bugfix", False), on_output=on_output)
        if for_test:
            game_rom = out_dir / "test.gba"
            result.rom_path.replace(game_rom)
            return BuildOutput(game_rom, None, result.matches_original)
        game_rom = out_dir / f"{slugify(self.name)}.gba"
        result.rom_path.replace(game_rom)
        patch_path = out_dir / f"{slugify(self.name)}.ups"
        patch_path.write_bytes(ups.create(rom.read_bytes(), game_rom.read_bytes()))
        return BuildOutput(game_rom, patch_path, result.matches_original)


def _write_json(path: Path, data) -> None:
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
