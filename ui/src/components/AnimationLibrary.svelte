<script lang="ts">
  // Battle animations of FE-Repo (ticket 44, server: ferepo.py): browse by kind of class, search; choosing
  // one shows its preview, its weapons, authors and license; a weapon's animation can be given to the class
  // (downloaded, converted and kept in the project).
  import Help from './Help.svelte'
  import { untrack } from 'svelte'
  import { api, ApiError } from '../lib/api'
  import { t } from '../lib/i18n.svelte'
  import type { FeRepoAnimation, FeRepoEntry } from '../lib/types'
  import { animationTargets, guessTarget, targetLabel } from '../lib/animationTargets'
  import FavoriteStar from './FavoriteStar.svelte'

  let { initial = '', classId, wtypes, open = null, onimported }: {
    /** a suggested search (the class's name) */
    initial?: string
    classId: string
    /** weapon types the animation can be given for */
    wtypes: string[]
    /** an animation to show (one already imported) */
    open?: FeRepoEntry | null
    onimported: () => void
  } = $props()

  const targets = $derived(animationTargets(wtypes))
  const guessWtype = (folderName: string) => guessTarget(folderName, wtypes)
  let rangedOnly = $state(false)
  let chosenWtype = $state<Record<string, string>>({})
  let importing = $state('')
  let importError = $state('')
  let imported = $state('')

  // Each weapon has its own folder and its own picture (ticket 86).
  let shownWeapon = $state('')
  let weaponPreviews = $state<Record<string, string | null>>({})

  async function showWeapon(weapon: string) {
    shownWeapon = weapon
    const folderUrl = detail?.files.find((f) => f.type === 'dir' && f.name === weapon)?.url
    if (!folderUrl || weapon in weaponPreviews) return
    const shown = picked?.url
    try {
      const { preview } = await api.feRepoAnimation(folderUrl)
      if (picked?.url === shown) weaponPreviews[weapon] = preview
    } catch {
      if (picked?.url === shown) weaponPreviews[weapon] = null
    }
  }

  async function importWeapon(weapon: string) {
    if (!detail || !picked) return
    const folderUrl = detail.files.find((f) => f.type === 'dir' && f.name === weapon)?.url
    if (!folderUrl) return
    importing = weapon
    importError = ''
    imported = ''
    try {
      await api.importAnimation({ url: folderUrl, animation: picked.url, classId, wtype: chosenWtype[weapon] ?? guessWtype(weapon) })
      imported = weapon
      onimported()
    } catch (e) {
      importError = e instanceof ApiError ? t(`banim.import.error.${e.detail.split(':')[0]}`) : String(e)
    } finally {
      importing = ''
    }
  }

  let query = $state('')
  let folder = $state('')
  let f2eOnly = $state(false)
  let favOnly = $state(false)
  // weapon filter (ticket 47): the first time, the server asks GitHub for the weapons of each folder
  // several can be ticked: animations having all of them (ticket 48)
  let weaponFilter = $state<string[]>([])
  let missingFolders = $state(0)
  const FILTER_WTYPES = ['sword', 'lance', 'axe', 'bow', 'anima', 'light', 'dark', 'staff', 'item']
  let entries = $state<FeRepoEntry[]>([])
  let folders = $state<{ name: string; count: number }[]>([])
  let total = $state(0)
  let loading = $state(false)
  let error = $state('')
  let picked = $state<FeRepoEntry | null>(null)
  let detail = $state<FeRepoAnimation | null>(null)
  const shownPreview = $derived(shownWeapon && shownWeapon in weaponPreviews ? weaponPreviews[shownWeapon] : detail?.preview)
  let detailError = $state('')
  let timer: ReturnType<typeof setTimeout> | undefined
  let request = 0

  const imageUrl = (url: string) => `/api/ferepo/image?url=${encodeURIComponent(url)}`

  async function run(refresh = false, more = false) {
    const n = ++request
    loading = true
    // filtering by weapon may first ask GitHub (a minute): no stale list meanwhile
    if (!more && weaponFilter.length) entries = []
    error = ''
    try {
      const r = await api.feRepoAnimations(query, { refresh, folder, f2e: f2eOnly, fav: favOnly, wtype: weaponFilter.join(','), ranged: rangedOnly, offset: more ? entries.length : 0 })
      if (n !== request) return
      entries = more ? [...entries, ...r.entries] : r.entries
      total = r.total
      missingFolders = r.missingFolders ?? 0
      folders = r.folders
    } catch (e) {
      if (n === request) error = e instanceof ApiError ? t(`ferepo.error.${e.detail}`) : String(e)
    } finally {
      if (n === request) loading = false
    }
  }

  $effect(() => {
    untrack(() => run())
  })

  $effect(() => {
    const e = open
    if (e) {
      untrack(() => {
        query = e.name
        run()
        pick(e)
      })
    }
  })

  function typed() {
    clearTimeout(timer)
    timer = setTimeout(() => run(), 350)
  }

  async function pick(e: FeRepoEntry) {
    picked = e
    detail = null
    shownWeapon = ''
    weaponPreviews = {}
    detailError = ''
    try {
      const d = await api.feRepoAnimation(e.url)
      if (picked?.url === e.url) detail = d
    } catch (err) {
      if (picked?.url === e.url) detailError = err instanceof ApiError ? t(`ferepo.error.${err.detail}`) : String(err)
    }
  }
