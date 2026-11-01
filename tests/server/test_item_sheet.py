"""The item sheet: properties, weapon effect, rank points, stat bonuses, spell, use text, and what a type brings."""
import json
import shutil

import pytest

from fe_maker.project import Project

from fe_maker.decomp.gamedata import ITEMS_FILE, SPELL_ASSOC_FILE, DecompData, _read_item_bonuses

SPELLS = """#define SPELL_ASSOC_DATA_WPN_DEFAULT(_item) SPELL_ASSOC_DATA_WPN(_item, -1)
CONST_DATA struct SpellAssoc gSpellAssocData[] = {
    SPELL_ASSOC_DATA_WPN_DEFAULT(ITEM_TESTBLADE),
    SPELL_ASSOC_DATA_WPN_MAGIC(ITEM_TESTFIRE, 0x16, SPELL_ASSOC_MCOLOR_FIRE),
    SPELL_ASSOC_DATA_WPN_DEFAULT(0xFFFF),
};
"""


@pytest.fixture
def game(decomp_dir, tmp_path):
    copy = tmp_path / "decomp"
    shutil.copytree(decomp_dir, copy)
    (copy / SPELL_ASSOC_FILE).write_bytes(SPELLS.encode("utf-8"))
    return DecompData(copy)


def blade(records):
    return next(r for r in records if r["id"] == "ITEM_TESTBLADE")


def changed_items(game, change):
    items = game.export_items()
    change(blade(items))
    game.apply_items(items)
    return game.changed_files()


def test_new_fields_change_nothing_by_themselves(game):
    record = blade(game.export_items())
    assert (record["properties"], record["weaponEffect"], record["weaponExp"], record["statBonuses"]) == ([], None, 0, None)
    game.apply_items(game.export_items())
    assert game.changed_files() == {}


def test_a_type_brings_what_the_engine_asks_of_it(game):
    text = changed_items(game, lambda r: r.update(weaponType="staff"))[ITEMS_FILE]
    assert "IA_STAFF | IA_LOCK_4" not in text and "IA_LOCK_4 | IA_STAFF" in text and "IA_WEAPON" not in text


def test_a_type_without_use_drops_the_flags(game):
    text = changed_items(game, lambda r: r.update(weaponType="item"))[ITEMS_FILE]
    assert ".attributes = IA_LOCK_4," in text


def test_properties_are_flags(game):
    text = changed_items(game, lambda r: r.update(properties=["brave", "unbreakable"]))[ITEMS_FILE]
    assert ".attributes = IA_WEAPON | IA_LOCK_4 | IA_UNBREAKABLE | IA_BRAVE," in text


def test_effect_and_rank_points(game):
    text = changed_items(game, lambda r: r.update(weaponEffect="poison", weaponExp=3))[ITEMS_FILE]
    assert ".weaponEffectId = WPN_EFFECT_POISON," in text and ".weaponExp = 3," in text


def test_stat_bonuses_are_written_above_the_table(game):
    text = changed_items(game, lambda r: r.update(statBonuses={"spd": 5, "lck": -2}))[ITEMS_FILE]
    assert "ItemStatBonuses ItemBonus_FEM_ITEM_TESTBLADE = {\n\t.spdBonus = 5,\n\t.lckBonus = -2,\n};" in text
    assert ".pStatBonuses = &ItemBonus_FEM_ITEM_TESTBLADE," in text
    assert text.index("ItemBonus_FEM_ITEM_TESTBLADE = {") < text.index("gItemData[]")


def test_the_games_bonuses_are_read():
    assert _read_item_bonuses("struct ItemStatBonuses ItemBonus_Ivaldi = {\n\t.powBonus = 3,\n\t.lckBonus  = -1,\n};") == {
        "ItemBonus_Ivaldi": {"pow": 3, "lck": -1}}


def test_a_spell_replaces_the_row_of_the_item(game):
    text = changed_items(game, lambda r: r.update(spellFrom="ITEM_TESTFIRE"))[SPELL_ASSOC_FILE]
    assert "SPELL_ASSOC_DATA_WPN_MAGIC(ITEM_TESTBLADE, 0x16, SPELL_ASSOC_MCOLOR_FIRE)," in text
    assert "SPELL_ASSOC_DATA_WPN_DEFAULT(ITEM_TESTBLADE)" not in text
    assert text.rstrip().endswith("SPELL_ASSOC_DATA_WPN_DEFAULT(0xFFFF),\n};")


def test_spell_items_leave_out_the_default_rows(game):
    assert game.spell_items() == ["ITEM_TESTFIRE"]


def test_a_use_text_shared_with_another_item_gets_its_own_message(game):
    first, second = game.items.entries[1], game.items.entries[0]
    first.original_fields["useDescTextId"] = first.fields["useDescTextId"] = second.fields["useDescTextId"] = hex(4)
    second.original_fields["useDescTextId"] = hex(4)
    before = game.texts.raw(4)
    items = game.export_items()
    blade(items)["useDescription"] = "Soigne un peu."
    game.apply_items(items)
    assert game.texts.raw(4) == before and first.fields["useDescTextId"] != hex(4)


def test_a_weapon_added_by_an_older_version_takes_the_new_fields_of_its_model(decomp_dir, tmp_path):
    project = Project.create(tmp_path / "older", "Older", decomp_dir=decomp_dir)
    path = project.root / "data" / "items.json"
    items = json.loads(path.read_text(encoding="utf-8"))
    added = {k: v for k, v in blade(items).items() if k not in ("properties", "weaponEffect", "weaponExp", "statBonuses")}
    items.append({**added, "id": "ITEM_NEW_CE", "model": "ITEM_TESTBLADE"})
    path.write_text(json.dumps(items), encoding="utf-8")
    assert next(i for i in project.load("items") if i["id"] == "ITEM_NEW_CE")["properties"] == []
    assert "properties" in json.loads(path.read_text(encoding="utf-8"))[-1]     # kept: the game is read only once
