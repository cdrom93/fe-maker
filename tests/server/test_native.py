"""Native Windows build (fe_maker.native): working copy sync, jsonproc and battle animation linker helpers.
The build itself needs the ROM and the toolchain: tests/local."""

import json
import os
import time
import zipfile
from io import BytesIO
from pathlib import Path

import pytest

from fe_maker import native
from fe_maker.native import asmdeps, banim_link, jsonproc


def write(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)
    return path


def test_sync_copies_overlay_then_restores_decomp(tmp_path):
    decomp, work, overlay = tmp_path / "decomp", tmp_path / "work", tmp_path / "overlay"
    write(decomp / "src/a.c", "original")
    write(decomp / ".git/config", "x")
    write(overlay / "src/a.c", "project")
    write(overlay / "sound/songs/midi/song1_fem_x.mid", "song")
    native.sync(decomp, work, overlay)
    assert (work / "src/a.c").read_text() == "project"
    assert (work / "sound/songs/midi/song1_fem_x.mid").is_file()
    assert not (work / ".git").exists()
    # Next project, without the overlay: the decomp's file comes back (same size, older time), the song goes.
    time.sleep(0.01)
    native.sync(decomp, work, None)
    assert (work / "src/a.c").read_text() == "original"
    assert not (work / "sound/songs/midi/song1_fem_x.mid").exists()


def test_sync_forgets_dependencies_on_a_removed_header(tmp_path):
    """A header only the previous project added (skills_fem.h): the .d files naming it go, make writes them again."""
    decomp, work, overlay = tmp_path / "decomp", tmp_path / "work", tmp_path / "overlay"
    write(decomp / "src/a.c", "original")
    write(decomp / "src/b.c", "original")
    write(overlay / "include/skills_fem.h", "numbers")
    native.sync(decomp, work, overlay)
    write(work / ".dep/src/a.d", "src/a.o: src/a.c include/eventscript.h \\\n include/skills_fem.h\n")
    write(work / ".dep/src/b.d", "src/b.o: src/b.c include/global.h\n")
    native.sync(decomp, work, None)
    assert not (work / "include/skills_fem.h").exists()
    assert not (work / ".dep/src/a.d").exists() and (work / ".dep/src/b.d").is_file()


def test_sync_leaves_unchanged_files_alone(tmp_path):
    decomp, work = tmp_path / "decomp", tmp_path / "work"
    write(decomp / "src/a.c", "same")
    native.sync(decomp, work, None)
    old = os.stat(work / "src/a.c").st_mtime_ns
    assert native.sync(decomp, work, None) == 0
    assert os.stat(work / "src/a.c").st_mtime_ns == old


def test_install_toolchain_checks_the_archive(tmp_path):
    good = BytesIO()
    with zipfile.ZipFile(good, "w") as z:
        z.writestr("bin/make.exe", "x")
        z.writestr("agbcc/bin/agbcc.exe", "x")
    native.install_toolchain(good.getvalue(), tmp_path / "toolchain")
    assert native.toolchain_ready(tmp_path / "toolchain")
    bad = BytesIO()
    with zipfile.ZipFile(bad, "w") as z:
        z.writestr("../evil.exe", "x")
    with pytest.raises(native.NativeBuildError):
        native.install_toolchain(bad.getvalue(), tmp_path / "other")
    assert not (tmp_path / "evil.exe").exists()


def test_make_command_quotes_paths_and_sets_bugfix(tmp_path):
    command = native.make_command(tmp_path / "with space", bugfix=True)
    assert command[0].endswith("make.exe")
    assert "CPP=arm-none-eabi-cpp -DBUGFIX=1" in command
    assert any(arg.startswith('PYTHON="') and arg.endswith('"') for arg in command)
    assert "NODEP=1" in command   # ticket 30: no scaninc (asmdeps.py)


