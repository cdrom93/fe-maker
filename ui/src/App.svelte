<script lang="ts">
  import { onMount } from 'svelte'
  import { api } from './lib/api'
  import { i18n, LANGUAGES, type Lang, t } from './lib/i18n.svelte'
  import LangFlag from './components/LangFlag.svelte'
  import type { Status } from './lib/types'
  import Setup from './components/Setup.svelte'
  import Home from './components/Home.svelte'
  import Workspace from './components/Workspace.svelte'
  import TicketPanel from './components/TicketPanel.svelte'

  let status = $state<Status | null>(null)
  let loadError = $state('')
  // The ticket column stays open across reloads (per-browser convenience).
  let showTickets = $state(readShowTickets())
  let headerHeight = $state(49)

  function readShowTickets(): boolean {
    try {
      return localStorage.getItem('fe-maker.tickets-open') === '1'
    } catch {
      return false
    }
  }

  function toggleTickets(open = !showTickets) {
    showTickets = open
    try {
      localStorage.setItem('fe-maker.tickets-open', open ? '1' : '0')
    } catch {
      // storage unavailable: the column just won't be remembered
    }
  }
  let openTickets = $state(0)

  async function refresh() {
    try {
      status = await api.status()
      i18n.lang = status.language
    } catch (e) {
      loadError = String(e)
    }
  }

  async function setLanguage(lang: Lang) {
    i18n.lang = lang
    status = await api.updateSettings({ language: lang })
  }

  onMount(() => {
    refresh()
    api.tickets().then((all) => (openTickets = all.filter((x) => x.status === 'open').length)).catch(() => {})
  })
</script>

<header bind:clientHeight={headerHeight}>
  <div class="brand">
    <strong>FE Maker</strong>
    <span class="muted">{t('app.tagline')}</span>
  </div>
  <div class="tools">
    <button class="ticket" title={t('ticket.buttonTitle')} aria-pressed={showTickets} class:active={showTickets} onclick={() => toggleTickets()}>
      🎫 {t('ticket.button')}{#if openTickets}<span class="count">{openTickets}</span>{/if}
    </button>
  <div class="lang" role="group" aria-label={t('app.language')}>
    {#each LANGUAGES as l (l.code)}
      <button class:active={i18n.lang === l.code} title={l.name} aria-label={l.name} aria-pressed={i18n.lang === l.code} onclick={() => setLanguage(l.code)}>
        <LangFlag lang={l.code} />
      </button>
    {/each}
  </div>
  </div>
</header>

{#if showTickets}
  <div style="--header-height: {headerHeight}px; display: contents">
  <TicketPanel onClose={() => toggleTickets(false)} onChanged={(n) => (openTickets = n)} />
  </div>
{/if}

<main class:with-side={showTickets} style="--header-height: {headerHeight}px">
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
  .lang { display: flex; gap: 0.25rem; }
  .lang button { padding: 0.3em 0.4em; display: grid; place-items: center; }
  .lang button.active { background: var(--accent-soft); border-color: var(--accent); }
  main { padding: 1.25rem; max-width: 1400px; margin: 0 auto; }
  /* The ticket column takes the right side: the app stays usable next to it. */
  main.with-side { margin-right: 380px; }
  @media (max-width: 1000px) { main.with-side { margin-right: 0; } }
  .ticket.active { background: var(--accent-soft); border-color: var(--accent); }
  @media (max-width: 600px) {
    .brand .muted { display: none; }
    main { padding: 1rem; }
  }
</style>
