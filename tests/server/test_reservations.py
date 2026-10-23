import pytest

from fe_maker.decomp.gamedata import DecompData, GameDataError


def _item(d, items, item_id):
    return next(i for i in items if i["id"] == item_id)


def test_reservation_is_read_from_locks(decomp_dir):
    d = DecompData(decomp_dir)
    blade = _item(d, d.export_items(), "ITEM_TESTBLADE")
    # TESTBLADE has IA_LOCK_4, which only the lord class has.
    assert blade["reservedFor"] == {"characters": [], "classes": ["CLASS_TESTLORD"]}
    assert blade["monsterWeapon"] is False


def test_abilities_hide_generic_locks(decomp_dir):
    lord = DecompData(decomp_dir).export_classes()[0]
    assert lord["abilities"] == ["lord"]  # CA_LOCK_4 is managed through reservations


def test_new_reservation_gets_a_free_lock(decomp_dir):
    d = DecompData(decomp_dir)
    items = d.export_items()
    _item(d, items, "ITEM_TESTBLADE")["reservedFor"] = {"characters": ["CHARACTER_TESTRIVAL"], "classes": ["CLASS_TESTKNIGHT"]}
    d.apply_items(items)
    files = d.changed_files()
    assert ".attributes = IA_WEAPON | IA_LOCK_7," in files["src/data_items.c"]
    assert "CA_LOCK_7" in files["src/data_classes.c"].split("[CLASS_TESTKNIGHT - 1]")[1]
    assert "CA_LOCK_7" not in files["src/data_classes.c"].split("[CLASS_TESTKNIGHT - 1]")[0]
    rival = files["src/data_characters.c"].split("[CHARACTER_TESTRIVAL - 1]")[1]
    assert ".attributes = CA_LOCK_7," in rival


def test_reserved_to_nobody_and_unrestricted(decomp_dir):
    d = DecompData(decomp_dir)
    items = d.export_items()
    _item(d, items, "ITEM_TESTBLADE")["reservedFor"] = None
    d.apply_items(items)
    assert ".attributes = IA_WEAPON," in d.changed_files()["src/data_items.c"]


def test_same_group_reuses_the_original_lock(decomp_dir):
    d = DecompData(decomp_dir)
    items = d.export_items()
    blade = _item(d, items, "ITEM_TESTBLADE")
    blade["reservedFor"] = {"characters": [], "classes": ["CLASS_TESTLORD"]}  # unchanged
    blade["might"] = 4
    d.apply_items(items)
    assert "IA_LOCK_4" in d.changed_files()["src/data_items.c"]


def test_too_many_groups(decomp_dir, monkeypatch):
    import fe_maker.decomp.gamedata as gd

    monkeypatch.setattr(gd, "LOCK_PREFERENCE", [])  # no free lock left
    d = DecompData(decomp_dir)
    items = d.export_items()
    _item(d, items, "ITEM_TESTBLADE")["reservedFor"] = {"characters": ["CHARACTER_TESTRIVAL"], "classes": []}
    with pytest.raises(GameDataError):
        d.apply_items(items)


def test_monster_weapon_flag(decomp_dir):
    d = DecompData(decomp_dir)
    items = d.export_items()
    _item(d, items, "ITEM_TESTBLADE")["monsterWeapon"] = True
    d.apply_items(items)
    assert "IA_LOCK_3" in d.changed_files()["src/data_items.c"]


def test_empty_reservation_means_unrestricted(decomp_dir):
    d = DecompData(decomp_dir)
    items = d.export_items()
    _item(d, items, "ITEM_TESTBLADE")["reservedFor"] = {"characters": [], "classes": []}
    d.apply_items(items)
    entry = d.changed_files()["src/data_items.c"].split("[ITEM_TESTBLADE] = {")[1].split("}")[0]
    assert ".attributes = IA_WEAPON," in entry
