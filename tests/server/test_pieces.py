from fe_maker.decomp.pieces import _components, one_building


def test_buildings_are_groups_of_touching_building_cells():
    # terrain by metatile: 0 plains, 1 village gate, 2 village wall (TILE_2E), 3 castle gate, 4 castle wall (TILE_2C)
    terrain = bytes([0x01, 0x03, 0x2E, 0x0B, 0x2C])
    cells = [
        2, 2, 0, 4, 4,
        2, 1, 0, 4, 3,
        0, 0, 0, 0, 0,
    ]
    groups = sorted(_components(5, 3, cells, terrain), key=min)
    assert groups == [{(0, 0), (1, 0), (0, 1), (1, 1)}, {(3, 0), (4, 0), (3, 1), (4, 1)}]


def test_only_whole_single_buildings():
    assert one_building([0x2E, 0x2E, 0x2E, 0x2E, 0x03, 0x2E])            # a village
    assert one_building([0x2C, 0x2C, 0x23])                              # a castle gate in its walls
    assert not one_building([0x2E, 0x03, 0x2E, 0x2E, 0x03, 0x2E])        # two villages side by side
    assert not one_building([0x07, 0x05])                                # a shop next to a house
    assert not one_building([0x0A, 0x0A])                                # a fort without its walls


def test_one_tile_pieces_are_the_most_drawn_of_each_kind():
    from collections import Counter

    from fe_maker.decomp.pieces import SINGLES_BY_KIND, _singles

    terrain = bytes([0x21] * 5 + [0x05, 0x01])
    uses = Counter({0: 9, 1: 8, 2: 7, 3: 6, 4: 5, 5: 4})
    found = _singles(uses, terrain)
    assert [p["rows"] for p in found if p["kind"] == "chest"] == [[[0]], [[1]], [[2]]][:SINGLES_BY_KIND]
    assert [(p["kind"], p["group"]) for p in found][0] == ("house", "building")
