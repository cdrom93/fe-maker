from fe_maker.decomp import supports as sp
from fe_maker.decomp.gamedata import DecompData
from fe_maker.validation import validate

# Fictional support lists written for the tests.
SOURCE = """#include "global.h"

CONST_DATA struct SupportData SupportData_A = {
    .characters = {
        CHARACTER_B,
        CHARACTER_C,
    },
    .supportExpBase = {
        30,
        10,
    },
    .supportExpGrowth = {
        4,
        2,
    },
    .supportCount = 2,
};

CONST_DATA struct SupportData SupportData_B = {
    .characters = {
        CHARACTER_A,
    },
    .supportExpBase = {
        30,
    },
    .supportExpGrowth = {
        4,
    },
    .supportCount = 1,
};
"""


def test_read_and_write_back():
    blocks = sp.read_blocks(SOURCE)
    assert blocks["SupportData_A"] == [("CHARACTER_B", 30, 4), ("CHARACTER_C", 10, 2)]
    assert sp.write_blocks(SOURCE, blocks) == SOURCE
    owners = {"SupportData_A": "CHARACTER_A", "SupportData_B": "CHARACTER_B"}
    assert sp.pairs_of(blocks, owners) == [{"a": "CHARACTER_A", "b": "CHARACTER_B", "base": 30, "growth": 4},
                                           {"a": "CHARACTER_A", "b": "CHARACTER_C", "base": 10, "growth": 2}]


def test_partners_keep_their_order():
    original = {"CHARACTER_A": [("CHARACTER_B", 30, 4), ("CHARACTER_C", 10, 2)]}
    pairs = [{"a": "CHARACTER_D", "b": "CHARACTER_A", "base": 5, "growth": 1},
             {"a": "CHARACTER_C", "b": "CHARACTER_A", "base": 12, "growth": 2}]
    out = sp.partners_by_character(pairs, original)
    # B left; C kept in its place with its new points; D added after.
    assert out["CHARACTER_A"] == [("CHARACTER_C", 12, 2), ("CHARACTER_D", 5, 1)]
    assert out["CHARACTER_D"] == [("CHARACTER_A", 5, 1)]


def test_turns_to_levels():
    assert sp.turns_to(1, 30, 4) == 13      # 50 points to the C conversation at 4 a turn
    assert sp.turns_to(3, 30, 4) == 52      # 240 - 30, minus one point from each conversation seen
    assert sp.turns_to(1, 80, 0) == 0 and sp.skipped_levels(80) == [] and sp.skipped_levels(161) == [1, 2]
    assert sp.turns_to(1, 90, 0) == 0
    assert sp.turns_to(2, 90, 0) is None


def test_new_pair_reaches_the_overlay(decomp_dir):
    d = DecompData(decomp_dir)
    assert d.original_supports() == []
    unchanged = DecompData(decomp_dir)
    unchanged.apply_dialogues({"messages": {}, "quotes": [], "supports": []})
    assert unchanged.changed_files() == {}
    steps = [{"kind": "face", "pos": "MidLeft", "face": "FID_Eirika"},
             {"kind": "say", "pos": "MidLeft", "text": "Hi.", "wait": True}]
    pair = {"a": "CHARACTER_TESTHERO", "b": "CHARACTER_TESTRIVAL", "base": 20, "growth": 3}
    talk_b = {"kind": "support", "a": "CHARACTER_TESTRIVAL", "b": "CHARACTER_TESTHERO", "rank": 2, "steps": steps}
    d.apply_dialogues({"messages": {}, "supports": [pair], "quotes": [talk_b]})
    files = d.changed_files()
    # The test hero points to a support list already (its block is written); the rival gets a new one.
    assert "SupportData_TestHero = {" in files["src/data_supports.c"]
    assert "SupportData_FEM_TESTRIVAL = {" in files["src/data_supports.c"]
    assert ".pSupportData = &SupportData_FEM_TESTRIVAL" in files["src/data_characters.c"]
    extern = "extern CONST_DATA struct SupportData SupportData_FEM_TESTRIVAL;"
    assert f'#include "bmreliance.h"\n{extern}' in files["src/data_characters.c"]
    talk = next(line for line in files["src/data_event_trigger.c"].splitlines() if "CHARACTER_TESTHERO" in line)
    assert talk.strip().startswith("{ CHARACTER_TESTHERO, CHARACTER_TESTRIVAL, 0x0000, 0x") and "0x0000, }," in talk


def test_support_problems(decomp_dir):
    d = DecompData(decomp_dir)
    chars = d.export_characters()
    pairs = [{"a": "CHARACTER_TESTHERO", "b": "CHARACTER_TESTRIVAL", "base": 300, "growth": 0},
             {"a": "CHARACTER_TESTRIVAL", "b": "CHARACTER_TESTHERO", "base": 10, "growth": 2},
             {"a": "CHARACTER_TESTHERO", "b": "CHARACTER_NOBODY", "base": 10, "growth": 2}]
    data = {"messages": {}, "quotes": [], "supports": pairs}
    codes = {(p.id, p.code) for p in validate(chars, d.export_items(), d, dialogues=data)}
    rid = "support:CHARACTER_TESTHERO:CHARACTER_TESTRIVAL"
    assert (rid, "outOfRange") in codes and (rid, "supportNoTalk") in codes and (rid, "supportSkipsTalk") in codes
    assert ("support:CHARACTER_TESTRIVAL:CHARACTER_TESTHERO", "supportSkipsTalk") not in codes
    assert ("support:CHARACTER_TESTRIVAL:CHARACTER_TESTHERO", "supportDuplicate") in codes
    assert ("support:CHARACTER_TESTHERO:CHARACTER_NOBODY", "unknownCharacter") in codes
