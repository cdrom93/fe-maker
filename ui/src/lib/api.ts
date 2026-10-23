import type { BuildStatus, ChapterInfo, ChapterUnits, Problem, ProjectInfo, Reference, Status, Ticket, TicketIn } from './types'

export type DataKind = 'characters' | 'items' | 'classes' | 'combat' | 'chapters'

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
  problems: () => request<{ problems: Problem[] }>('GET', '/api/project/problems'),
  testOptions: () => request<{ start: string }>('GET', '/api/project/test-options'),
  setTestOptions: (o: { start?: string }) => request<{ start: string }>('PUT', '/api/project/test-options', o),
  startBuild: (launch: boolean) => request<BuildStatus>('POST', '/api/project/build', { launch }),
  buildStatus: (since: number) => request<BuildStatus>('GET', `/api/project/build?since=${since}`),
  tickets: () => request<Ticket[]>('GET', '/api/tickets'),
  createTicket: (ticket: TicketIn) => request<Ticket>('POST', '/api/tickets', ticket),
  updateTicket: (id: string, changes: Partial<Pick<Ticket, 'body' | 'status' | 'priority' | 'kind'>>) =>
    request<Ticket>('PATCH', `/api/tickets/${id}`, changes),
  deleteTicket: (id: string) => request<{ ok: boolean }>('DELETE', `/api/tickets/${id}`),
}

export const ticketImageUrl = (name: string) => `/api/tickets/images/${name}`
export const chapterMapUrl = (index: number) => `/api/chapters/${index}/map.png`
export const mapSpriteUrl = (classId: string, side: string, trim = false) =>
  `/api/assets/map-sprite/${classId}?side=${side}${trim ? '&trim=true' : ''}`
export const portraitUrl = (id: number) => `/api/assets/portrait/${id}`
export const itemIconUrl = (id: number) => `/api/assets/item-icon/${id}`
export const patchUrl = '/api/project/patch'
