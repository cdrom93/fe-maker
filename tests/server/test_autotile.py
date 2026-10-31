from fe_maker.decomp import autotile

GRASS, STRAIGHT, BEND, BANK = 1, 2, 3, 5
TERRAIN = bytes([0, 1, 16, 16, 16, 1])


def test_filling_the_empty_space_keeps_what_was_built():
    grass, wood, wall = 1, 2, 3
    model = autotile.Model(bytes([0, 1, 12, 0x1E]))
    model.borders = [("", "", "", "")] * 4
    model.tiles[1][grass] = model.tiles[12][wood] = 0   # only terrains the game's maps use are studied below
    for _ in range(6):
        autotile.study(model, [[grass, grass, grass, grass], [grass, wood, wood, grass],
                               [grass, wood, wood, grass], [grass, grass, grass, grass]])
    rows = [[grass] * 12 for _ in range(10)]
    rows[0][0] = wall
    costs = [-1] * 0x40
    costs[1] = costs[12] = 1
    out = autotile.fill(model, rows, costs, [(9, 7)], seed=3)
    assert all(out[y][x] == grass for x in (8, 9, 10) for y in (6, 7, 8))
    assert out[0][0] == wall and out[0][1] == out[1][0] == out[1][1] == grass    # a free cell around what stays
    assert sum(row.count(wood) for row in out) > 3
    costs[12] = -1
    assert autotile.fill(model, rows, costs, seed=3) == rows      # nothing a unit could not cross


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
