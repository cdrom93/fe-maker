import json

import pytest

from fe_maker.decomp.tweaks import TweakError, skip_intro
from fe_maker.project import Project


def test_skip_intro_inserts_goto(decomp_dir):
    source = (decomp_dir / "src" / "gamecontrol.c").read_text(encoding="utf-8")
    out = skip_intro(source)
    assert "    PROC_REPEAT(GameControl_8009A60_Null),\n    PROC_GOTO(LGAMECTRL_EXEC_SAVEMENU)," in out
    assert out.count("PROC_GOTO(LGAMECTRL_EXEC_SAVEMENU)") == 1


def test_skip_intro_refuses_unknown_source():
    with pytest.raises(TweakError):
        skip_intro("struct ProcCmd CONST_DATA gProcScr_GameControl[] = { PROC_END };")


def test_skip_intro_only_in_test_builds(tmp_path, decomp_dir):
    project = Project.create(tmp_path / "p", "P", decomp_dir=decomp_dir)
    assert project.test_options == {"skipIntro": True}

    overlay = project.generate_overlay(decomp_dir, for_test=True)
    assert (overlay / "src" / "gamecontrol.c").is_file()

    overlay = project.generate_overlay(decomp_dir, for_test=False)
    assert not (overlay / "src" / "gamecontrol.c").exists()

    project.set_test_options({"skipIntro": False})
    assert json.loads((tmp_path / "p" / "fe-maker.json").read_text(encoding="utf-8"))["testOptions"] == {"skipIntro": False}
    overlay = project.generate_overlay(decomp_dir, for_test=True)
    assert not (overlay / "src" / "gamecontrol.c").exists()
