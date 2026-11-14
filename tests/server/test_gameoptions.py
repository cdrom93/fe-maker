from pathlib import Path

import pytest

from fe_maker.decomp import gameoptions
from fe_maker.decomp.tweaks import TweakError

# Fictional excerpt in the shape of the decomp's InitPlayConfig (src/bmio.c).
SOURCE = """void InitPlayConfig(int isDifficult, s8 unk) {
    gPlaySt.config.animationType = 0;
    gPlaySt.config.autoCursor = 0;
    gPlaySt.config.textSpeed = 1; // a comment
    gPlaySt.config.gameSpeed = 0;
}

void Other(void) {
    gPlaySt.config.textSpeed = 1;
}
"""


def test_new_game_defaults_only_in_init_play_config():
    out = gameoptions.with_defaults(SOURCE, {"textSpeed": 2, "autoCursor": 1})
    assert "gPlaySt.config.textSpeed = 2; // a comment" in out and "gPlaySt.config.autoCursor = 1;" in out
    assert out.endswith("void Other(void) {\n    gPlaySt.config.textSpeed = 1;\n}\n")   # other functions untouched
    with pytest.raises(TweakError):
        gameoptions.with_defaults("void Something(void) {}", {"textSpeed": 2})


def test_options_are_checked():
    assert gameoptions.validate({"textSpeed": 3, "skipOpening": True}) is None
    assert gameoptions.validate({"textSpeed": 9}) == "badGameOption"
    assert gameoptions.validate({"skipOpening": 1}) == "badGameOption"
    assert gameoptions.validate({"somethingElse": True}) == "unknownGameOption"


def test_no_option_no_file(tmp_path):
    assert gameoptions.apply(tmp_path, {}, {}) == {}
    assert gameoptions.apply(tmp_path, {"textSpeed": 1}, {}) == {}   # the game's own default


def test_the_goal_display_is_added_to_init_play_config():
    # InitPlayConfig does not set it: the cleared state leaves it at 0
    out = gameoptions.with_defaults(SOURCE, {"objective": 1})
    assert "    gPlaySt.config.gameSpeed = 0;\n    gPlaySt.config.disableGoalDisplay = 1;\n}\n\nvoid Other" in out


def test_new_switches_are_known_and_stop_on_a_changed_decomp(tmp_path):
    assert gameoptions.validate({"quickExpBar": True, "quickLevelUp": True, "noSupportAnimations": True}) is None
    (tmp_path / "src").mkdir()
    (tmp_path / gameoptions.EXP_BAR_FILE).write_text("nothing here")
    with pytest.raises(TweakError):
        gameoptions.apply(tmp_path, {"quickExpBar": True}, {})


def test_the_story_intro_goes_with_the_world_map_tale_but_not_the_lord():
    root = Path(__file__).parents[2] / "decomp"
    if not (root / gameoptions.WORLD_MAP_INTRO_FILE).is_file():
        pytest.skip("no decomp")
    text = gameoptions.apply(root, {"skipStoryIntro": True}, {})[gameoptions.WORLD_MAP_INTRO_FILE]
    assert "WM_TEXT(0x08DB, 0)" not in text and "WM_SPAWNLORD(WM_MU_0, CHARACTER_EIRIKA" in text
    assert "EventScrWM_Prologue_ChapterIntro" in text


def test_every_switch_has_one_group():
    assert len(gameoptions.SWITCHES) == len(set(gameoptions.SWITCHES)) == 24


def test_a_unit_acts_after_a_talk():
    source = Path(__file__).parents[2] / "decomp" / gameoptions.RANGE_DISPLAY_FILE
    if not source.is_file():
        pytest.skip("no decomp")
    text = gameoptions.apply(source.parents[1], {"actAfterTalk": True}, {})[gameoptions.RANGE_DISPLAY_FILE]
    assert "PROC_CALL_2(FemAfterTalk)" in text and "gBmSt.taken_action |= 16;" in text


