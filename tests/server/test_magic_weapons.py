"""Magic weapons: the game's lists by item number, the rules, and the ranged mode built for an animation that has none."""
from fe_maker.decomp import banim, gameoptions, magicweapons

BATTLE = """void SetBattleUnitWeapon(struct BattleUnit* bu, int itemSlot) {
        if (bu->weaponAttributes & IA_MAGICDAMAGE) {
            switch (GetItemIndex(bu->weapon)) {

            case ITEM_SWORD_RUNESWORD:
                bu->weaponType = ITYPE_DARK;
                break;

            } // switch (GetItemIndex(bu->weapon))
        } // if (bu->weaponAttributes & IA_MAGICDAMAGE)
}
    if (GetItemIndex(gBattleActor.weapon) == ITEM_SWORD_RUNESWORD) {
        gBattleActor.battleAttack -= gBattleActor.unit.pow / 2;

        gBattleActor.battleCritRate = 0;
        gBattleActor.battleEffectiveCritRate = 0;
    }
    if (GetItemAttributes(defender->weapon) & IA_MAGICDAMAGE)
        switch (GetItemIndex(attacker->weapon)) {

        case ITEM_SWORD_LIGHTBRAND:
        case ITEM_SWORD_RUNESWORD:
        case ITEM_SWORD_WINDSWORD:
            attacker->battleAttack -= attacker->unit.pow / 2;

            attacker->battleCritRate = 0;
            attacker->battleEffectiveCritRate = 0;

            break;
        }
    if (bu->weaponAttributes & (IA_MAGICDAMAGE | IA_LOCK_3))
    result = bu->unit.ranks[bu->weaponType];
        if (i == bu->weaponType)
    int oldWexp = bu->unit.ranks[bu->weaponType];
        unit->ranks[bu->weaponType] = tmp;
        unit->ranks[bu->weaponType] = wexp;
"""


def weapons():
    return {"ITEM_AXE_BOLT": ("range", "ITYPE_ANIMA"), "ITEM_LANCE_DARK": ("always", None)}


def test_each_weapon_gets_its_case_in_the_game_list():
    text = magicweapons.battle_with(BATTLE, weapons())
    assert ("case ITEM_AXE_BOLT:\n                if (gBattleStats.range >= 2)\n"
            "                    bu->weaponType = ITYPE_ANIMA;\n                else\n"
            "                    bu->weaponAttributes = bu->weaponAttributes &~ IA_MAGICDAMAGE;\n") in text
    assert "case ITEM_LANCE_DARK:\n                break;\n" in text and "RUNESWORD" not in text


def test_the_rules_of_the_game_reach_every_weapon():
    text = magicweapons.battle_with(BATTLE, weapons())
    assert "if (GetItemIndex(gBattleActor.weapon) == ITEM_LANCE_DARK) {" in text
    assert "        case ITEM_AXE_BOLT:\n        case ITEM_LANCE_DARK:\n            attacker->battleAttack" in text


def test_without_a_weapon_always_magic_the_ui_test_is_false():
    assert "if (FALSE) {" in magicweapons.battle_with(BATTLE, {"ITEM_AXE_BOLT": ("range", None)})


def test_a_weapon_always_magic_plays_its_ranged_animation_up_close():
    text = magicweapons.parse_with(magicweapons._FORCE_RANGED, weapons())
    assert text.count("ITEM_LANCE_DARK") == 2 and "ITEM_AXE_BOLT" not in text and "RUNESWORD" not in text


def apply_rules(tmp_path, *keys):
    source = tmp_path / gameoptions.BATTLE_FILE
    source.parent.mkdir(exist_ok=True)
    source.write_text(BATTLE, encoding="utf-8")
    return gameoptions.apply(tmp_path, {key: True for key in keys}, {})[gameoptions.BATTLE_FILE]


def test_full_force_rule(tmp_path):
    assert "unit.pow / 2" not in apply_rules(tmp_path, "magicFullForce")


def test_criticals_rule(tmp_path):
    assert "CritRate" not in apply_rules(tmp_path, "magicCriticals")


def test_rank_points_go_to_the_weapons_own_type(tmp_path):
    text = apply_rules(tmp_path, "magicRankPoints")
    assert "if (bu->weaponAttributes & IA_LOCK_3)" in text and "ranks[bu->weaponType]" not in text
    assert "result = bu->unit.ranks[GetItemType(bu->weaponBefore)];" in text


def test_defense_up_close_rule(tmp_path):
    assert "if (defender->weaponAttributes & IA_MAGICDAMAGE)\n" in apply_rules(tmp_path, "magicMeleeDefense")


def script(frames):
    return "".join(f"\tbanim_code_frame {d}, x_sheet_0, {n}, x_oam_frame_{n}_r - x_oam_r\n" for n, d in frames)


def test_a_ranged_mode_is_built_from_the_wind_up(tmp_path):
    text = ("x_oam_frame_0_r:\n\tbanim_frame_oam 0x0, 0x0, 0x0, 0, 0\n"
            "x_oam_frame_1_r:\n\tbanim_frame_oam 0x0, 0x0, 0x0, 4, 0\n"
            "x_oam_frame_2_r:\n\tbanim_frame_oam 0x0, 0x0, 0x0, 60, 0\n"
            "x_mode_attack_close:\n\tbanim_code_start_attack_1\n\tbanim_code_start_attack_2\n"
            + script([(0, 1), (1, 5), (2, 9)])
            + "\tbanim_code_prepare_hp_deplete\n\tbanim_code_hit_normal\n\tbanim_code_end_mode\n"
            "x_mode_attack_range:\n\tbanim_code_start_attack_1\n\tbanim_code_start_attack_2\n"
            + script([(0, 1)]) + "\tbanim_code_end_mode\n")
    folder = tmp_path / banim.MOTION_DIR
    folder.mkdir(parents=True)
    (folder / "x_motion.s").write_text(text, encoding="utf-8")
    banim.motion.cache_clear()
    new = magicweapons.motion_with_spell(tmp_path, "x", text)
    banim.motion.cache_clear()
    ranged = new.split("x_mode_attack_range:\n")[1]
    assert "x_oam_frame_2_r" not in ranged                      # the leap toward the enemy stays out
    assert ranged.index("x_oam_frame_1_r") < ranged.index("banim_code_call_spell_anim") < ranged.index("wait_hp_deplete")
    assert ranged.rstrip().endswith("banim_code_end_dodge\n\tbanim_code_end_mode") and "hit_normal" not in ranged
    assert new.split("x_mode_attack_range:")[0] == text.split("x_mode_attack_range:")[0]


def test_a_mode_that_already_casts_stays(tmp_path):
    text = ("x_mode_attack_close:\n" + script([(0, 1)]) + "\tbanim_code_end_mode\n"
            "x_mode_attack_range:\n\tbanim_code_call_spell_anim\n\tbanim_code_end_mode\n")
    (tmp_path / banim.MOTION_DIR).mkdir(parents=True)
    (tmp_path / banim.MOTION_DIR / "x_motion.s").write_text(text, encoding="utf-8")
    banim.motion.cache_clear()
    assert magicweapons.motion_with_spell(tmp_path, "x", text) == text
    banim.motion.cache_clear()
