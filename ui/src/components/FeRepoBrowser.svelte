<script lang="ts">
  // Portraits of FE-Repo (server: ferepo.py): search, thumbnails, authors and license; "Use" imports one.
  import { api, ApiError } from '../lib/api'
  import { t } from '../lib/i18n.svelte'
  import type { FeRepoEntry } from '../lib/types'

  let { initial = '', busy = false, onpick }: { initial?: string; busy?: boolean; onpick: (e: FeRepoEntry) => void } = $props()

  let query = $state('')
  let entries = $state<FeRepoEntry[]>([])
  let total = $state(0)
  let indexDate = $state(0)
  let loading = $state(false)
  let error = $state('')
  let timer: ReturnType<typeof setTimeout> | undefined

  const imageUrl = (url: string) => `/api/ferepo/image?url=${encodeURIComponent(url)}`

  async function run(refresh = false) {
    loading = true
    error = ''
    try {
      const r = await api.feRepoPortraits(query, refresh)
      entries = r.entries
      total = r.total
      indexDate = r.indexDate
    } catch (e) {
      error = e instanceof ApiError ? t(`ferepo.error.${e.detail}`) : String(e)
    } finally {
      loading = false
    }
  }

  $effect(() => {
    query = initial
    run()
  })

  function typed() {
    clearTimeout(timer)
    timer = setTimeout(() => run(), 350)
  }
</script>

<div class="browser">
  <div class="bar">
    <input bind:value={query} oninput={typed} placeholder={t('ferepo.search')} />
    <button onclick={() => run(true)} disabled={loading} title={t('ferepo.refreshHint')}>⟳</button>
  </div>
  <p class="muted tiny">
    {t('ferepo.hint')}
    {#if indexDate}· {t('ferepo.indexDate', { date: new Date(indexDate * 1000).toLocaleDateString() })}{/if}
  </p>
  {#if loading}<p class="muted small">{t('ferepo.loading')}</p>{/if}
  {#if error}<p class="bad small">{error}</p>{/if}
  {#if !loading && !error}<p class="muted tiny">{t('ferepo.count', { shown: entries.length, total })}</p>{/if}
  <div class="grid">
    {#each entries as e (e.url)}
      <div class="card">
        <img src={imageUrl(e.url)} alt={e.name} loading="lazy" />
        <div class="info">
          <strong class="small">{e.name}</strong>
          <span class="tiny muted">{e.authors.join(', ') || t('ferepo.unknownAuthor')}</span>
          <span class="tiny muted folder">{e.folder}</span>
          <span class="badge" class:f2e={e.license === 'F2E'} title={t(`ferepo.license.${e.license}`)}>{e.license}</span>
        </div>
        <button onclick={() => onpick(e)} disabled={busy}>{t('ferepo.use')}</button>
      </div>
    {/each}
  </div>
</div>

<style>
  .browser { display: flex; flex-direction: column; gap: 0.4rem; border: 1px solid var(--border); border-radius: 6px; padding: 0.5rem; }
  .bar { display: flex; gap: 0.3rem; }
  .bar input { flex: 1; }
  .grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(150px, 1fr)); gap: 0.5rem; max-height: 26rem; overflow-y: auto; }
  .card { display: flex; flex-direction: column; gap: 0.25rem; padding: 0.35rem; border: 1px solid var(--border); border-radius: 6px; }
  .card img { width: 128px; height: 112px; image-rendering: pixelated; align-self: center; }
  .info { display: flex; flex-direction: column; gap: 0.1rem; min-width: 0; }
  .folder { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .badge { align-self: flex-start; font-size: 0.7rem; padding: 0 0.3rem; border-radius: 4px; background: var(--warn-soft); color: var(--warn); }
  .badge.f2e { background: var(--accent-soft); color: var(--good); }
  .small { font-size: 0.8rem; }
  .tiny { font-size: 0.72rem; }
  .bad { color: var(--bad); }
  p { margin: 0; }
</style>
