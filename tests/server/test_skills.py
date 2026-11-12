from pathlib import Path

import pytest

from fe_maker.decomp import skills

DECOMP = Path(__file__).parents[2] / "decomp"
PAGE = {"label": 1, "talk": 50, "lead": 51, "leadHelp": 52, "leadValue": 53}   # page 1 texts (ticket 171)


def test_the_catalogue_marks_magic_skills_and_names_the_game_ones_sources():
    magic = {s["id"] for s in skills.catalogue() if s["magic"]}
    assert magic == {"MagBonus", "DefiantMag", "PushMagic", "ArcaneBlade", "Imbue"}
    assert all(s.text.count("[NL]") >= 1 for s in skills.CATALOGUE + skills.GAME_SKILLS)
    assert skills.icon_path("NoGuard").name == "_placeholder.png"   # no icon at the pinned commit: a "?"
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
    assert "int value = GetUnitPowerBaseFem(unit) + SkillStatBonusFem(unit, 0);" in unit
    assert "if (defiant && SkillTesterFem(unit, SKILL_FEM_DefiantSpd))" in unit
    assert "GetUnitDefenseBaseFem(unit) +" not in unit   # no Defense skill: its getter stays
    battle = files["src/bmbattle.c"]
    assert battle.count("CpuFill16(0, (void*) sSkillShownFem, SKILL_SHOWN_SIZE_FEM);") == 2   # each battle, each item use
    assert "ApplyBattleSkillsFem(attacker, defender);" in battle and "attacker->battleSpeed += 6;" in battle
    assert "SkillTesterFem(&(t)->unit, SKILL_FEM_Vantage)" in battle and "BattleDoublesFem(a)" in battle
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


def test_batch_5_passives_see_the_foe_and_several_stats(monkeypatch):
    """Batch 5: both units' base stats come before either's skills (C-SkillSys's PreBattleCalcInit), comparisons run
    once both are applied, and a stat skill raises or lowers several stats under a condition (Magic only with the
    split)."""
    if not (DECOMP / "src/bmbattle.c").is_file():
        pytest.skip("no decomp")
    monkeypatch.setattr(skills, "icon_png", lambda skill_id: b"\x89PNG")
    monkeypatch.setattr(skills, "box_png", lambda: b"\x89PNG")
    characters = [{"id": "CHARACTER_EIRIKA", "skills": ["FortressDef", "PushSpeed", "HeavyBlade"]},
                  {"id": "CHARACTER_SETH", "skills": ["StanceFierce", "Chivalry"]}]
    used = skills.used(characters, [], False)
    files = skills.apply(DECOMP, {}, characters, [], {**PAGE, **{s.id: 2 for s in used}}, False)
    unit = files["src/bmunit.c"]
    assert "if (full && SkillTesterFem(unit, SKILL_FEM_PushSpeed))\n            bonus += 5;" in unit
    assert "bonus += -3;" in unit and "GetUnitMagicFem" not in unit   # Fortress: Str -3, Def +5, no Magic
    assert "return value < 0 ? 0 : value;" in unit                    # ticket 50: never under 0
    screen = files["src/fontgrp.c"] + files["src/statscreen.c"]       # ticket 50: "-3", not "+7"
    assert "TEXT_COLOR_SYSTEM_GRAY, TEXT_SPECIAL_DASH" in screen and "(sMalusColorsFem, STATSCREEN_BGPAL_MALUS_FEM)" in screen
    battle = files["src/bmbattle.c"]
    calc = battle[battle.index("void ComputeBattleUnitStats("):]
    assert calc.index("ComputeBattleUnitBaseStatsFem(defender, attacker);") < calc.index("ApplyBattleSkillsFem(")
    assert "if (attacker == &gBattleTarget) attacker->battleAttack += 6;" in battle
    assert "ApplyLateBattleSkillsFem(&gBattleTarget, &gBattleActor);" in battle
    assert "if (attacker->battleAttack > defender->battleAttack) attacker->battleCritRate += 15;" in battle
    assert "if (bu->battleHitRate < 0)" in battle
    assert battle.count("void ComputeBattleUnitStats(") == 1


