"""Build errors said plainly (builderrors.py), from the toolchain's real messages."""

from fe_maker import builderrors

NOISE = ["C:/x/native/win.mk:6: warning: overriding recipe for target 'objects.lst'",
         "Makefile:240: warning: ignoring old recipe for target 'objects.lst'",
         "src/bmdifficulty.s:4200: Warning: ignoring changed section attributes for .data"]   # in every build


def test_compiler_and_assembler_errors_name_the_file_and_its_part(tmp_path):
    (tmp_path / "src").mkdir()
    (tmp_path / "src/data_items.c").write_text("x", encoding="utf-8")
    why = builderrors.explain("Build failed", [*NOISE, "src/data_items.c:2950: syntax error before `;'",
                                               "make: *** [Makefile:251: src/data_items.o] Error 1"], tmp_path)
    assert why == {"kind": "code", "file": "src/data_items.c", "line": 2950, "message": "syntax error before `;'",
                   "area": "items", "written": True}
    why = builderrors.explain("Build failed", ["data/data_item_icon.s:680: Error: bad instruction `bogus_op r0'"])
    assert why["message"] == "bad instruction `bogus_op r0'" and why["written"] is False


def test_text_errors_name_their_message(tmp_path):
    (tmp_path / "texts").mkdir()
    (tmp_path / "texts/texts.txt").write_text("## MSG_001\nHi[X]\n\n#0x914\nBad [Nope][X]\n", encoding="utf-8")
    why = builderrors.explain("Build failed", ["error: line 5: unknown control code [Nope]"], tmp_path)
    assert why == {"kind": "text", "line": 5, "message": "unknown control code [Nope]", "text": "0x914"}


def test_other_known_failures():
    assert builderrors.explain("x", ["make: *** No rule to make target 'nothing_here.h', needed by "
                                     "'src/data_items.o'.  Stop."]) == {
        "kind": "missingFile", "file": "nothing_here.h", "area": "items"}
    assert builderrors.explain("x", ["ld: region `rom' overflowed by 2048 bytes"]) == {"kind": "romFull", "bytes": 2048}
    assert builderrors.explain("x", ["src/a.c:(.text+0x1): undefined reference to `Foo'"]) == {
        "kind": "undefined", "symbol": "Foo"}
    assert builderrors.explain("Fix these problems before building: A; B") == {"kind": "problems",
                                                                               "problems": ["A", "B"]}
    assert builderrors.explain("CParseError: Array gItemData not found")["kind"] == "decompMismatch"
    assert builderrors.explain("Build failed", NOISE) is None
