from pathlib import Path

import pytest

from fe_maker.decomp import skills

DECOMP = Path(__file__).parents[2] / "decomp"
PAGE = {"label": 1, "talk": 50, "lead": 51, "leadHelp": 52, "leadValue": 53}   # page 1 texts (ticket 171)


def test_the_catalogue_marks_magic_skills_and_names_the_game_ones_sources():
    magic = {s["id"] for s in skills.catalogue() if s["magic"]}
    assert magic == {"MagBonus", "DefiantMag"}
    assert all(s.icon and s.text.count("[NL]") >= 1 for s in skills.CATALOGUE + skills.GAME_SKILLS)
    game = {g["id"]: g for g in skills.game_catalogue()}
    assert game["Dance"]["abilities"] == ["dance", "play"] and game["Pierce"]["classes"][0] == "CLASS_WYVERN_KNIGHT"


def test_used_skills_in_catalogue_order_then_the_game_ones():
    used = skills.used([{"skills": ["Wrath", "StrBonus"]}], [{"skills": ["MagBonus", "Wrath"]}, {}], False)
    ids = [s.id for s in used]
    assert ids[:2] == ["StrBonus", "Wrath"]   # MagBonus left out without the split
    assert ids[2:] == [s.id for s in skills.GAME_SKILLS]


def test_texts_go_on_lines_of_the_game():
    class Data:
        bodies: tuple = ()

        def add_texts(self, *bodies):
            self.bodies = bodies
            return tuple(range(100, 100 + len(bodies)))

    data = Data()
    numbers = skills.add_texts(data, [skills.BY_ID["Wrath"]])
    assert numbers == {"label": 100, "talk": 101, "lead": 102, "leadHelp": 103, "leadValue": 104, "Wrath": 105}
    assert data.bodies == ("Skills", *skills.PAGE_TEXTS, "Wrath:[LF]\nIf current HP is < 50%[LF]\nof max, +20 Crit Rate.")


def test_skills_match_the_decomp(monkeypatch):
    if not (DECOMP / "src/bmunit.c").is_file():
        pytest.skip("no decomp")
    monkeypatch.setattr(skills, "icon_png", lambda skill_id: b"\x89PNG")
    monkeypatch.setattr(skills, "box_png", lambda: b"\x89PNG")
    characters = [{"id": "CHARACTER_EIRIKA", "skills": ["StrBonus", "Vantage", "DefiantSpd"]}]
    classes = [{"id": "CLASS_EIRIKA_LORD", "skills": ["BlowDarting"]}]
    used = skills.used(characters, classes, False)
    texts = {**PAGE, **{s.id: 2 + k for k, s in enumerate(used)}}
    files = skills.apply(DECOMP, {}, characters, classes, texts, False)
    unit = files["src/bmunit.c"]
    assert "    [0x01] = { 1, 4, 2 }," in unit   # StrBonus, Vantage, DefiantSpd: numbered in catalogue order
    assert "return GetUnitPowerBaseFem(unit) + SkillStatBonusFem(unit, 0);" in unit
    assert "if (defiant && SkillTesterFem(unit, SKILL_FEM_DefiantSpd))" in unit
    assert "GetUnitDefenseBaseFem(unit) +" not in unit   # no Defense skill: its getter stays
    battle = files["src/bmbattle.c"]
    assert "ApplyBattleSkillsFem(attacker, defender);" in battle and "attacker->battleSpeed += 6;" in battle
    assert "SkillTesterFem(&gBattleTarget.unit, SKILL_FEM_Vantage)" in battle
    assert "#define DrawnIconLookupTable ((struct IconStruct*) 0x02028900)" in files["src/icon.c"]
    sheet = files["data/data_item_icon.s"]
    assert sheet.index("item_icon_skill_fem_StrBonus") < sheet.index("item_icon_palette:")
    assert files["graphics/item_icon/item_icon_skill_fem_Vantage.png"] == b"\x89PNG"
    status = files["src/statscreen.c"]
    assert "DisplaySkillsFem();" in status and "sHelpInfo_SkillFem3" in status
    assert "static const u16 sSkillIconFem[SKILL_COUNT_FEM + 1] = { 0, 224, 225," in status
    # ticket 171: Mov below Res (row 13 without the split), Con at the top of the right column, Lead and Talk
    assert "STATSCREEN_TEXT_MOVLABEL, gUiTmScratchA + TILEMAP_INDEX(1, 13)," in status
    assert "    DrawStatWithBar(6, 5, 13,\n" in status and "    DrawStatWithBar(7, 13, 1,\n" in status
    assert "static const u32 sMidLeadFem = 51;" in status and "DisplayLeadTalkFem();" in status
    assert "sHelpInfo_SkillFem5 =" in status and "    166, 72, 52,\n" in status   # Lead's help
    assert "TILEMAP_INDEX(12, 9)" not in status   # the affinity icon left the right column


