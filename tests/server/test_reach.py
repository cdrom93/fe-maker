from fe_maker.decomp import reach

PLAIN, WALL, FOREST = 0, 1, 2
COSTS = [1, -1, 2]


def test_movement_follows_terrain_costs():
    terrain = [[PLAIN, WALL, PLAIN],
               [PLAIN, FOREST, PLAIN],
               [PLAIN, PLAIN, PLAIN]]
    assert reach.movement(terrain, COSTS, 2, 0, 0) == {(0, 0), (0, 1), (0, 2)}
    cells = reach.movement(terrain, COSTS, 3, 0, 0)
    assert (1, 1) in cells and (1, 0) not in cells   # the forest costs 2, the wall stops
    assert reach.movement(terrain, COSTS, 3, 5, 5) == set()


def test_strikes_stay_on_the_map_and_keep_the_minimum_range():
    assert reach.strikes({(0, 0)}, [(2, 2)], 3, 3) == {(2, 0), (1, 1), (0, 2)}


def test_only_weapons_strike():
    items = [{"id": "A", "weaponType": "sword", "range": {"min": 1, "max": 2}},
             {"id": "B", "weaponType": "item", "range": {"min": 1, "max": 1}},
             {"id": "C", "weaponType": "staff", "range": {"min": 1, "max": 0}}]
    assert reach.weapon_ranges(["A", "B", "C", "D"], items) == [(1, 2)]


def test_the_ai_of_a_unit_limits_its_reach():
    assert reach.ai_reach(None) == (True, True)
    assert reach.ai_reach([0, 0, 0, 0]) == (True, True)
    assert reach.ai_reach([3, 0, 0, 0]) == (False, True)   # acts from its tile
    assert reach.ai_reach([0, 3, 0, 0]) == (False, True)   # stays
    assert reach.ai_reach([6, 0, 0, 0]) == (True, False)   # never acts


def test_staves_reach_mag_by_2_tiles_at_least_5():
    items = [{"id": "HEAL", "weaponType": "staff", "range": {"min": 1, "max": 1}},
             {"id": "PHYSIC", "weaponType": "staff", "range": {"min": 1, "max": 0}},
             {"id": "SWORD", "weaponType": "sword", "range": {"min": 1, "max": 1}}]
    assert reach.staff_ranges(["HEAL", "PHYSIC", "SWORD"], items, mag=7) == [(1, 1), (1, 5)]
    assert reach.staff_ranges(["PHYSIC"], items, mag=16) == [(1, 8)]