def test_the_danger_zone_is_written_with_the_other_range_option():
    source = (Path(__file__).parents[2] / "decomp" / gameoptions.RANGE_DISPLAY_FILE)
    if not source.exists():
        pytest.skip("no decomp")
    files = gameoptions.apply(source.parents[1], {"dangerZone": True, "stationaryRange": True}, {})
    text = files[gameoptions.RANGE_DISPLAY_FILE]
    assert "Select shows the enemies' range" in text and "movement AI 3" in text
    assert "if (gActiveUnit && (gActiveUnit->state & US_HAS_MOVED))" in text


def test_bars_and_bubble_tiles_wait_for_the_end_of_a_battle_animation():
    """Ticket 161: a battle quote's talk reloads the object UI graphics while the right fighter's sheet sits on the
    bars' and bubble's tiles."""
    source = Path(__file__).parents[2] / "decomp" / gameoptions.MAP_UI_FILE
    if not source.is_file():
        pytest.skip("no decomp")
    text = gameoptions.apply(source.parents[1], {"hpBars": True, "talkBubbles": True}, {})[gameoptions.MAP_UI_FILE]
    assert text.count("if (IsBattleDeamonActive())\n        return;") == 2


def test_enemy_warnings_with_the_bars_and_the_bubble():
    """FEBuilder's HP bar warnings: a "!" on the enemies (white: an effective weapon or a Slayer, orange: more than 24
    crit), on their own tiles after the bubble's, with the bars and the bubble in the same files."""
    root = Path(__file__).parents[2] / "decomp"
    if not (root / gameoptions.MAP_SPRITES_FILE).is_file():
        pytest.skip("no decomp")
    files = gameoptions.apply(root, {"hpBars": True, "talkBubbles": True, "enemyWarnings": True}, {})
    sprites = files[gameoptions.MAP_SPRITES_FILE]
    assert "FemPutHpBar(unit);" in sprites and "FemPutBubble(unit);" in sprites and "FemPutWarning(unit);" in sprites
    assert "IsItemEffectiveAgainst(item, gActiveUnit)" in sprites and "GetItemCrit(item) > 24" in sprites
    assert files[gameoptions.MAP_UI_FILE].count("if (IsBattleDeamonActive())\n        return;") == 3
    assert gameoptions._warning_tiles().startswith("    { 0x00544300, ")   # row "00344500", left pixel low
    assert "enemyWarnings" in gameoptions.SWITCH_GROUPS["map"]


def test_growths_on_the_status_screen_colour_the_stat_names():
    """Ticket 166: Select shows the growths; each name takes its growth's colour (two palettes loaded with the screen)."""
    root = Path(__file__).parents[2] / "decomp"
    if not (root / gameoptions.STATUS_FILE).is_file():
        pytest.skip("no decomp")
    text = gameoptions.apply(root, {"statusGrowths": True}, {})[gameoptions.STATUS_FILE]
    assert "ApplyPalettes(sGrowthColorsFem[0], STATSCREEN_BGPAL_GROWTHS_FEM, 2);" in text
    assert text.index("ColorStatLabelsFem();") < text.index("// displaying mov stat value")
    assert "PutGrowthLabelFem(STATSCREEN_TEXT_BWL, y, MSG_4E9, 9);" in text


