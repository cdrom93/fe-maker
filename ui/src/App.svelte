<script lang="ts">
  import { onMount } from 'svelte'
  import { api } from './lib/api'
  import { i18n, t } from './lib/i18n.svelte'
  import type { Status } from './lib/types'
  import Setup from './components/Setup.svelte'
  import Home from './components/Home.svelte'
  import Workspace from './components/Workspace.svelte'

  let status = $state<Status | null>(null)
  let loadError = $state('')

  async function refresh() {
    try {
      status = await api.status()
      i18n.lang = status.language
    } catch (e) {
      loadError = String(e)
    }
  }

  async function setLanguage(lang: 'fr' | 'en') {
    i18n.lang = lang
    status = await api.updateSettings({ language: lang })
  }

  onMount(refresh)
</script>

<header>
  <div class="brand">
    <strong>FE Maker</strong>
    <span class="muted">{t('app.tagline')}</span>
  </div>
  <div class="lang" role="group" aria-label={t('app.language')}>
    <button class:active={i18n.lang === 'fr'} onclick={() => setLanguage('fr')}>FR</button>
    <button class:active={i18n.lang === 'en'} onclick={() => setLanguage('en')}>EN</button>
  </div>
</header>

<main>
  {#if loadError}
    <p class="panel">{loadError}</p>
  {:else if !status}
    <p class="muted">…</p>
  {:else if !status.hasRom}
    <Setup onDone={refresh} />
  {:else if !status.project}
    <Home {status} onOpened={refresh} />
  {:else}
    <Workspace project={status.project} onClosed={refresh} />
  {/if}
</main>

<style>
  header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 0.6rem 1.25rem;
    border-bottom: 1px solid var(--border);
    background: var(--panel);
  }
  .brand { display: flex; gap: 0.75rem; align-items: baseline; }
  .brand strong { font-size: 1.15rem; }
  .lang button { padding: 0.25em 0.6em; font-size: 0.8rem; }
  .lang button.active { background: var(--accent-soft); border-color: var(--accent); }
  main { padding: 1.25rem; max-width: 1400px; margin: 0 auto; }
  @media (max-width: 600px) {
    .brand .muted { display: none; }
    main { padding: 1rem; }
  }
</style>
