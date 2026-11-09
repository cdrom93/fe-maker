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
  import FileMenu from './components/FileMenu.svelte'

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
  /** FE Maker stopped from File > Quit: only the tab is left to close */
  let stopped = $state(false)

  async function refresh() {
    try {
      status = await api.status()
      // a language set aside since (Spanish, Italian) falls back to French
      i18n.lang = LANGUAGES.some((l) => l.code === status!.language) ? (status.language as Lang) : 'fr'
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
  <div class="left">
  <FileMenu {status} onChanged={refresh} onQuit={() => (stopped = true)} />
  <div class="brand">
    {#if status?.version}<span class="version" title={t('app.version')}>{status.version}</span>{/if}
    <span class="muted">{t('app.tagline')}</span>
  </div>
  </div>
  <!-- The open project's actions (Workspace.svelte moves them here, ticket 145) -->
  <div id="header-actions"></div>
  <div class="tools">
    <button class="ticket" title={t('ticket.buttonTitle')} aria-pressed={showTickets} class:active={showTickets} onclick={() => toggleTickets()}>
      {t('ticket.button')}{#if openTickets}<span class="count">{openTickets}</span>{/if}
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
  {#if stopped}
    <p class="panel">{t('file.stopped')}</p>
  {:else if loadError}
    <p class="panel">{loadError}</p>
  {:else if !status}
    <p class="muted">…</p>
  {:else if !status.hasRom}
    <Setup onDone={refresh} />
  {:else if !status.project}
    <Home {status} onOpened={refresh} />
  {:else}
    {#key status.project.path}<Workspace project={status.project} onClosed={refresh} onRenamed={refresh} />{/key}
  {/if}
</main>

<style>
  header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 0.6rem 1.5rem;
    background: var(--header);
    color: var(--header-text);
    /* Always visible: tickets and languages stay at hand while scrolling. */
    position: sticky;
    top: 0;
    z-index: 20;
  }
  .left { display: flex; gap: 0.6rem; align-items: center; }
  .brand { display: flex; gap: 0.75rem; align-items: baseline; }
  .brand .muted { color: var(--header-muted); }
  .brand .version { color: var(--header-muted); font-size: 0.75rem; }
  #header-actions { margin-left: auto; margin-right: 1.25rem; }
  .tools { display: flex; gap: 0.75rem; align-items: center; }
  .tools button { background: transparent; color: var(--header-text); border-color: #ffffff33; }
  .tools button:hover:not(:disabled) { border-color: var(--header-text); }
  .ticket { padding: 0.25em 0.7em; font-size: 0.85rem; display: inline-flex; align-items: center; gap: 0.35rem; }
  .ticket.active { background: var(--panel); color: var(--text); }
  .count { min-width: 1.4em; padding: 0 0.3em; border-radius: 999px; background: var(--accent); color: var(--accent-text); font-size: 0.72rem; text-align: center; }
  .lang { display: flex; gap: 0.25rem; }
  .lang button { padding: 0.3em 0.4em; display: grid; place-items: center; }
  .lang button.active { background: var(--panel); border-color: var(--panel); }
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
