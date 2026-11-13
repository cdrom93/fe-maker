<script lang="ts">
  // The Music tab: the project's songs (MIDI files from the PC, with the instruments of one of the game's songs)
  // and the game's, all heard here with the game's instruments (lib/songplayer.svelte.ts). Chapters choose theirs in
  // their settings (ChapterMusic). Server: decomp/music.py.
  import { api, type BattleMusic, type MusicLibrary, type ScreenMusic, type SongRef } from '../lib/api'
  import { t } from '../lib/i18n.svelte'
  import { loadMusicLibrary } from '../lib/musiclibrary.svelte'
  import { songPlayer } from '../lib/songplayer.svelte'
  import Help from './Help.svelte'
  import NumberField from './NumberField.svelte'
  import SongPicker from './SongPicker.svelte'
  import SongPlayButton from './SongPlayButton.svelte'

  let library = $state<MusicLibrary | null>(null)
  let battle = $state<BattleMusic | null>(null)
  let screens = $state<ScreenMusic | null>(null)
  const SCREEN_SLOTS = ['intro', 'title', 'storyIntro', 'preparations', 'prepSupports', 'shop', 'armory', 'arenaMenu',
                        'arenaVictory', 'allyDeath', 'gameOver', 'epilogue', 'credits', 'supportViewer', 'dungeonRecord']
  const BATTLE_SLOTS = ['playerAttacks', 'enemyAttacks', 'healStaff', 'statusStaff', 'dance', 'promotion', 'arena']
  let error = $state('')
  const NIMAP = 'nimap'   // server: nimap.KEY, General MIDI order
  let busy = $state(false)
  let input: HTMLInputElement | undefined = $state()

  async function load() {
    try {
      ;[library, battle, screens] = await Promise.all([loadMusicLibrary(true), api.battleMusic(), api.screenMusic()])
    } catch (e) {
      error = String(e)
    }
  }
  load()

  /** Each instrument set named after the first game song that plays with it. */
  const setNames = $derived.by(() => {
    const names = new Map<number, string>()
    for (const s of library?.game ?? []) if (!names.has(s.voicegroup)) names.set(s.voicegroup, s.name)
    return names
  })

  async function importFile(file: File | undefined) {
    if (!file) return
    error = ''
    busy = true
    try {
      await api.importMusic(file)
      await load()
    } catch (e) {
      error = String(e).includes('notAMidi') ? t('music.notAMidi') : String(e)
    } finally {
      busy = false
      if (input) input.value = ''
    }
  }

  async function edit(key: string, body: { name?: string; voicegroup?: number | string; volume?: number }) {
    error = ''
    try {
      await api.editMusic(key, body)
      await load()
    } catch (e) {
      error = String(e)
    }
  }

  async function setBattle(slot: string, song: SongRef | null) {
    error = ''
    try {
      await api.setBattleMusic({ slot, song })
      battle = await api.battleMusic()
    } catch (e) {
      error = String(e)
    }
  }

  async function setScreen(slot: string, song: SongRef | null) {
    error = ''
    try {
      await api.setScreenMusic({ slot, song })
      screens = await api.screenMusic()
    } catch (e) {
      error = String(e)
    }
  }

  async function remove(key: string, name: string) {
    if (!confirm(t('music.removeConfirm', { name }))) return
    error = ''
    try {
      await api.removeMusic(key)
    } catch (e) {
      error = String(e).includes('songInScene') ? t('music.songInScene', { name }) : String(e)
    }
    await load()
  }
</script>