def test_triggered_skills_go_into_each_hit(monkeypatch):
    if not (DECOMP / "src/bmbattle.c").is_file():
        pytest.skip("no decomp")
    monkeypatch.setattr(skills, "icon_png", lambda skill_id: b"\x89PNG")
    monkeypatch.setattr(skills, "box_png", lambda: b"\x89PNG")
    characters = [{"id": "CHARACTER_EIRIKA", "skills": ["Luna", "Sol", "Colossus"]}]
    classes = [{"id": "CLASS_EIRIKA_LORD", "skills": ["Pavise"]}]
    used = skills.used(characters, classes, False)
    files = skills.apply(DECOMP, {}, characters, classes, {**PAGE, **{s.id: 2 for s in used}}, False)
    battle = files["src/bmbattle.c"]
    assert "ApplyHitSkillsFem(attacker, defender, &attack, &defense);\n\n    gBattleStats.damage = attack - defense;" in battle
    assert "SkillProcFem(defender, SKILL_FEM_Pavise)" in battle and "gBattleStats.damage *= 3;" in battle
    assert "|| (sHitDrainFem && gBattleStats.damage > 0)) { /* FE Maker: Sol, Aether */" in battle
    assert battle.index("static void ApplyHitSkillsFem") < battle.index("void BattleGenerateHitAttributes(")


def test_adept_and_astra_add_hits_within_the_games_six(monkeypatch):
    if not (DECOMP / "src/bmbattle.c").is_file():
        pytest.skip("no decomp")
    monkeypatch.setattr(skills, "icon_png", lambda skill_id: b"\x89PNG")
    monkeypatch.setattr(skills, "box_png", lambda: b"\x89PNG")
    characters = [{"id": "CHARACTER_EIRIKA", "skills": ["Adept", "Astra"]}]
    used = skills.used(characters, [], False)
    battle = skills.apply(DECOMP, {}, characters, [], {**PAGE, **{s.id: 2 for s in used}}, False)["src/bmbattle.c"]
    assert "result += HitCountSkillsFem(attacker);" in battle and "SKILL_FEM_Astra, unit->unit.spd)" in battle
    assert "i < count && gBattleHitIterator < gBattleHitArray + BATTLE_HIT_MAX - 1;" in battle
    assert "    sAstraFem = FALSE;\n" in battle and "gBattleStats.damage /= 2;" in battle


def test_triggered_skill_name_shown_in_battle(monkeypatch):
    """Lot 2: each triggered skill is noted with its hit, then shown at C07 in the battle animation (Huichelaar's
    display); the HP bar leaves the skill icon's tiles alone."""
    if not (DECOMP / "include/bmunit.h").is_file():
        pytest.skip("no decomp")
    monkeypatch.setattr(skills, "icon_png", lambda skill_id: b"\x89PNG")
    monkeypatch.setattr(skills, "box_png", lambda: b"\x89PNG")
    characters = [{"id": "CHARACTER_EIRIKA", "skills": ["Luna"]}]
    used = skills.used(characters, [], False)
    files = skills.apply(DECOMP, {}, characters, [], {**PAGE, **{s.id: 2 for s in used}}, False)
    assert "sSkillShownFem[(gBattleHitIterator - gBattleHitArray) * 2 + (unit == &gBattleTarget)] = skill;" in files[
        "src/bmbattle.c"]
    assert "void StartSkillNameFem(struct Anim* anim)\n" in files["src/bmbattle.c"]
    assert "StartSkillNameFem(anim); /* FE Maker */" in files["src/banim-main.c"]
    assert "0x06013400, 0x380);" in files["src/banim-ekrgauge.c"]
    assert files["graphics/item_icon/skill_box_fem.png"] == b"\x89PNG"


def test_event_skill_commands_render_and_count_as_used():
    from fe_maker.decomp.events import render_command

    text = render_command({"op": "GiveSkill", "args": ["CHARACTER_EIRIKA", "Luna"]})
    assert "SVAL(EVT_SLOT_2, SKILL_FEM_Luna)" in text and "SVAL(EVT_SLOT_3, 1)" in text
    assert "ASMC(FemSkillEvent)" in text and text.startswith("#ifdef SKILLS_FEM_EVENTS")
    assert "SVAL(EVT_SLOT_3, 0)" in render_command({"op": "RemoveSkill", "args": ["CHARACTER_EIRIKA", "Luna"]})
    assert skills.event_skills([text]) == {"Luna"}
    assert "Luna" in [s.id for s in skills.used([], [], False, {"Luna"})]
