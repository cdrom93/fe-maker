"""Test domains: every test belongs to one, so a change runs only the tests of its domain (`pytest -m maps`).

Server tests take the domain of their file; playtests (tests/local/test_playtest.py) are listed by name. A test in no
domain stops the run: add it below. Domains are registered in pytest.ini; how to run them: docs/architecture.md.
"""

import pytest

FILES = {
    "data": ["test_gamedata", "test_classes_combat", "test_item_sheet", "test_convoy", "test_reservations",
             "test_supports", "test_strmag", "test_weaponrange", "test_reach"],
    "skills": ["test_skills"],
    "maps": ["test_maps_units", "test_map_objects", "test_map_changes", "test_autotile", "test_tiled", "test_tileedit",
             "test_pieces"],
    "events": ["test_events", "test_dialogues", "test_story", "test_triggers", "test_objectives", "test_chapterflags",
               "test_blank"],
    "media": ["test_assets", "test_banim", "test_danceanim", "test_mapsprites", "test_portraits", "test_portraitcolors",
              "test_charpalettes", "test_chaptitle", "test_music", "test_songasm"],
    "options": ["test_gameoptions", "test_tweaks"],
    "build": ["test_project", "test_builderrors", "test_migrations",
              "test_build_lock", "test_buildcancel", "test_buildtimes", "test_native",
              "test_ups", "test_release", "test_playtest", "test_rom_build"],
    "app": ["test_validation", "test_update", "test_emulator", "test_folderpick", "test_tickets", "test_missions",
            "test_githubauth", "test_locales", "test_main",
            "test_ferepo"],
}

PLAYTESTS = {
    "data": ["edited_character_is_on_the_prologue_map", "ally_level_comes_from_the_sheet", "item_sheet_reaches_the_game",
             "added_characters_on_the_prologue_map", "added_weapon_in_seth_inventory", "added_class_moves_on_the_map",
             "enemies_keep_their_dropped_item_and_average_stats", "a_copied_vulnerary_heals_in_game",
             "copies_heal_and_protect_their_own_amount", "weapon_sheet_in_a_battle", "magic_split_from_strength",
             "a_range_the_game_does_not_list_is_drawn_and_shown"],
    "skills": ["an_event_gives_a_skill_with_its_popup", "skills_in_battle_and_on_the_status_screen",
               "batch_5_passives_in_battle", "batch_6_hit_crit_and_damage", "batch_7_order_of_the_rounds",
               "batch_8_status_sturdy_and_armsthrift", "batch_9_auras_in_battle", "batch_10_mangs_list_first_part",
               "batch_10_after_combat", "batch_10_seals", "batch_9_heals_at_the_start_of_the_turn",
               "batch_9_shade_plus_is_never_targeted", "learned_skill_counts_in_battle", "skill_learned_at_a_level_up",
               "experience_skills", "batch_10_counter", "batch_10_savage_blow", "batch_10_pass", "batch_10_rally_and_smite",
               "batch_10_resolve",
               "game_ability_given_as_a_skill", "canto_plus_moves_after_a_battle", "pivot_command",
               "reposition_shove_and_swap_commands", "renewal_and_galeforce_on_the_map",
               "galeforce_flash_after_a_battle_animation", "vantage_and_desperation_change_the_order_of_attacks",
               "luna_and_sol_trigger_on_each_hit", "adept_and_astra_add_hits", "triggered_skill_name_in_battle_animation",
               "effect_spore_status_flashes_the_attacker_in_battle_animation", "sol_heal_shows_in_battle_animation",
               "triggered_skill_icon_in_map_battle", "renewal_for_an_enemy_steal_and_canto_given",
               "dance_and_supply_given_as_skills"],
    "maps": ["painted_door_chest_village_and_convoy_in_game", "enemy_destroys_a_painted_village", "fog_of_war",
             "original_village_follows_a_moved_map", "weather_battle_background_and_camera_in_game"],
    "events": ["changed_next_chapter_in_game", "other_character_seizes", "world_map_ending_in_test_builds",
               "chapter_one_straight_to_chapter_two", "condition_in_the_prologue_opening", "added_chapter",
               "blank_project_starts_on_its_empty_chapter", "a_three_chapter_hack_from_a_blank_project_to_the_end",
               "a_scene_moved_to_another_turn_builds_and_plays", "a_removed_scene_builds_and_plays",
               "an_event_changes_a_units_stats", "a_condition_gives_an_item_to_a_living_character",
               "event_commands_change_weather_hp_side_and_ai", "screen_tint_counters_and_leaving_the_party"],
    "media": ["imported_battle_animation", "sound_command_of_an_imported_animation", "character_colours_in_battle",
              "class_generic_portrait_reaches_the_game", "portrait_colours_in_battle", "imported_map_sprite",
              "imported_music_in_the_prologue", "map_music_comes_back_after_a_battle", "a_players_theme_and_the_sound_room",
              "imported_music_in_a_scene", "imported_music_on_the_title_screen",
              "sixteen_tracks_and_twelve_notes", "imported_music_with_general_midi_instruments",
              "song_written_in_the_games_music_assembly",
              "full_drum_kit",
              "added_chapter_title_picture", "an_imported_icon_is_in_the_game",
              "a_priest_given_the_dance_dances_without_breaking_the_game"],
    "options": ["game_options", "stationary_enemy_shows_no_movement_range",
                "the_comfort_switches_build_and_the_game_starts", "the_added_line_of_the_options_menu_is_whole",
                "hp_bars_under_wounded_units", "casual_mode_brings_a_fallen_unit_back", "select_shows_the_danger_zone",
                "hp_bars_hide_under_a_portrait", "talk_bubble_is_vision_quests",
                "heal_preview_battle_speed_and_fallen_items", "level_up_screen_with_l_held",
                "damage_and_heal_numbers_in_battle_animation", "test_this_chapter", "test_chapter_one_army"],
    "build": ["a_project_keeps_only_what_is_chosen"],
}

BY_FILE = {name: domain for domain, names in FILES.items() for name in names}
BY_PLAYTEST = {"test_" + name: domain for domain, names in PLAYTESTS.items() for name in names}


def pytest_collection_modifyitems(config, items):
    lost = []
    for item in items:
        module = item.path.stem
        domain = BY_PLAYTEST.get(item.originalname) if item.path.parent.name == "local" and module == "test_playtest" \
            else BY_FILE.get(module)
        if domain:
            item.add_marker(getattr(pytest.mark, domain))
        else:
            lost.append(item.nodeid)
    if lost:
        raise pytest.UsageError("Tests in no domain (add them to tests/conftest.py): " + ", ".join(lost))
