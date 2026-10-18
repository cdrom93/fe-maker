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
}

export interface ClassInfo {
  id: string
  name: string
  bases: Record<StatKey, number>
  mov: number
}

export interface Reference {
  classes: ClassInfo[]
  weaponTypes: string[]
  rankableTypes: string[]
  ranks: string[]
  iconCount: number
  portraits: (string | null)[]
}

export interface Problem {
  severity: 'error' | 'warning'
  kind: 'characters' | 'items'
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
  language: 'fr' | 'en'
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
