"""FE Maker projects: a folder with readable JSON data (see CAHIER_DES_CHARGES.md, section 3)."""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from . import builder, ferepo, migrations, newchapter, ups
from .decomp import gameoptions, tweaks
from .decomp.gamedata import DecompData
from .decomp.tweaks import START_MODES, TweakError, apply_test_tweaks, without_world_map
from .migrations import FORMAT_VERSION, PROJECT_FILE, ProjectError
from .paths import DECOMP_COMMIT, DECOMP_DIR
from .validation import Problem, validate

# Project data file -> DecompData method exporting it from the original game.
DATA_FILES = {
    "characters": "export_characters",
    "items": "export_items",
    "classes": "export_classes",
    "combat": "export_combat",
    "chapters": "export_chapters",
    "maps": "export_maps",
    "dialogues": "export_dialogues",
    "portraits": "export_portraits",
    "animations": "export_animations",
    "mapsprites": "export_map_sprites",
    "music": "export_music",
}
PORTRAITS_DIR = "portraits"   # imported portrait sheets, in the project's assets folder
ANIMATIONS_DIR = "animations"   # imported battle animations (decomp files), in the assets folder
DEFAULT_TEST_OPTIONS = {"start": "map", "simplePrologue": True, "chapter": 0}  # see decomp/tweaks.py
# Record fields added after the first project format: filled from the original game on load.
FIELDS_ADDED_LATER = {"characters": ("affinity", "abilities"), "items": ("effectiveness", "reservedFor", "monsterWeapon")}

RESOURCES_HEADER = "Community resources (written by FE Maker)\n----------------------------------------\n"
PROJECT_GITIGNORE = "build/\n*.gba\n"
CREDITS_HEADER = "Credits\n=======\n\nMade with FE Maker, on the Fire Emblem: The Sacred Stones decompilation\n(https://github.com/FireEmblemUniverse/fireemblem8u).\n"


def decomp_commit() -> str | None:
    git = shutil.which("git")
    if not git or not (DECOMP_DIR / ".git").exists():
        return DECOMP_COMMIT
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
    map_path: Path | None = None  # linker map of this build, for playtests


