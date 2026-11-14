/**
 * Favourites: FE-Repo files starred in the browsers, kept by the server in FE Maker's config dir (library.py), so the
 * same in every project. Loaded once, then changed here and on the server together.
 */
import { api, type FavoriteKind } from './api'

export const favorites = $state<{ loaded: boolean; keys: Record<string, string[]> }>({ loaded: false, keys: {} })

let loading: Promise<void> | null = null

export function loadFavorites(): Promise<void> {
  loading ??= api.favorites().then((keys) => {
    favorites.keys = keys
    favorites.loaded = true
  }).catch(() => { loading = null })
  return loading
}

export const isFavorite = (kind: FavoriteKind, key: string) => (favorites.keys[kind] ?? []).includes(key)

export async function toggleFavorite(kind: FavoriteKind, key: string): Promise<void> {
  const on = !isFavorite(kind, key)
  const before = favorites.keys[kind] ?? []
  favorites.keys[kind] = on ? [...before, key] : before.filter((k) => k !== key)
  try {
    favorites.keys[kind] = (await api.setFavorite(kind, key, on)).keys
  } catch {
    favorites.keys[kind] = before
  }
}
