from pathlib import Path

import pytest

from fe_maker.decomp import strmag

DECOMP = Path(__file__).parents[2] / "decomp"
MAGE = {"id": "CLASS_MAGE", "weaponRanks": {"anima": "D"}, "bases": {"pow": 1}, "growths": {"pow": 55},
        "maxes": {"pow": 20}, "promotionGains": {"pow": 2}}
FIGHTER = {"id": "CLASS_FIGHTER", "weaponRanks": {"axe": "D"}, "bases": {"pow": 5}, "growths": {"pow": 50},
           "maxes": {"pow": 20}, "promotionGains": {"pow": 1}}


def test_a_class_with_magic_takes_its_strength_figures_others_start_at_zero():
    assert strmag.class_magic(MAGE) == (1, 55, 20, 2)
    assert strmag.class_magic(FIGHTER) == (0, strmag.NON_MAGIC_GROWTH, 20, 0)
    assert strmag.class_magic({**FIGHTER, "bases": {"pow": 5, "mag": 3}}) == (3, strmag.NON_MAGIC_GROWTH, 20, 0)
    classes = {c["id"]: c for c in (MAGE, FIGHTER)}
    assert strmag.character_magic({"class": "CLASS_MAGE", "bases": {"pow": 2}, "growths": {"pow": 40}}, classes) == (2, 40)
    assert strmag.character_magic({"class": "CLASS_FIGHTER", "bases": {"pow": 2}, "growths": {"pow": 40}}, classes) == (0, 10)


def test_one_row_per_entry_a_named_record_wins():
    rows = strmag._rows([{"id": "0x1b"}, {"id": "CHARACTER_NEW_1B"}, {"id": "CHARACTER_A"}], {"CHARACTER_A": 2},
                        "CHARACTER_NEW_", lambda record: (-1, 5))
    assert rows == "    [0x02] = { 255, 5 },\n    [0x1B] = { 255, 5 },\n"


def test_the_split_matches_the_decomp():
    if not (DECOMP / "src/bmunit.c").is_file():
        pytest.skip("no decomp")
    files = strmag.apply(DECOMP, {}, [{"id": "CHARACTER_EIRIKA", "class": "CLASS_EIRIKA_LORD"}],
                         [{"id": "CLASS_EIRIKA_LORD", "weaponRanks": {"sword": "D"}}])
    assert "BATTLE_ATTACK_STAT_FEM(attacker)" in files["src/bmbattle.c"]
    assert files["src/bmbattle.c"].count("ApplyPromotionMagicFem(unit, promotedClass->number);") == 2
    assert "[0x01] = { 0, " in files["src/bmunit.c"] and "WriteMagicFem(slot, UNIT_SAVE_AMOUNT_BLUE);" in files["src/bmsave.c"]
    assert "sym_iwram.txt" not in files   # no temporary bonuses: their spare bytes stay