def test_batch_6_hit_crit_and_damage(monkeypatch):
    """Batch 6: hit and crit after the game's effective rates (a defender's skill acts on its attacker), damage skills
    on each hit after the critical roll."""
    if not (DECOMP / "src/bmbattle.c").is_file():
        pytest.skip("no decomp")
    monkeypatch.setattr(skills, "icon_png", lambda skill_id: b"\x89PNG")
    monkeypatch.setattr(skills, "box_png", lambda: b"\x89PNG")
    characters = [{"id": "CHARACTER_EIRIKA", "skills": ["Hawkeye", "InfinityEdge", "Flare"]},
                  {"id": "CHARACTER_SETH", "skills": ["Fortune", "DragonSkin"]}]
    used = skills.used(characters, [], False)
    battle = skills.apply(DECOMP, {}, characters, [], {**PAGE, **{s.id: 2 for s in used}}, False)["src/bmbattle.c"]
    eff = battle[battle.index("void ComputeBattleUnitEffectiveStats("):]
    eff = eff[:eff.index("\n}\n")]
    assert "ComputeBattleUnitSpecialWeaponStats(attacker, defender);\n    if (!(gBattleStats.config" in eff
    assert "SkillTesterFem(&defender->unit, SKILL_FEM_Fortune)" in eff and "battleEffectiveHitRate = 100;" in eff
    assert "gBattleStats.damage = gBattleStats.damage * 4 / 3;" in battle and "*defense /= 2;" in battle
    assert "SkillTesterFem(&defender->unit, SKILL_FEM_DragonSkin)" in battle


def test_batch_7_order_of_the_rounds(monkeypatch):
    """Batch 7: C-SkillSys's round table, its doubling rules for both units, the forecast's x2 for each side."""
    if not (DECOMP / "src/bmbattle.c").is_file():
        pytest.skip("no decomp")
    monkeypatch.setattr(skills, "icon_png", lambda skill_id: b"\x89PNG")
    monkeypatch.setattr(skills, "box_png", lambda: b"\x89PNG")
    characters = [{"id": "CHARACTER_EIRIKA", "skills": ["RecklessFighter", "Dazzle", "LastWord", "DoubleLion"]},
                  {"id": "CHARACTER_SETH", "skills": ["Pursuer", "PassionsFlow"]}]
    used = skills.used(characters, [], False)
    files = skills.apply(DECOMP, {}, characters, [], {**PAGE, **{s.id: 2 for s in used}}, False)
    battle = files["src/bmbattle.c"]
    assert "{1, 1, 2, 2},\n    {2, 1, 1, 2}\n};" in battle and "config = sBattleUnwindFem[mask];" in battle
    assert "SkillTesterFem(&(a)->unit, SKILL_FEM_RecklessFighter) && a->hpInitial * 2 > a->unit.maxHP" in battle
    assert "SkillTesterFem(&(a)->unit, SKILL_FEM_LastWord) && CanFollowUpFem(a) && CanDoubleFem(t, a)" in battle
    assert "SkillTesterFem(&(a)->unit, SKILL_FEM_Pursuer)" in battle and "static int SupportedFem(" in battle
    assert "gBattleActor.unit.curHP--;" in battle and "gBattleTarget.canCounter = FALSE;\n    }\n\n    // Target" in battle
    assert "if (BattleDoublesFem(&gBattleActor)) {\n        *outAttacker" in battle
    assert "SKILL_FEM_Vantage" not in battle and "SKILL_FEM_GaleWings" not in battle
    forecast = files["src/bksel.c"]
    assert "if (BattleDoublesFem(&gBattleActor)) {" in forecast and "if (BattleDoublesFem(&gBattleTarget)) {" in forecast


