"""Full in-game verification before a release (spec, section 4, alpha, automatic tests point 5), on the developer's
machine (it needs the ROM and the build tools): every playtest of tests/local, then a reference hack played chapter
by chapter, and a report of one line per test.

    server/.venv/Scripts/python tools/verify_in_game.py [--hack <project folder>] [--chapters 0,1,2] [--skip-playtests] [-- <pytest arguments>]

The ROM is FE_MAKER_ROM, else the one in FE Maker's settings, else rom/*.gba. The reference hack is copied first:
its own folder is never changed. For each chapter its story reaches (or those given), a test build starting on that
chapter must play its opening (texts passed with A, a preparations screen with START) and reach the player phase of turn 1 with units on the map. The report goes to
verify-report.txt beside this script's working folder (or --report) and is printed.
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import tempfile
import time
import xml.etree.ElementTree as ElementTree
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "server"))


def find_rom() -> Path | None:
    if os.environ.get("FE_MAKER_ROM"):
        return Path(os.environ["FE_MAKER_ROM"])
    try:
        from fe_maker.config import Settings

        rom = Settings.load().rom_path
        if rom and Path(rom).is_file():
            return Path(rom)
    except Exception:  # settings unreadable: look in the repository
        pass
    return next(iter(sorted((ROOT / "rom").glob("*.gba"))), None)


def playtest_lines(rom: Path, extra: list[str]) -> list[str]:
    """Every test of tests/local run by pytest, one line each: OK / FAIL / SKIP, its name, its time or reason."""
    with tempfile.TemporaryDirectory() as tmp:
        xml = Path(tmp) / "report.xml"
        env = {**os.environ, "FE_MAKER_ROM": str(rom), "PYTHONUTF8": "1"}
        subprocess.run([sys.executable, "-m", "pytest", "tests/local", "-q", "-p", "no:cacheprovider",
                        f"--junitxml={xml}", *extra], cwd=ROOT, env=env, check=False)
        if not xml.is_file():
            return ["FAIL  pytest: no report (see the output above)"]
        lines = []
        for case in ElementTree.parse(xml).iter("testcase"):
            name = f"{Path(case.get('classname', '').replace('.', '/')).name}::{case.get('name')}"
            seconds = float(case.get("time") or 0)
            failure = case.find("failure") if case.find("failure") is not None else case.find("error")
            skipped = case.find("skipped")
            if failure is not None:
                reason = (failure.get("message") or failure.text or "").strip().splitlines()
                lines.append(f"FAIL  {name}: {reason[0][:160] if reason else '?'}")
            elif skipped is not None:
                lines.append(f"SKIP  {name}: {(skipped.get('message') or '')[:120]}")
            else:
                lines.append(f"OK    {name} ({seconds:.0f} s)")
        return lines


def hack_lines(rom: Path, hack: Path, chapters: list[int] | None) -> list[str]:
    """The reference hack, chapter by chapter: its opening plays and the map is reached in player phase."""
    from fe_maker.decomp.gamedata import DecompData
    from fe_maker.newchapter import story_order
    from fe_maker.playtest import Game
    from fe_maker.project import Project

    lines = []
    with tempfile.TemporaryDirectory() as tmp:
        copy = Path(tmp) / hack.name
        shutil.copytree(hack, copy, ignore=shutil.ignore_patterns("build", "backups"))
        project = Project(copy)
        if chapters is None:
            data = DecompData(project.decomp_dir)
            data._load_chapter_events()
            chapters = story_order(data.chapter_links(project.load("dialogues").get("scripts", {})))
            chapters += sorted({int(k) for k in project.load("chapters").get("added", {})} - set(chapters))
        for index in chapters:
            start = time.time()
            try:
                project.set_test_options({"start": "map", "chapter": index})
                out = project.build(rom, for_test=True)
                with Game(out.rom_path, out.map_path) as game:
                    def on_map() -> bool:
                        return (game.chapter() == index and game.turn() == 1 and game.phase() == "player"
                                and bool(game.units()))

                    reached = game.wait_until(on_map, seconds=300, step=20, tap="A")
                    if not reached and game.turn() == 0:   # preparations screen: START is "Fight!"
                        reached = game.wait_until(on_map, seconds=60, step=20, tap="START")
                    if reached:
                        game.run(120)   # a few seconds on the map: no crash right after the opening
                        reached = game.chapter() == index
                    if reached:
                        lines.append(f"OK    hack chapter {index}: map reached with {len(game.units())} units "
                                     f"({time.time() - start:.0f} s)")
                    else:
                        shot = Path.cwd() / f"verify-chapter-{index}.png"
                        game.screenshot().save(shot)
                        lines.append(f"FAIL  hack chapter {index}: map not reached (chapter {game.chapter()}, "
                                     f"turn {game.turn()}, {game.phase()}), screenshot {shot.name}")
            except Exception as e:  # one chapter failing does not stop the others
                lines.append(f"FAIL  hack chapter {index}: {type(e).__name__}: {str(e).splitlines()[0][:160] if str(e) else ''}")
    return lines


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--hack", type=Path, help="the reference hack's project folder")
    parser.add_argument("--chapters", help="chapter numbers to play, comma-separated (default: the story's)")
    parser.add_argument("--skip-playtests", action="store_true")
    parser.add_argument("--report", type=Path, default=Path("verify-report.txt"))
    parser.add_argument("pytest_args", nargs="*", help="passed to pytest (e.g. -m maps)")
    args = parser.parse_args()
    rom = find_rom()
    if rom is None or not rom.is_file():
        sys.exit("No ROM: set FE_MAKER_ROM, or choose it in FE Maker.")
    started = time.time()
    lines = [] if args.skip_playtests else playtest_lines(rom, args.pytest_args)
    if args.hack:
        chapters = [int(c) for c in args.chapters.split(",")] if args.chapters else None
        lines += hack_lines(rom, args.hack.resolve(), chapters)
    failed = sum(line.startswith("FAIL") for line in lines)
    summary = (f"{len(lines) - failed} OK or skipped, {failed} failed, in {(time.time() - started) / 60:.0f} min "
               f"({time.strftime('%d/%m/%Y %H:%M')})")
    report = "\n".join([*lines, "", summary]) + "\n"
    args.report.write_text(report, encoding="utf-8")
    print("\n" + report + f"Report: {args.report.resolve()}")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
