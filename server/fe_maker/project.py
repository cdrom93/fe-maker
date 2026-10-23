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
# Project data file -> DecompData method exporting it from the original game.
DATA_FILES = {
    "characters": "export_characters",
    "items": "export_items",
    "classes": "export_classes",
    "combat": "export_combat",
    "chapters": "export_chapters",
    "maps": "export_maps",
    "dialogues": "export_dialogues",
}
DEFAULT_TEST_OPTIONS = {"start": "map", "simplePrologue": True}  # see decomp/tweaks.py
# Record fields added after the first project format: filled from the original game on load.
FIELDS_ADDED_LATER = {"characters": ("affinity", "abilities"), "items": ("effectiveness", "reservedFor", "monsterWeapon")}

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
    def __init__(self, root: Path, decomp_dir: Path = DECOMP_DIR):
        self.root = root
        self.decomp_dir = decomp_dir
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
        for kind, exporter in DATA_FILES.items():
            _write_json(root / "data" / f"{kind}.json", getattr(data, exporter)())
        (root / "CREDITS.txt").write_text(CREDITS_HEADER, encoding="utf-8")
        (root / ".gitignore").write_text(PROJECT_GITIGNORE, encoding="utf-8")
        return cls(root, decomp_dir)

    # ---------- data ----------

    @property
    def name(self) -> str:
        return self.meta["name"]

    def load(self, kind: str):
        if kind not in DATA_FILES:
            raise ProjectError(f"Unknown data type {kind}")
        path = self.root / "data" / f"{kind}.json"
        if not path.is_file():
            # Data type added after this project was created: start from the original game.
            _write_json(path, getattr(DecompData(self.decomp_dir), DATA_FILES[kind])())
        records = json.loads(path.read_text(encoding="utf-8"))
        return self._fill_new_fields(kind, records) if isinstance(records, list) else records

    def _fill_new_fields(self, kind: str, records: list[dict], decomp_dir: Path | None = None) -> list[dict]:
        """Projects created by an older FE Maker lack fields added since: take them from the original game."""
        added = FIELDS_ADDED_LATER.get(kind, ())
        if all(key in record for record in records for key in added):
            return records
        data = DecompData(decomp_dir or self.decomp_dir)
        original = {r["id"]: r for r in getattr(data, DATA_FILES[kind])()}
        for record in records:
            for key in added:
                if key not in record and key in original.get(record["id"], {}):
                    record[key] = original[record["id"]][key]
        return records

    def save(self, kind: str, records) -> list[Problem]:
        if kind not in DATA_FILES:
            raise ProjectError(f"Unknown data type {kind}")
        _write_json(self.root / "data" / f"{kind}.json", records)
        return self.validate()

    def validate(self) -> list[Problem]:
        return validate(self.load("characters"), self.load("items"), DecompData(self.decomp_dir),
                        classes=self.load("classes"), combat=self.load("combat"), chapters=self.load("chapters"),
                        maps=self.load("maps"), dialogues=self.load("dialogues"))

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
        simple = bool(options.get("simplePrologue", self.test_options["simplePrologue"]))
        self.meta["testOptions"] = {"start": start, "simplePrologue": simple}
        (self.root / PROJECT_FILE).write_text(json.dumps(self.meta, indent=2, ensure_ascii=False), encoding="utf-8")

    def generate_overlay(self, decomp_dir: Path | None = None, for_test: bool = False) -> Path:
        """Write the decomp files changed by this project into build/overlay."""
        decomp_dir = decomp_dir or self.decomp_dir
        data = DecompData(decomp_dir)
        data.apply_classes(self.load("classes"))
        data.apply_characters(self.load("characters"))
        data.apply_items(self.load("items"))
        data.apply_combat(self.load("combat"))
        data.apply_chapters(self.load("chapters"))
        data.apply_maps(self.load("maps"))
        data.apply_dialogues(self.load("dialogues"))
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
            if isinstance(content, bytes):
                path.write_bytes(content)
                continue
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
