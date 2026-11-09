<script lang="ts">
  import { api, ApiError } from '../lib/api'
  import { t } from '../lib/i18n.svelte'
  import type { Status } from '../lib/types'
  import Checks from './Checks.svelte'
  import Help from './Help.svelte'
  import FolderPickButton from './FolderPickButton.svelte'
  import { inFolder } from '../lib/paths'

  let { status, onOpened }: { status: Status; onOpened: () => void } = $props()

  let name = $state('')
  let author = $state('')
  /** a blank project (ticket 66): what it drops; weapons and classes stay */
  let blank = $state(false)
  /** where it goes (ticket 174): empty, a new folder named after it in the projects folder */
  let folder = $state('')
  let busy = $state(false)
  let error = $state('')

  async function run(action: () => Promise<unknown>) {
    busy = true
    error = ''
    try {
      await action()
      onOpened()
    } catch (e) {
      error = !(e instanceof ApiError) ? String(e) : e.detail.startsWith('project.') ? t(e.detail) : e.detail
    } finally {
      busy = false
    }
  }

  function create() {
    if (blank) {
      try {
        sessionStorage.setItem('fe-maker.first-tab', 'options')
      } catch {
        // storage unavailable: the project opens on its first tab
      }
    }
    run(() => api.createProject(name, author, blank ? { characters: true, title: t('home.blankTitle'), hero: t('home.blankHero') } : undefined, folder))
  }
</script>

<Checks />
<div class="home">
  <section class="panel">
    <h2>{t('home.new')}</h2>
    <form onsubmit={(e) => { e.preventDefault(); create() }}>
      <label>{t('home.name')}<input bind:value={name} required maxlength="60" /></label>
      <label>{t('home.author')}<input bind:value={author} maxlength="60" /></label>
      <label>{t('home.folder')}
        <span class="pick"><input bind:value={folder} placeholder={status.defaultProjectsDir} />
          <FolderPickButton initial={status.defaultProjectsDir} onpick={(p) => (folder = inFolder(p, name))} /></span>
      </label>
      <label class="choice"><input type="checkbox" bind:checked={blank} /> {t('home.blank')} <Help text={t('home.blankHint')} /></label>
      <button class="primary" disabled={busy || !name.trim()}>{t('home.create')}</button>
      <p class="muted hint">{t('home.createHint', { dir: status.defaultProjectsDir })}</p>
    </form>
  </section>

  <section class="panel">
    <h2>{t('home.recent')}</h2>
    {#if status.recentProjects.length === 0}
      <p class="muted">{t('home.noRecent')}</p>
    {:else}
      <ul>
        {#each status.recentProjects as p (p)}
          <li><button class="link" disabled={busy} onclick={() => run(() => api.openProject(p))}>{p}</button></li>
        {/each}
      </ul>
    {/if}
    <div class="row">
      <FolderPickButton label={t('file.openOther')} title={t('file.pickProject')} initial={status.defaultProjectsDir}
                        disabled={busy} onpick={(p) => run(() => api.openProject(p))} />
    </div>
  </section>

  {#if error}<p class="error">{error}</p>{/if}
</div>

<style>
  .choice { color: var(--text); font-weight: 600; }
  .home { display: grid; grid-template-columns: repeat(auto-fit, minmax(320px, 1fr)); gap: 1rem; max-width: 900px; margin: 2rem auto; }
  form { display: flex; flex-direction: column; gap: 0.75rem; }
  .row { display: flex; flex-wrap: wrap; gap: 0.5rem; align-items: center; margin-top: 1rem; }
  .pick { display: flex; gap: 0.4rem; }
  .pick input { flex: 1; }
  .hint { font-size: 0.85rem; margin: 0; word-break: break-all; }
  ul { list-style: none; padding: 0; margin: 0; display: flex; flex-direction: column; gap: 0.25rem; }
  .link { border: none; background: none; padding: 0.2em 0; color: var(--accent); text-align: left; word-break: break-all; }
  .error { color: var(--bad); grid-column: 1 / -1; }
</style>
