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
    assert project.test_options == {"start": "map", "simplePrologue": True, "chapter": 0}

    overlay = project.generate_overlay(decomp_dir, for_test=True)
    assert "FEMaker_QuickStartOnMap" in (overlay / "src" / "gamecontrol.c").read_text(encoding="utf-8")
    # No world map in this mode: MNCH goes straight to its chapter (ticket 38)
    assert "#define MNCH EvtChangeChapterBM" in (overlay / "include" / "EAstdlib.h").read_text(encoding="utf-8")

    overlay = project.generate_overlay(decomp_dir, for_test=False)
    assert not (overlay / "src" / "gamecontrol.c").exists()
    assert not (overlay / "include" / "EAstdlib.h").exists()

    project.set_test_options({"start": "normal"})
    meta = json.loads((tmp_path / "p" / "fe-maker.json").read_text(encoding="utf-8"))
    assert meta["testOptions"] == {"start": "normal", "simplePrologue": True, "chapter": 0}
    overlay = project.generate_overlay(decomp_dir, for_test=True)
    assert not (overlay / "src" / "gamecontrol.c").exists()

    # "Test this chapter": the quick start goes to that chapter
    project.set_test_options({"start": "map", "chapter": 2})
    source = (project.generate_overlay(decomp_dir, for_test=True) / "src" / "gamecontrol.c").read_text(encoding="utf-8")
    assert "gPlaySt.chapterIndex = 2; /* FE Maker: test this chapter */" in source
    project.set_test_options({"chapter": 0})
    with pytest.raises(ProjectError):
        project.set_test_options({"start": "nowhere"})


def test_no_world_map_option(tmp_path, decomp_dir):
    """Ticket 39: like FEBuilder's option, chapters follow each other without the world map, in the
    exported patch too; a test build started on the map does not apply it twice."""
    project = Project.create(tmp_path / "p", "P", decomp_dir=decomp_dir)
    assert project.world_map
    assert not (project.generate_overlay(decomp_dir, for_test=False) / "include" / "EAstdlib.h").exists()
    project.set_world_map(False)
    assert not Project(tmp_path / "p", decomp_dir).world_map
    for for_test in (False, True):
        macros = (project.generate_overlay(decomp_dir, for_test=for_test) / "include" / "EAstdlib.h").read_text(encoding="utf-8")
        assert macros.count("#define MNCH EvtChangeChapterBM") == 1
        assert "#define MNCH EvtChangeChapterWM" not in macros
        kind = (project.generate_overlay(decomp_dir, for_test=for_test) / "src" / "worldmap_path.c").read_text(encoding="utf-8")
        assert kind.count("return BATTLEMAP_KIND_STORY;") == 2  # chapters are never taken for skirmishes


def test_old_skip_intro_option_is_migrated(tmp_path, decomp_dir):
    project = Project.create(tmp_path / "p", "P", decomp_dir=decomp_dir)
    project.meta["testOptions"] = {"skipIntro": True}
    assert project.test_options == {"start": "menu", "simplePrologue": True, "chapter": 0}


def test_simplified_prologue(tmp_path, decomp_dir):
    from fe_maker.decomp import units

    project = Project.create(tmp_path / "p", "P", decomp_dir=decomp_dir)
    overlay = project.generate_overlay(decomp_dir, for_test=True)
    script = (overlay / "src" / "events" / "prologue-eventscript.h").read_text(encoding="utf-8")
    scene = script.split("EventScr_Prologue_BeginningScene[] = {")[1].split("};")[0]
    assert "CALL(" not in scene and "Text(" not in scene
    assert scene.index("UnitDef_Event_PrologueAlly") < scene.index("UnitDef_Event_PrologueEnemy")
    assert "EventScr_Prologue_EndingScene" in script
    # Units appear where their entry path ends.
    (tmp_path / "read" / "src" / "events").mkdir(parents=True)
    (tmp_path / "read" / "src" / "events" / "prologue-eventudefs.h").write_text(
        (overlay / "src" / "events" / "prologue-eventudefs.h").read_text(encoding="utf-8"), encoding="utf-8")
    units.read_unit_groups.cache_clear()
    ally = units.read_unit_groups(tmp_path / "read")["UnitDef_Event_PrologueAlly"].units[0]
    assert (ally["x"], ally["y"], ally["endX"], ally["endY"]) == (3, 4, 3, 4)

    project.set_test_options({"simplePrologue": False})
    overlay = project.generate_overlay(decomp_dir, for_test=True)
    assert not (overlay / "src" / "events" / "prologue-eventscript.h").exists()
    # Never in the exported game.
    project.set_test_options({"simplePrologue": True})
    overlay = project.generate_overlay(decomp_dir, for_test=False)
    assert not (overlay / "src" / "events" / "prologue-eventscript.h").exists()


def test_animation_modes_by_weapon_only_for_mixed_units(tmp_path):
    """Ticket 52: a mage with a sword rank strikes with her sword animation's close moves."""
    from fe_maker.decomp import tweaks

    classes = [{"id": "CLASS_MAGE", "weaponRanks": {"anima": "E"}}, {"id": "CLASS_LORD", "weaponRanks": {"sword": "E"}}]
    assert not tweaks.mixes_magic([{"class": "CLASS_LORD", "weaponRanks": {"sword": "D"}}], classes)
    assert tweaks.mixes_magic([{"class": "CLASS_MAGE", "weaponRanks": {"sword": "D"}}], classes)
    assert tweaks.mixes_magic([{"class": "CLASS_LORD", "weaponRanks": {"dark": "D"}}], classes)
    checks = "    if (!UnitHasMagicRank(unit_r6)) {}\n" * 4
    source = '#include "global.h"\n#include "bmunit.h"\n\nvoid f(void)\n{\n' + checks + "}\n"
    (tmp_path / "src").mkdir()
    (tmp_path / tweaks.BATTLE_PARSE_FILE).write_text(source, encoding="utf-8")
    out = tweaks.animation_modes_by_weapon(tmp_path, {})[tweaks.BATTLE_PARSE_FILE]
    assert out.count("FEMaker_MagicAttack(unit_r6)") == 4 and "UnitHasMagicRank(unit_r6)" not in out
    assert out.index('#include "bmunit.h"') < out.index("static s8 FEMaker_MagicAttack") < out.index("void f(void)")