<div class="music-page">
  <section class="panel">
    <div class="head">
      <h3>{t('music.projectSongs')} <Help text={t('music.projectHint')} /></h3>
      <button onclick={() => input?.click()} disabled={busy}>{t('music.import')}</button>
      <input type="file" accept=".mid,.midi,audio/midi" hidden bind:this={input}
             onchange={(e) => importFile((e.target as HTMLInputElement).files?.[0])} />
    </div>
    {#if error}<p class="bad small">{error}</p>{/if}
    {#if songPlayer.error}<p class="bad small">{t('music.playError', { error: songPlayer.error })}</p>{/if}
    {#if library && library.imported.length}
      <table class="songs">
        <thead>
          <tr>
            <th></th><th>{t('music.name')}</th>
            <th>{t('music.instruments')} <Help text={t('music.instrumentsHint')} /></th>
            <th></th><th></th>
          </tr>
        </thead>
        <tbody>
          {#each library.imported as s (s.key)}
            <tr>
              <td><SongPlayButton song={s.key} /></td>
              <td><input value={s.name} aria-label={t('music.name')} onchange={(e) => edit(s.key, { name: (e.target as HTMLInputElement).value })} />{#if (s.tracks ?? 0) > library.maxTracks}<span class="warn" title={t('music.tooManyTracks', { n: s.tracks ?? 0, max: library.maxTracks })}> ⚠</span>{/if}</td>
              <td>
                <select value={s.voicegroup} aria-label={t('music.instruments')}
                        onchange={(e) => { const v = (e.target as HTMLSelectElement).value; edit(s.key, { voicegroup: v === NIMAP ? v : Number(v) }) }}>
                  <option value={NIMAP}>{t('music.nimap')}</option>
                  {#each library.voicegroups as n (n)}
                    <option value={n}>{setNames.has(n) ? t('music.instrumentsOf', { name: setNames.get(n)! }) : t('music.instrumentSet', { n })}</option>
                  {/each}
                </select>
              </td>
              <td><NumberField label={t('music.volume')} value={s.volume} min={0} max={127} compact inline onchange={(v) => edit(s.key, { volume: v })} /></td>
              <td><button class="icon" title={t('music.remove')} aria-label={t('music.remove')} onclick={() => remove(s.key, s.name)}>✕</button></td>
            </tr>
          {/each}
        </tbody>
      </table>
    {:else if library}
      <p class="muted small">{t('music.noneImported')}</p>
    {/if}
  </section>

  <section class="panel">
    <h3>{t('music.battleTitle')} <Help text={t('music.battleHint')} /></h3>
    {#if library && battle}
      <div class="battle">
        {#each BATTLE_SLOTS.filter((slot) => slot in battle!.game) as slot (slot)}
          <SongPicker label={t(`music.battle.${slot}`)} value={battle.chosen[slot] ?? null} gameValue={battle.game[slot]} {library}
                      onchange={(song) => setBattle(slot, song)} />
        {/each}
      </div>
    {/if}
  </section>

  <section class="panel">
    <h3>{t('music.screensTitle')} <Help text={t('music.screensHint')} /></h3>
    {#if library && screens}
      <div class="battle">
        {#each SCREEN_SLOTS.filter((slot) => slot in screens!.game) as slot (slot)}
          <SongPicker label={t(`music.screen.${slot}`)} value={screens.chosen[slot] ?? null} gameValue={screens.game[slot]} {library}
                      onchange={(song) => setScreen(slot, song)} />
        {/each}
      </div>
    {/if}
  </section>

  <section class="panel">
    <h3>{t('music.gameSongs')} <Help text={t('music.gameHint')} /></h3>
    {#if library}
      <ul class="game-songs">
        {#each library.game as s (s.number)}
          <li><SongPlayButton song={s.number} /> <span>{s.name}</span> <span class="muted tiny">{s.number}</span></li>
        {/each}
      </ul>
    {/if}
  </section>
</div>

<style>
  .music-page { display: flex; flex-direction: column; gap: 1rem; max-width: 70rem; }
  .head { display: flex; align-items: center; gap: 0.8rem; }
  .head h3 { margin: 0; flex: 1; }
  .songs { border-collapse: collapse; margin-top: 0.6rem; }
  .songs th { text-align: left; font-size: 0.8rem; font-weight: 600; color: var(--muted); padding: 0 0.4rem 0.3rem; }
  .songs td { padding: 0.15rem 0.4rem; vertical-align: middle; }
  .songs select { width: auto; max-width: 20rem; }
  .icon { border: none; background: none; padding: 0 0.3rem; color: var(--muted); }
  .icon:hover { color: var(--bad); }
  .game-songs { list-style: none; margin: 0.6rem 0 0; padding: 0; columns: 3 16rem; column-gap: 1.5rem; }
  .game-songs li { display: flex; align-items: center; gap: 0.4rem; padding: 0.12rem 0; break-inside: avoid; font-size: 0.9rem; }
  .battle { display: flex; flex-direction: column; gap: 0.35rem; margin-top: 0.6rem; }
  .bad { color: var(--bad); margin: 0.4rem 0 0; }
  .warn { color: var(--warn); cursor: help; }
  .small { font-size: 0.8rem; }
  .tiny { font-size: 0.7rem; }
</style>
