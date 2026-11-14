<script lang="ts">
  // What this computer still lacks (server: checks.py), each with what to do; nothing shows when all is well.
  // What FE Maker downloads itself (the game's code, the build tools, mGBA on Windows) runs in the background, each
  // with its own progress (ticket 81): several at once.
  import { onMount } from 'svelte'
  import { api, ApiError } from '../lib/api'
  import { i18n, t } from '../lib/i18n.svelte'
  import type { Check } from '../lib/types'

  const LINKS: Record<string, string> = { docker: 'https://www.docker.com/products/docker-desktop/', mgba: 'https://mgba.io/downloads.html' }
  const START: Record<string, () => Promise<Check[]>> = {
    decomp: api.downloadDecomp, toolchain: api.downloadToolchain, mgba: api.downloadMgba,
  }

  let checks = $state<Check[]>([])
  let busy = $state(false)
  let error = $state('')
  const missing = $derived(checks.filter((c) => !c.ok && c.id !== 'rom'))
  const running = $derived(checks.some((c) => c.download?.state === 'running'))

  async function check(action: () => Promise<Check[]> = api.checks) {
    busy = true
    error = ''
    try {
      checks = await action()
    } catch (e) {
      error = e instanceof ApiError ? t(`checks.error.${e.detail}`) : String(e)
    } finally {
      busy = false
    }
  }

  async function download(id: string) {
    try {
      checks = await START[id]()
    } catch (e) {
      error = e instanceof ApiError ? t(`checks.error.${e.detail}`) : String(e)
    }
  }

  const mb = (bytes: number) => (bytes / 1048576).toLocaleString(i18n.lang, { maximumFractionDigits: bytes < 10485760 ? 1 : 0 })

  onMount(() => {
    check()
    // While something downloads, follow it each second; while Docker Desktop starts or the first build runs, look
    // again every five seconds until it is over.
    let ticks = 0
    const timer = setInterval(() => {
      ticks++
      if (busy) return
      if (running || (ticks % 5 === 0 && checks.some((c) => c.detail === 'starting' || c.detail === 'running'))) check()
    }, 1000)
    return () => clearInterval(timer)
  })
</script>

{#if missing.length || error}
  <section class="panel checks">
    <h2>{t(missing.every((c) => c.id === 'firstBuild') && !error ? 'checks.titlePreparing' : 'checks.title')}</h2>
    {#each missing as c (c.id)}
      <div class="check">
        <strong>{t(`checks.${c.id}`)}</strong>
        <span class="muted">{t(`checks.${c.id}.${c.detail || (c.id === 'mgba' && c.download !== undefined ? 'missingDownload' : 'missing')}`)}</span>
        {#if c.download?.state === 'running'}
          <div class="bar">
            <progress value={c.download.total ? c.download.received : undefined} max={c.download.total || undefined}></progress>
            <span>{c.download.total && c.download.received >= c.download.total
              ? t('checks.installing')
              : c.download.total ? `${mb(c.download.received)} / ${mb(c.download.total)} ${t('checks.mb')}` : `${mb(c.download.received)} ${t('checks.mb')}`}</span>
          </div>
        {:else if c.download !== undefined}
          <div class="actions">
            <button class="primary" onclick={() => download(c.id)}>{t(c.download?.state === 'error' ? 'checks.retry' : 'checks.download')}</button>
            {#if LINKS[c.id]}<a href={LINKS[c.id]} target="_blank" rel="noreferrer">{t('checks.site')}</a>{/if}
          </div>
          {#if c.download?.state === 'error'}<p class="bad">{t(`checks.error.${c.download.error}`)}</p>{/if}
        {:else if LINKS[c.id]}
          <a href={LINKS[c.id]} target="_blank" rel="noreferrer">{t('checks.get')}</a>
        {/if}
      </div>
    {/each}
    {#if error}<p class="bad">{error}</p>{/if}
    <button disabled={busy} onclick={() => check()}>{t('checks.again')}</button>
  </section>
{/if}

<style>
  .checks { margin-bottom: 1rem; }
  .check { display: flex; flex-direction: column; gap: 0.25rem; align-items: flex-start; margin-bottom: 0.75rem; }
  .actions { display: flex; align-items: center; gap: 0.75rem; }
  .bar { display: flex; align-items: center; gap: 0.6rem; width: min(100%, 28rem); }
  .bar progress { flex: 1; }
  .bar span { white-space: nowrap; font-variant-numeric: tabular-nums; color: var(--muted); }
  .bad { color: var(--bad); margin: 0; }
</style>
