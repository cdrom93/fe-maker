<script lang="ts">
  // A chapter's songs (server: decomp/music.py, the chapter settings' mapBgmIds): each phase, the variants played
  // once the event flag 4 is set, the opening, and the victory theme when few enemies are left.
  import { api, type ChapterMusic, type MusicLibrary, type SongRef } from '../lib/api'
  import { t } from '../lib/i18n.svelte'
  import Help from './Help.svelte'
  import NumberField from './NumberField.svelte'
  import SongPicker from './SongPicker.svelte'

  let { index }: { index: number } = $props()

  const MAIN = ['bluePhase', 'redPhase', 'greenPhase', 'prologue']
  const VARIANTS = ['blueGreenPhaseAlt', 'redPhaseAlt']
  const OPTIONAL = ['blueGreenPhaseAlt', 'redPhaseAlt', 'prologue']

  let library = $state<MusicLibrary | null>(null)
  let music = $state<ChapterMusic | null>(null)
  let error = $state('')

  $effect(() => {
    const i = index
    music = null
    Promise.all([api.musicLibrary(), api.chapterMusic(i)])
      .then(([l, m]) => { if (index === i) { library = l; music = m } })
      .catch((e) => (error = String(e)))
  })

  async function set(body: { slot?: string; song?: SongRef | null; victory?: number; resetVictory?: boolean }) {
    error = ''
    const i = index
    try {
      await api.setChapterMusic(i, body)
      music = await api.chapterMusic(i)
    } catch (e) {
      error = String(e)
    }
  }
</script>

<div class="chapter-music">
  <h3>{t('music.chapterTitle')} <Help text={t('music.chapterHint')} /></h3>
  {#if library && music}
    {#each MAIN as slot (slot)}
      <SongPicker label={t(`music.slot.${slot}`)} value={music.chosen[slot] ?? null} gameValue={music.game[slot]} {library}
                  optional={OPTIONAL.includes(slot)} onchange={(song) => set({ slot, song })} />
    {/each}
    <div class="row victory">
      <NumberField label={t('music.victory')} hint={t('music.victoryHint')} value={music.victory ?? music.gameVictory}
                   min={0} max={127} compact inline
                   onchange={(v) => set(v === music!.gameVictory ? { resetVictory: true } : { victory: v })} />
      {#if music.victory !== null && music.victory !== undefined}<span class="edited">✎</span>{/if}
    </div>
    <div class="music-title">
      <span class="small">{t('music.variants')}</span>
      <Help text={t('music.variantsHint')} />
    </div>
    {#each VARIANTS as slot (slot)}
      <SongPicker label={t(`music.slot.${slot}`)} value={music.chosen[slot] ?? null} gameValue={music.game[slot]} {library}
                  optional onchange={(song) => set({ slot, song })} />
    {/each}
  {:else if !error}
    <span class="muted small">…</span>
  {/if}
  {#if error}<p class="bad small">{error}</p>{/if}
</div>

<style>
  .chapter-music { display: flex; flex-direction: column; gap: 0.35rem; }
  h3 { margin: 0 0 0.4rem; }
  .music-title { display: flex; align-items: center; gap: 0.4rem; margin: 0.8rem 0 0.2rem; }
  .victory { display: flex; align-items: center; gap: 0.4rem; min-height: 2rem; }
  .edited { color: var(--accent); }
  .bad { color: var(--bad); margin: 0; }
  .small { font-size: 0.8rem; }
</style>
