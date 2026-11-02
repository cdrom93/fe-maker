export type StatKey = 'hp' | 'pow' | 'skl' | 'spd' | 'def' | 'res' | 'lck' | 'con'

/** A character's colours for a class: 5 lines of 16 colours (server: decomp/charpalettes.py). */
export interface BattleColors {
  base: string[][]
  game: string[][] | null
  others: { character: string; lines: string[][] }[]
}

export interface Character {
  /** by class; null: the class's colours; a class left out stays as in the game */
  battleColors?: Record<string, string[][] | null>
  /** the user's colours by class while another choice is in use (never built) */
  customColors?: Record<string, string[][]>
  /** the help text, when the project changes it */
  description?: string
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
  /** opens the convoy, with the units next to them (missing in older projects: Eirika and Ephraim) */
  convoyAccess?: boolean
  /** can seize (missing in older projects: Eirika and Ephraim, by route; server: seize.py) */
  canSeize?: boolean
}

export interface Item {
  /** the help text, when the project changes it */
  description?: string
  id: string
  name: string
  /** weapons the project adds (ITEM_NEW_xx): the game's weapon they copy (spell, own animations) */
  model?: string
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
  /** boxes of the sheet: "magic", "brave"... */
  properties: string[]
  weaponEffect: string | null
  /** weapon rank points won with each hit */
  weaponExp: number
  /** stats given while equipped, or for good by a consumable */
  statBonuses: Record<string, number> | null
  /** the text of the Use screen, when the project changes it */
  useDescription?: string
  /** another item whose spell this one takes */
  spellFrom?: string
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
  /** the face of the class's units whose character has none; 0: none */
  genericPortrait?: number
  /** the help text, when the project changes it */
  description?: string
  id: string
  name: string
  /** classes the project adds (CLASS_NEW_xx): the game's class they copy (sprites, animations) */
  model?: string
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
  /** a chapter of the game a blank project does not use */
  hidden?: boolean
  index: number
  id: string
  title: string
  /** a chapter the project adds, on a free slot of the game's (its title can be changed) */
  added?: boolean
  map: string | null
  events: string | null
  /** the convoy can be used in this chapter, in the game */
  convoy: boolean
  /** the preparations screen comes before the battle, unless changed */
  prep: boolean
  /** fog of war in the game: the units' vision range, 0 for none */
  fog: number
  /** HP of the map's cracked walls in the game */
  wallHp: number
  /** in the game: weather at the start, battle background set (0: default), cell the camera shows first */
  weather: string
  battleBg: number
  camera: [number, number]
  levelBonus: LevelBonus
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
  /** drops their last item on death */
  itemDrop?: boolean
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
  /** titles the project gives its chapters, by chapter index */
  titles?: Record<string, string>
  /** groups made in the project (reinforcements), their units in unitGroups */
  newGroups?: Record<string, NewGroup>
  /** objectives edited in the project, by chapter index */
  objectives?: Record<string, ObjectiveEdit>
  /** convoy available or not, by chapter index, once changed from the game (server: convoy.py) */
  convoy?: Record<string, boolean>
  /** chapters the project cleared (server: newchapter.py) */
  cleared?: number[]
  /** the game's reinforcement groups moved to another turn, by group (server: DecompData._apply_group_turns) */
  groupTurns?: Record<string, { chapter: number; turn?: number; phase?: NewGroup['phase'] }>
  /** preparations screen or not, by chapter index, once changed (server: prep.py) */
  prep?: Record<string, boolean>
  /** fog of war (vision range, 0: none), by chapter index, once changed from the game */
  fog?: Record<string, number>
  /** HP of the cracked walls, by chapter index, once changed from the game */
  wallHp?: Record<string, number>
  weather?: Record<string, string>
  battleBg?: Record<string, number>
  camera?: Record<string, [number, number]>
  levelBonus?: Record<string, LevelBonus>
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
  /** its own tile config (`tileset` is the sheet the project chose for it, if any) */
  originalTileset: string
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
  /** per terrain: avoid, defense, resistance bonuses, healing (percent), cost on foot and on horse (-1: impassable); older servers: none */
  terrainEffects?: Record<'avoid' | 'defense' | 'resistance' | 'foot' | 'horse', number[]> & { heal?: number[] }
  /** metatiles per row of the tileset sheet */
  columns: number
  /** original map changes; null when the map has no change layer */
  changes: MapChange[] | null
  /** the map's palette in the game, and the tileset's palettes in the game (ticket 16) */
  palette: string | null
  palettes: { id: string; chapters: number[]; colors: string[]; lines?: string[][] }[]
  /** the map's tile sheet in the game, and the game's tile sheets it can be drawn with (ticket 21) */
  originalBase: string
  bases: { id: string; name: string; chapters: number[]; palette: string }[]
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
  /** where a map moved when its left or top side did: its original events follow it */
  offsets?: Record<string, [number, number]>
  /** retouched colors of the game's palettes: palette -> color index -> #rrggbb */
  paletteColors?: Record<string, Record<string, string>>
  /** another tile sheet of the game, by layout id (its tile config name, server: maps.base_choices) */
  bases?: Record<string, string>
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
  /** new village: the ruined village change FE Maker adds (an enemy that pillages destroys it) */
  ruin?: MapChange | null
  /** new object whose used state is unknown for this tileset */
  noAfter: boolean
  /** its location event in the original game */
  event: { macro: string; item?: string; gold?: number; script?: string; shop?: string; items?: string[] } | null
}

