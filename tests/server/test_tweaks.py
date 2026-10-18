import json

import pytest

from fe_maker.decomp.tweaks import TweakError, skip_intro, start_on_map
from fe_maker.project import Project, ProjectError


def _source(decomp_dir):
    return (decomp_dir / "src" / "gamecontrol.c").read_text(encoding="utf-8")


def test_skip_intro_inserts_goto(decomp_dir):
    out = skip_intro(_source(decomp_dir))
    assert "    PROC_REPEAT(GameControl_8009A60_Null),\n    PROC_GOTO(LGAMECTRL_EXEC_SAVEMENU)," in out
    assert out.count("PROC_GOTO(LGAMECTRL_EXEC_SAVEMENU)") == 1


def test_start_on_map_declares_calls_and_defines(decomp_dir):
    out = start_on_map(_source(decomp_dir))
    decl = out.index("void FEMaker_QuickStartOnMap(ProcPtr proc);")
    array = out.index("gProcScr_GameControl[]")
    call = out.index("PROC_CALL(FEMaker_QuickStartOnMap),")
    definition = out.index("void FEMaker_QuickStartOnMap(ProcPtr proc)\n{")
    assert decl < array < call < definition
    assert "Proc_Goto(proc, LGAMECTRL_EXEC_BM_EXT);" in out


def test_tweaks_refuse_unknown_source():
    for tweak in (skip_intro, start_on_map):
        with pytest.raises(TweakError):
            tweak("struct ProcCmd CONST_DATA gProcScr_GameControl[] = { PROC_END };")


def test_start_mode_only_in_test_builds(tmp_path, decomp_dir):
    project = Project.create(tmp_path / "p", "P", decomp_dir=decomp_dir)
    assert project.test_options == {"start": "map"}

    overlay = project.generate_overlay(decomp_dir, for_test=True)
    assert "FEMaker_QuickStartOnMap" in (overlay / "src" / "gamecontrol.c").read_text(encoding="utf-8")

    overlay = project.generate_overlay(decomp_dir, for_test=False)
    assert not (overlay / "src" / "gamecontrol.c").exists()

    project.set_test_options({"start": "normal"})
    assert json.loads((tmp_path / "p" / "fe-maker.json").read_text(encoding="utf-8"))["testOptions"] == {"start": "normal"}
    overlay = project.generate_overlay(decomp_dir, for_test=True)
    assert not (overlay / "src" / "gamecontrol.c").exists()

    with pytest.raises(ProjectError):
        project.set_test_options({"start": "nowhere"})


def test_old_skip_intro_option_is_migrated(tmp_path, decomp_dir):
    project = Project.create(tmp_path / "p", "P", decomp_dir=decomp_dir)
    project.meta["testOptions"] = {"skipIntro": True}
    assert project.test_options == {"start": "menu"}