def test_batch_8_statuses_survival_and_weapons(monkeypatch):
    """Inori / Sturdy on the damage, statuses and Armsthrift where the game consumes the attacker's weapon."""
    if not (DECOMP / "src/bmbattle.c").is_file():
        pytest.skip("no decomp")
    monkeypatch.setattr(skills, "icon_png", lambda skill_id: b"\x89PNG")
    monkeypatch.setattr(skills, "box_png", lambda: b"\x89PNG")
    characters = [{"id": "CHARACTER_EIRIKA", "skills": ["Sturdy", "Petrify", "Armsthrift"]},
                  {"id": "CHARACTER_SETH", "skills": ["PoisonPoint", "EffectSpore"]}]
    used = skills.used(characters, [], False)
    battle = skills.apply(DECOMP, {}, characters, [], {**PAGE, **{s.id: 2 for s in used}}, False)["src/bmbattle.c"]
    assert "ShowSkillFem(defender, SKILL_FEM_Sturdy);" in battle
    assert "status = UNIT_STATUS_PETRIFY;" in battle and "InjectStatusFem(attacker, spores[NextRN_N(3)], FALSE);" in battle
    # ticket 33: the status flashes the unit that got it in battle animations (Effect Spore: the hit's attacker)
    assert "InjectStatusFem(defender, status, TRUE);" in battle and "void StatusHitFem(" in battle
    utils = skills.apply(DECOMP, {}, characters, [], {**PAGE, **{s.id: 2 for s in used}}, False)["src/banim-ekrutils.c"]
    assert "StatusHitFem(anim, animr7); /* FE Maker: skills */" in utils
    assert battle.index("SKILL_FEM_Petrify") < battle.index("SKILL_FEM_PoisonPoint")      # C-SkillSys's order
    assert "&& !ApplyHitEffectSkillsFem(attacker, defender)) { /* FE Maker: skills (lot 8) */" in battle
    assert battle.index("static int ApplyHitEffectSkillsFem") < battle.index("void BattleGenerateHitEffects(")


def test_skill_numbers_header_spares_bmunit_h(monkeypatch):
    """Ticket 34: the skills' numbers live in skills_fem.h, included by the C files using them; bmunit.h, included almost
    everywhere, stays the same when a character gets another skill (no full rebuild)."""
    if not (DECOMP / "src/bmbattle.c").is_file():
        pytest.skip("no decomp")
    monkeypatch.setattr(skills, "icon_png", lambda skill_id: b"\x89PNG")
    monkeypatch.setattr(skills, "box_png", lambda: b"\x89PNG")

    def build(names):
        characters = [{"id": "CHARACTER_EIRIKA", "skills": names}]
        used = skills.used(characters, [], False)
        return skills.apply(DECOMP, {}, characters, [], {**PAGE, **{s.id: 2 for s in used}}, False)

    one, two = build(["Vantage"]), build(["Forager", "Vantage"])
    assert one["include/bmunit.h"] == two["include/bmunit.h"] and "SKILL_FEM_" not in one["include/bmunit.h"]
    assert one["include/skills_fem.h"] != two["include/skills_fem.h"]
    for rel, text in two.items():
        if rel.endswith(".c") and isinstance(text, str) and "SKILL_FEM_" in text:
            assert '#include "skills_fem.h"' in text, rel


def test_batch_9_auras_by_distance_and_side(monkeypatch):
    """An aura acts on the units on its side within its reach; the holder's own skills count the units around."""
    if not (DECOMP / "src/bmbattle.c").is_file():
        pytest.skip("no decomp")
    monkeypatch.setattr(skills, "icon_png", lambda skill_id: b"\x89PNG")
    monkeypatch.setattr(skills, "box_png", lambda: b"\x89PNG")
    characters = [{"id": "CHARACTER_EIRIKA", "skills": ["Charm", "Hex", "Peacebringer"]},
                  {"id": "CHARACTER_SETH", "skills": ["Tantivy"]}]
    used = skills.used(characters, [], False)
    battle = skills.apply(DECOMP, {}, characters, [], {**PAGE, **{s.id: 2 for s in used}}, False)["src/bmbattle.c"]
    aura = battle[battle.index("static void ApplyAuraSkillsFem"):battle.index("ApplyAuraSkillsFem(attacker, defender);")]
    allies, foes = aura.split("} else {")[0], aura.split("} else {")[1]
    assert "if (d <= 2 && SkillTesterFem(unit, SKILL_FEM_Charm))" in allies and "SKILL_FEM_Charm" not in foes
    assert "if (d <= 1 && SkillTesterFem(unit, SKILL_FEM_Hex))" in foes and "SKILL_FEM_Hex" not in allies
    assert "SKILL_FEM_Peacebringer" in allies and "SKILL_FEM_Peacebringer" in foes
    assert "if (SkillTesterFem(&attacker->unit, SKILL_FEM_Tantivy))\n        if (allies3 == 0) {" in aura
    wrath = [{"id": "CHARACTER_EIRIKA", "skills": ["Wrath"]}]
    texts = {**PAGE, **{s.id: 2 for s in skills.used(wrath, [], False)}}
    plain = skills.apply(DECOMP, {}, wrath, [], texts, False)["src/bmbattle.c"]
    assert "ApplyAuraSkillsFem" not in plain


