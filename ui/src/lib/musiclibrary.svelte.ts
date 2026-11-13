// The project's and the game's songs, read once and shared by the editors that name songs (server: GET /api/music).
// Event commands name a song by its SONG_ constant, or an imported one by SCENE_PREFIX + its key (music.py).
import { api, type MusicLibrary, type SongRef } from './api'

export const SCENE_PREFIX = 'FEM_SONG_'

export const musicLibrary = $state<{ value: MusicLibrary | null }>({ value: null })
let loading: Promise<MusicLibrary> | null = null

export function loadMusicLibrary(force = false): Promise<MusicLibrary> {
  if (force || !loading) {
    loading = api.musicLibrary().then((l) => (musicLibrary.value = l))
    loading.catch(() => (loading = null))
  }
  return loading
}

/** The song an event command's argument names, to listen to it: a game number or an imported key. */
export function sceneSongRef(arg: string): SongRef | null {
  if (arg.startsWith(SCENE_PREFIX)) return arg.slice(SCENE_PREFIX.length)
  return musicLibrary.value?.game.find((s) => s.constant === arg)?.number ?? null
}

/** A readable name for an event command's song argument, or null when the library does not know it. */
export function sceneSongName(arg: string): string | null {
  const lib = musicLibrary.value
  if (!lib) return null
  if (arg.startsWith(SCENE_PREFIX)) return lib.imported.find((s) => s.key === arg.slice(SCENE_PREFIX.length))?.name ?? null
  return lib.game.find((s) => s.constant === arg)?.name ?? null
}