export interface MapObjects {
  objects: MapObject[]
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

/** Item icons imported into the project, on the places the game leaves free. */
export interface ItemIcons {
  imported: number[]
  free: number
}

export interface ChapterUnits {
  width: number
  height: number
  /** the map's changes (doors, villages...), to see the map with one of them */
  changes: { id: number; x: number; y: number; w: number; h: number }[]
  groups: UnitGroup[]
}

/** Levels the game takes from a chapter's enemies in easy and normal, and adds in hard. */
export interface LevelBonus {
  easy: number
  normal: number
  hard: number
}

export interface AffinityBonus {
  attack: number
  defense: number
  hit: number
  avoid: number
  crit: number
  dodge: number
}

export interface Reference {
  /** help texts of the game, by kind and id */
  descriptions: Record<'characters' | 'classes' | 'items' | 'itemUses', Record<string, string>>
  /** items with a spell or projectile of their own */
  spellItems: string[]
  classFacts: Record<string, ClassFacts>
  movementTypes: string[]
  effectivenessLists: string[]
  classes: ClassInfo[]
  itemLocks: Record<string, { classes: string[]; characters: string[] }>
  lockItems: Record<string, string[]>
  affinities: string[]
  /** table values of each affinity, read from the game */
  affinityBonuses: Record<string, AffinityBonus>
  abilities: string[]
  weaponTypes: string[]
  rankableTypes: string[]
  ranks: string[]
  iconCount: number
  portraits: (string | null)[]
  /** the first portrait id after the game's ones (portraits the project adds) */
  firstNewPortrait: number
  /** class cards, the pictures of nameless units, by portrait id */
  portraitCards: Record<string, string>
  /** the game's named characters only met as enemies */
  gameEnemies: string[]
  /** named in the decomp, generic in use */
  namedGenerics: string[]
  /** characters' levels in the game: a sheet that differs gives its level to the units */
  gameLevels: Record<string, number>
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
  trigger: { kind: string; turn?: string; end?: string; flag?: string; faction?: string; a?: string; b?: string; x?: string; y?: string; via?: string }
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
  /** name of a portrait the project adds */
  name?: string
}

/** A past choice of the player, a name for a permanent flag of the game (server: events.MEMORY_FLAGS). */
export interface Memory {
  flag: number
  name: string
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
  memories?: Memory[]
  /** What the project changed in what starts the game's scenes, by scene. */
  triggers?: Record<string, Partial<DialogueScene['trigger']>>
  /** scenes of the game nothing starts any more */
  removedScenes?: string[]
}

/** A command of an event script: a macro and its arguments (no args: a bare macro);
 * op "#" is a comment (text), op "" a blank line. */
export interface EventCommand {
  op: string
  args?: string[]
  text?: string
}

export interface EventsReference {
  /** first and last flag for memories */
  memoryFlags: [number, number]
  /** known commands: their arguments (name, kind: song, message, character, group, x, y, frames, ...) */
  commands: Record<string, { name: string; kind: string }[]>
  /** commands the editor offers to add */
  addable: string[]
  songs: string[]
  backgrounds: string[]
  /** the chapters' event scripts, for CALL */
  scripts: string[]
  /** the project's items, to give one */
  items: { id: string; name: string }[]
  /** the chapters, to go to one */
  chapters: { index: number; title: string }[]
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
  kind: 'battle' | 'death' | 'talk' | 'turn' | 'support' | 'scene' | 'area' | 'flag'
  /** a scene's message ending on a Yes / No choice */
  question?: boolean
  /** message of an event script ("scene"): scripts refer to it as "new:<key>" */
  key?: string
  /** support conversation: 1 = C, 2 = B, 3 = A */
  rank?: number
  /** turn scene: the turn and the side whose phase starts it */
  turn?: number
  phase?: 'player' | 'enemy' | 'ally'
  /** turn scene: last turn of a range (shown at the start of each of these turns); 0 or none: once */
  endTurn?: number
  /** area scene: x1, y1, x2, y2 (a player unit stops there) */
  area?: number[]
  /** flag scene: shown once this flag is set (a memory, or a flag another scene sets) */
  flag?: number
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
  version: string
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
/** Something FE Maker needs on this computer (server: checks.py). */
export interface Check {
  id: 'rom' | 'decomp' | 'docker' | 'mgba'
  ok: boolean
  detail: string
}

export interface Ticket {
  id: string
  number: number
  kind: TicketKind
  priority: TicketPriority
  status: 'open' | 'done' | 'cancelled'
  body: string
  context: Record<string, string>
  images: string[]
  comments: TicketComment[]
  createdAt: string
  updatedAt: string
}

/** A reply that completes a ticket. */
export interface TicketComment {
  id: string
  body: string
  images: string[]
  createdAt: string
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
  /** "Test this chapter": the chapter index the test starts on (0: the prologue) */
  chapter: number
}

/** A portrait sheet imported in the project (server: decomp/portraits.py): mouth and eye frames
 * in 8-pixel tiles from the face's top-left corner. */
export interface PortraitImport {
  file: string
  /** name of a portrait the project adds (after the game's ones) */
  name?: string
  /** imported from FE-Repo: credited in the project's CREDITS.txt */
  source?: FeRepoEntry
  mouth: [number, number]
  eyes: [number, number]
}

/** A file of FE-Repo, as its name describes it (server: ferepo.py). */
export interface FeRepoEntry {
  url: string
  folder: string
  name: string
  authors: string[]
  /** F2E: free to use and edit; F2U: free to use, not to edit */
  license: 'F2E' | 'F2U'
  /** battle animations filtered by weapon: the weapon types it has (ticket 47) */
  weapons?: string[]
  /** map sprites: the moving sheet going with this standing one, if FE-Repo has it */
  walk?: string | null
}

export interface PortraitInfo {
  id: number
  name: string
  /** other portrait ids drawn with the same pictures */
  sharedWith: number[]
  original: { mouth: [number, number]; eyes: [number, number] } | null
  imported: PortraitImport | null
  /** a portrait the project adds, after the game's ones */
  added: boolean
}

/** A command of a chapter's script that starts another chapter (server: decomp/story.py, ticket 31). */
export interface ChapterLink {
  script: string
  /** the script is the chapter's ending scene */
  ending: boolean
  /** index of the command in the script */
  at: number
  op: string
  kind: 'worldMap' | 'direct' | 'noSave' | 'ending' | 'title'
  /** chapter index, null for the game's ending or the title screen */
  to: number | null
}

export interface ChapterLinks {
  /** by chapter index */
  links: ChapterLink[][]
  /** each chapter's ending scene */
  endings: (string | null)[]
  kinds: Record<string, ChapterLink['kind']>
  toChapter: string[]
}

/** A map read from a .tmx (server: decomp/tiled.py, ticket 25). */
export interface TiledMap {
  rows: number[][]
  changes: (MapChange & { name: string })[]
  properties: Record<string, string>
}

/** A whole building of the game's maps (ticket 41): a block painted in one click. */
export interface MapPiece {
  group: 'building' | 'decor'
  kind: string
  rows: number[][]
  uses: number
  maps: string[]
}

/** A class's battle animation for a weapon type or an item (ticket 44). */
export interface ClassAnimation {
  wtype: string | null
  item: string | null
  /** the game animation's number, or "new-<key>" for one the project imported */
  ref: string
  number: number | null
  name: string
  modes: string[]
  /** empty movements of an attacking weapon -> the weapons that need them */
  empty: Record<string, string[]>
  /** imported in the project (FE-Repo) */
  imported: boolean
  /** changed by the project for this weapon type */
  changed: boolean
  /** where an animation imported from FE-Repo comes from */
  source?: FeRepoEntry | null
}

/** A battle animation's folder in FE-Repo: its files, weapons (subfolders) and preview picture. */
export interface FeRepoAnimation extends FeRepoEntry {
  files: { name: string; type: 'file' | 'dir'; url: string; size: number }[]
  weapons: string[]
  preview: string | null
}
