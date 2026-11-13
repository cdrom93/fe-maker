<script lang="ts">
  // A newer FE Maker published on GitHub (server: update.py, question #58): one click installs it and FE Maker starts
  // again; the page waits for the new version, then reloads. Only a packaged FE Maker offers it.
  import { onMount } from 'svelte'
  import { api } from '../lib/api'
  import { t } from '../lib/i18n.svelte'

  let release = $state<{ version: string; page: string } | null>(null)
  let busy = $state(false)
  let error = $state('')

  onMount(() => {
    api.updateCheck().then((u) => (release = u.release)).catch(() => {})
  })

  async function waitForVersion(version: string) {
    for (let i = 0; i < 180; i++) {
      await new Promise((r) => setTimeout(r, 1000))
      try {
        if ((await api.status()).version === version) {
          location.reload()
          return
        }
      } catch {
        // the server is restarting
      }
    }
    busy = false
    error = t('update.noRestart')
  }

  async function install() {
    if (!release || !confirm(t('update.confirm', { version: release.version }))) return
    busy = true
    error = ''
    try {
      const { version } = await api.updateInstall()
      await waitForVersion(version)
    } catch (e) {
      busy = false
      error = String(e).includes('buildRunning') ? t('update.buildRunning') : t('update.failed', { error: String(e) })
    }
  }
</script>

{#if release}
  <span class="update">
    {#if busy}
      <span>{t('update.installing', { version: release.version })}</span>
    {:else}
      <button onclick={install} title={t('update.title')}>{t('update.available', { version: release.version })}</button>
    {/if}
    {#if error}<span class="error" role="alert">{error}</span>{/if}
  </span>
{/if}

<style>
  .update { display: inline-flex; gap: 0.5rem; align-items: baseline; font-size: 0.8rem; color: var(--header-text); }
  .update button { padding: 0.15em 0.6em; font-size: 0.8rem; background: var(--accent); color: var(--accent-text); border-color: var(--accent); }
  .error { color: var(--header-text); }
</style>
