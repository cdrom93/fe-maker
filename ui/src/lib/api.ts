import type { BuildStatus, ChapterInfo, ChapterUnits, MapChange, MapInfo, MapLayout, MapObjects, MapObjectSettings, MapsData, Objective, TilesetEdits, DialogueFace, DialogueFont, DialogueScene, SupportPair, DialogueStep, Problem, ProjectInfo, Reference, Status, TestOptions, Ticket, TicketIn } from './types'

export type DataKind = 'characters' | 'items' | 'classes' | 'combat' | 'chapters' | 'maps' | 'dialogues'

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
  supportDialogues: () =>
    request<{ pairs: SupportPair[]; scenes: DialogueScene[]; messages: Record<string, DialogueStep[]>; levelPoints: number[]; maxPartners: number }>(
      'GET', '/api/dialogues/supports'),
  commonDialogues: () => request<{ scenes: DialogueScene[]; messages: Record<string, DialogueStep[]> }>('GET', '/api/dialogues/common'),
  map: (id: string) => request<MapLayout>('GET', `/api/maps/${id}`),
  mapObjects: (id: string, body: { rows: number[][]; changes: MapChange[] | null; objects: Record<string, MapObjectSettings>; tileset: TilesetEdits | null }) =>
    request<MapObjects>('POST', `/api/maps/${id}/objects`, body),
  mapTileset: (id: string, edits: TilesetEdits | null, palette: string | null) =>
    request<{ sheet: string; terrains: number[]; duplicates: boolean[] }>('POST', `/api/maps/${id}/tileset`, { edits, palette }),
  transformTiles: (id: string, body: { rows: number[][]; op: string; terrain?: number; edits: TilesetEdits | null; painted: MapsData['layouts'] }) =>
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
export const mapTilesetUrl = (id: string) => `/api/maps/${id}/tileset.png`
export const mapSpriteUrl = (classId: string, side: string, trim = false) =>
  `/api/assets/map-sprite/${classId}?side=${side}${trim ? '&trim=true' : ''}`
export const portraitUrl = (id: number, face = false) => `/api/assets/portrait/${id}${face ? '?face=true' : ''}`
export const itemIconUrl = (id: number) => `/api/assets/item-icon/${id}`
export const patchUrl = '/api/project/patch'
