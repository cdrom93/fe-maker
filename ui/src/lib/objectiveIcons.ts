/** Objective type -> the game's item icon standing for it: door key, sword, crest, shield, boots. */
export const OBJECTIVE_ICONS = { seize: 104, defeat_all: 0, defeat_boss: 98, defense: 219, area: 96 } as const
/** Fights shown as enemy map sprites (ticket 140): a brigand marked with the boss crest, a pair of soldiers. */
export const OBJECTIVE_SPRITES = { defeat_boss: ['CLASS_BRIGAND'], defeat_all: ['CLASS_SOLDIER', 'CLASS_SOLDIER'] } as const
