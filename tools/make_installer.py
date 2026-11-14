"""FE Maker's Windows installer: the release package (tools/make_release.py) with its own Python, so that nothing else
has to be installed. Run on Windows, by a 64-bit CPython of the same minor version as EMBED_VERSION (the release
workflow's), after make_release.py:

    python tools/make_release.py
    python tools/make_installer.py      ->  dist/fe-maker-setup-<version>.exe (Inno Setup 6's ISCC needed)

The Python is python.org's embeddable package; it lacks Tk, which the folder picker needs (folderpick.py): tkinter,
its DLLs and Tcl/Tk's scripts are copied from the Python running this script. The dependencies (server/pyproject.toml)
and pip (for an update's new dependencies, update.pip_command) go into python/Lib/site-packages; fe_maker itself is
found through the ._pth file (../server), so an update only has to replace server/fe_maker.
"""

from __future__ import annotations

import argparse
import io
import os
import re
import shutil
import subprocess
import sys
import tempfile
import urllib.request
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import make_release  # noqa: E402

ROOT = make_release.ROOT
EMBED_VERSION = "3.11.9"
EMBED_URL = f"https://www.python.org/ftp/python/{EMBED_VERSION}/python-{EMBED_VERSION}-embed-amd64.zip"
TK_DLLS = ("_tkinter.pyd", "tcl86t.dll", "tk86t.dll")
TCL_DIRS = ("tcl8.6", "tk8.6", "tcl8")


def dependencies(root: Path = ROOT) -> list[str]:
    text = (root / "server" / "pyproject.toml").read_text(encoding="utf-8")
    block = re.search(r"^dependencies = \[(.*?)^\]", text, re.MULTILINE | re.DOTALL)
    return re.findall(r'^\s*"([^"]+)"', block.group(1), re.MULTILINE)


def pth(tag: str) -> str:
    """The embeddable Python's path file: its standard library, the copied tkinter (Lib), the dependencies, and
    fe_maker from the server folder beside it; `import site` for pip."""
    return "\n".join([f"python{tag}.zip", ".", "Lib", r"Lib\site-packages", r"..\server", "import site", ""])


def python_folder(target: Path, embed: bytes) -> None:
    major, minor = EMBED_VERSION.split(".")[:2]
    if sys.version_info[:2] != (int(major), int(minor)) or sys.platform != "win32" or sys.maxsize < 2**32:
        sys.exit(f"Run this script with a 64-bit Python {major}.{minor} on Windows (Tk and wheels are copied from it)")
    tag = f"{major}{minor}"
    with zipfile.ZipFile(io.BytesIO(embed)) as archive:
        archive.extractall(target)
    (target / f"python{tag}._pth").write_text(pth(tag), encoding="ascii")
    base = Path(sys.base_prefix)
    shutil.copytree(base / "Lib" / "tkinter", target / "Lib" / "tkinter", ignore=shutil.ignore_patterns("__pycache__", "test"))
    for name in TK_DLLS:
        shutil.copy2(base / "DLLs" / name, target / name)
    for name in TCL_DIRS:
        if (base / "tcl" / name).is_dir():
            shutil.copytree(base / "tcl" / name, target / "tcl" / name, ignore=shutil.ignore_patterns("demos"))
    subprocess.run([sys.executable, "-m", "pip", "install", "--quiet", "--disable-pip-version-check", "--no-compile",
                    "--target", str(target / "Lib" / "site-packages"), "--only-binary=:all:", "pip",
                    *dependencies()], check=True)


def stage(release_zip: Path, target: Path, embed: bytes) -> None:
    shutil.rmtree(target, ignore_errors=True)
    with zipfile.ZipFile(release_zip) as archive:
        for name in archive.namelist():
            if name.endswith("/"):
                continue
            path = target / name.removeprefix("fe-maker/")
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(archive.read(name))
    python_folder(target / "python", embed)
    # the bundled Python runs FE Maker: the server, Tk (the folder picker) and the dependencies all load
    check = subprocess.run([str(target / "python" / "python.exe"), "-c",
                            "import fe_maker, fe_maker.api, tkinter, _tkinter, numpy, PIL, uvicorn; "
                            "print(fe_maker.__version__)"],
                           cwd=target, capture_output=True, text=True, env={**os.environ, "PYTHONPATH": ""})
    if check.returncode or check.stdout.strip() != make_release.version():
        sys.exit(f"The bundled Python does not run FE Maker:\n{check.stdout}{check.stderr}")
    # ...and the decomp's scripts as the native build runs them (native.python_command): one importing its neighbour,
    # which the embeddable Python alone does not find (ticket 82)
    with tempfile.TemporaryDirectory() as folder:
        (Path(folder) / "neighbour.py").write_text("WORD = 'found'\n")
        (Path(folder) / "script.py").write_text("from neighbour import WORD\nprint(WORD)\n")
        check = subprocess.run([str(target / "python" / "python.exe"),
                                str(target / "server" / "fe_maker" / "native" / "runscript.py"),
                                str(Path(folder) / "script.py")], capture_output=True, text=True)
        if check.returncode or check.stdout.strip() != "found":
            sys.exit(f"The bundled Python does not run the decomp's scripts:\n{check.stdout}{check.stderr}")


def iscc() -> str | None:
    found = shutil.which("iscc") or shutil.which("ISCC")
    for folder in (os.environ.get("ProgramFiles(x86)", ""), os.environ.get("ProgramFiles", ""),
                   os.path.join(os.environ.get("LOCALAPPDATA", ""), "Programs")):
        candidate = Path(folder) / "Inno Setup 6" / "ISCC.exe"
        if not found and folder and candidate.is_file():
            found = str(candidate)
    return found


def numeric(version: str) -> str:
    """"0.43" -> "0.43.0.0", "0.1.0-prealpha.41" -> "0.1.0.41" (the file's version information takes numbers only)."""
    numbers = re.findall(r"\d+", version)
    return ".".join((numbers + ["0"] * 4)[:4])


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--embed", type=Path, help="the embeddable Python's zip, already downloaded")
    parser.add_argument("--stage-only", action="store_true", help="prepare dist/installer without compiling it")
    args = parser.parse_args()
    version = make_release.version()
    release_zip = ROOT / "dist" / f"fe-maker-{version}.zip"
    if not release_zip.is_file():
        sys.exit("Make the package first: python tools/make_release.py")
    if args.embed:
        embed = args.embed.read_bytes()
    else:
        with urllib.request.urlopen(EMBED_URL, timeout=120) as response:
            embed = response.read()
    target = ROOT / "dist" / "installer"
    stage(release_zip, target, embed)
    if args.stage_only:
        print(target)
        return
    compiler = iscc()
    if not compiler:
        sys.exit("Inno Setup 6 is needed (ISCC.exe): https://jrsoftware.org/isdl.php")
    subprocess.run([compiler, "/Q", f"/DAppVersion={version}", f"/DNumericVersion={numeric(version)}",
                    f"/DStage={target}", f"/DOutputDir={ROOT / 'dist'}", str(ROOT / "tools" / "installer.iss")],
                   check=True)
    print(ROOT / "dist" / f"fe-maker-setup-{version}.exe")


if __name__ == "__main__":
    main()
