import copy
import json

from fe_maker.decomp import assets
from fe_maker.decomp.combat import parse_effectiveness, parse_promotions, parse_triangle
from fe_maker.decomp.gamedata import DecompData
from fe_maker.project import Project
from fe_maker.validation import validate


def test_classes_export(decomp_dir):
    lord = DecompData(decomp_dir).export_classes()[0]
    assert lord["id"] == "CLASS_TESTLORD"
    assert lord["bases"]["hp"] == 10
    assert lord["mov"] == 5
    assert lord["promotions"] == ["CLASS_TESTKNIGHT"]
    assert lord["movement"] == "CommonT1"
    assert lord["terrainBonus"] == "Common"
    assert lord["abilities"] == ["lord"]


def test_a_class_generic_portrait_is_written_only_when_it_changes(decomp_dir):
    d = DecompData(decomp_dir)
    classes = d.export_classes()
    assert classes[0]["genericPortrait"] == 0
    del classes[1]["genericPortrait"]                     # a class added by an older project
    classes[0]["genericPortrait"] = 0x7F
    d.apply_classes(classes)
    assert ".defaultPortraitId = 127," in "".join(d.changed_files().values())


def test_class_cards_are_the_rows_without_a_face(tmp_path):
    table = tmp_path / assets.PORTRAIT_TABLE
    table.parent.mkdir(parents=True)
    table.write_text("{\n{portrait_Eirika_tileset, 0},\n{0, 0, portrait_Soldier_palette, 0, portrait_Soldier_card, 0},\n")
    assert assets.card_names(tmp_path) == {2: "Soldier"}
    assert assets.card_preview(tmp_path, 2) is None        # its picture is not there
    assert assets.card_preview(tmp_path, 1) is None


def test_full_round_trip_changes_nothing(decomp_dir):
    d = DecompData(decomp_dir)
    d.apply_classes(copy.deepcopy(d.export_classes()))
    characters = d.export_characters()
    characters[0]["customColors"] = {"CLASS_PALADIN": [["#000000"] * 16] * 5}   # kept aside, never built (ticket 126)
    d.apply_characters(characters)
    d.apply_items(d.export_items())
    d.apply_combat(d.export_combat())
    assert d.changed_files() == {}


def test_edit_class(decomp_dir):
    d = DecompData(decomp_dir)
    classes = d.export_classes()
    lord = classes[0]
    lord["maxes"]["hp"] = 80
    lord["mov"] = 7
    lord["movement"] = "Fly"
    lord["terrainBonus"] = "Fly"
    lord["promotions"] = ["CLASS_TESTKNIGHT", "CLASS_TESTUNUSED"]
    d.apply_classes(classes)
    files = d.changed_files()
    src = files["src/data_classes.c"]
    assert ".maxHP = 80," in src
    assert ".baseMov = 7," in src
    assert "TerrainTable_MovCost_FlyNormal, TerrainTable_MovCost_FlyRain, TerrainTable_MovCost_FlySnow," in src
    assert ".pTerrainDefenseLookup = TerrainTable_Def_Fly," in src
    promos = parse_promotions(files["src/classchg-data.c"])
    assert promos["CLASS_TESTLORD"] == ["CLASS_TESTKNIGHT", "CLASS_TESTUNUSED"]
    assert promos["CLASS_TESTKNIGHT"] == ["CLASS_TESTLORD"]
    assert "gSomethingElse" in files["src/classchg-data.c"]


def test_combat_tables(decomp_dir):
    d = DecompData(decomp_dir)
    combat = d.export_combat()
    assert combat["triangle"][0] == {"attacker": "sword", "defender": "axe", "hit": 10, "damage": 2}
    assert combat["effectiveness"]["ItemEffectiveness_TestKnights"] == ["CLASS_TESTKNIGHT"]
    combat["triangle"][0]["hit"] = 20
    combat["effectiveness"]["ItemEffectiveness_TestKnights"].append("CLASS_TESTLORD")
    d.apply_combat(combat)
    files = d.changed_files()
    assert parse_triangle(files["src/bmbattle.c"])[0]["hit"] == 20
    assert "SomeEngineCode" in files["src/bmbattle.c"]
    eff = parse_effectiveness(files["src/data_itemuse.c"])
    assert eff["ItemEffectiveness_TestKnights"] == ["CLASS_TESTKNIGHT", "CLASS_TESTLORD"]
    assert eff["ItemEffectiveness_TestEveryone"] == ["CLASS_TESTLORD", "CLASS_TESTKNIGHT"]


def test_item_effectiveness(decomp_dir):
    d = DecompData(decomp_dir)
    items = d.export_items()
    assert items[0]["effectiveness"] == "ItemEffectiveness_TestKnights"
    items[0]["effectiveness"] = "ItemEffectiveness_TestEveryone"
    d.apply_items(items)
    assert ".pEffectiveness = ItemEffectiveness_TestEveryone," in d.changed_files()["src/data_items.c"]
    d = DecompData(decomp_dir)
    items[0]["effectiveness"] = None
    d.apply_items(items)
    assert ".pEffectiveness = NULL," in d.changed_files()["src/data_items.c"]


def test_class_validation(decomp_dir):
    d = DecompData(decomp_dir)
    classes = d.export_classes()
    classes[0]["mov"] = 30
    classes[0]["promotions"] = ["CLASS_A", "CLASS_B", "CLASS_C"]
    classes[0]["weaponRanks"]["lance"] = "C"  # the lord class only animates swords
    codes = {(p.id, p.field, p.code) for p in validate([], [], d, classes=classes, combat=d.export_combat())}
    assert ("CLASS_TESTLORD", "mov", "outOfRange") in codes
    assert ("CLASS_TESTLORD", "promotions", "tooManyPromotions") in codes
    assert ("CLASS_TESTLORD", "weaponRanks.lance", "noBattleAnimation") in codes


def test_old_project_gets_new_data_files(tmp_path, decomp_dir):
    root = tmp_path / "old"
    project = Project.create(root, "Old", decomp_dir=decomp_dir)
    (root / "data" / "classes.json").unlink()
    (root / "data" / "combat.json").unlink()
    project = Project(root, decomp_dir)
    assert project.load("classes")[0]["id"] == "CLASS_TESTLORD"
    assert "triangle" in project.load("combat")
    assert json.loads((root / "data" / "classes.json").read_text(encoding="utf-8"))
