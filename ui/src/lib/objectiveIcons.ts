/** Objective type -> the game's item icon standing for it: door key, sword, crest, shield, boots. */
export const OBJECTIVE_ICONS = { seize: 104, defeat_all: 0, defeat_boss: 98, defense: 219, area: 96 } as const
/** Fights shown as enemy map sprites (ticket 140): a brigand with the map's boss mark, a pair of soldiers. */
export const OBJECTIVE_SPRITES = { defeat_boss: ['CLASS_BRIGAND'], defeat_all: ['CLASS_SOLDIER', 'CLASS_SOLDIER'] } as const
/** Seizing: a fort of the game's maps, one cell (TERRAIN_FORT). */
export const SEIZE_TERRAIN = 0x0a
