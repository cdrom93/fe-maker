<script lang="ts">
  // Portraits of FE-Repo (server: ferepo.py): browse by folder, search, thumbnails, authors and license;
  // "Use" imports one.
  import { untrack } from 'svelte'
  import { api, ApiError } from '../lib/api'
  import { t } from '../lib/i18n.svelte'
  import type { FeRepoEntry } from '../lib/types'

  let { initial = '', busy = false, onpick }: {
    /** a suggested search (the character's name) */
    initial?: string; busy?: boolean; onpick: (e: FeRepoEntry) => void
  } = $props()

  let query = $state('')
  let folder = $state('')
  let f2eOnly = $state(false)
  let entries = $state<FeRepoEntry[]>([])
  let folders = $state<{ name: string; count: number }[]>([])
  let total = $state(0)
  let indexDate = $state(0)
  let loading = $state(false)
  let error = $state('')
  let timer: ReturnType<typeof setTimeout> | undefined
  /** files that are not 128 x 112 portrait sheets (parts, tutorials): they cannot be imported */
  let notSheets = $state<Record<string, boolean>>({})
  let request = 0

  const imageUrl = (url: string) => `/api/ferepo/image?url=${encodeURIComponent(url)}`

  /** The first page of the search (`more`: the next page, added below). */
  async function run(refresh = false, more = false) {
    const n = ++request
    loading = true
    error = ''
    try {
      const r = await api.feRepoPortraits(query, { refresh, folder, f2e: f2eOnly, offset: more ? entries.length : 0 })
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

  function suggest() {
    query = initial
    run()
  }
</script>

<div class="browser">
  <div class="bar">
    <select bind:value={folder} onchange={() => run()} aria-label={t('ferepo.folder')}>
      <option value="">{t('ferepo.allFolders')}</option>
      {#each folders as f (f.name)}<option value={f.name}>{f.name} ({f.count})</option>{/each}
    </select>
    <input bind:value={query} oninput={typed} placeholder={t('ferepo.search')} />
    <label class="small f2e"><input type="checkbox" bind:checked={f2eOnly} onchange={() => run()} /> {t('ferepo.f2eOnly')}</label>
    <button onclick={() => run(true)} disabled={loading} title={t('ferepo.refreshHint')}>⟳</button>
  </div>
  {#if initial && query !== initial}
    <p class="small"><button class="link" onclick={suggest}>🔎 {t('ferepo.suggest', { name: initial })}</button></p>
  {/if}
  <p class="muted tiny">
    {t('ferepo.hint')}
    {#if indexDate}· {t('ferepo.indexDate', { date: new Date(indexDate * 1000).toLocaleDateString() })}{/if}
  </p>
  {#if error}<p class="bad small">{error}</p>{/if}
  {#if !error}<p class="muted tiny">{loading && !entries.length ? t('ferepo.loading') : t('ferepo.count', { shown: entries.length, total })}</p>{/if}
  <div class="grid">
    {#each entries as e (e.url)}
      <div class="card">
        <img src={imageUrl(e.url)} alt={e.name} loading="lazy"
             onload={(ev) => {
               const img = ev.target as HTMLImageElement
               if (img.naturalWidth !== 128 || img.naturalHeight !== 112) notSheets[e.url] = true
             }} />
        <div class="info">
          <strong class="small">{e.name}</strong>
          <span class="tiny muted">{e.authors.join(', ') || t('ferepo.unknownAuthor')}</span>
          <button class="link tiny folder" title={e.folder} onclick={() => { folder = e.folder.split('/')[0]; run() }}>{e.folder}</button>
          <span class="badge" class:f2e={e.license === 'F2E'} title={t(`ferepo.license.${e.license}`)}>{e.license}</span>
        </div>
        <button onclick={() => onpick(e)} disabled={busy || notSheets[e.url]} title={notSheets[e.url] ? t('ferepo.notSheet') : ''}>{t('ferepo.use')}</button>
      </div>
    {/each}
    {#if entries.length < total}
      <button class="more" onclick={() => run(false, true)} disabled={loading}>{t('ferepo.more', { n: total - entries.length })}</button>
    {/if}
  </div>
</div>

<style>
  .browser { display: flex; flex-direction: column; gap: 0.4rem; border: 1px solid var(--border); border-radius: 6px; padding: 0.5rem; }
  .bar { display: flex; gap: 0.3rem; align-items: center; flex-wrap: wrap; }
  .bar input:not([type]) { flex: 1; min-width: 10rem; }
  .bar select { max-width: 16rem; }
  .f2e { display: flex; gap: 0.2rem; align-items: center; white-space: nowrap; }
  .grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(150px, 1fr)); gap: 0.5rem; max-height: 26rem; overflow-y: auto; }
  .card { display: flex; flex-direction: column; gap: 0.25rem; padding: 0.35rem; border: 1px solid var(--border); border-radius: 6px; }
  .card img { width: 128px; height: 112px; object-fit: contain; image-rendering: pixelated; align-self: center; }
  .info { display: flex; flex-direction: column; gap: 0.1rem; min-width: 0; align-items: flex-start; }
  .folder { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; max-width: 100%; text-align: left; }
  .badge { align-self: flex-start; font-size: 0.7rem; padding: 0 0.3rem; border-radius: 4px; background: var(--warn-soft); color: var(--warn); }
  .badge.f2e { background: var(--accent-soft); color: var(--good); }
  .more { grid-column: 1 / -1; }
  .link { border: none; background: none; padding: 0; color: var(--accent); font: inherit; cursor: pointer; }
  .link.tiny { font-size: 0.72rem; }
  .small { font-size: 0.8rem; }
  .tiny { font-size: 0.72rem; }
  .bad { color: var(--bad); }
  p { margin: 0; }
</style>
