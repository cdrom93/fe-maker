import { mapSpriteVersion, portraitVersion } from './portraits.svelte'
import type { BattleColors, BuildStatus, Character, Check, ClassData, Item, ChapterInfo, ChapterLinks, TiledMap, ChapterUnits, MapChange, MapInfo, MapLayout, MapObjects, MapObjectSettings, MapPiece, ClassAnimation, FeRepoAnimation, MapsData, Objective, UnitGroup, TilesetEdits, DialogueFace, DialogueFont, DialogueScene, SupportPair, EventCommand, EventsReference, PortraitImport, PortraitInfo, FeRepoEntry, DialogueStep, Problem, ProjectInfo, Reference, Status, TestOptions, Ticket, TicketIn } from './types'

/** What a project keeps of the game (server: scope.py) */
export type ScopeRow = { id: string | number; name: string; kept: boolean }
export type ProjectScope = {
  chapters: ScopeRow[]; characters: ScopeRow[]; classes: ScopeRow[]; items: ScopeRow[]; supports: boolean
  needed: { characters: string[]; classes: string[]; items: string[] }
}

/** Options of the built game (server: decomp/gameoptions.py) */
type GameOptionsData = {
  options: Record<string, number | boolean>
  groups: Record<string, string[]>
  defaults: Record<string, { game: number; values: number[] }>
}
export type DataKind = 'characters' | 'items' | 'classes' | 'combat' | 'chapters' | 'maps' | 'dialogues' | 'portraits' | 'mapsprites'

export class ApiError extends Error {
  constructor(public status: number, public detail: string) {
    super(detail)
  }
}

async function request<T>(method: string, url: string, body?: unknown): Promise<T> {
  const init: RequestInit = { method }
  if (body instanceof FormData) {
    init.body = body
  } else if (body !== undefined) {
    init.body = JSON.stringify(body)
    init.headers = { 'Content-Type': 'application/json' }
  }
  const res = await fetch(url, init)
  if (!res.ok) {
    let detail = res.statusText
    try {
      detail = (await res.json()).detail ?? detail
    } catch {
      // not JSON
    }
    throw new ApiError(res.status, detail)
  }
  return res.json() as Promise<T>
}