def test_batch_9_heals_add_up_with_the_terrain(monkeypatch):
    if not (DECOMP / "src/bmtarget.c").is_file():
        pytest.skip("no decomp")
    monkeypatch.setattr(skills, "icon_png", lambda skill_id: b"\x89PNG")
    monkeypatch.setattr(skills, "box_png", lambda: b"\x89PNG")
    characters = [{"id": "CHARACTER_EIRIKA", "skills": ["Renewal", "Relief", "Amaterasu"]}]
    used = skills.used(characters, [], False)
    target = skills.apply(DECOMP, {}, characters, [], {**PAGE, **{s.id: 2 for s in used}}, False)["src/bmtarget.c"]
    assert "/ 100 + PrePhaseHealFem(unit);" in target
    heal = target[target.index("static int PrePhaseHealFem"):target.index("void MakeTerrainHealTargetList")]
    assert "ret += GetUnitMaxHp(unit) * (allies == 0 ? 20 : 0) / 100;" in heal
    assert "if (SkillTesterFem(other, SKILL_FEM_Amaterasu))" in heal and "SKILL_FEM_Forager" not in heal


def test_batch_9_shade_and_provoke_in_the_ai(monkeypatch):
    if not (DECOMP / "src/cp_battle.c").is_file():
        pytest.skip("no decomp")
    monkeypatch.setattr(skills, "icon_png", lambda skill_id: b"\x89PNG")
    monkeypatch.setattr(skills, "box_png", lambda: b"\x89PNG")
    characters = [{"id": "CHARACTER_EIRIKA", "skills": ["Shade", "Provoke"]}]
    used = skills.used(characters, [], False)
    ai = skills.apply(DECOMP, {}, characters, [], {**PAGE, **{s.id: 2 for s in used}}, False)["src/cp_battle.c"]
    assert "if (SkillTesterFem(unit, SKILL_FEM_Shade) && Roll1RN(unit->lck))" in ai and "ShadePlus" not in ai
    assert ai.index("SKILL_FEM_Shade)") < ai.index("if (!isEnemy(unit))")
    assert "if (SkillTesterFem(&gBattleTarget.unit, SKILL_FEM_Provoke))" in ai and '#include "rng.h"' in ai


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
    assert "ASMC(FemSkillEvent)\n    STAL(1)\n" in text and text.startswith("#ifdef SKILLS_FEM_EVENTS")   # the popup
    assert "SVAL(EVT_SLOT_3, 0)" in render_command({"op": "RemoveSkill", "args": ["CHARACTER_EIRIKA", "Luna"]})
    assert skills.event_skills([text]) == {"Luna"}
    assert "Luna" in [s.id for s in skills.used([], [], False, {"Luna"})]


def test_game_abilities_given_as_skills_join_the_class_attributes(monkeypatch):
    if not (DECOMP / "src/bmbattle.c").is_file():
        pytest.skip("no decomp")
    monkeypatch.setattr(skills, "icon_png", lambda skill_id: b"\x89PNG")
    monkeypatch.setattr(skills, "box_png", lambda: b"\x89PNG")
    assert {"id": "Canto", "kind": "map", "magic": False} in skills.catalogue()   # ticket 26: by what it does
    characters = [{"id": "CHARACTER_EIRIKA", "skills": ["Canto"], "learnedSkills": [{"skill": "Steal", "level": 5}]}]
    used = skills.used(characters, [], False)
    files = skills.apply(DECOMP, {}, characters, [], {**PAGE, **{s.id: 2 for s in used}}, False)
    assert "| SkillAttributesFem(aUnit))" in files["include/bmunit.h"]
    unit = files["src/bmunit.c"]
    assert "if (SkillTesterFem(unit, SKILL_FEM_Canto))\n        attributes |= CA_CANTO;" in unit
    assert "attributes |= CA_STEAL;" in unit and "CA_THIEF" not in unit.split("int SkillAttributesFem")[1]
    # without any, the game's macro stays
    plain = [{"id": "CHARACTER_EIRIKA", "skills": ["Luna"]}]
    files = skills.apply(DECOMP, {}, plain, [], {**PAGE, **{s.id: 2 for s in skills.used(plain, [], False)}}, False)
    assert "SkillAttributesFem" not in files["include/bmunit.h"]
    assert "src/bmmenu.c" not in files or "SKILL_FEM_LockTouch" not in files["src/bmmenu.c"]
    # ticket 28: Lock Touch also gives the Rogue's Pick command (doors and chests without keys)
    picker = [{"id": "CHARACTER_EIRIKA", "skills": ["LockTouch"]}]
    files = skills.apply(DECOMP, {}, picker, [], {**PAGE, **{s.id: 2 for s in skills.used(picker, [], False)}}, False)
    assert "!= CLASS_ROGUE && !SkillTesterFem(gActiveUnit, SKILL_FEM_LockTouch))" in files["src/bmmenu.c"]


