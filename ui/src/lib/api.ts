import { portraitVersion } from './portraits.svelte'
import type { BuildStatus, ChapterInfo, ChapterLinks, TiledMap, ChapterUnits, MapChange, MapInfo, MapLayout, MapObjects, MapObjectSettings, MapsData, Objective, TilesetEdits, DialogueFace, DialogueFont, DialogueScene, SupportPair, EventCommand, EventsReference, PortraitImport, PortraitInfo, FeRepoEntry, DialogueStep, Problem, ProjectInfo, Reference, Status, TestOptions, Ticket, TicketIn } from './types'

export type DataKind = 'characters' | 'items' | 'classes' | 'combat' | 'chapters' | 'maps' | 'dialogues' | 'portraits'

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
  createProject: (name: string, author: string) => request<ProjectInfo>('POST', '/api/projects', { name, author }),
  openProject: (path: string) => request<ProjectInfo>('POST', '/api/projects/open', { path }),
  closeProject: () => request<Status>('POST', '/api/projects/close'),
  reference: () => request<Reference>('GET', '/api/reference'),
  getData: <T>(kind: DataKind) => request<T>('GET', `/api/project/data/${kind}`),
  saveData: (kind: DataKind, records: unknown) =>
    request<{ problems: Problem[] }>('PUT', `/api/project/data/${kind}`, records),
  chapters: () => request<ChapterInfo[]>('GET', '/api/chapters'),
  chapterUnits: (index: number) => request<ChapterUnits>('GET', `/api/chapters/${index}/units`),
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
  startBuild: (launch: boolean) => request<BuildStatus>('POST', '/api/project/build', { launch }),
  buildStatus: (since: number) => request<BuildStatus>('GET', `/api/project/build?since=${since}`),
  tickets: () => request<Ticket[]>('GET', '/api/tickets'),
  createTicket: (ticket: TicketIn) => request<Ticket>('POST', '/api/tickets', ticket),
  updateTicket: (id: string, changes: Partial<Pick<Ticket, 'body' | 'status' | 'priority' | 'kind'>>) =>
    request<Ticket>('PATCH', `/api/tickets/${id}`, changes),
  deleteTicket: (id: string) => request<{ ok: boolean }>('DELETE', `/api/tickets/${id}`),
}

export const ticketImageUrl = (name: string) => `/api/tickets/images/${name}`
/** `version` changes when the project's painted layout changes (the image is not cached then). */
export const chapterMapUrl = (index: number, version = '') => `/api/chapters/${index}/map.png${version ? `?v=${version}` : ''}`
export const mapTilesetUrl = (id: string, base: string | null = null) =>
  `/api/maps/${id}/tileset.png${base ? `?base=${encodeURIComponent(base)}` : ''}`
export const mapSpriteUrl = (classId: string, side: string, trim = false) =>
  `/api/assets/map-sprite/${classId}?side=${side}${trim ? '&trim=true' : ''}`
/** `smile`, `eyes`: the dialogue face as the expression codes leave it. */
export const portraitUrl = (id: number, face = false, expression?: { smile?: boolean; eyes?: string }) =>
  `/api/assets/portrait/${id}?v=${portraitVersion.n}${face ? '&face=true' : ''}` +
  `${expression?.smile ? '&smile=true' : ''}${expression?.eyes && expression.eyes !== 'open' ? `&eyes=${expression.eyes}` : ''}`
export const portraitSheetUrl = (id: number) => `/api/portraits/${id}/sheet.png?v=${portraitVersion.n}`
export const itemIconUrl = (id: number) => `/api/assets/item-icon/${id}`
export const patchUrl = '/api/project/patch'