export const api = {
  status: () => request<Status>('GET', '/api/status'),
  updateSettings: (s: { language?: string; mgbaPath?: string; keys?: Record<string, string> }) => request<Status>('PUT', '/api/settings', s),
  uploadRom: (file: File) => {
    const form = new FormData()
    form.append('file', file)
    return request<Status>('POST', '/api/rom', form)
  },
  createProject: (name: string, author: string, blank?: { characters: boolean; title: string; hero: string }) =>
    request<ProjectInfo>('POST', '/api/projects', { name, author, blank }),
  portraitColors: (classId: string, portrait: number, line: number) =>
    request<{ colours: string[] }>('GET', `/api/classes/${classId}/portrait-colors?portrait=${portrait}&line=${line}`),
  battleColors: (character: string, classId: string) => request<BattleColors>('GET', `/api/characters/${character}/battle-colors/${classId}`),
  openProject: (path: string) => request<ProjectInfo>('POST', '/api/projects/open', { path }),
  closeProject: () => request<Status>('POST', '/api/projects/close'),
  checks: () => request<Check[]>('GET', '/api/checks'),
  projectScope: () => request<ProjectScope>('GET', '/api/project/scope'),
  applyProjectScope: (kept: { chapters: number[]; characters: string[]; classes: string[]; items: string[]; supports: boolean; title: string; hero: string }) =>
    request<{ backup: string; forced: Record<string, string[]> }>('POST', '/api/project/scope', kept),
  chapterReach: (index: number, units: { classId: string; x: number; y: number; items: string[]; ai?: number[] }[]) =>
    request<{ move: [number, number][]; strike: [number, number][] }>('POST', `/api/chapters/${index}/reach`, { units }),
  downloadDecomp: () => request<Check[]>('POST', '/api/decomp/download'),
  reference: () => request<Reference>('GET', '/api/reference'),
  getData: <T>(kind: DataKind) => request<T>('GET', `/api/project/data/${kind}`),
  saveData: (kind: DataKind, records: unknown) =>
    request<{ problems: Problem[] }>('PUT', `/api/project/data/${kind}`, records),
  newClass: (model: string) => request<ClassData>('POST', '/api/classes/new', { model }),
  newItem: (model: string) => request<Item>('POST', '/api/items/new', { model }),
  newCharacter: (ally: boolean) =>
    request<{ record: Character; replaces: string | null }>('POST', '/api/characters/new', { ally }),
  gameOptions: () => request<GameOptionsData>('GET', '/api/project/game-options'),
  setGameOptions: (options: Record<string, number | boolean>) => request<GameOptionsData>('PUT', '/api/project/game-options', options),
  chapters: () => request<ChapterInfo[]>('GET', '/api/chapters'),
  newChapter: (after: number, width: number, height: number, title: string) =>
    request<{ index: number; problems: Problem[] }>('POST', '/api/chapters/new', { after, width, height, title }),
  freeChapters: () => request<{ free: number }>('GET', '/api/chapters/free'),
  chapterMusic: (index: number) => request<Record<string, { key: string; name?: string }>>('GET', `/api/chapters/${index}/music`),
  importChapterMusic: (index: number, file: File) => {
    const form = new FormData()
    form.append('file', file)
    return request<{ problems: Problem[] }>('POST', `/api/chapters/${index}/music`, form)
  },
  removeChapterMusic: (index: number, phase: string) =>
    request<{ problems: Problem[] }>('DELETE', `/api/chapters/${index}/music/${phase}`),
  chapterUnits: (index: number) => request<ChapterUnits>('GET', `/api/chapters/${index}/units`),
  chaptersOverview: () =>
    request<Record<string, { objective: Objective | null; groups: Pick<UnitGroup, 'name' | 'origin' | 'units'>[] }>>('GET', '/api/chapters/overview'),
  chapterObjective: (index: number) => request<Objective>('GET', `/api/chapters/${index}/objective`),
  maps: () => request<MapInfo[]>('GET', '/api/maps'),
  chapterDialogues: (index: number) =>
    request<{ scenes: DialogueScene[]; messages: Record<string, DialogueStep[]> }>('GET', `/api/chapters/${index}/dialogues`),
  dialogueFaces: () => request<DialogueFace[]>('GET', '/api/dialogues/faces'),
  dialogueFont: () => request<DialogueFont>('GET', '/api/dialogues/font'),
  portrait: (id: number) => request<PortraitInfo>('GET', `/api/portraits/${id}`),
  importPortrait: (id: number, file: File) => {
    const form = new FormData()
    form.append('file', file)
    return request<{ entry: PortraitImport; problems: Problem[] }>('POST', `/api/portraits/${id}`, form)
  },
  addPortrait: (file: File) => {
    const form = new FormData()
    form.append('file', file)
    return request<{ id: number; entry: PortraitImport; problems: Problem[] }>('POST', '/api/portraits/new', form)
  },
  addFeRepoPortrait: (url: string) =>
    request<{ id: number; entry: PortraitImport; problems: Problem[] }>('POST', '/api/portraits/new/ferepo', { url }),
  renamePortrait: (id: number, name: string) =>
    request<{ entry: PortraitImport; problems: Problem[] }>('PATCH', `/api/portraits/${id}`, { name }),
  importFeRepoPortrait: (id: number, url: string) =>
    request<{ entry: PortraitImport; problems: Problem[] }>('POST', `/api/portraits/${id}/ferepo`, { url }),
  feRepoPortraits: (q: string, options: { refresh?: boolean; folder?: string; offset?: number; f2e?: boolean } = {}) =>
    request<{ entries: FeRepoEntry[]; total: number; indexDate: number; folders: { name: string; count: number }[] }>(
      'GET', `/api/ferepo/portraits?q=${encodeURIComponent(q)}&folder=${encodeURIComponent(options.folder ?? '')}`
        + `&offset=${options.offset ?? 0}${options.f2e ? '&f2e=true' : ''}${options.refresh ? '&refresh=true' : ''}`),
  feRepoMapSprites: (q: string, options: { refresh?: boolean; folder?: string; offset?: number; f2e?: boolean } = {}) =>
    request<{ entries: FeRepoEntry[]; total: number; indexDate: number; folders: { name: string; count: number }[] }>(
      'GET', `/api/ferepo/mapsprites?q=${encodeURIComponent(q)}&folder=${encodeURIComponent(options.folder ?? '')}`
        + `&offset=${options.offset ?? 0}${options.f2e ? '&f2e=true' : ''}${options.refresh ? '&refresh=true' : ''}`),
  importFeRepoMapSprite: (classId: string, stand: string, walk: string | null) =>
    request<{ problems: Problem[] }>('POST', `/api/classes/${classId}/mapsprite/ferepo`, { stand, walk }),
  importLocalMapSprite: (classId: string, stand: File, walk: File | null) => {
    const form = new FormData()
    form.append('stand', stand)
    if (walk) form.append('walk', walk)
    return request<{ problems: Problem[] }>('POST', `/api/classes/${classId}/mapsprite`, form)
  },
  removeMapSprite: (classId: string) => request<{ problems: Problem[] }>('DELETE', `/api/classes/${classId}/mapsprite`),
  feRepoAnimations: (q: string, options: { refresh?: boolean; folder?: string; offset?: number; f2e?: boolean; wtype?: string } = {}) =>
    request<{ entries: FeRepoEntry[]; total: number; indexDate: number; folders: { name: string; count: number }[]; missingFolders?: number }>(
      'GET', `/api/ferepo/animations?q=${encodeURIComponent(q)}&folder=${encodeURIComponent(options.folder ?? '')}`
        + `&offset=${options.offset ?? 0}${options.f2e ? '&f2e=true' : ''}${options.refresh ? '&refresh=true' : ''}`
        + `&wtype=${encodeURIComponent(options.wtype ?? '')}`),
  importAnimation: (body: { url: string; animation: string; classId: string; wtype: string }) =>
    request<{ key: string; problems: Problem[] }>('POST', '/api/animations/import', body),
  importLocalAnimation: (classId: string, wtype: string, name: string, files: File[]) => {
    const form = new FormData()
    form.append('classId', classId)
    form.append('wtype', wtype)
    form.append('name', name)
    for (const file of files) form.append('files', file)
    return request<{ key: string; problems: Problem[] }>('POST', '/api/animations/import/local', form)
  },
  removeAnimation: (key: string) => request<{ problems: Problem[] }>('DELETE', `/api/animations/project/${key}`),
  setClassAnimation: (classId: string, wtype: string, animation: string | number | null) =>
    request<{ problems: Problem[] }>('PUT', `/api/classes/${classId}/animations`, { wtype, animation }),
  feRepoAnimation: (url: string) => request<FeRepoAnimation>('GET', `/api/ferepo/animation?url=${encodeURIComponent(url)}`),
  removePortrait: (id: number) => request<{ problems: Problem[] }>('DELETE', `/api/portraits/${id}`),
  eventsReference: () => request<EventsReference>('GET', '/api/events/reference'),
  chapterLinks: () => request<ChapterLinks>('GET', '/api/chapters/links'),
  eventScript: (name: string) => request<{ name: string; file: string; commands: EventCommand[] }>('GET', `/api/events/scripts/${name}`),
  supportDialogues: () =>
    request<{ pairs: SupportPair[]; scenes: DialogueScene[]; messages: Record<string, DialogueStep[]>; levelPoints: number[]; maxPartners: number }>(
      'GET', '/api/dialogues/supports'),
  commonDialogues: () => request<{ scenes: DialogueScene[]; messages: Record<string, DialogueStep[]> }>('GET', '/api/dialogues/common'),
  map: (id: string, base: string | null = null) =>
    request<MapLayout>('GET', `/api/maps/${id}${base ? `?base=${encodeURIComponent(base)}` : ''}`),
  convertMap: (id: string, body: { rows: number[][]; changes: MapChange[] | null; base: string | null; to: string; edits: TilesetEdits | null }) =>
    request<{ rows: number[][]; changes: MapChange[]; missingTerrains: number[] }>('POST', `/api/maps/${id}/convert`, body),
  classAnimations: (classId: string) => request<ClassAnimation[]>('GET', `/api/classes/${classId}/animations`),
  animationMode: (number: number | string, mode: string, palette = 0) =>
    request<{ durations: number[]; width: number; height: number }>('GET', `/api/animations/${number}/${mode}.json?palette=${palette}`),
  mapBrushes: (id: string, base: string | null = null) =>
    request<{ brushes: { terrain: number; tile: number }[] }>('GET', `/api/maps/${id}/brushes${base ? `?base=${encodeURIComponent(base)}` : ''}`),
  mapAutotile: (id: string, body: { rows: number[][]; cells: [number, number][]; base: string | null }) =>
    request<{ rows: number[][] }>('POST', `/api/maps/${id}/autotile`, body),
  mapFill: (id: string, body: { rows: number[][]; keep: [number, number][]; base: string | null }) =>
    request<{ rows: number[][] }>('POST', `/api/maps/${id}/fill`, body),
  mapPieces: (id: string, base: string | null = null) =>
    request<{ pieces: MapPiece[] }>('GET', `/api/maps/${id}/pieces${base ? `?base=${encodeURIComponent(base)}` : ''}`),
  mapObjects: (id: string, body: { rows: number[][]; changes: MapChange[] | null; objects: Record<string, MapObjectSettings>; tileset: TilesetEdits | null; base: string | null }) =>
    request<MapObjects>('POST', `/api/maps/${id}/objects`, body),
  /** Tiled (ticket 25): write the map in the project's tiled/ folder and open Tiled; read it back; read any .tmx */
  exportTiled: (id: string, body: { rows: number[][]; changes: MapChange[] | null; edits: TilesetEdits | null; palette: string | null; base: string | null }) =>
    request<{ path: string; launched: boolean; modified: number }>('POST', `/api/maps/${id}/tiled`, body),
  importTiled: (id: string) => request<TiledMap & { modified: number }>('GET', `/api/maps/${id}/tiled`),
  readTmx: (id: string, text: string) => request<TiledMap>('POST', `/api/maps/${id}/tiled/read`, { text }),
  mapTileset: (id: string, edits: TilesetEdits | null, palette: string | null, base: string | null) =>
    request<{ sheet: string; terrains: number[]; duplicates: boolean[] }>('POST', `/api/maps/${id}/tileset`, { edits, palette, base }),
  transformTiles: (id: string, body: {
    rows: number[][]; op: string; terrain?: number; edits: TilesetEdits | null; painted: MapsData['layouts']; bases: Record<string, string>
  }) =>
    request<{ rows: number[][]; edits: TilesetEdits; tileset: string; similar: number[][] | null }>('POST', `/api/maps/${id}/transform`, body),
  problems: () => request<{ problems: Problem[] }>('GET', '/api/project/problems'),
  testOptions: () => request<TestOptions>('GET', '/api/project/test-options'),
  setTestOptions: (o: Partial<TestOptions>) => request<TestOptions>('PUT', '/api/project/test-options', o),
  worldMap: () => request<{ worldMap: boolean }>('GET', '/api/project/world-map'),
  setWorldMap: (worldMap: boolean) => request<{ worldMap: boolean }>('PUT', '/api/project/world-map', { worldMap }),
  startBuild: (launch: boolean) => request<BuildStatus>('POST', '/api/project/build', { launch }),
  buildStatus: (since: number) => request<BuildStatus>('GET', `/api/project/build?since=${since}`),
  tickets: () => request<Ticket[]>('GET', '/api/tickets'),
  createTicket: (ticket: TicketIn) => request<Ticket>('POST', '/api/tickets', ticket),
  updateTicket: (id: string, changes: Partial<Pick<Ticket, 'body' | 'status' | 'priority' | 'kind'>>) =>
    request<Ticket>('PATCH', `/api/tickets/${id}`, changes),
  deleteTicket: (id: string) => request<{ ok: boolean }>('DELETE', `/api/tickets/${id}`),
  addTicketComment: (id: string, comment: { body: string; images: string[] }) =>
    request<Ticket>('POST', `/api/tickets/${id}/comments`, comment),
  deleteTicketComment: (id: string, commentId: string) => request<Ticket>('DELETE', `/api/tickets/${id}/comments/${commentId}`),
}

