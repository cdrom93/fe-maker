import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("port", ROOT / "docker/cskillsys/port.py")
port = importlib.util.module_from_spec(spec)
spec.loader.exec_module(port)

# Fictional symbol tables: (address, size, name, is a function)
VANILLA = [(0x08000100, 0x40, "FuncA", True), (0x08000140, 0x20, "FuncB", True),
           (0x08000200, 0, "TableC", False), (0x08000300, 0x10, "Rewritten", True)]
OURS = [(0x08000100, 0x40, "FuncA", True), (0x08000180, 0x20, "FuncB", True),
        (0x08000260, 0, "TableC", False), (0x08000400, 0x18, "Rewritten", True)]


def test_addresses_follow_their_symbol():
    tr = port.Translator(VANILLA, OURS)
    assert tr.translate(0x08000141) == 0x08000181      # thumb bit kept
    assert tr.translate(0x150) == 0x190                 # ROM offsets stay offsets
    assert tr.translate(0x08000210) == 0x08000270       # inside a size 0 symbol: up to the next one
    assert tr.translate(0x08000100) == 0x08000100 and not tr.conflicts
    tr.translate(0x08000304, "x.event")                 # inside a function FE Maker changed
    assert "changed size" in tr.conflicts[-1]


def test_event_files_reference_and_memmap():
    tr = port.Translator(VANILLA, OURS)
    # Rewritten (0x300) moved to 0x400; offsets inside it are reported as conflicts but still moved
    text = "ORG $300\nPROTECT 0x300 0x310\n  BL(0x300)\n#define Tbl 0x8000200\nWORD 0x10 0x8000204\nBYTE 0x20\n"
    assert port.port_event_text(text, tr, "t") == \
        "ORG $400\nPROTECT 0x400 0x410\n  BL(0x400)\n#define Tbl 0x8000260\nWORD 0x10 0x8000264\nBYTE 0x20\n"
    ref = "dat 0x02000000, gRam\nfun 0x08000141, FuncB\n"
    assert tr.ref_source(ref) == "dat 0x02000000, gRam\nfun 0x08000181, FuncB\n"
    assert tr.sym_source("08000140 FuncB\n") == "08000180 FuncB\n"
    assert "0x1000000" in port.port_memmap("#define FreeSpaceCommon 0xB2A604\n")
