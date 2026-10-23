export type StatKey = 'hp' | 'pow' | 'skl' | 'spd' | 'def' | 'res' | 'lck' | 'con'

export interface Character {
  id: string
  name: string
  class: string
  level: number
  portraitId: number
  bases: Record<StatKey, number>
  growths: Record<Exclude<StatKey, 'con'>, number>
  weaponRanks: Record<string, string | number>
  affinity: string | null
  abilities: string[]
}

export interface Item {
  id: string
  name: string
  weaponType: string
  might: number
  hit: number
  crit: number
  weight: number
  range: { min: number; max: number }
  uses: number
  pricePerUse: number
  weaponRank: string | number
  iconId: number
  effectiveness: string | null
  /** null = anyone; empty lists = nobody */
  reservedFor: { characters: string[]; classes: string[] } | null
  monsterWeapon: boolean
}

export interface ClassInfo {
  id: string
  name: string
  bases: Record<StatKey, number>
  mov: number
  animatedWeapons: string[]
  usedInGame: boolean
  abilities: string[]
  gender: 'male' | 'female' | null
}

export type ClassStatKey = 'hp' | 'pow' | 'skl' | 'spd' | 'def' | 'res' | 'con'

/** Editable class data (project data/classes.json). */
export interface ClassData {
  id: string
  name: string
  bases: Record<ClassStatKey, number>
  mov: number
  maxes: Record<ClassStatKey, number>
  growths: Record<Exclude<StatKey, 'con'>, number>
  promotionGains: Record<Exclude<ClassStatKey, 'con'>, number>
  relativePower: number
  weaponRanks: Record<string, string | number>
  abilities: string[]
  promotions: string[]
  movement: string | null
  terrainBonus: string | null
}

/** Read-only facts about a class, derived from the decomp. */
export interface ClassFacts {
  animatedWeapons: string[]
  usedInGame: boolean
  gender: 'male' | 'female' | null
}

/** What the editors need about a class: project data + facts. */
export type ClassView = ClassData & ClassFacts

export interface TriangleRule {
  attacker: string
  defender: string
  hit: number
  damage: number
}

export interface Combat {
  triangle: TriangleRule[]
  effectiveness: Record<string, string[]>
}

export interface ChapterInfo {
  index: number
  id: string
  title: string
  map: string | null
  events: string | null
}

export interface MapUnit {
  /** position in the original group; null for a unit added in the project */
  slot: number | null
  /** for an added unit: slot of the original unit it copies (AI and other hidden fields) */
  copyOf?: number | null
  character: string
  class: string
  level: number
  autolevel: boolean
  side: 'player' | 'ally' | 'enemy'
  x: number
  y: number
  endX: number
  endY: number
  items: string[]
  /** action, movement, target/recovery settings, flags (0x20: guards its tile) */
  ai: number[] | string
  /** entry path not decompiled yet: the unit cannot be moved */
  fixedPath?: boolean
}

/** Project chapter data: unit groups once edited (data/chapters.json). */
export interface ChaptersData {
  unitGroups: Record<string, MapUnit[]>
  /** objectives edited in the project, by chapter index */
  objectives?: Record<string, ObjectiveEdit>
}

export type ObjectiveType = 'seize' | 'defeat_all' | 'defeat_boss' | 'defense' | 'special'

/** What the project stores for an edited objective (server/fe_maker/decomp/objectives.py). */
export interface ObjectiveEdit {
  type: ObjectiveType
  seize: { x: number; y: number }[]
  seizeLabel: 'throne' | 'gate'
  /** turns to survive (defense) */
  turns: number
  /** text of the status screen; lines separated by \n */
  statusText: string
}

export interface Objective extends ObjectiveEdit {
  /** written with the standard forms: type and tiles can be changed */
  editable: boolean
  /** why it cannot be edited: custom, escort, noEvents */
  reason: string
  hasStatusText: boolean
  /** other chapters sharing the status text / the events */
  statusShared: number
  eventsShared: number
}

export interface UnitGroup {
  name: string
  origin: 'players' | 'opening' | 'cutscene' | 'turn'
  turn: number | null
  units: MapUnit[]
  edited?: boolean
}

export interface ChapterUnits {
  width: number
  height: number
  groups: UnitGroup[]
}

export interface Reference {
  classFacts: Record<string, ClassFacts>
  movementTypes: string[]
  effectivenessLists: string[]
  classes: ClassInfo[]
  itemLocks: Record<string, { classes: string[]; characters: string[] }>
  lockItems: Record<string, string[]>
  affinities: string[]
  abilities: string[]
  weaponTypes: string[]
  rankableTypes: string[]
  ranks: string[]
  iconCount: number
  portraits: (string | null)[]
}

export interface Problem {
  severity: 'error' | 'warning'
  kind: 'characters' | 'items' | 'classes' | 'combat' | 'chapters'
  id: string
  field: string
  code: string
  params: Record<string, string | number>
  message: string
}

export interface ProjectInfo {
  path: string
  name: string
  meta: Record<string, unknown>
}

export interface Status {
  hasRom: boolean
  language: 'fr' | 'en' | 'es' | 'it'
  mgbaPath: string | null
  keys: Record<string, string>
  gbaButtons: string[]
  recentProjects: string[]
  defaultProjectsDir: string
  project: ProjectInfo | null
}

export interface BuildStatus {
  state: 'idle' | 'running' | 'done' | 'error'
  log: string[]
  logSize: number
  error: string | null
  patch: string | null
  launch: boolean
}

export type TicketKind = 'bug' | 'idea' | 'question'
export type TicketPriority = 'high' | 'normal' | 'low'

/** Test feedback written from the app (server/fe_maker/tickets.py). */
export interface Ticket {
  id: string
  number: number
  kind: TicketKind
  priority: TicketPriority
  status: 'open' | 'done' | 'cancelled'
  body: string
  context: Record<string, string>
  images: string[]
  createdAt: string
  updatedAt: string
}

export interface TicketIn {
  body: string
  kind: TicketKind
  priority: TicketPriority
  context: Record<string, string>
  /** screenshots as data URLs */
  images: string[]
}

/** Options of "Test" builds only (never in the exported patch). */
export interface TestOptions {
  start: string
  /** prologue without its cutscene: units are simply on the map */
  simplePrologue: boolean
}
