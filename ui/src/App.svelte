<script lang="ts">
  import { onMount } from 'svelte'
  import { api } from './lib/api'
  import { i18n, t } from './lib/i18n.svelte'
  import type { Status } from './lib/types'
  import Setup from './components/Setup.svelte'
  import Home from './components/Home.svelte'
  import Workspace from './components/Workspace.svelte'
  import TicketDialog from './components/TicketDialog.svelte'

  let status = $state<Status | null>(null)
  let loadError = $state('')
  let showTickets = $state(false)
  let openTickets = $state(0)

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

  onMount(() => {
    refresh()
    api.tickets().then((all) => (openTickets = all.filter((x) => x.status === 'open').length)).catch(() => {})
  })
</script>

<header>
  <div class="brand">
    <strong>FE Maker</strong>
    <span class="muted">{t('app.tagline')}</span>
  </div>
  <div class="tools">
    <button class="ticket" title={t('ticket.buttonTitle')} onclick={() => (showTickets = true)}>
      🎫 {t('ticket.button')}{#if openTickets}<span class="count">{openTickets}</span>{/if}
    </button>
  <div class="lang" role="group" aria-label={t('app.language')}>
    <button class:active={i18n.lang === 'fr'} onclick={() => setLanguage('fr')}>FR</button>
    <button class:active={i18n.lang === 'en'} onclick={() => setLanguage('en')}>EN</button>
  </div>
  </div>
</header>

{#if showTickets}
  <TicketDialog onClose={() => (showTickets = false)} onChanged={(n) => (openTickets = n)} />
{/if}

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
  .tools { display: flex; gap: 0.75rem; align-items: center; }
  .ticket { padding: 0.25em 0.7em; font-size: 0.85rem; display: inline-flex; align-items: center; gap: 0.35rem; }
  .count { min-width: 1.4em; padding: 0 0.3em; border-radius: 999px; background: var(--accent); color: var(--accent-text); font-size: 0.72rem; text-align: center; }
  .lang button { padding: 0.25em 0.6em; font-size: 0.8rem; }
  .lang button.active { background: var(--accent-soft); border-color: var(--accent); }
  main { padding: 1.25rem; max-width: 1400px; margin: 0 auto; }
  @media (max-width: 600px) {
    .brand .muted { display: none; }
    main { padding: 1rem; }
  }
</style>
