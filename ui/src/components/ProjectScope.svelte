<script lang="ts">
  // What the project keeps of the game (server: scope.py), at creation or at any time after.
  import { onMount } from 'svelte'
  import { api, type ProjectScope } from '../lib/api'
  import { t } from '../lib/i18n.svelte'

  let { onchanged }: { /** the project's data changed on the server */ onchanged: () => void } = $props()

  type Kind = 'chapters' | 'characters' | 'classes' | 'items'
  const KINDS: Kind[] = ['chapters', 'characters', 'classes', 'items']

  let scope = $state<ProjectScope | null>(null)
  let error = $state('')
  let busy = $state(false)
  let done = $state('')
  let open = $state<Kind | null>('chapters')
  let search = $state('')

  onMount(load)

  async function load() {
    try {
      scope = await api.projectScope()
    } catch (e) {
      error = String(e)
    }
  }

  const count = (k: Kind) => scope![k].filter((r) => r.kept).length
  const needed = (k: Kind, id: string | number) => k !== 'chapters' && scope!.needed[k].includes(String(id))
  const shown = (k: Kind) => scope![k].filter((r) => !search || r.name.toLowerCase().includes(search.toLowerCase()))

  function setAll(k: Kind, kept: boolean) {
    for (const r of shown(k)) r.kept = kept
  }

  async function apply() {
    if (!scope || !confirm(t('scope.confirm'))) return
    busy = true
    error = ''
    done = ''
    const kept = (k: Kind) => scope!.chapters && scope![k].filter((r) => r.kept).map((r) => r.id)
    try {
      const r = await api.applyProjectScope({
        chapters: kept('chapters') as number[], characters: kept('characters') as string[], classes: kept('classes') as string[],
        items: kept('items') as string[], supports: scope.supports, title: t('home.blankTitle'), hero: t('home.blankHero'),
      })
      await load()
      onchanged()
      done = t('scope.done', { path: r.backup, n: Object.values(r.forced).flat().length })
    } catch (e) {
      error = String(e)
    } finally {
      busy = false
    }
  }
</script>

<section class="panel" id="project-scope">
  <h3>{t('scope.title')}</h3>
  <p class="muted small">{t('scope.hint')}</p>
  {#if error}<p class="bad small">{error}</p>{/if}
  {#if scope}
    <div class="kinds" role="tablist">
      {#each KINDS as k (k)}
        <button role="tab" aria-selected={open === k} class:active={open === k} onclick={() => (open = k)}>
          {t(`scope.${k}`)} <span class="muted">{count(k)} / {scope[k].length}</span>
        </button>
      {/each}
    </div>
    {#if open}
      {@const k = open}
      <div class="bar">
        <input type="search" bind:value={search} placeholder={t('ws.search')} aria-label={t('ws.search')} />
        <button onclick={() => setAll(k, true)}>{t('scope.all')}</button>
        <button onclick={() => setAll(k, false)}>{t('scope.none')}</button>
      </div>
      <p class="muted small">{t(`scope.${k}Hint`)}</p>
      <ul>
        {#each shown(k) as r (r.id)}
          <li>
            <label class:needed={needed(k, r.id)} title={needed(k, r.id) ? t('scope.needed') : undefined}>
              <input type="checkbox" bind:checked={r.kept} /> {r.name || r.id}{#if needed(k, r.id)} <span class="muted tiny">{t('scope.neededShort')}</span>{/if}
            </label>
          </li>
        {/each}
      </ul>
    {/if}
    <label class="supports"><input type="checkbox" bind:checked={scope.supports} /> {t('scope.supports')}</label>
    <button class="primary" disabled={busy} onclick={apply}>{t('scope.apply')}</button>
    {#if done}<p class="small good">{done}</p>{/if}
  {:else}
    <p class="muted">…</p>
  {/if}
</section>

<style>
  .kinds, .bar { display: flex; flex-wrap: wrap; gap: 0.3rem; margin-bottom: 0.5rem; }
  .kinds button.active { background: var(--accent-soft); border-color: var(--accent); }
  ul { list-style: none; margin: 0.4rem 0; padding: 0; max-height: 20rem; overflow-y: auto; display: grid; grid-template-columns: repeat(auto-fill, minmax(13rem, 1fr)); gap: 0.1rem 0.75rem; }
  label { color: var(--text); font-weight: 400; }
  .supports { margin: 0.5rem 0; }
  .small { font-size: 0.8rem; }
  .tiny { font-size: 0.7rem; }
  .bad { color: var(--bad); }
  .good { color: var(--good); }
</style>
