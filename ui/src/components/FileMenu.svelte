<script lang="ts">
  import { api, ApiError } from '../lib/api'
  import { fileMenu } from '../lib/filemenu.svelte'
  import { i18n, t } from '../lib/i18n.svelte'
  import type { Status } from '../lib/types'
  import OptionsDialog from './OptionsDialog.svelte'
  import FolderPickButton from './FolderPickButton.svelte'

  /** The File menu, top left like in office software: projects, FE Maker's settings, help, quit (languages stay
   * as flags at the top right, the user's choice). */
  let { status, onChanged, onQuit }: {
    status: Status | null
    onChanged: () => void
    onQuit: () => void
  } = $props()

  type Pane = 'recent' | 'help'
  let open = $state(false)
  let pane = $state<Pane>('recent')
  let busy = $state(false)
  let error = $state('')
  let showOptions = $state(false)

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
        <button role="menuitem" onclick={() => { open = false; showOptions = true }}>{t('file.optionsMenu')}</button>
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

{#if showOptions && status}
  <OptionsDialog {status} {onChanged} onClose={() => (showOptions = false)} />
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
  .pane h3 { margin: 0 0 0.25rem; font-size: 0.95rem; padding-bottom: 0.35rem; border-bottom: 1px solid var(--border); }
  ol { list-style: none; margin: 0; padding: 0; }
  .entry { display: flex; gap: 0.6rem; width: 100%; border: none; border-radius: var(--radius); background: none; color: var(--text); padding: 0.35rem 0.5rem; text-align: left; text-decoration: none; }
  .entry:hover:not(:disabled) { background: var(--accent-soft); }
  .num { color: var(--muted); min-width: 1.2em; }
  .where { display: flex; flex-direction: column; min-width: 0; }
  .path { color: var(--muted); font-size: 0.78rem; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .row { display: flex; flex-wrap: wrap; gap: 0.4rem; align-items: center; margin-top: 0.25rem; }
  .error { color: var(--bad); margin: 0; }
  @media (max-width: 700px) {
    .sheet { grid-template-columns: 1fr; position: fixed; left: 0.5rem; right: 0.5rem; }
    .commands { border-right: none; border-bottom: 1px solid var(--border); }
  }
</style>
