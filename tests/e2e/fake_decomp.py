"""A fictional decomp for the interface tests (ui/e2e): the server tests' fixture decomp plus one chapter with a
map, its units and its events, all written here (no data from the game: the CI has neither the ROM nor the decomp).
"""

import json
import shutil
import struct
from pathlib import Path

from PIL import Image

FIXTURE = Path(__file__).resolve().parents[1] / "server" / "fixtures" / "decomp"
WIDTH, HEIGHT = 15, 10

# Metatiles of the fictional tileset: (terrain id, color index); the fixture names none, plains, forest, river, sea
METATILES = [(0x00, 0), (0x01, 1), (0x0C, 2), (0x10, 3), (0x15, 4)]


def _map(folder: Path) -> list[str]:
    """Tileset, palette, tile configuration and layout of a WIDTH x HEIGHT map; the symbols in asset table order."""
    folder.mkdir(parents=True, exist_ok=True)
    # One 8x8 tile per metatile, each filled with its color (inverted grayscale: 255 = color 0, 17 per step)
    tileset = Image.new("L", (8 * len(METATILES), 8), 255)
    for k, (_terrain, color) in enumerate(METATILES):
        for x in range(8 * k, 8 * k + 8):
            for y in range(8):
                tileset.putpixel((x, y), 255 - 17 * color)
    tileset.save(folder / "FakeObjects.png")
    colors = [(0, 0, 0)] * 160
    for k, rgb in enumerate([(0, 0, 0), (136, 192, 88), (48, 120, 56), (150, 120, 90), (72, 112, 200)]):
        colors[k] = rgb
        colors[80 + k] = tuple(min(255, c + 60) for c in rgb)   # fog of war
    (folder / "FakePalette.pal").write_text(
        "JASC-PAL\n0100\n160\n" + "\n".join(f"{r} {g} {b}" for r, g, b in colors) + "\n", encoding="utf-8")
    config = bytearray(0x2400)
    for k, (terrain, _color) in enumerate(METATILES):
        struct.pack_into("<4H", config, 8 * k, k, k, k, k)
        config[0x2000 + k] = terrain
    (folder / "FakeTileConfig.bin").write_bytes(bytes(config))
    cells = []
    for y in range(HEIGHT):
        for x in range(WIDTH):
            cells.append(4 if x == 0 else 3 if y == 0 else 2 if (x + y) % 5 == 0 else 1)
    (folder / "FakeMap.mar").write_bytes(struct.pack(f"<{len(cells)}H", *(m << 5 for m in cells)))
    (folder / "FakeMap.json").write_text(json.dumps({"id": "FakeMap", "width": WIDTH, "height": HEIGHT}), encoding="utf-8")
    return ["FakeObjects", "FakePalette", "FakeTileConfig", "FakeMap"]


def _chapter(index: int) -> dict:
    return {
        "internalName": f"F{index:02}",
        "map": {"obj1Id": 1, "obj2Id": 0, "paletteId": 2, "tileConfigId": 3, "mainLayerId": 4, "objAnimId": 0,
                "paletteAnimId": 0, "changeLayerId": 0},
        "initialFogLevel": 0, "hasPrepScreen": False, "chapTitleId": 0, "chapTitleIdInHectorStory": 0,
        "initialPosX": 2, "initialPosY": 2, "initialWeather": "fine", "battleTileSet": 0,
        "easyModeLevelMalus": 0, "difficultModeLevelBonus": 0, "normalModeLevelMalus": 0,
        "bgm": {"bluePhase": 1, "redPhase": 2, "greenPhase": 2, "bluePhaseInHectorStory": 1,
                "redPhaseInHectorStory": 2, "greenPhaseInHectorStory": 2, "blueGreenPhaseAlt": 1,
                "redPhaseAlt": 65535, "prologueInLynStory": 1, "prologue": 65535, "prologueInHectorStory": 65535},
        "mapCrackedWallHeath": 20, "rank": {}, "unk3D": 0, "unk5E": 0,
        "chapTitleTextId": 0, "chapTitleTextIdInHectorStory": 0, "mapEventDataId": 5, "gmapEventId": 0,
        "divination": {"text": {"beginning": 0, "EliwoodStory": 0, "HectorStory": 0, "ending": 0},
                       "portrait": 0, "fee": 0},
        "prepScreenNumber": 0, "prepScreenNumberInHectorStory": 0, "merchantPosX": 255,
        "merchantPosXInHectorStory": 255, "merchantPosY": 0, "merchantPosYInHectorStory": 0,
        "victorySongEnemyThreshold": 1, "fadeToBlack": 1,
        "goal": {"statusObjectiveTextId": 0, "windowTextId": 0, "windowDataType": "defeat_all",
                 "windowEndTurnNumber": 0, "protectCharacterIndex": 0, "destPosX": 255, "destPosY": 0},
        "unk91": 0, "unk92": 0, "unk93": 0,
    }


