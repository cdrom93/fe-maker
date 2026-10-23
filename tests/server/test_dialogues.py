from fe_maker.decomp import dialogues as dl

# Fictional conversation written for the tests, in the game's message format.
RAW = ("[OpenRight][LoadFace][FID_Seth][ToggleSmile]\n"
       "[OpenRight]We ride at dawn,[LF]\nmy lady.[A][LF]\nStay close.[.][A]\n"
       "[OpenFarLeft][LoadFace][FID_Eirika]\n"
       "[OpenFarLeft]I will[ToggleMouthMove]...[ToggleMouthMove][A]\n"
       "[OpenFarLeft][CloseEyes]\n"
       "[OpenRight][MoveMidRight]\n"
       "[OpenFarLeft][ClearFace]\n"
       "[CloseSpeechSlow][X]")


def test_parse_steps():
    steps = dl.parse(RAW)
    assert steps[0] == {"kind": "face", "pos": "Right", "face": "FID_Seth"}
    assert steps[1] == {"kind": "code", "code": "ToggleSmile", "pos": "Right"}
    assert steps[2] == {"kind": "say", "pos": "Right", "text": "We ride at dawn,\nmy lady.\n\nStay close.", "wait": True,
                        "open": True}
    assert steps[4]["text"] == "I will[ToggleMouthMove]...[ToggleMouthMove]"
    assert steps[5] == {"kind": "code", "code": "CloseEyes", "pos": "FarLeft", "open": True}
    assert steps[6] == {"kind": "move", "pos": "Right", "to": "MidRight"}
    assert steps[7] == {"kind": "clear", "pos": "FarLeft"}
    assert steps[8]["code"] == "CloseSpeechSlow"


def test_round_trip_and_padding():
    out = dl.render(dl.parse(RAW))
    assert dl.same_message(RAW, out)
    # Odd runs are padded: "my lady." is 8 bytes, "Stay close." 11 -> padded.
    assert "Stay close.[.][A]" in out and "my lady.[A]" in out


def test_new_dialogue():
    steps = [{"kind": "face", "pos": "MidLeft", "face": "FID_Eirika"},
             {"kind": "say", "pos": "MidLeft", "text": "Hello.\nI am here.\n\nLet us go!", "wait": True}]
    assert dl.render(steps) == ("[OpenMidLeft][LoadFace][FID_Eirika]\n"
                                "[OpenMidLeft]Hello.[LF]\nI am here.[A][LF]\nLet us go![A][X]")


def test_empty_line_is_not_a_new_box():
    steps = dl.parse("[OpenLeft]A list:[LF][LF]one[A][X]")
    assert steps[0]["text"] == "A list:\n[LF]one"
    assert dl.same_message(dl.render(steps), "[OpenLeft]A list:[LF][LF]one[A][X]")


def test_script_messages_and_triggers():
    source = ("CONST_DATA EventListScr EventScr_A[] = {\n    Text(0x900)\n    Text_BG(BG_HOUSE, 0x901)\n    ENDA\n};\n"
              "CONST_DATA EventListScr EventScr_B[] = {\n    TEXTSHOW(0x902)\n    ENDA\n};\n")
    assert dl.script_messages(source) == [("EventScr_A", [0x900, 0x901]), ("EventScr_B", [0x902])]
    group = {"beginningSceneEvents": "EventScr_A", "characterBasedEvents": "Talks"}
    lists = {"Talks": "    CHAR(EVFLAG_TMP(7), EventScr_B, CHARACTER_EIRIKA, CHARACTER_SETH)\n    END_MAIN\n"}
    assert dl.scene_triggers(group, lists, {"EventScr_A", "EventScr_B"}) == {
        "EventScr_A": {"kind": "beginning"}, "EventScr_B": {"kind": "talk", "a": "CHARACTER_EIRIKA", "b": "CHARACTER_SETH"}}


def test_faces():
    assert dl.read_faces("[FID_Active] = 0xFF, 0xFF\n[FID_Eirika] = 0x02, 0x01\n") == {"FID_Eirika": 2}
