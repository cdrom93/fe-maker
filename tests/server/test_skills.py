from pathlib import Path

import pytest

from fe_maker.decomp import skills

DECOMP = Path(__file__).parents[2] / "decomp"


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
    assert numbers == {"label": 100, "Wrath": 101}
    assert data.bodies == ("Skills", "Wrath:[LF]\nIf current HP is < 50%[LF]\nof max, +20 Crit Rate.")


def test_skills_match_the_decomp(monkeypatch):
    if not (DECOMP / "src/bmunit.c").is_file():
        pytest.skip("no decomp")
    monkeypatch.setattr(skills, "icon_png", lambda skill_id: b"\x89PNG")
    characters = [{"id": "CHARACTER_EIRIKA", "skills": ["StrBonus", "Vantage", "DefiantSpd"]}]
    classes = [{"id": "CLASS_EIRIKA_LORD", "skills": ["BlowDarting"]}]
    used = skills.used(characters, classes, False)
    texts = {"label": 1, **{s.id: 2 + k for k, s in enumerate(used)}}
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
