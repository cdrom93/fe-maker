from fe_maker.decomp import autotile

GRASS, STRAIGHT, BEND, BANK = 1, 2, 3, 5
TERRAIN = bytes([0, 1, 16, 16, 16, 1])


def _model() -> autotile.Model:
    model = autotile.Model(TERRAIN)
    autotile.study(model, [[GRASS, STRAIGHT, GRASS],
                           [GRASS, STRAIGHT, GRASS],
                           [GRASS, BEND, BANK],
                           [GRASS, GRASS, GRASS]])
    return model


def _seen(model, rows):
    return (all(model.right[a, b] for row in rows for a, b in zip(row, row[1:]))
            and all(model.below[a, b] for up, down in zip(rows, rows[1:]) for a, b in zip(up, down)))


def test_every_two_tiles_side_by_side_are_tiles_the_game_draws_so():
    model = _model()
    autotile.study(model, [[GRASS, GRASS, GRASS], [GRASS, BEND, GRASS], [GRASS, GRASS, GRASS]])
    rows = [[GRASS, GRASS, GRASS], [GRASS, STRAIGHT, GRASS], [GRASS, GRASS, GRASS]]
    joined = autotile.paint(model, rows, [(1, 1)])
    assert joined[1][1] == BEND      # the game never draws a straight piece alone in the grass
    assert _seen(model, joined)
    assert rows[1][1] == STRAIGHT    # the rows given are left alone


def test_a_stroke_with_no_join_stays_as_painted():
    model = _model()
    rows = [[GRASS, GRASS, GRASS], [GRASS, BEND, GRASS], [GRASS, GRASS, GRASS]]
    assert autotile.paint(model, rows, [(1, 1)]) == rows


def test_tiles_join_on_borders_of_the_same_material_too():
    model = autotile.Model(TERRAIN)
    autotile.study(model, [[GRASS, GRASS], [STRAIGHT, GRASS]])
    model.borders = [("g", "g", "g", "g")] * len(TERRAIN)
    assert autotile._links(model)[0][STRAIGHT] >> STRAIGHT & 1   # never seen side by side, same border


def test_material_of_a_border():
    assert autotile._material(40, 80, 200) == "w"
    assert autotile._material(90, 170, 60) == "g"
    assert autotile._material(230, 210, 120) == "s"


def test_the_middle_of_a_big_area_keeps_its_tile():
    model = _model()
    rows = [[GRASS] * 9 for _ in range(9)]
    cells = [(x, y) for y in range(9) for x in range(9)]
    assert autotile.paint(model, rows, cells) == rows


def test_cells_outside_the_map_are_ignored():
    rows = [[GRASS, GRASS], [GRASS, GRASS]]
    assert autotile.paint(_model(), rows, [(5, 5)]) == rows


def test_brushes_are_ground_terrains_the_most_used_first():
    model = autotile.Model(bytes([0, 1, 16, 3]))
    autotile.study(model, [[1] * 8, [2] * 8, [1, 2, 3, 1, 2, 3, 1, 2]])
    found = autotile.brushes(model)
    assert [b["terrain"] for b in found] == [16, 1]
    assert found[0]["tile"] == 2
