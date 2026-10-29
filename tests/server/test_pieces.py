from fe_maker.decomp.pieces import _components


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
