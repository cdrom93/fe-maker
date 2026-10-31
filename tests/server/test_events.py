from fe_maker.decomp import events as ev
from fe_maker.decomp.gamedata import DecompData
from fe_maker.validation import validate

# Fictional script written for the tests, in the game's event format.
BODY = """
    MUSC(SONG_TENSION)

    LOAD1(1, UnitDef_Test)
    ENUN
    /* a comment */
    Text_BG(BG_GRASS_PLAINS, 0x929)
    MOVE(0, CHARACTER_TEST, 2,
         3)
    NoFade
    ENDA
"""


def test_parse_and_render():
    cmds = ev.parse_script(BODY)
    assert cmds[0] == {"op": "MUSC", "args": ["SONG_TENSION"]}
    assert cmds[1] == {"op": ""}                              # the blank line
    assert cmds[3] == {"op": "ENUN"}
    assert cmds[4] == {"op": "#", "text": "/* a comment */"}
    assert cmds[6] == {"op": "MOVE", "args": ["0", "CHARACTER_TEST", "2", "3"]}
    again = ev.parse_script(ev.render_script(cmds))
    assert again == cmds and ev.same_commands(cmds, again)
    assert "    MOVE(0, CHARACTER_TEST, 2, 3)\n" in ev.render_script(cmds)


def test_validate_command():
    assert ev.validate_command({"op": "MUSC", "args": ["SONG_TENSION"]}) is None
    assert ev.validate_command({"op": "MUSC", "args": []}) == "badArguments"
    assert ev.validate_command({"op": "ENUN", "args": ["1"]}) == "badArguments"
    assert ev.validate_command({"op": "MUSC", "args": ["X); ENDA("]}) == "badArguments"
    assert ev.validate_command({"op": "not a macro"}) == "badCommand"
    assert ev.validate_command({"op": "SomethingElse", "args": ["1"]}) is None   # kept as it is


def test_read_constants():
    header = "enum {\n    SONG_NONE = 0x00,\n    SONG_ATTACK\t= 0x19,\n};\n"
    assert ev.read_constants(header, "SONG_") == ["SONG_NONE", "SONG_ATTACK"]


def test_edited_script_reaches_the_overlay(decomp_dir):
    d = DecompData(decomp_dir)
    original = d.script_commands("EventScr_TestOpening")
    d.apply_dialogues({"messages": {}, "quotes": [], "scripts": {"EventScr_TestOpening": original}})
    assert d.changed_files() == {}          # unchanged: nothing written
    edited = [{"op": "MUSC", "args": ["SONG_ATTACK"]}, *original]
    d.apply_dialogues({"messages": {}, "quotes": [], "scripts": {"EventScr_TestOpening": edited}})
    files = d.changed_files()
    (rel, source), = files.items()
    assert rel.endswith("test-eventinfo.h") and "    MUSC(SONG_ATTACK)\n" in source
    assert DecompData(decomp_dir).script_commands("EventScr_TestShared") == d.script_commands("EventScr_TestShared")


def test_script_problems(decomp_dir):
    d = DecompData(decomp_dir)
    scripts = {"EventScr_Nowhere": [], "EventScr_TestOpening": [{"op": "Text", "args": ["0x7777"]}, {"op": "MUSC"}]}
    codes = {(p.id, p.code) for p in validate(d.export_characters(), d.export_items(), d,
                                               dialogues={"messages": {}, "quotes": [], "scripts": scripts})}
    assert ("script:EventScr_Nowhere", "unknownScript") in codes
    assert ("script:EventScr_TestOpening#0", "unknownMessage") in codes
    assert ("script:EventScr_TestOpening#1", "badArguments") in codes


def test_new_scene_message_and_unknown_names(decomp_dir):
    d = DecompData(decomp_dir)
    say = [{"kind": "say", "pos": None, "text": "A new line."}]
    quotes = [{"kind": "scene", "key": "s1", "chapter": 0, "a": "", "steps": say}]
    scripts = {"EventScr_TestOpening": [{"op": "Text", "args": ["new:s1"]}, {"op": "LOAD1", "args": ["1", "UnitDef_Nope"]},
                                        {"op": "Text", "args": ["new:gone"]}, {"op": "ENDA"}]}
    codes = {(p.id, p.code) for p in validate(d.export_characters(), d.export_items(), d,
                                               dialogues={"messages": {}, "quotes": quotes, "scripts": scripts})}
    assert ("script:EventScr_TestOpening#0", "unknownMessage") not in codes
    assert ("script:EventScr_TestOpening#1", "unknownName") in codes
    assert ("script:EventScr_TestOpening#2", "lostMessage") in codes
    assert not any(c == "quoteWithoutCharacter" for _id, c in codes)
    # At build time, "new:s1" becomes the id of the new message
    scripts["EventScr_TestOpening"] = scripts["EventScr_TestOpening"][:1] + [{"op": "ENDA"}]
    d.apply_dialogues({"messages": {}, "quotes": quotes, "scripts": scripts})
    import re
    files = "".join(s for s in d.changed_files().values() if isinstance(s, str))
    new_id = int(re.search(r"Text\((0x[0-9A-F]+)\)", files).group(1), 16)
    assert "A new line." in files and new_id not in DecompData(decomp_dir).texts.messages


def test_conditions_and_jumps():
    ok = [{"op": "CHECK_ALIVE", "args": ["CHARACTER_TEST"]}, {"op": "BEQ", "args": ["0x1", "EVT_SLOT_C", "EVT_SLOT_0"]},
          {"op": "SVAL", "args": ["EVT_SLOT_1", "5"]}, {"op": "BLT", "args": ["2", "EVT_SLOT_C", "0x1"]},
          {"op": "GOTO", "args": ["0x1"]}, {"op": "LABEL", "args": ["0x1"]}, {"op": "CALL", "args": ["EventScr_Test"]},
          {"op": "CHECK_TURNS"}]
    assert [ev.validate_command(c) for c in ok] == [None] * len(ok)
    assert ev.validate_command({"op": "BEQ", "args": ["0x1", "EVT_SLOT_E", "EVT_SLOT_0"]}) == "badArguments"   # no slot E
    assert ev.validate_command({"op": "LABEL", "args": ["start"]}) == "badArguments"   # labels are numbers
    assert ev.validate_command({"op": "CALL", "args": ["Two words"]}) == "badArguments"
    assert ev.parse_script(ev.render_script(ok)) == ok
