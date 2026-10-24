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
  /** groups made in the project (reinforcements), their units in unitGroups */
  newGroups?: Record<string, NewGroup>
  /** objectives edited in the project, by chapter index */
  objectives?: Record<string, ObjectiveEdit>
}

export type ObjectiveType = 'seize' | 'defeat_all' | 'defeat_boss' | 'defense' | 'area' | 'special'

/** What the project stores for an edited objective (server/fe_maker/decomp/objectives.py). */
export interface ObjectiveEdit {
  type: ObjectiveType
  seize: { x: number; y: number }[]
  seizeLabel: 'throne' | 'gate'
  /** turns to survive (defense) */
  turns: number
  /** text of the status screen; lines separated by \n */
  statusText: string
  /** defeat boss: the character whose defeat wins (death quote table) */
  boss?: string | null
  /** reach an area: its corners, and who must reach it ("" = any player unit) */
  area?: { x1: number; y1: number; x2: number; y2: number } | null
  areaWho?: string
  /** defense: defeating the boss also wins */
  orBoss?: boolean
  /** the game is lost if this character dies (any objective) */
  protect?: string | null
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
  /** false when the chapter has one boss per route (not editable yet) */
  bossEditable: boolean
}

/** A map layout of the original game (GET /api/maps). */
export interface MapInfo {
  id: string
  width: number
  height: number
  /** indices of the chapters that use it */
  chapters: number[]
  tileset: string
}

/** What the map editor needs about a layout and its tileset (GET /api/maps/{id}). */
export interface MapLayout {
  id: string
  /** original metatile number of each cell, row by row */
  rows: number[][]
  tileset: string
  /** terrain id of each metatile */
  terrains: number[]
  /** metatiles identical to an earlier one: hidden from the palette */
  duplicates: boolean[]
  /** in-game terrain names, by terrain id */
  terrainNames: string[]
  /** metatiles per row of the tileset sheet */
  columns: number
  /** original map changes; null when the map has no change layer */
  changes: MapChange[] | null
  /** the map's palette in the game, and the tileset's palettes in the game (ticket 16) */
  palette: string | null
  palettes: { id: string; chapters: number[]; colors: string[] }[]
}

/** A map change: tiles put over a rectangle of the map during the game (door, village, wall...). */
export interface MapChange {
  /** number used by events; doors, villages and chests use the change covering them */
  id: number
  x: number
  y: number
  w: number
  h: number
  /** metatile of each cell of the rectangle */
  rows: number[][]
  /** tile block of the original change (kept when edited) */
  tiles?: string
  /** drawn by hand for an object (ticket 19): it counts for the object whatever its tiles */
  manual?: boolean
}

/** Project map data (data/maps.json): layouts once painted. */
export interface MapsData {
  layouts: Record<string, { rows: number[][] }>
  /** map changes by layout id, once edited (the whole list) */
  changes?: Record<string, MapChange[]>
  /** object settings by layout id, then by "x,y" of the object's first cell */
  objects?: Record<string, Record<string, MapObjectSettings>>
  /** mirrored and turned tiles added to tilesets, by tile config name (server: tileedit.py) */
  tilesets?: Record<string, TilesetEdits>
  /** another palette of the tileset, by layout id (an asset name of the game, server: maps.palette_choices) */
  palettes?: Record<string, string>
}

export interface TilesetEdits {
  /** slot -> its 4 tile entries and terrain */
  metatiles: Record<string, { tiles: number[]; terrain: number }>
  /** 8x8 tile index -> 64 color indices */
  tiles: Record<string, number[]>
}

export type MapObjectKind = 'village' | 'house' | 'armory' | 'vendor' | 'chest' | 'door' | 'wall' | 'snag'

/** What a chest holds, what a village gives and says (server: mapobjects.py). */
export interface MapObjectSettings {
  item?: string
  gold?: number
  face?: string
  text?: string
  /** what a shop sells */
  items?: string[]
  /** shop only open to a unit with a member card */
  secret?: boolean
  /** no event and no automatic change: the object is only decoration */
  off?: boolean
}

/** A village, house, chest, door, cracked wall or snag found on the map. */
export interface MapObject {
  kind: MapObjectKind
  x: number
  y: number
  cells: number[][]
  /** not on the original map */
  new: boolean
  /** id of the change applied when it is used (null: none) */
  change: number | null
  /** the change FE Maker adds by itself */
  auto: MapChange | null
  /** new object whose used state is unknown for this tileset */
  noAfter: boolean
  /** its location event in the original game */
  event: { macro: string; item?: string; gold?: number; script?: string; shop?: string; items?: string[] } | null
}

