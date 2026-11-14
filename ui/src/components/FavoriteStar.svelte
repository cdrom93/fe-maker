<script lang="ts">
  // The star of a FE-Repo file in the browsers: on, the file is one of the user's favourites (lib/favorites.svelte.ts),
  // found again with the "Favourites" filter, in every project.
  import { t } from '../lib/i18n.svelte'
  import type { FavoriteKind } from '../lib/api'
  import { favorites, isFavorite, loadFavorites, toggleFavorite } from '../lib/favorites.svelte'

  let { kind, key }: { kind: FavoriteKind; key: string } = $props()

  $effect(() => { if (!favorites.loaded) loadFavorites() })

  const on = $derived(isFavorite(kind, key))
</script>

<button type="button" class="star" class:on aria-pressed={on} title={t(on ? 'favorites.remove' : 'favorites.add')}
        aria-label={t(on ? 'favorites.remove' : 'favorites.add')}
        onclick={(e) => { e.stopPropagation(); toggleFavorite(kind, key) }}>{on ? '★' : '☆'}</button>

<style>
  .star { border: none; background: none; padding: 0 0.15rem; font-size: 1rem; line-height: 1; color: var(--muted); cursor: pointer; flex: none; }
  .star.on { color: var(--warn); }
  .star:hover { color: var(--warn); }
</style>
