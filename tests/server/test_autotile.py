from fe_maker.decomp import autotile

GRASS, STRAIGHT, BEND, END_N, BANK = 1, 2, 3, 4, 5
TERRAIN = bytes([0, 1, 16, 16, 16, 1])


def _model() -> autotile.Model:
    model = autotile.Model(TERRAIN)
    autotile.study(model, [[GRASS, STRAIGHT, GRASS],
                           [GRASS, STRAIGHT, GRASS],
                           [GRASS, BEND, BANK],
                           [GRASS, GRASS, GRASS]])
    return model


def test_a_painted_cell_takes_the_tile_of_its_shape():
    rows = [[GRASS, GRASS, GRASS], [GRASS, STRAIGHT, GRASS], [GRASS, STRAIGHT, GRASS], [GRASS, STRAIGHT, GRASS],
            [GRASS, GRASS, GRASS]]
    joined = autotile.paint(_model(), rows, [(1, 1), (1, 2), (1, 3)])
    assert joined[3][1] == BEND
    assert joined[2][1] == STRAIGHT


def test_a_neighbor_changes_only_to_fit():
    rows = [[GRASS, STRAIGHT, GRASS], [GRASS, BEND, GRASS], [GRASS, GRASS, GRASS]]
    joined = autotile.paint(_model(), rows, [(1, 1)])
    assert joined[1][2] == BANK      # the game draws this tile right of a bend
    assert joined[0][0] == GRASS
    assert rows[1][2] == GRASS       # the rows given are left alone


def test_cells_outside_the_map_are_ignored():
    rows = [[GRASS, GRASS], [GRASS, GRASS]]
    assert autotile.paint(_model(), rows, [(5, 5)]) == rows


def test_brushes_are_ground_terrains_the_most_used_first():
    model = autotile.Model(bytes([0, 1, 16, 3]))
    autotile.study(model, [[1] * 8, [2] * 8, [1, 2, 3, 1, 2, 3, 1, 2]])
    found = autotile.brushes(model)
    assert [b["terrain"] for b in found] == [16, 1]
    assert found[0]["tile"] == 2
