<script lang="ts">
  // Songs of FE-Repo-Music (server: ferepo_music.py): browse by folder, search, listen to their recorded preview;
  // "Use" imports one into the project (converted to MIDI, General MIDI instruments). Same look as FeRepoBrowser.
  import { onDestroy, untrack } from 'svelte'
  import { api, ApiError, type FeRepoSong } from '../lib/api'
  import { t } from '../lib/i18n.svelte'
  import { stopSong } from '../lib/songplayer.svelte'

  let { busy = false, onpick }: { busy?: boolean; onpick: (e: FeRepoSong) => void } = $props()

  let query = $state('')
  let folder = $state('')
  let entries = $state<FeRepoSong[]>([])
  let folders = $state<{ name: string; count: number }[]>([])
  let total = $state(0)
  let indexDate = $state(0)
  let loading = $state(false)
  let error = $state('')
  let playing = $state('')
  let timer: ReturnType<typeof setTimeout> | undefined
  let request = 0
  const audio = new Audio()
  audio.onended = () => (playing = '')
  audio.onerror = () => { if (playing) error = t('ferepoMusic.previewError'); playing = '' }
  onDestroy(() => audio.pause())

  async function run(refresh = false, more = false) {
    const n = ++request
    loading = true
    error = ''
    try {
      const r = await api.feRepoMusic(query, { refresh, folder, offset: more ? entries.length : 0 })
      if (n !== request) return
      entries = more ? [...entries, ...r.entries] : r.entries
      total = r.total
      indexDate = r.indexDate
      folders = r.folders
    } catch (e) {
      if (n === request) error = e instanceof ApiError ? t(`ferepo.error.${e.detail}`) : String(e)
    } finally {
      if (n === request) loading = false
    }
  }

  $effect(() => {
    untrack(() => run())
  })

  function typed() {
    clearTimeout(timer)
    timer = setTimeout(() => run(), 350)
  }

  function listen(e: FeRepoSong) {
    if (playing === e.path) {
      audio.pause()
      playing = ''
      return
    }
    stopSong()
    audio.src = `/api/ferepo/music/preview?path=${encodeURIComponent(e.preview!)}`
    playing = e.path
    audio.play().catch(() => (playing = ''))
  }
</script>

<div class="browser">
  <div class="bar">
    <select bind:value={folder} onchange={() => run()} aria-label={t('ferepo.folder')}>
      <option value="">{t('ferepo.allFolders')}</option>
      {#each folders as f (f.name)}<option value={f.name}>{f.name} ({f.count})</option>{/each}
    </select>
    <input bind:value={query} oninput={typed} placeholder={t('ferepoMusic.search')} />
    <button onclick={() => run(true)} disabled={loading} title={t('ferepoMusic.refreshHint')}>⟳</button>
  </div>
  <p class="muted tiny">
    {t('ferepoMusic.hint')}
    {#if indexDate}· {t('ferepo.indexDate', { date: new Date(indexDate * 1000).toLocaleDateString() })}{/if}
  </p>
  {#if error}<p class="bad small">{error}</p>{/if}
  {#if !error}<p class="muted tiny">{loading && !entries.length ? t('ferepoMusic.loading') : t('ferepoMusic.count', { shown: entries.length, total })}</p>{/if}
  <ul class="list">
    {#each entries as e (e.path)}
      <li>
        <button type="button" class="listen" class:playing={playing === e.path} disabled={!e.preview}
                title={!e.preview ? t('ferepoMusic.noPreview') : playing === e.path ? t('music.stop') : t('ferepoMusic.listen')}
                aria-label={playing === e.path ? t('music.stop') : t('ferepoMusic.listen')}
                onclick={() => listen(e)}>{playing === e.path ? '■' : '▶'}</button>
        <span class="name small"><strong>{e.name}</strong> <span class="muted tiny">{e.authors.join(', ') || t('ferepo.unknownAuthor')}</span></span>
        <button class="link tiny folder" title={e.folder} onclick={() => { folder = e.folder; run() }}>{e.folder}</button>
        <button onclick={() => onpick(e)} disabled={busy}>{t('ferepo.use')}</button>
      </li>
    {/each}
    {#if entries.length < total}
      <li><button class="more" onclick={() => run(false, true)} disabled={loading}>{t('ferepo.more', { n: total - entries.length })}</button></li>
    {/if}
  </ul>
</div>

<style>
  .browser { display: flex; flex-direction: column; gap: 0.4rem; border: 1px solid var(--border); border-radius: 6px; padding: 0.5rem; margin-top: 0.6rem; }
  .bar { display: flex; gap: 0.3rem; align-items: center; flex-wrap: wrap; }
  .bar input:not([type]) { flex: 1; min-width: 10rem; }
  .bar select { max-width: 22rem; }
  .list { list-style: none; margin: 0; padding: 0; max-height: 26rem; overflow-y: auto; }
  .list li { display: flex; align-items: center; gap: 0.5rem; padding: 0.15rem 0; border-bottom: 1px solid var(--border); }
  .name { flex: 1; min-width: 0; }
  .folder { max-width: 16rem; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; text-align: right; }
  .listen { width: 1.9rem; height: 1.7rem; padding: 0; display: inline-grid; place-items: center; font-size: 0.8rem; flex: none; }
  .listen.playing { background: var(--accent-soft); border-color: var(--accent); color: var(--accent); }
  .more { width: 100%; }
  .link { border: none; background: none; padding: 0; color: var(--accent); font: inherit; cursor: pointer; }
  .link.tiny { font-size: 0.72rem; }
  .small { font-size: 0.8rem; }
  .tiny { font-size: 0.72rem; }
  .bad { color: var(--bad); }
  p { margin: 0; }
</style>