export const ticketImageUrl = (name: string) => `/api/tickets/images/${name}`
/** `version` changes when the project's painted layout changes (the image is not cached then). */
export const chapterMapUrl = (index: number, version = '') => `/api/chapters/${index}/map.png${version ? `?v=${version}` : ''}`
export const animationUrl = (number: number | string, mode: string, palette = 0, colors?: string[]) =>
  `/api/animations/${number}/${mode}.png?palette=${palette}${colors ? `&colors=${colors.map((c) => c.slice(1)).join(',')}` : ''}`
export const mapTilesetUrl = (id: string, base: string | null = null) =>
  `/api/maps/${id}/tileset.png${base ? `?base=${encodeURIComponent(base)}` : ''}`
export const mapSpriteUrl = (classId: string, side: string, trim = false) =>
  `/api/assets/map-sprite/${classId}?side=${side}${trim ? '&trim=true' : ''}&v=${mapSpriteVersion.n}`
/** `smile`, `eyes`: the dialogue face as the expression codes leave it. */
export const portraitUrl = (id: number, face = false, expression?: { smile?: boolean; eyes?: string }) =>
  `/api/assets/portrait/${id}?v=${portraitVersion.n}${face ? '&face=true' : ''}` +
  `${expression?.smile ? '&smile=true' : ''}${expression?.eyes && expression.eyes !== 'open' ? `&eyes=${expression.eyes}` : ''}`
export const portraitSheetUrl = (id: number) => `/api/portraits/${id}/sheet.png?v=${portraitVersion.n}`
export const itemIconUrl = (id: number, line = 0) => `/api/assets/item-icon/${id}${line ? `?line=${line}` : ''}`
export const patchUrl = '/api/project/patch'
