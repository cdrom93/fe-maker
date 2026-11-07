"""Build FE Maker's Windows toolchain archive (native build without Docker, docs/sans-docker.md).

Run on Windows by .github/workflows/toolchain.yml, or by hand. Inputs are downloaded from their official sources
beforehand (the workflow says which versions):
  --w64devkit  unpacked w64devkit (GCC for MinGW, make, busybox): builds the tools, gives make and busybox
  --arm        unpacked Arm GNU Toolchain for arm-none-eabi: gives as, ld, objcopy, strip, cpp
  --agbcc      pret/agbcc source, at the commit of docker/Dockerfile
  --decomp     the decomp, for its MIT tools' sources (jsonproc, without license, is replaced by native/jsonproc.py)
  --zlib, --libpng  sources, built statically into gbagfx
Output: <out>/ (the toolchain folder FE Maker uses) and <out>.zip.
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
from pathlib import Path

BUSYBOX_APPLETS = ("sh", "sed", "find", "iconv", "echo", "cp", "mv", "rm", "mkdir", "uname", "sha1sum", "cat",
                   "touch", "test", "printf", "tr", "cut", "grep", "dirname", "basename", "env", "true", "false",
                   "ls", "head", "tail", "sort", "expr", "wc")
ARM_TOOLS = ("as", "ld", "objcopy", "strip", "cpp", "ar")
DECOMP_TOOLS = ("aif2pcm", "bin2c", "gbagfx", "mid2agb", "scaninc", "textencode")


def sh(w64devkit: Path, arm: Path, script: str, cwd: Path, extra_path: str = "") -> None:
    path = os.pathsep.join(p for p in (str(w64devkit / "bin"), str(arm / "bin"), extra_path) if p)
    env = {**os.environ, "PATH": path + os.pathsep + os.environ.get("PATH", "")}
    subprocess.run([str(w64devkit / "bin" / "sh.exe"), "-c", "set -e; " + script], cwd=cwd, env=env, check=True)


def build_agbcc(args, out: Path) -> None:
    src = args.agbcc
    # One job at a time, as its build.sh: in parallel, generated headers (genrtl.h) are missing.
    if not args.skip_agbcc_build:
        sh(args.w64devkit, args.arm, "make -C gcc clean; make -C gcc old -j1; mv gcc/old_agbcc.exe .;"
           " make -C gcc clean; make -C gcc -j1; mv gcc/agbcc.exe .;"
           " make -C libgcc clean; make -C libgcc; mv libgcc/libgcc.a .;"
           " make -C libc clean; make -C libc; mv libc/libc.a .", src)
    target = out / "agbcc"
    (target / "bin").mkdir(parents=True)
    (target / "lib").mkdir()
    for exe in ("agbcc.exe", "old_agbcc.exe"):
        shutil.copy2(src / exe, target / "bin")
    shutil.copytree(src / "libc" / "include", target / "include")
    for header in (src / "ginclude").iterdir():
        shutil.copy2(header, target / "include")
    for lib in ("libgcc.a", "libc.a"):
        shutil.copy2(src / lib, target / "lib")


def build_png(args, prefix: Path) -> None:
    (prefix / "include").mkdir(parents=True)
    (prefix / "lib" / "pkgconfig").mkdir(parents=True)
    sh(args.w64devkit, args.arm, "make -f win32/Makefile.gcc libz.a", args.zlib)
    sh(args.w64devkit, args.arm, "cp scripts/pnglibconf.h.prebuilt pnglibconf.h;"
       f" make -f scripts/makefile.gcc ZLIBINC='{args.zlib.as_posix()}' ZLIBLIB='{args.zlib.as_posix()}' libpng.a",
       args.libpng)
    for header in ("zlib.h", "zconf.h"):
        shutil.copy2(args.zlib / header, prefix / "include")
    for header in ("png.h", "pngconf.h", "pnglibconf.h"):
        shutil.copy2(args.libpng / header, prefix / "include")
    shutil.copy2(args.zlib / "libz.a", prefix / "lib")
    shutil.copy2(args.libpng / "libpng.a", prefix / "lib")
    (prefix / "lib" / "pkgconfig" / "libpng.pc").write_text(
        f"prefix={prefix.as_posix()}\nName: libpng\nDescription: png\nVersion: 1\n"
        "Cflags: -I${prefix}/include\nLibs: -L${prefix}/lib -lpng -lz\n")


def build_tools(args, out: Path, prefix: Path) -> None:
    tools = out / "tools"
    tools.mkdir()
    for tool in DECOMP_TOOLS:
        folder = args.decomp / "tools" / tool
        env_line = f"export PKG_CONFIG_PATH='{(prefix / 'lib' / 'pkgconfig').as_posix()}';"
        sh(args.w64devkit, args.arm, f"{env_line} make clean || true; make", folder)
        exe = folder / f"{tool}.exe"
        if not exe.is_file():
            exe = folder / tool
        shutil.copy2(exe, tools / f"{tool}.exe")
        if (folder / "LICENSE").is_file():
            shutil.copy2(folder / "LICENSE", tools / f"{tool}.LICENSE")
        else:   # textencode: the MIT notice heads its source file
            source = (folder / f"{tool}.c").read_text(encoding="utf-8").splitlines()
            notice = [line[2:].strip() for line in source if line.startswith("//")][:20]
            (tools / f"{tool}.LICENSE").write_text("\n".join(notice) + "\n", encoding="utf-8")


def copy_programs(args, out: Path) -> None:
    bin_dir = out / "bin"
    bin_dir.mkdir()
    shutil.copy2(args.w64devkit / "bin" / "make.exe", bin_dir)
    shutil.copy2(args.w64devkit / "bin" / "busybox.exe", bin_dir)
    for applet in BUSYBOX_APPLETS:   # w64devkit's small launchers that run busybox with their own name
        shutil.copy2(args.w64devkit / "bin" / f"{applet}.exe", bin_dir)
    for tool in ARM_TOOLS:
        shutil.copy2(args.arm / "bin" / f"arm-none-eabi-{tool}.exe", bin_dir)
    # cpp runs cc1 from ../libexec/gcc/arm-none-eabi/<version>/
    for cc1 in (args.arm / "libexec" / "gcc" / "arm-none-eabi").glob("*/cc1.exe"):
        target = out / cc1.relative_to(args.arm)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(cc1, target)
    for dll in args.arm.joinpath("bin").glob("*.dll"):
        shutil.copy2(dll, bin_dir)


def main() -> None:
    parser = argparse.ArgumentParser()
    for name in ("w64devkit", "arm", "agbcc", "decomp", "zlib", "libpng", "out"):
        parser.add_argument(f"--{name}", type=Path, required=True)
    parser.add_argument("--skip-agbcc-build", action="store_true", help="agbcc is already built in --agbcc")
    args = parser.parse_args()
    out: Path = args.out
    shutil.rmtree(out, ignore_errors=True)
    out.mkdir(parents=True)
    copy_programs(args, out)
    build_agbcc(args, out)
    prefix = out.with_name(out.name + "-png")
    shutil.rmtree(prefix, ignore_errors=True)
    build_png(args, prefix)
    build_tools(args, out, prefix)
    (out / "README.txt").write_text(
        "FE Maker toolchain for building the FE8 decomp on Windows without Docker.\n"
        "GPL programs (make, busybox, Arm binutils and cpp, agbcc): their sources are attached to the same release.\n"
        "The decomp's tools are under the MIT license (tools/*.LICENSE).\n")
    shutil.make_archive(str(out), "zip", out)


if __name__ == "__main__":
    main()
