<script lang="ts">
  // What this computer still lacks (server: checks.py), each with what to do; nothing shows when all is well.
  import { onMount } from 'svelte'
  import { api, ApiError } from '../lib/api'
  import { t } from '../lib/i18n.svelte'
  import type { Check } from '../lib/types'

  const LINKS: Record<string, string> = { docker: 'https://www.docker.com/products/docker-desktop/', mgba: 'https://mgba.io/downloads.html' }

  let checks = $state<Check[]>([])
  let busy = $state(false)
  let error = $state('')
  const missing = $derived(checks.filter((c) => !c.ok && c.id !== 'rom'))

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

  onMount(() => {
    check()
    // While Docker Desktop starts or the first build runs (checks.py), look again until it is over.
    const timer = setInterval(() => { if (!busy && checks.some((c) => c.detail === 'starting' || c.detail === 'running')) check() }, 5000)
    return () => clearInterval(timer)
  })
</script>

{#if missing.length || error}
  <section class="panel checks">
    <h2>{t(missing.every((c) => c.id === 'firstBuild') && !error ? 'checks.titlePreparing' : 'checks.title')}</h2>
    {#each missing as c (c.id)}
      <div class="check">
        <strong>{t(`checks.${c.id}`)}</strong>
        <span class="muted">{t(`checks.${c.id}.${c.detail || 'missing'}`)}</span>
        {#if c.id === 'decomp' || c.id === 'toolchain'}
          <button class="primary" disabled={busy} onclick={() => check(c.id === 'decomp' ? api.downloadDecomp : api.downloadToolchain)}>{busy ? t('checks.downloading') : t('checks.download')}</button>
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
  .bad { color: var(--bad); }
</style>