export interface MapObjects {
  objects: MapObject[]
  hasChangeLayer: boolean
  defaults: Record<MapObjectKind, MapObjectSettings>
  faces: { id: string; portrait: number }[]
}

export interface UnitGroup {
  name: string
  origin: 'players' | 'opening' | 'cutscene' | 'turn'
  turn: number | null
  units: MapUnit[]
  edited?: boolean
  /** made in the project */
  new?: boolean
}

/** Reinforcements made in the project: they arrive at the start of turn N of a side. */
export interface NewGroup {
  chapter: number
  turn: number
  phase: 'player' | 'enemy' | 'ally'
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

/** A step of a dialogue (server: decomp/dialogues.py). */
export interface DialogueStep {
  kind: 'face' | 'clear' | 'move' | 'say' | 'code'
  /** speaker slot (FarLeft... FarFarRight); null for a line without speaker */
  pos?: string | null
  face?: string
  to?: string
  /** a line: "\n" new line, blank line = new box after a button press, other codes kept as [Code] */
  text?: string
  wait?: boolean
  open?: boolean
  code?: string
}

export interface DialogueScene {
  script: string
  file: string
  messages: number[]
  trigger: { kind: string; turn?: string; faction?: string; a?: string; b?: string; x?: string; y?: string; via?: string }
}

/** The game's talk font: character -> [byte, width in pixels], and the box sizes. */
export interface DialogueFont {
  chars: Record<string, [number, number]>
  talkWidth: number
  battleWidth: number
  boxLines: number
}

export interface DialogueFace {
  id: string
  portrait: number
}

export interface DialoguesData {
  /** edited messages by id (decimal), as steps */
  messages: Record<string, DialogueStep[]>
  /** new battle quotes (a fights b; b "" = anyone) and death quotes (a's last words) */
  quotes?: NewQuote[]
  /** support pairs, once edited (the whole list; server: decomp/supports.py) */
  supports?: SupportPair[]
  /** event scripts edited in the visual editor, by script name (server: decomp/events.py) */
  scripts?: Record<string, EventCommand[]>
}

/** A command of an event script: a macro and its arguments (no args: a bare macro);
 * op "#" is a comment (text), op "" a blank line. */
export interface EventCommand {
  op: string
  args?: string[]
  text?: string
}

export interface EventsReference {
  /** known commands: their arguments (name, kind: song, message, character, group, x, y, frames, ...) */
  commands: Record<string, { name: string; kind: string }[]>
  /** commands the editor offers to add */
  addable: string[]
  songs: string[]
  backgrounds: string[]
}

export interface SupportPair {
  a: string
  b: string
  /** points at the start, and gained each turn the two start side by side (C at 81, B 161, A 241) */
  base: number
  growth: number
}

export interface NewQuote {
  /** battle quote, last words, or a conversation started with "Talk" (a talks to b) */
  kind: 'battle' | 'death' | 'talk' | 'turn' | 'support'
  /** support conversation: 1 = C, 2 = B, 3 = A */
  rank?: number
  /** turn scene: the turn and the side whose phase starts it */
  turn?: number
  phase?: 'player' | 'enemy' | 'ally'
  /** chapter index; 255 = every chapter */
  chapter: number
  a: string
  b?: string
  /** conversation: b joins the player's army */
  recruit?: boolean
  /** conversation: b can also start it */
  both?: boolean
  steps: DialogueStep[]
}

export interface Problem {
  severity: 'error' | 'warning'
  kind: 'characters' | 'items' | 'classes' | 'combat' | 'chapters' | 'maps' | 'dialogues'
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

/** A portrait sheet imported in the project (server: decomp/portraits.py): mouth and eye frames
 * in 8-pixel tiles from the face's top-left corner. */
export interface PortraitImport {
  file: string
  mouth: [number, number]
  eyes: [number, number]
}

export interface PortraitInfo {
  id: number
  name: string
  /** other portrait ids drawn with the same pictures */
  sharedWith: number[]
  original: { mouth: [number, number]; eyes: [number, number] } | null
  imported: PortraitImport | null
}
