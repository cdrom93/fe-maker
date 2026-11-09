<script lang="ts">
  import { api, ApiError } from '../lib/api'
  import { fileMenu } from '../lib/filemenu.svelte'
  import { i18n, t } from '../lib/i18n.svelte'
  import type { Status } from '../lib/types'
  import KeysDialog from './KeysDialog.svelte'
  import Help from './Help.svelte'
  import ProjectSettings from './ProjectSettings.svelte'
  import FolderPickButton from './FolderPickButton.svelte'

  /** The File menu, top left like in office software: projects, FE Maker's settings, help, quit (languages stay
   * as flags at the top right, the user's choice). */
  let { status, onChanged, onQuit }: {
    status: Status | null
    onChanged: () => void
    onQuit: () => void
  } = $props()

  type Pane = 'recent' | 'options' | 'help'
  let open = $state(false)
  let pane = $state<Pane>('recent')
  let busy = $state(false)
  let error = $state('')
  let showKeys = $state(false)
  $effect(() => { fileMenu.keysOpen = showKeys })

  const project = $derived(fileMenu.project)
  const ready = $derived(!!status?.hasRom)
  const guide = $derived(`https://github.com/cdrom93/fe-maker/blob/main/docs/${i18n.lang === 'fr' ? 'guide.md' : 'guide.en.md'}`)

  function toggle() {
    open = !open
    pane = 'recent'
    error = ''
  }

  function message(e: unknown): string {
    if (!(e instanceof ApiError)) return String(e)
    return e.detail.startsWith('project.') ? t(e.detail) : e.detail === 'buildRunning' ? t('file.buildRunning') : e.detail
  }

  /** Run a command, then close the menu (or keep it open with the error). */
  async function run(action: () => unknown) {
    busy = true
    error = ''
    try {
      await action()
      open = false
    } catch (e) {
      error = message(e)
    } finally {
      busy = false
    }
  }

  /** Leave the open project (saved first), back to the start page and its "New project" form. */
  const newProject = () => run(async () => {
    if (project) await project.close()
    else onChanged()
  })

  const openProject = (p: string) => run(async () => {
    await project?.flush()
    await api.openProject(p)
    onChanged()
  })

  const quit = () => run(async () => {
    await project?.flush()
    await api.shutdown()
    onQuit()
  })

  /** mGBA's sound for the next tests: once set here, FE Maker writes the volume too (it stays 100 % until moved). */
  async function setSound(change: { volume?: number; mute?: boolean }) {
    error = ''
    try {
      await api.updateSettings({ volume: status?.volume ?? 100, ...change })
      onChanged()
    } catch (e) {
      error = message(e)
    }
  }

  function onKey(e: KeyboardEvent) {
    if (open && e.key === 'Escape') open = false
  }
</script>

<svelte:window onkeydown={onKey} />