def test_battle_numbers_hook_the_hp_bars(monkeypatch):
    """Ticket 169: C-SkillSys's AnimNumber on the HP bar's flash (damage), efxHPBarLive (heal) and efxHPBarResire
    (drain); its image downloaded, never in the repository."""
    from fe_maker.decomp import battlenumbers

    root = Path(__file__).parents[2] / "decomp"
    if not (root / battlenumbers.HPBAR_FILE).is_file():
        pytest.skip("no decomp")
    monkeypatch.setattr(battlenumbers, "image_png", lambda: b"\x89PNG")
    files = gameoptions.apply(root, {"battleNumbers": True}, {})
    bar = files[battlenumbers.HPBAR_FILE]
    assert "    PROC_REPEAT(EfxHpBarResire_SetAnotherSide),\n    PROC_REPEAT(EfxHpBarResireNumberFem),\n" in bar
    assert "    PROC_CALL(EfxHpBarLiveNumberFem),\n" in bar and "AnimSprite_AnimNumberFem15[]" in bar
    assert "NewEfxAnimNumberFem(anim, -gBattleHitArray[anim->nextRoundId - 1].hpChange);" in files[battlenumbers.FLASH_FILE]
    assert '.incbin "graphics/banim/anim_number_fem.4bpp"' in files[battlenumbers.DATA_FILE]
    assert files[battlenumbers.IMAGE] == b"\x89PNG"


def test_dead_items_heal_preview_and_battle_speed():
    """Tickets 8, 6 and 7: a fallen unit's items to the convoy (not with casual mode), the staff's healing shown in the
    target's window, L held runs the battle animation's update twice."""
    root = Path(__file__).parents[2] / "decomp"
    if not (root / gameoptions.UNIT_FILE).is_file():
        pytest.skip("no decomp")
    files = gameoptions.apply(root, {"deadItemsToConvoy": True, "healPreview": True, "holdLBattleSpeed": True}, {})
    unit = files[gameoptions.UNIT_FILE]
    assert '#include "bmcontainer.h"\n' in unit and "AddItemToConvoy(unit->items[i]);" in unit
    assert "RefreshUnitHealPreviewWindowFem(GetUnit(target->uid));" in files[gameoptions.HEAL_SELECT_FILE]
    assert "gActiveUnit->items[gActionData.itemSlotIndex]" in files[gameoptions.INFO_WINDOW_FILE]
    assert "heldKeys & L_BUTTON" in files[gameoptions.BATTLE_ANIM_FILE]
    casual = gameoptions.apply(root, {"deadItemsToConvoy": True, "casualMode": True}, {})
    assert "AddItemToConvoy" not in casual[gameoptions.UNIT_FILE]


def test_music_tracks_option():
    decomp = Path(__file__).parents[2] / "decomp"
    if not (decomp / gameoptions.SOUND_FILE).is_file():
        pytest.skip("no decomp")
    files = gameoptions.apply(decomp, {"musicTracks": True}, {})
    players, sound = files[gameoptions.MUSIC_PLAYERS_FILE], files[gameoptions.SOUND_FILE]
    assert "music_player gMPlayInfo_BGM1, 0x02027000, 16, 0" in players
    assert "music_player gMPlayInfo_BGM2, 0x02027500, 16, 0" in players
    assert ".space TRACK_SIZE * NUM_TRACKS_BGM1" in players   # the IWRAM space stays, nothing else moves
    assert "Sound_SetMaxNumChannels(12); /* FE Maker: 12 notes */" in sound and "Sound_SetMaxNumChannels(7)" not in sound
    assert gameoptions.MUSIC_PLAYERS_FILE not in gameoptions.apply(decomp, {}, {})


def test_monster_weapons_show_their_stats():
    """FEBuilder's "Monster Weapon display fix" (Brendor) in C: the type's name, the item panel, the R help box."""
    root = Path(__file__).parents[2] / "decomp"
    if not (root / gameoptions.ITEM_PANEL_FILE).is_file():
        pytest.skip("no decomp")
    files = gameoptions.apply(root, {"monsterWeaponStats": True}, {})
    assert "if (wpnType == ITYPE_MONSTER)\n        return GetStringFromIndex(0x26B);" in files[gameoptions.ITEM_FILE]
    assert "case ITYPE_MONSTER:" not in files[gameoptions.ITEM_PANEL_FILE]
    assert "&& GetItemType(item) != ITYPE_MONSTER)" in files[gameoptions.STATUS_FILE]
    assert "monsterWeaponStats" in gameoptions.SWITCH_GROUPS["screens"]
