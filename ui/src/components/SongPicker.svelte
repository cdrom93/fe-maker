<script lang="ts">
  // One of the project's songs or of the game's, listened to before choosing (SongPlayButton). `value` null keeps
  // the game's choice (`gameValue`); `optional` adds "none" (the game's 0xFFFF).
  import type { MusicLibrary, SongRef } from '../lib/api'
  import { t } from '../lib/i18n.svelte'
  import SongPlayButton from './SongPlayButton.svelte'

  const NO_SONG = 0xffff

  let { label, value, gameValue, library, optional = false, onchange }: {
    label: string
    value: SongRef | null
    gameValue: number
    library: MusicLibrary
    optional?: boolean
    onchange: (song: SongRef | null) => void
  } = $props()

  const current = $derived(value ?? gameValue)
  const songName = (ref: SongRef) => ref === NO_SONG ? t('music.none')
    : typeof ref === 'string' ? library.imported.find((s) => s.key === ref)?.name ?? ref
    : library.game.find((s) => s.number === ref)?.name ?? t('music.number', { n: ref })
  const encode = (ref: SongRef) => (typeof ref === 'string' ? `p:${ref}` : `g:${ref}`)

  function pick(code: string) {
    if (code === 'game') return onchange(null)
    const ref: SongRef = code.startsWith('p:') ? code.slice(2) : Number(code.slice(2))
    onchange(ref === gameValue ? null : ref)
  }
</script>

<label class="small song-picker">
  <span>{label}</span>
  <select value={value === null ? 'game' : encode(value)} onchange={(e) => pick((e.target as HTMLSelectElement).value)}>
    <option value="game">{t('music.game', { name: songName(gameValue) })}</option>
    {#if optional}<option value={encode(NO_SONG)}>{t('music.none')}</option>{/if}
    {#if library.imported.length}
      <optgroup label={t('music.projectSongs')}>
        {#each library.imported as s (s.key)}<option value={encode(s.key)}>{s.name}</option>{/each}
      </optgroup>
    {/if}
    <optgroup label={t('music.gameSongs')}>
      {#each library.game as s (s.number)}<option value={encode(s.number)}>{s.name}</option>{/each}
    </optgroup>
  </select>
  <SongPlayButton song={current === NO_SONG ? null : current} />
  {#if value !== null}<span class="edited">✎</span>{/if}
</label>

<style>
  .song-picker { flex-direction: row; align-items: center; gap: 0.4rem; color: var(--text); }
  .song-picker > span { min-width: 9.5rem; }
  .song-picker select { width: 17rem; }
  .small { font-size: 0.8rem; }
  .edited { color: var(--accent); }
</style>