</script>

<div class="library">
  <div class="bar">
    <select bind:value={folder} onchange={() => run()} aria-label={t('ferepo.folder')}>
      <option value="">{t('ferepo.allFolders')}</option>
      {#each folders as f (f.name)}<option value={f.name}>{f.name} ({f.count})</option>{/each}
    </select>
    <input bind:value={query} oninput={typed} placeholder={t('ferepo.search')} />
    <label class="small f2e"><input type="checkbox" bind:checked={f2eOnly} onchange={() => run()} /> {t('ferepo.f2eOnly')}</label>
    <label class="small f2e" title={t('favorites.filterHint')}><input type="checkbox" bind:checked={favOnly} onchange={() => run()} /> {t('favorites.only')}</label>
    {#if initial && query !== initial}
      <button class="link small" onclick={() => { query = initial; run() }}>{t('ferepo.suggest', { name: initial })}</button>
    {/if}
  </div>
  <div class="wfilter" role="group" aria-label={t('banim.weaponFilter')}>
    <span class="small">{t('banim.weaponFilter')} :</span>
    {#each FILTER_WTYPES as wt (wt)}
      <label class="wchip small" class:on={weaponFilter.includes(wt)}>
        <input type="checkbox" checked={weaponFilter.includes(wt)}
               onchange={(e) => { weaponFilter = (e.target as HTMLInputElement).checked ? [...weaponFilter, wt] : weaponFilter.filter((w) => w !== wt); run() }} />
        {t(`wtype.${wt}`)}
      </label>
    {/each}
    {#if weaponFilter.length}<button class="link small" onclick={() => { weaponFilter = []; run() }}>{t('banim.allWeapons')}</button>{/if}
    {#if loading && weaponFilter.length}<Help text={t('banim.weaponFilterHint')} />{/if}
    <label class="wchip small" class:on={rangedOnly}>
      <input type="checkbox" checked={rangedOnly} onchange={(e) => { rangedOnly = (e.target as HTMLInputElement).checked; run() }} />
      {t('banim.ranged')}
    </label>
    <Help text={t('banim.rangedHint')} />
  </div>
  {#if error}<p class="bad small">{error}</p>{/if}
  {#if missingFolders && weaponFilter.length}<p class="warn small">{t('banim.missingFolders', { n: missingFolders })}</p>{/if}
  <div class="columns">
    <ul class="list">
      {#each entries as e (e.url)}
        <li class="row">
          <button class:active={picked?.url === e.url} onclick={() => pick(e)}>
            <span>{e.name}</span>
            <span class="muted tiny">{e.folder}{#if e.license === 'F2E'} · F2E{/if}{#if e.weapons?.length} · {e.weapons.map((w) => t(`wtype.${w}`)).join(', ')}{/if}</span>
          </button>
          <FavoriteStar kind="animations" key={e.url} />
        </li>
      {/each}
      {#if entries.length < total}
        <li><button class="link small" disabled={loading} onclick={() => run(false, true)}>{t('ferepo.more', { n: total - entries.length })}</button></li>
      {/if}
      {#if !loading && !entries.length && !error}<li class="muted small">{t('ferepo.none')}</li>{/if}
    </ul>
    <div class="preview">
      {#if picked}
        <h4>{picked.name} <FavoriteStar kind="animations" key={picked.url} /></h4>
        {#if shownPreview}
          <img src={imageUrl(shownPreview)} alt={shownWeapon || picked.name} />
        {:else if detailError}
          <p class="bad small">{detailError}</p>
        {:else if !detail}
          <p class="muted">…</p>
        {:else}
          <p class="muted small">{t('banim.lib.noPreview')}</p>
        {/if}
        {#if detail?.weapons.length}
          <div class="weapons">
            {#each detail.weapons as w (w)}
              <div class="weapon">
                <button class="small" class:shown={shownWeapon === w} title={t('banim.lib.showWeapon')} onclick={() => showWeapon(w)}>{w}</button>
                <select value={chosenWtype[w] ?? guessWtype(w)} onchange={(e) => (chosenWtype[w] = (e.target as HTMLSelectElement).value)} aria-label={t('banim.weapon')}>
                  {#each targets as wt (wt)}<option value={wt}>{targetLabel(wt)}</option>{/each}
                </select>
                <button class="play" disabled={!!importing} onclick={() => importWeapon(w)}>
                  {importing === w ? t('banim.import.busy') : t('banim.import.use')}
                </button>
              </div>
            {/each}
          </div>
          {#if importError}<p class="bad small">{importError}</p>{/if}
          {#if imported}<p class="good small">✓ {t('banim.import.done', { weapon: imported })}</p>{/if}
        {/if}
        <p class="small">{t('banim.lib.authors')} : {picked.authors.join(', ') || t('banim.lib.seeCredits')} · {picked.license}</p>
        <a class="small" href={picked.url} target="_blank" rel="noreferrer">{t('banim.lib.open')} ↗</a>
        <Help text={t('banim.import.hint')} />
      {:else}
        <p class="muted small">{t('banim.lib.pick')}</p>
      {/if}
    </div>
  </div>
</div>

<style>
  .library { display: flex; flex-direction: column; gap: 0.5rem; margin-top: 0.75rem; }
  .bar { display: flex; flex-wrap: wrap; gap: 0.5rem; align-items: center; }
  .bar > input { flex: 1; min-width: 140px; }
  .f2e { flex-direction: row; align-items: center; gap: 0.3rem; }
  .wfilter { display: flex; flex-direction: row; flex-wrap: wrap; align-items: center; gap: 0.3rem; margin: 0.4rem 0; }
  .wchip { display: inline-flex; flex-direction: row; width: auto; align-items: center; gap: 0.25rem; padding: 0.1rem 0.55rem; border: 1px solid var(--border); border-radius: 999px; cursor: pointer; }
  .wchip.on { background: var(--accent-soft); border-color: var(--accent); color: var(--accent); }
  .wchip input { margin: 0; }
  .columns { display: grid; grid-template-columns: minmax(0, 1fr) minmax(0, 1fr); gap: 0.75rem; }
  .list { list-style: none; margin: 0; padding: 0; max-height: 320px; overflow: auto; border: 1px solid var(--border); border-radius: var(--radius); }
  .list li button { display: flex; flex-direction: column; align-items: flex-start; width: 100%; border: none; border-radius: 0; text-align: left; font-weight: 600; }
  .list li.row { display: flex; align-items: center; }
  .list li.row > button { flex: 1; min-width: 0; }
  .list li button.active { background: var(--accent-soft); }
  .preview { display: flex; flex-direction: column; gap: 0.3rem; }
  .preview h4 { margin: 0; }
  .preview img { image-rendering: pixelated; max-width: 100%; align-self: flex-start; background: var(--accent-soft); border-radius: var(--radius); }
  .small { font-size: 0.8rem; margin: 0; }
  .bad { color: var(--bad); }
  .good { color: var(--good-text); }
  .weapons { display: flex; flex-direction: column; gap: 0.35rem; }
  .weapon { display: flex; gap: 0.4rem; align-items: center; flex-wrap: wrap; }
  .weapon .small { min-width: 6rem; font-weight: 700; }
  .weapon button.small { background: none; border: none; padding: 0; color: inherit; text-align: left; text-decoration: underline dotted; cursor: pointer; }
  .weapon button.shown { color: var(--accent); }
  @media (max-width: 700px) { .columns { grid-template-columns: 1fr; } }
</style>