class Project:
    def __init__(self, root: Path, decomp_dir: Path = DECOMP_DIR):
        self.root = root
        self.decomp_dir = decomp_dir
        meta_path = root / PROJECT_FILE
        if not meta_path.is_file():
            raise ProjectError(f"Not an FE Maker project: {root}")
        self.meta = json.loads(meta_path.read_text(encoding="utf-8"))
        migrations.migrate(root, self.meta)

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
        characters, chapters = self.load("characters"), self.load("chapters")
        problems = validate(characters, self.load("items"), DecompData(self.decomp_dir),
                            classes=self.load("classes"), combat=self.load("combat"), chapters=chapters,
                            maps=self.load("maps"), dialogues=self.load("dialogues"),
                            portraits=self.load("portraits"), assets_dir=self.root / "assets",
                            animations=self.load("animations"), unplayed=newchapter.unplayed_groups(self))
        if chapters.get("blankCharacters"):   # the game's chapters still carry the characters a blank project dropped
            ids = {c["id"] for c in characters}
            problems = [p for p in problems if p.kind != "characters" or p.id in ids]
        # What the original game already does is not the user's to fix: only warnings on what the project changed.
        data = DecompData(self.decomp_dir)
        games = {"items": data.export_items(), "classes": data.export_classes(), "characters": data.export_characters()}
        untouched = {(kind, g["id"]) for kind, records in games.items() for g in records
                     if g in (characters if kind == "characters" else self.load(kind))}
        problems = [p for p in problems if p.severity == "error" or (p.kind, p.id) not in untouched]
        return newchapter.story_problems(self) + problems

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
        chapter = max(0, int(options.get("chapter", self.test_options["chapter"]) or 0))   # "Test this chapter"
        self.meta["testOptions"] = {"start": start, "simplePrologue": simple, "chapter": chapter}
        (self.root / PROJECT_FILE).write_text(json.dumps(self.meta, indent=2, ensure_ascii=False), encoding="utf-8")

    @property
    def world_map(self) -> bool:
        """False: the game goes from chapter to chapter without the world map (ticket 39), in the exported
        patch too: MNCH / MoveToChapter go straight to the chapter they name."""
        return bool(self.meta.get("worldMap", True))

    def set_world_map(self, on: bool) -> None:
        self.meta["worldMap"] = bool(on)
        (self.root / PROJECT_FILE).write_text(json.dumps(self.meta, indent=2, ensure_ascii=False), encoding="utf-8")

    @property
    def game_options(self) -> dict:
        """Options of the built game the project changes (decomp/gameoptions.py): defaults of a new save's options,
        comfort changes."""
        return dict(self.meta.get("gameOptions", {}))

    def set_game_options(self, options: dict) -> None:
        problem = gameoptions.validate(options)
        if problem:
            raise ProjectError(problem)
        self.meta["gameOptions"] = {k: v for k, v in options.items()
                                    if k in gameoptions.SWITCHES and v or k in gameoptions.DEFAULTS
                                    and v != gameoptions.DEFAULTS[k][1]}
        (self.root / PROJECT_FILE).write_text(json.dumps(self.meta, indent=2, ensure_ascii=False), encoding="utf-8")

    def update_credits(self) -> None:
        """CREDITS.txt lists the community resources the project uses (imported from FE-Repo), after
        what the user wrote."""
        path = self.root / "CREDITS.txt"
        text = path.read_text(encoding="utf-8") if path.is_file() else CREDITS_HEADER
        mine = text.split(RESOURCES_HEADER)[0].rstrip("\n") + "\n"
        sources = [e["source"] for e in self.load("portraits").values() if isinstance(e, dict) and e.get("source")]
        sources += [e["source"] for e in self.load("animations").get("animations", {}).values()
                    if isinstance(e, dict) and e.get("source")]
        sources += [e["source"] for e in self.load("mapsprites").get("sprites", {}).values()
                    if isinstance(e, dict) and e.get("source")]
        lines = sorted({ferepo.credit_line(s) for s in sources})
        if lines:
            mine += "\n" + RESOURCES_HEADER + "".join(f"{line}\n" for line in lines)
        path.write_text(mine, encoding="utf-8")

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
        data.apply_prep(self.load("chapters"))
        data.apply_portraits(self.load("portraits"), self.root / "assets")
        data.apply_animations(self.load("animations"), self.root / "assets")
        data.apply_map_sprites(self.load("mapsprites"), self.root / "assets")
        data.apply_music(self.load("music"), self.root / "assets")
        menu_texts = (0, 0)
        if self.game_options.get("noSupportAnimations"):
            menu_texts = data.add_texts(gameoptions.MENU_TEXTS["label"], gameoptions.MENU_TEXTS["help"])
        files = data.changed_files()
        if not self.world_map:
            files = without_world_map(decomp_dir, files)
        files = gameoptions.apply(decomp_dir, self.game_options, files, menu_texts)
        if tweaks.mixes_magic(self.load("characters"), self.load("classes")):
            files = tweaks.animation_modes_by_weapon(decomp_dir, files)
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
            return BuildOutput(game_rom, None, result.matches_original, out_dir / "fireemblem8.map")
        game_rom = out_dir / f"{slugify(self.name)}.gba"
        result.rom_path.replace(game_rom)
        patch_path = out_dir / f"{slugify(self.name)}.ups"
        patch_path.write_bytes(ups.create(rom.read_bytes(), game_rom.read_bytes()))
        return BuildOutput(game_rom, patch_path, result.matches_original, out_dir / "fireemblem8.map")


def _write_json(path: Path, data) -> None:
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
