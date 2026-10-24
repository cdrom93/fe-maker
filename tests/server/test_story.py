from fe_maker.decomp import events, story


def test_links_read_every_chapter_change():
    commands = events.parse_script("""
    MUSC(SONG_VICTORY)
    MNCH(0x3)
    MoveToChapter(0x38)
    MNC2(5)
    MNC3(0x16)
    MNCH(0xffff)
    MNCH(-1)
    MNC4
    MNTS(0x0)
    ENDA
""")
    found = [(link["op"], link["kind"], link["to"]) for link in story.links(commands)]
    assert found == [
        ("MNCH", "worldMap", 3), ("MoveToChapter", "worldMap", 0x38), ("MNC2", "direct", 5), ("MNC3", "noSave", 0x16),
        ("MNC4", "ending", None), ("MNTS", "title", None),
    ]
    # the command's place in the script, to rewrite it
    assert story.links(commands)[0]["at"] == 1


def test_edited_link_renders_back():
    commands = events.parse_script("\n    MNCH(0x3)\n    ENDA\n")
    commands[0] = {"op": "MNC2", "args": ["0x4"]}
    assert events.render_script(commands) == "\n    MNC2(0x4)\n    ENDA\n"
    assert events.validate_command(commands[0]) is None
