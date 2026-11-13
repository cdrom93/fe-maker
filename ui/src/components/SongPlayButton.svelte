<script lang="ts">
  // Listen to a song (game number or imported key) with the game's instruments; a second click stops it.
  import type { SongRef } from '../lib/api'
  import { t } from '../lib/i18n.svelte'
  import { playSong, songPlayer, stopSong } from '../lib/songplayer.svelte'

  let { song, disabled = false }: { song: SongRef | null | undefined; disabled?: boolean } = $props()

  const playing = $derived(song != null && songPlayer.playing === song)
</script>

<button type="button" class="listen" class:playing aria-pressed={playing} disabled={disabled || song == null}
  title={playing ? t('music.stop') : t('music.listen')}
  aria-label={playing ? t('music.stop') : t('music.listen')}
  onclick={() => (playing ? stopSong() : song != null && playSong(song))}>
  {#if playing && songPlayer.loading}…{:else if playing}■{:else}▶{/if}
</button>

<style>
  .listen { width: 1.9rem; height: 1.7rem; padding: 0; display: inline-grid; place-items: center; font-size: 0.8rem; flex: none; }
  .listen.playing { background: var(--accent-soft); border-color: var(--accent); color: var(--accent); }
</style>
