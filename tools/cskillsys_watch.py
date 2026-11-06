"""What changed in C-SkillSys since the commit FE Maker's skills were ported from (docs/competences.md).

Lists the upstream files changed since `skills.COMMIT` among those the port follows, with a link to each diff;
corrections are then carried over by hand, skill by skill. Nothing is updated automatically.

    server/.venv/Scripts/python tools/cskillsys_watch.py
"""

from __future__ import annotations

import json
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "server"))

from fe_maker.decomp.skills import COMMIT, REPO  # noqa: E402
from fe_maker.ferepo import _ssl_context  # noqa: E402

# The upstream files the port follows (docs/competences.md, lot 1)
FOLLOWED = (
    "Kernel/Wizardry/Core/SkillSys/kernel/",
    "Kernel/Wizardry/Core/UnitStatusGetter/source/",
    "Kernel/Wizardry/Core/BattleSys/Source/PreBattleCalc.c",
    "Kernel/Wizardry/Core/BattleSys/Source/BattleOrder.c",
    "Contents/Texts/Source/texts/",
    "Contents/Gfx/Sources/SkillIcon/",
)


def main() -> int:
    url = f"https://api.github.com/repos/{REPO}/compare/{COMMIT}...HEAD"
    request = urllib.request.Request(url, headers={"User-Agent": "FE-Maker", "Accept": "application/vnd.github+json"})
    with urllib.request.urlopen(request, timeout=60, context=_ssl_context()) as response:
        compare = json.load(response)
    files = [f for f in compare.get("files", []) if f["filename"].startswith(FOLLOWED)]
    print(f"C-SkillSys: {compare.get('ahead_by', 0)} commits since {COMMIT[:10]}; {len(files)} followed files changed")
    for f in files:
        print(f"  {f['status']:<9} {f['filename']}  (+{f['additions']} -{f['deletions']})")
    if files:
        print(compare.get("html_url", ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
