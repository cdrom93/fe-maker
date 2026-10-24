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


def test_new_quotes():
    from fe_maker.decomp import quotes

    constants = {"CHAPTER_L_2": 2}
    source = ("CONST_DATA struct BattleTalkExtEnt gBattleTalkList[] = {\n    {\n        .pidA = CHARACTER_BONE,\n"
              "        .chapter = CHAPTER_L_2,\n        .flag = EVFLAG_BATTLE_QUOTES,\n        .msg = 0x0960,\n    },\n"
              "    {\n        .pidA = 0xffff,\n        .chapter = 0x00,\n        .msg = 0x0000,\n    },\n};\n\n"
              "CONST_DATA struct DefeatTalkEnt gDefeatTalkList[] = {\n    {\n        .pid = CHARACTER_BONE,\n"
              "        .route = CHAPTER_MODE_ANY,\n        .chapter = CHAPTER_L_2,\n        .flag = EVFLAG_DEFEAT_BOSS,\n"
              "        .msg = 0x0000,\n    },\n    {\n        .pid = 0xFFFF,\n    },\n};\n")
    found = quotes.read_quotes(source, constants)
    assert found["battle"] == [{"a": "CHARACTER_BONE", "b": "", "chapter": 2, "flag": "EVFLAG_BATTLE_QUOTES", "msg": 0x960}]
    source = quotes.add_battle_quote(source, constants, 2, "CHARACTER_ROSS", "CHARACTER_BONE", 0xD4C, 50)
    source = quotes.add_death_quote(source, constants, 2, "CHARACTER_BONE", 0xD4D)   # the boss entry gets words
    source = quotes.add_death_quote(source, constants, 255, "CHARACTER_ROSS", 0xD4E)
    found = quotes.read_quotes(source, constants)
    assert [(q["a"], q["b"], q["msg"]) for q in found["battle"]][1:] == [
        ("CHARACTER_ROSS", "CHARACTER_BONE", 0xD4C), ("CHARACTER_BONE", "CHARACTER_ROSS", 0xD4C)]
    assert [(q["a"], q["chapter"], q["msg"], q["flag"]) for q in found["death"]] == [
        ("CHARACTER_BONE", 2, 0xD4D, "EVFLAG_DEFEAT_BOSS"), ("CHARACTER_ROSS", 255, 0xD4E, "0")]
    # Ross must survive chapter 2: a chapter entry before his every-chapter one, with his words.
    source = quotes.set_death_flag(source, constants, 2, "CHARACTER_ROSS", "EVFLAG_GAMEOVER")
    found = quotes.read_quotes(source, constants)
    assert (found["death"][0]["a"], found["death"][0]["chapter"], found["death"][0]["flag"], found["death"][0]["msg"]) == (
        "CHARACTER_ROSS", 2, "EVFLAG_GAMEOVER", 0xD4E)


def test_talk_script():
    recruit = dl.talk_script("EventScr_Test", 0xD4C, "CHARACTER_GARCIA")
    assert "MUSS(0x30)" in recruit and "TEXTSHOW(0xD4C)" in recruit and "CUSA(CHARACTER_GARCIA)" in recruit
    plain = dl.talk_script("EventScr_Test", 0xD4C, None)
    assert "CUSA" not in plain and "MUSS" not in plain and plain.rstrip().endswith("};")


def test_scene_script():
    script = dl.scene_script("EventScr_Test", 0xD4C)
    assert "TEXTSHOW(0xD4C)" in script and script.startswith("CONST_DATA EventListScr EventScr_Test[] = {")


def test_layout_cuts_long_lines_into_boxes():
    widths = {b: 5 for b in range(0x21, 0x7F)} | {0x20: 3}
    # 10 pixels wide at most: "aa bb" is 5+5+3+5+5 = 23 px, "aa" 10 px.
    assert dl.layout("aa bb cc", widths, 23) == "aa bb\ncc"
    # Five lines once cut: boxes of two lines.
    assert dl.layout("aa bb cc dd ee", widths, 10) == "aa\nbb\n\ncc\ndd\n\nee"
    # Lines that fit are kept as written, even three of them in a box (the game scrolls).
    assert dl.layout("aa\nbb\ncc", widths, 10) == "aa\nbb\ncc"
    # Codes take no room and stay with their word; a word too wide is cut.
    assert dl.layout("aa[ToggleSmile] bb", widths, 23) == "aa[ToggleSmile] bb"
    assert dl.layout("abcdef", widths, 10) == "ab\ncd\n\nef"


def test_accented_letters_are_written_as_codes():
    from fe_maker.decomp.texts import TextFile, encode_special, name_message, textdefs_with

    assert name_message("Léa") == "Léa[.][X]"   # 3 bytes in the game: é is one byte
    assert encode_special("Allons-y, Léa ! ☃") == "Allons-y, L[é]a ! ☃"
    assert textdefs_with("[X] = 0x00\n", {"é", "à"}).endswith("[à] = 0xE0\n[é] = 0xE9\n")
    tf = TextFile("#0x1\nOld[X]\n")
    tf.set_raw(1, "Déjà[X]")
    assert tf.special_chars() == {"é", "à"} and "D[é]j[à][X]" in tf.render()


def test_edited_message_is_laid_out_at_build(decomp_dir):
    from fe_maker.decomp.gamedata import DecompData

    d = DecompData(decomp_dir)
    long = " ".join(["word"] * 30)   # 30 words of 23 px: far wider than a box
    d.apply_dialogues({"messages": {"1": [{"kind": "say", "pos": "MidLeft", "text": long + " é", "wait": True}]}})
    body = d.texts.raw(1)
    lines = [ln for ln in body.split("\n") if "word" in ln]
    assert len(lines) > 2 and "[A][LF]" in body
    files = d.changed_files()
    assert "[é] = 0xE9" in files["texts/textdefs.txt"] and "[é]" in files["texts/texts.txt"]
