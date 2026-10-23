from fe_maker.decomp import mapobjects as mo
from fe_maker.decomp.texts import TextFile

# Fictional terrains for the tests: metatile -> terrain id.
PLAINS, FLOOR, VILLAGE, CLOSED, CHEST, EMPTY, DOOR, WALL, CRACKED = 0, 1, 2, 3, 4, 5, 6, 7, 8
TERRAIN = bytes([0x01, 0x17, 0x03, 0x04, 0x21, 0x20, 0x1E, 0x1A, 0x1B])


def _grid(w, h, m=PLAINS):
    return [[m] * w for _ in range(h)]


def test_detect_objects():
    rows = _grid(6, 5, FLOOR)
    rows[0][0] = CHEST
    rows[1][2] = rows[1][3] = rows[2][2] = DOOR   # one door of three cells
    rows[2][5] = rows[3][5] = CRACKED              # stacked cracked walls: one obstacle
    rows[4][0] = VILLAGE
    found = {(o["kind"], o["x"], o["y"]): o["cells"] for o in mo.detect(rows, TERRAIN)}
    assert found == {
        ("chest", 0, 0): [[0, 0]],
        ("door", 2, 1): [[2, 1], [3, 1], [2, 2]],
        ("wall", 5, 2): [[5, 2], [5, 3]],
        ("village", 0, 4): [[0, 4]],
    }


def _rule():
    # A cracked wall change from a fictional original map: the wall becomes floor and the wall
    # above it loses its shadow (metatile 7 -> 1 is not an object cell, it comes with the template).
    template = {"kind": "wall", "shape": frozenset({(0, 0)}), "first": (0, 1),
                "before": ((WALL,), (CRACKED,)), "after": ((FLOOR,), (FLOOR,)), "uses": 3}
    return {"templates": [template], "tiles": {CHEST: EMPTY, VILLAGE: CLOSED, CRACKED: FLOOR},
            "terrain": TERRAIN, "pixels": [bytes([m]) * 256 for m in range(len(TERRAIN))]}


def test_after_change_uses_original_templates_then_tiles():
    rows = _grid(5, 5, FLOOR)
    rows[1][1], rows[2][1] = WALL, CRACKED
    rows[3][3] = CHEST
    wall, chest = sorted(mo.detect(rows, TERRAIN), key=lambda o: o["kind"], reverse=True)
    assert mo.after_change(wall, rows, _rule()) == {"x": 1, "y": 1, "w": 1, "h": 2, "rows": [[FLOOR], [FLOOR]]}
    assert mo.after_change(chest, rows, _rule()) == {"x": 3, "y": 3, "w": 1, "h": 1, "rows": [[EMPTY]]}


def test_after_change_guesses_unknown_tiles():
    rule = {**_rule(), "tiles": {}, "templates": []}
    rows = _grid(3, 3, FLOOR)
    rows[1][1] = DOOR
    door = mo.detect(rows, TERRAIN)[0]
    assert mo.after_change(door, rows, rule)["rows"] == [[FLOOR]]  # the floor next to it
    rows[1][1] = CHEST
    chest = mo.detect(rows, TERRAIN)[0]
    assert mo.after_change(chest, rows, rule)["rows"] == [[EMPTY]]  # the tile of the empty chest terrain


def test_change_must_use_the_object():
    village = {"kind": "village", "x": 1, "y": 1, "cells": [[1, 1]]}
    ruins = {"id": 0, "x": 0, "y": 0, "w": 3, "h": 3, "rows": _grid(3, 3, PLAINS)}  # brigands: no "closed" state
    closing = {"id": 1, "x": 1, "y": 1, "w": 1, "h": 1, "rows": [[CLOSED]]}
    assert mo._covered(village, [ruins], TERRAIN) is None
    assert mo._covered(village, [ruins, closing], TERRAIN) == 1


def test_read_location_events():
    body = """
    Village(EVFLAG_TMP(9),  EventScr_Ch2_Village1, 4, 2)
    House(0x0, EventScr_Ch1_Loca_Visit1, 13, 6)
    Chest(ITEM_LANCE_IRON,    6, 3)
    ChestMoney(3000, 10, 3)
    Door(12, 17, EVFLAG_TMP(17))
    Door_(1, 2)
    Armory(ShopList_Event_Ch2Armory, 5, 7)
    END_MAIN
"""
    events = mo.read_location_events(body)
    assert [(e["kind"], e["x"], e["y"]) for e in events] == [
        ("village", 4, 2), ("house", 13, 6), ("chest", 6, 3), ("chest", 10, 3), ("door", 12, 17), ("door", 1, 2)]
    assert events[0]["script"] == "EventScr_Ch2_Village1"
    assert events[2]["item"] == "ITEM_LANCE_IRON" and events[3]["gold"] == 3000
    s, e = events[2]["span"]
    assert body[s:e].strip() == "Chest(ITEM_LANCE_IRON,    6, 3)"


def test_dialogue_message_pads_text_runs():
    body = mo.dialogue_message("FID_VillagerWoman", "Hello there.\nTake it.")
    assert body == ("[OpenMidLeft][LoadFace][FID_VillagerWoman]\n[OpenMidLeft]Hello there.[LF]\n"
                    "Take it.[A][X]")
    long = mo.dialogue_message("FID_VillagerWoman", "word " * 30)
    lines = [line for line in long.split("\n")[1:]]
    assert all(len(line.replace("[OpenMidLeft]", "").split("[")[0]) <= mo.LINE_WIDTH for line in lines)
    assert long.count("[A]") == 3  # 5 lines, two per box


def test_village_script():
    script = mo.village_script("EventScr_Test", 0xD4C, "ITEM_ELIXIR", None)
    assert "Text_BG(0x2, 0xD4C)" in script and "SVAL(EVT_SLOT_3, ITEM_ELIXIR)" in script
    money = mo.village_script("EventScr_Test", 0xD4C, None, 500)
    assert "GIVEITEMTOMAIN(CHAR_EVT_PLAYER_LEADER)" in money
    house = mo.village_script("EventScr_Test", 0xD4C, None, None, house=True)
    assert "Text_BG(0x0, 0xD4C)" in house and "GIVE" not in house


def test_new_messages_are_appended():
    texts = TextFile("#0x0\n[X]\n\n## MSG_001\nHi[X]\n")
    index = texts.add("New[X]")
    assert index == 2 and texts.raw(2) == "New[X]"
    assert texts.render().endswith("## MSG_001\nHi[X]\n\n## MSG_002\nNew[X]\n\n")
