<script lang="ts">
  // Battle animations of FE-Repo (ticket 44, server: ferepo.py): browse by kind of class, search; choosing
  // one shows its preview, its weapons, authors and license; a weapon's animation can be given to the class
  // (downloaded, converted and kept in the project).
  import { untrack } from 'svelte'
  import { api, ApiError } from '../lib/api'
  import { t } from '../lib/i18n.svelte'
  import type { FeRepoAnimation, FeRepoEntry } from '../lib/types'

  let { initial = '', classId, wtypes, onimported }: {
    /** a suggested search (the class's name) */
    initial?: string
    classId: string
    /** weapon types the animation can be given for */
    wtypes: string[]
    onimported: () => void
  } = $props()

  /** FEditor's numbered weapon folders ("1. Sword", "6. Magic") -> weapon type. */
  const FOLDER_WTYPES: [RegExp, string][] = [
    [/staff|staves/i, 'staff'], [/light/i, 'light'], [/dark|flux/i, 'dark'], [/magic|anima|tome/i, 'anima'],
    [/hand ?axe|axe/i, 'axe'], [/bow|arrow/i, 'bow'], [/lance|spear|javelin/i, 'lance'], [/sword|blade|knife/i, 'sword'],
    [/unarmed|item|refresh|dance|play/i, 'item'],
  ]
  function guessWtype(folderName: string): string {
    const found = FOLDER_WTYPES.find(([re]) => re.test(folderName))?.[1]
    return found && wtypes.includes(found) ? found : wtypes[0] ?? 'sword'
  }
  let chosenWtype = $state<Record<string, string>>({})
  let importing = $state('')
  let importError = $state('')
  let imported = $state('')

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
  // weapon filter (ticket 47): the first time, the server asks GitHub for the weapons of each folder
  let weaponFilter = $state('')
  const FILTER_WTYPES = ['sword', 'lance', 'axe', 'bow', 'anima', 'light', 'dark', 'staff', 'item']
  let entries = $state<FeRepoEntry[]>([])
  let folders = $state<{ name: string; count: number }[]>([])
  let total = $state(0)
  let loading = $state(false)
  let error = $state('')
  let picked = $state<FeRepoEntry | null>(null)
  let detail = $state<FeRepoAnimation | null>(null)
  let detailError = $state('')
  let timer: ReturnType<typeof setTimeout> | undefined
  let request = 0

  const imageUrl = (url: string) => `/api/ferepo/image?url=${encodeURIComponent(url)}`

  async function run(refresh = false, more = false) {
    const n = ++request
    loading = true
    error = ''
    try {
      const r = await api.feRepoAnimations(query, { refresh, folder, f2e: f2eOnly, wtype: weaponFilter, offset: more ? entries.length : 0 })
      if (n !== request) return
      entries = more ? [...entries, ...r.entries] : r.entries
      total = r.total
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

  function typed() {
    clearTimeout(timer)
    timer = setTimeout(() => run(), 350)
  }

  async function pick(e: FeRepoEntry) {
    picked = e
    detail = null
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
    <select bind:value={weaponFilter} onchange={() => run()} aria-label={t('banim.weaponFilter')} title={t('banim.weaponFilterHint')}>
      <option value="">{t('banim.allWeapons')}</option>
      {#each FILTER_WTYPES as wt (wt)}<option value={wt}>{t(`wtype.${wt}`)}</option>{/each}
    </select>
    <input bind:value={query} oninput={typed} placeholder={t('ferepo.search')} />
    <label class="small f2e"><input type="checkbox" bind:checked={f2eOnly} onchange={() => run()} /> {t('ferepo.f2eOnly')}</label>
    {#if initial && query !== initial}
      <button class="link small" onclick={() => { query = initial; run() }}>🔎 {initial}</button>
    {/if}
  </div>
  {#if error}<p class="bad small">{error}</p>{/if}
  {#if loading && weaponFilter}<p class="muted small">{t('banim.weaponFilterHint')}</p>{/if}
  <div class="columns">
    <ul class="list">
      {#each entries as e (e.url)}
        <li>
          <button class:active={picked?.url === e.url} onclick={() => pick(e)}>
            <span>{e.name}</span>
            <span class="muted tiny">{e.folder}{#if e.license === 'F2E'} · F2E{/if}{#if e.weapons?.length} · {e.weapons.map((w) => t(`wtype.${w}`)).join(', ')}{/if}</span>
          </button>
        </li>
      {/each}
      {#if entries.length < total}
        <li><button class="link small" disabled={loading} onclick={() => run(false, true)}>{t('ferepo.more', { n: total - entries.length })}</button></li>
      {/if}
      {#if !loading && !entries.length && !error}<li class="muted small">{t('ferepo.none')}</li>{/if}
    </ul>
    <div class="preview">
      {#if picked}
        <h4>{picked.name}</h4>
        {#if detail?.preview}
          <img src={imageUrl(detail.preview)} alt={picked.name} />
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
                <span class="small">{w}</span>
                <select value={chosenWtype[w] ?? guessWtype(w)} onchange={(e) => (chosenWtype[w] = (e.target as HTMLSelectElement).value)} aria-label={t('banim.weapon')}>
                  {#each wtypes as wt (wt)}<option value={wt}>{t(`wtype.${wt}`)}</option>{/each}
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
        <p class="muted tiny">{t('banim.import.hint')}</p>
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
  .columns { display: grid; grid-template-columns: minmax(0, 1fr) minmax(0, 1fr); gap: 0.75rem; }
  .list { list-style: none; margin: 0; padding: 0; max-height: 320px; overflow: auto; border: 1px solid var(--border); border-radius: var(--radius); }
  .list li button { display: flex; flex-direction: column; align-items: flex-start; width: 100%; border: none; border-radius: 0; text-align: left; font-weight: 600; }
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
  @media (max-width: 700px) { .columns { grid-template-columns: 1fr; } }
</style>