def test_odd_icons_get_the_common_frame(tmp_path, monkeypatch):
    """Ticket 31: the stat bonuses' square frame replaced by the common one, stray corner pixels cleared, the inside
    kept; Last Word's empty icon is the "?"."""
    from PIL import Image

    monkeypatch.setattr(skills, "_cache", lambda: tmp_path / "SkillIcon")
    for name, fill in (("StrBonus", 6), ("FaireSword", 4)):
        image = Image.new("P", (16, 16), fill)
        image.putpalette([c for rgb in skills.ICON_PALETTE for c in rgb])
        image.save(tmp_path / f"{name}.png", bits=4)
    frame = Image.open(skills._retouched("StrBonus", tmp_path / "StrBonus.png")).load()
    assert [frame[x, 0] for x in range(16)] == [int(c, 16) for c in skills.STANDARD_FRAME[0]]
    assert frame[0, 0] == 0 and frame[15, 15] == 0 and frame[7, 7] == 6
    corners = Image.open(skills._retouched("FaireSword", tmp_path / "FaireSword.png")).load()
    assert corners[0, 0] == 0 and corners[1, 0] == 4 and corners[7, 7] == 4
    assert skills.BY_ID["LastWord"].icon == ""


def test_a_malus_with_the_growth_rates(monkeypatch):
    """Ticket 50: with the growth rates on the status screen (ticket 166), the bar's call is there twice; the malus goes
    in the stats' path, after the growths' branch."""
    if not (DECOMP / "src/statscreen.c").is_file():
        pytest.skip("no decomp")
    from fe_maker.decomp import gameoptions
    monkeypatch.setattr(skills, "icon_png", lambda skill_id: b"\x89PNG")
    monkeypatch.setattr(skills, "box_png", lambda: b"\x89PNG")
    characters = [{"id": "CHARACTER_EIRIKA", "skills": ["FortressDef"]}]
    used = skills.used(characters, [], False)
    files = gameoptions.apply(DECOMP, {"statusGrowths": True}, {})
    files = skills.apply(DECOMP, files, characters, [], {**PAGE, **{s.id: 2 for s in used}}, False)
    screen = files["src/statscreen.c"]
    start = screen.index("void DrawStatWithBar(int num")
    assert screen.index("if (growth >= 0)", start) < screen.index("if (diff < 0)", start)


def test_drain_hp_bars_at_a_plain_hits_pace():
    """Ticket 44: Sol's drain shows Nosferatu's HP bars, from a copy of their script waiting 0x1E frames, not 0x54."""
    from fe_maker.decomp import battlenumbers

    if not (DECOMP / "src/banim-efxhpbar.c").is_file():
        pytest.skip("decomp submodule not checked out")
    characters = [{"id": "CHARACTER_SETH", "skills": ["Sol"]}]
    used = skills.used(characters, [], False)
    texts = {**PAGE, **{s.id: 2 for s in used}}
    files = skills.apply(DECOMP, {}, characters, [], texts, False)
    assert "NewEfxHpBarDrainFem(animr5);" in files["src/banim-ekrutils.c"]
    bar = files["src/banim-efxhpbar.c"]
    copy = bar[bar.index("static const struct ProcCmd ProcScr_EfxHpBarDrainFem[]"):]
    assert "PROC_REPEAT(EfxHpBarDrainWaitFem)," in copy and "EfxHpBarResire_WaitOnCurrentSide" not in copy
    assert "proc->timer2 == 0x1E && proc->finished == true" in bar
    # with the battle numbers option, the copy keeps their step
    numbered = skills.apply(DECOMP, battlenumbers.apply(DECOMP, {}), characters, [], texts, False)["src/banim-efxhpbar.c"]
    copy = numbered[numbered.index("static const struct ProcCmd ProcScr_EfxHpBarDrainFem[]"):]
    assert "PROC_REPEAT(EfxHpBarResireNumberFem)," in copy
