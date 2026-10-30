<script lang="ts">
  import { api, ApiError } from '../lib/api'
  import { t } from '../lib/i18n.svelte'
  import type { Status } from '../lib/types'
  import Checks from './Checks.svelte'

  let { status, onOpened }: { status: Status; onOpened: () => void } = $props()

  let name = $state('')
  let author = $state('')
  /** a blank project (ticket 66): what it drops; weapons and classes stay */
  let blank = $state(false)
  let blankCharacters = $state(true)
  let path = $state('')
  let busy = $state(false)
  let error = $state('')

  async function run(action: () => Promise<unknown>) {
    busy = true
    error = ''
    try {
      await action()
      onOpened()
    } catch (e) {
      error = e instanceof ApiError ? e.detail : String(e)
    } finally {
      busy = false
    }
  }
</script>

<Checks />
<div class="home">
  <section class="panel">
    <h2>{t('home.new')}</h2>
    <form onsubmit={(e) => { e.preventDefault(); run(() => api.createProject(name, author, blank ? { characters: blankCharacters, title: t('home.blankTitle'), hero: t('home.blankHero') } : undefined)) }}>
      <label>{t('home.name')}<input bind:value={name} required maxlength="60" /></label>
      <label>{t('home.author')}<input bind:value={author} maxlength="60" /></label>
      <label class="choice"><input type="checkbox" bind:checked={blank} /> {t('home.blank')}</label>
      {#if blank}
        <div class="blank">
          <p class="muted hint">{t('home.blankHint')}</p>
          <label class="choice"><input type="checkbox" bind:checked={blankCharacters} /> {t('home.blankCharacters')}</label>
          <p class="muted hint">{t('home.blankKept')}</p>
        </div>
      {/if}
      <p class="muted hint">{t('home.createHint', { dir: status.defaultProjectsDir })}</p>
      <button class="primary" disabled={busy || !name.trim()}>{t('home.create')}</button>
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
    <form class="row" onsubmit={(e) => { e.preventDefault(); run(() => api.openProject(path)) }}>
      <input bind:value={path} placeholder={t('home.openPath')} aria-label={t('home.openPath')} />
      <button disabled={busy || !path.trim()}>{t('home.open')}</button>
    </form>
  </section>

  {#if error}<p class="error">{error}</p>{/if}
</div>

<style>
  .choice { color: var(--text); font-weight: 600; }
  .blank { padding-left: 1.4rem; display: flex; flex-direction: column; gap: 0.35rem; }
  .blank p { margin: 0; }
  .home { display: grid; grid-template-columns: repeat(auto-fit, minmax(320px, 1fr)); gap: 1rem; max-width: 900px; margin: 2rem auto; }
  form { display: flex; flex-direction: column; gap: 0.75rem; }
  form.row { flex-direction: row; margin-top: 1rem; }
  form.row input { flex: 1; }
  .hint { font-size: 0.85rem; margin: 0; word-break: break-all; }
  ul { list-style: none; padding: 0; margin: 0; display: flex; flex-direction: column; gap: 0.25rem; }
  .link { border: none; background: none; padding: 0.2em 0; color: var(--accent); text-align: left; word-break: break-all; }
  .error { color: var(--bad); grid-column: 1 / -1; }
</style>