def test_asmdeps_finds_what_scaninc_finds(tmp_path):
    """Ticket 30: includes searched in include/, the working copy, then the including file's folder, recursively;
    incbins as written; comments and strings skipped."""
    write(tmp_path / "include/macro.inc", '.include "inner.inc"\n')
    write(tmp_path / "include/inner.inc", "@ nothing\n")
    write(tmp_path / "asm/local.inc", '.incbin "graphics/x.4bpp.lz"\n')
    write(tmp_path / "asm/a.s", (
        '\t.include "macro.inc"\n'
        '.include "local.inc"\n'
        '.include "missing.inc"\n'
        '; .include "commented.inc"\n'
        '/* .incbin "hidden.bin"\n.incbin "hidden2.bin" */\n'
        '.string ".include \\"no\\""\n'
        '#incbin "baserom.gba"\n'))
    write(tmp_path / "data/b.s", "nop\n")
    assert asmdeps.dependencies(tmp_path, "asm/a.s") == [
        "asm/local.inc", "baserom.gba", "graphics/x.4bpp.lz", "include/inner.inc", "include/macro.inc"]
    assert asmdeps.write(tmp_path) == 2
    rules = (tmp_path / asmdeps.DEPS_FILE).read_text(encoding="utf-8")
    assert "asm/a.o: asm/local.inc baserom.gba" in rules and "data/b.o: \n" in rules


def test_jsonproc_renders_loops_conditions_and_header(tmp_path):
    data = write(tmp_path / "d.json", json.dumps({
        "items": [{"id": "0x1", "flag": True, "sub": {"k": 3}}, {"id": 2, "flag": False, "sub": {}}],
    }))
    template = write(tmp_path / "t.txt", (
        "{{ doNotModifyHeader }}\n"
        "## for item in items\n"
        "    .byte {{ item.id }}, {% if existsIn(item.sub, \"k\") %}{{ item.sub.k }}{% else %}0{% endif %}, "
        "{% if item.flag %}TRUE{% else %}FALSE{% endif %}, {{ upper(\"ab\") }}\n"
        "## endfor\n"
        "    .word 0\n"))
    out = tmp_path / "out.inc"
    jsonproc.main([str(data), str(template), str(out)])
    assert out.read_text() == (
        f"//\n// DO NOT MODIFY THIS FILE! It is auto-generated from {data} and Inja template {template}\n//\n\n"
        "    .byte 0x1, 3, TRUE, AB\n"
        "    .byte 2, 0, FALSE, AB\n"
        "    .word 0\n")


def test_banim_link_reads_the_script_and_names_labels_like_the_original(tmp_path):
    script = write(tmp_path / "s.txt", "# comment\n\ngraphics/a_sheet_0.4bpp.lz\n"
                   "data/a_motion.o|.data.script>lz\ndata/a_modes.bin\n")
    assert banim_link.parse_script(script) == [
        ("graphics/a_sheet_0.4bpp.lz", ".data", None),
        ("data/a_motion.o", ".data.script", "lz"),
        ("data/a_modes.bin", ".data", None),
    ]
    assert banim_link.label_for("graphics/a_sheet_0.4bpp.lz") == "a_sheet_0"
    assert banim_link.label_for("graphics/a.agbpal.lz") == "a_agbpal"
    assert banim_link.label_for("data/a_motion.o.bin.lz") == "a_motion_o"
    assert banim_link.label_for("data/a_modes.bin") == "a_modes_bin"


def test_a_missing_header_in_the_log_forgets_its_dependency_lists(tmp_path):
    """A working copy left with stale lists (#51): make's "No rule to make target" names the file to forget."""
    write(tmp_path / ".dep/src/a.d", "src/a.o: src/a.c include/skills_fem.h\n")
    log = "make: *** No rule to make target 'include/skills_fem.h', needed by 'src/a.o'.  Stop.\n"
    native._forget_dependencies(tmp_path, set(native._NO_RULE.findall(log)))
    assert not (tmp_path / ".dep/src/a.d").exists()


def test_decomp_scripts_find_their_neighbours_with_an_isolated_python(tmp_path):
    """The installer's embeddable Python leaves the script's folder out of sys.path, like `python -I` (ticket 82):
    make's $(PYTHON) goes through runscript.py, which puts it back."""
    import subprocess
    import sys

    (tmp_path / "huffman.py").write_text("WORD = 'found'\n")
    (tmp_path / "tool.py").write_text("import sys\nfrom huffman import WORD\nprint(WORD, sys.argv[1:])\n")
    plain = subprocess.run([sys.executable, "-I", str(tmp_path / "tool.py")], capture_output=True, text=True)
    assert "No module named 'huffman'" in plain.stderr
    runner = native.NATIVE_DIR / "runscript.py"
    fixed = subprocess.run([sys.executable, "-I", str(runner), str(tmp_path / "tool.py"), "a", "b"],
                           capture_output=True, text=True)
    assert fixed.stdout.strip() == "found ['a', 'b']"
    assert native.python_command().endswith('/runscript.py"')