def _map_sprites(target: Path) -> None:
    """One standing sheet (a round token, 16 x 16 frames) for every class, and the three sides' palettes."""
    folder = target / "graphics" / "unit_icon"
    (folder / "wait").mkdir(parents=True)
    (folder / "palette").mkdir()
    sheet = Image.new("P", (16, 48), 0)
    for y in range(48):
        for x in range(16):
            r = (x - 7.5) ** 2 + (y % 16 - 8.5) ** 2
            sheet.putpixel((x, y), 0 if r > 36 else 1 if r > 20 else 2)
    sheet.putpalette([0, 0, 0] * 16)
    sheet.save(folder / "wait" / "unit_icon_wait_Fake_sheet.png")
    for side, rgb in (("player", (40, 80, 200)), ("enemy", (200, 50, 40)), ("npc", (40, 160, 60))):
        colors = [(0, 0, 0), (20, 20, 20), rgb] + [(0, 0, 0)] * 13
        gba = b"".join(struct.pack("<H", (r >> 3) | (g >> 3) << 5 | (b >> 3) << 10) for r, g, b in colors)
        (folder / "palette" / f"unit_icon_pal_{side}.agbpal").write_bytes(gba)
    (target / "src" / "unit_icon_wait_data.c").write_text(
        "// Fictional\nUnitIconWait unit_icon_wait_table[] = {\n"
        + "".join(f"\t{{0, UNIT_ICON_SIZE_16x16, unit_icon_wait_Fake_sheet}}, // {k}\n" for k in range(16)) + "};\n",
        encoding="utf-8")


def make(target: Path) -> Path:
    """Write the fictional decomp into `target` (emptied first)."""
    if target.exists():
        shutil.rmtree(target)
    shutil.copytree(FIXTURE, target)
    symbols = _map(target / "graphics" / "map" / "fake") + ["TestChapterEvents"]
    (target / "data" / "data_8B363C.s").write_text(
        "gChapterDataAssetTable:\n\t.word 0\n" + "".join(f"\t.word {s}\n" for s in symbols), encoding="utf-8")
    files = {"FakeObjects": "FakeObjects.4bpp.lz", "FakePalette": "FakePalette.gbapal",
             "FakeTileConfig": "FakeTileConfig.bin.lz", "FakeMap": "FakeMap.mar.lz"}
    (target / "data" / "const_data_chapter_maps.s").write_text(
        "".join(f'{s}:\n\t.incbin "graphics/map/fake/{f}"\n' for s, f in files.items()), encoding="utf-8")
    (target / "src" / "data").mkdir(parents=True, exist_ok=True)
    (target / "src" / "data" / "chapter_settings.json").write_text(
        json.dumps({"chapters": [_chapter(0)]}, indent=2), encoding="utf-8")
    (target / "include" / "constants" / "terrains.h").write_text(
        "enum {\n    TERRAIN_NONE = 0x00,\n    TERRAIN_PLAINS = 0x01,\n    TERRAIN_FOREST = 0x0C,\n"
        "    TERRAIN_MOUNTAIN = 0x10,\n    TERRAIN_SEA = 0x15,\n    TERRAIN_COUNT = 0x41,\n};\n", encoding="utf-8")
    (target / "src" / "data_terrains.c").write_text(
        "// Fictional: terrain names and no battle background\nconst u16 gUnknown_0880D374[] = {\n"
        "    [TERRAIN_PLAINS] = 0x1,\n};\n", encoding="utf-8")
    (target / "data" / "data_btl_bg.s").write_text("gBattleBGDataTable:\nbtl_bg_0_tiles:\n", encoding="utf-8")
    _map_sprites(target)
    udefs = target / "src" / "events_udefs.c"   # the player's units side by side, not all on (0, 0)
    parts = udefs.read_text(encoding="utf-8").split(".level = ")
    udefs.write_text(parts[0] + "".join(f".xPosition = {3 + 2 * k}, .yPosition = 4, .level = {part}"
                                        for k, part in enumerate(parts[1:])), encoding="utf-8")
    events = target / "src" / "events" / "test-eventinfo.h"   # the opening says something (message 1)
    events.write_text(events.read_text(encoding="utf-8").replace(
        "    CALL(EventScr_TestShared)\n    ENDA", "    CALL(EventScr_TestShared)\n    Text(0x1)\n    ENDA", 1),
        encoding="utf-8")
    (target / "data" / "data_59E8E0.s").write_text("@ no boss mark: the server shows none\n", encoding="utf-8")
    return target


if __name__ == "__main__":
    import sys

    print(make(Path(sys.argv[1])))