<div class="file-menu">
  <!-- The app's name is the menu's button, like an office suite's File tab -->
  <button class="file" class:open title={t('file.menu')} aria-label={t('file.menu')} aria-expanded={open} aria-haspopup="menu"
          onclick={toggle}>FE Maker<span class="caret">▾</span></button>
  {#if open}
    <div class="backdrop" role="presentation" onclick={() => (open = false)}></div>
    <div class="sheet" role="menu">
      <div class="commands">
        <button role="menuitem" disabled={!ready || busy} onclick={newProject}>{t('file.new')}</button>
        <button role="menuitem" class="sub" class:here={pane === 'recent'} disabled={!ready}
                onmouseenter={() => (pane = 'recent')} onclick={() => (pane = 'recent')}>{t('file.open')}<span>▸</span></button>
        <button role="menuitem" disabled={!project || busy} title="Ctrl+S" onclick={() => run(() => project!.flush())}>{t('ws.save')}</button>
        <button role="menuitem" disabled={!project || busy} onclick={() => run(async () => { await project!.flush(); project!.saveAs() })}>{t('ws.saveAs')}</button>
        <button role="menuitem" disabled={!project || busy} onclick={() => run(() => project!.rename())}>{t('ws.rename')}</button>
        <hr />
        <button role="menuitem" disabled={!project || busy} onclick={() => run(() => project!.openFolder())}>{t('ws.openFolder')}</button>
        <button role="menuitem" disabled={!project || busy || !project.canExport()} onclick={() => run(() => project!.exportPatch())}>{t('ws.exportPatch')}</button>
        <button role="menuitem" disabled={!project || busy} onclick={() => run(() => project!.close())}>{t('ws.close')}</button>
        <hr />
        <button role="menuitem" class="sub" class:here={pane === 'options'}
                onmouseenter={() => (pane = 'options')} onclick={() => (pane = 'options')}>{t('file.options')}<span>▸</span></button>
        <button role="menuitem" class="sub" class:here={pane === 'help'}
                onmouseenter={() => (pane = 'help')} onclick={() => (pane = 'help')}>{t('file.help')}<span>▸</span></button>
        <hr />
        <button role="menuitem" class="to-quit" disabled={busy} onclick={quit}>{t('file.quit')}</button>
      </div>

      <div class="pane">
        {#if pane === 'recent'}
          <h3>{t('home.recent')}</h3>
          {#if !status?.recentProjects.length}
            <p class="muted">{t('home.noRecent')}</p>
          {:else}
            <ol>
              {#each status.recentProjects as p, i (p)}
                <li><button class="entry" disabled={!ready || busy} title={p} onclick={() => openProject(p)}>
                  <span class="num">{i + 1}</span>
                  <span class="where"><strong>{p.split(/[\\/]/).filter(Boolean).pop()}</strong><span class="path">{p}</span></span>
                </button></li>
              {/each}
            </ol>
          {/if}
          <div class="row">
            <FolderPickButton label={t('file.openOther')} title={t('file.pickProject')} initial={status?.defaultProjectsDir}
                              disabled={!ready || busy} onpick={openProject} />
          </div>
        {:else if pane === 'options'}
          <h3>{t('file.options')}</h3>
          <div class="option">
            <span>{t('file.emulator')}</span>
            <button onclick={() => { open = false; showKeys = true }}>{t('file.keys')}</button>
          </div>
          {#if status}
            <div class="option">
              <span>{t('file.sound')} <Help text={t('file.soundHint')} /></span>
              <span class="sound">
                <input type="range" min="0" max="100" step="5" value={status.volume ?? 100} disabled={status.mute}
                       aria-label={t('file.sound')} onchange={(e) => setSound({ volume: Number((e.target as HTMLInputElement).value) })} />
                <span class="pct">{status.volume ?? 100} %</span>
                <label class="mute"><input type="checkbox" checked={status.mute}
                       onchange={(e) => setSound({ mute: (e.target as HTMLInputElement).checked })} /> {t('file.mute')}</label>
              </span>
            </div>
          {/if}
          {#if project}
            <h3 class="sub-title">{t('file.projectOptions')} <Help text={t('options.editorHint')} /></h3>
            <ProjectSettings />
          {/if}
        {:else}
          <h3>{t('file.help')}</h3>
          <a class="entry" href={guide} target="_blank" rel="noreferrer">{t('file.guide')}</a>
          {#if status?.version}<p class="muted" title={t('app.version')}>FE Maker {status.version}</p>{/if}
        {/if}
        {#if error}<p class="error">{error}</p>{/if}
      </div>
    </div>
  {/if}
</div>

{#if showKeys}
  <KeysDialog onClose={() => (showKeys = false)} />
{/if}

<style>
  .file-menu { position: relative; }
  /* The app's name in the top bar, clickable: where everything about files and settings is. */
  .file {
    display: inline-flex; align-items: center; gap: 0.35rem; margin-left: -0.5rem; padding: 0.2em 0.5em;
    background: transparent; color: var(--header-text); border-color: transparent;
    font-size: 1.15rem; font-weight: 800; letter-spacing: 0.02em; white-space: nowrap;
  }
  .file:hover, .file.open { background: #ffffff1a; border-color: #ffffff33; }
  .caret { font-size: 0.7rem; color: var(--header-muted); }
  .backdrop { position: fixed; inset: 0; z-index: 40; }
  .sheet {
    position: absolute; z-index: 41; top: calc(100% + 0.45rem); left: 0;
    display: grid; grid-template-columns: 15rem minmax(22rem, 34rem);
    background: var(--panel); color: var(--text); border: 1px solid var(--border); border-radius: var(--radius);
    box-shadow: 0 8px 24px #0004; overflow: hidden;
  }
  .commands { display: flex; flex-direction: column; padding: 0.35rem 0; border-right: 1px solid var(--border); background: var(--panel-2); }
  .commands button {
    display: flex; justify-content: space-between; align-items: center; text-align: left;
    border: none; border-radius: 0; background: none; color: var(--text); padding: 0.5rem 1rem; font-weight: 600;
  }
  .commands button:hover:not(:disabled), .commands button.here { background: var(--accent-soft); }
  .commands button:disabled { color: var(--muted); }
  .commands button span { color: var(--muted); font-size: 0.75rem; }
  .commands hr { width: 100%; margin: 0.3rem 0; border: none; border-top: 1px solid var(--border); }
  .pane { padding: 0.75rem 1rem; max-height: 70vh; overflow-y: auto; display: flex; flex-direction: column; gap: 0.5rem; }
  .pane h3.sub-title { margin-top: 0.75rem; }
  .pane h3 { margin: 0 0 0.25rem; font-size: 0.95rem; padding-bottom: 0.35rem; border-bottom: 1px solid var(--border); }
  ol { list-style: none; margin: 0; padding: 0; }
  .entry { display: flex; gap: 0.6rem; width: 100%; border: none; border-radius: var(--radius); background: none; color: var(--text); padding: 0.35rem 0.5rem; text-align: left; text-decoration: none; }
  .entry:hover:not(:disabled) { background: var(--accent-soft); }
  .num { color: var(--muted); min-width: 1.2em; }
  .where { display: flex; flex-direction: column; min-width: 0; }
  .path { color: var(--muted); font-size: 0.78rem; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .row { display: flex; flex-wrap: wrap; gap: 0.4rem; align-items: center; margin-top: 0.25rem; }
  .option { display: flex; justify-content: space-between; align-items: center; gap: 1rem; padding: 0.25rem 0; }
  .option > span { font-weight: 600; }
  .sound { display: inline-flex; align-items: center; gap: 0.5rem; }
  .sound input[type='range'] { width: 8rem; }
  .pct { min-width: 3.2em; text-align: right; color: var(--muted); font-size: 0.85rem; }
  .mute { display: inline-flex; align-items: center; gap: 0.25rem; font-weight: 600; flex-direction: row; }
  .error { color: var(--bad); margin: 0; }
  @media (max-width: 700px) {
    .sheet { grid-template-columns: 1fr; position: fixed; left: 0.5rem; right: 0.5rem; }
    .commands { border-right: none; border-bottom: 1px solid var(--border); }
  }
</style>
