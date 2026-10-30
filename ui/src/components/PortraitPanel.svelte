<script lang="ts">
  // Replace a portrait of the game with a 128 x 112 sheet (server: decomp/portraits.py).
  import { api, ApiError, portraitSheetUrl } from '../lib/api'
  import { problemText, t } from '../lib/i18n.svelte'
  import { portraitsChanged } from '../lib/portraits.svelte'
  import type { FeRepoEntry, PortraitImport, PortraitInfo, Problem } from '../lib/types'
  import FeRepoBrowser from './FeRepoBrowser.svelte'
  import NumberField from './NumberField.svelte'

  let { portraitId, problems, onproblems, characterName = '', onnew, onremoved }: {
    portraitId: number; problems: Problem[]; onproblems: (p: Problem[]) => void
    /** the character's name, the first search in FE-Repo */
    characterName?: string
    /** a new portrait was added for this character (after the game's ones), or renamed */
    onnew?: (id: number, name: string) => void
    /** a portrait the project added was deleted */
    onremoved?: (id: number) => void
  } = $props()

  const SCALE = 2
  let info = $state<PortraitInfo | null>(null)
  /** no portrait with this id (a deleted new portrait, or a number past the end) */
  let missing = $state(false)
  let error = $state('')
  let busy = $state(false)
  let fileInput = $state<HTMLInputElement>()
  let newInput = $state<HTMLInputElement>()
  /** what a FE-Repo pick does: replace this portrait or add a new one */
  let browsing = $state<'replace' | 'new' | null>(null)

  const imported = $derived(info?.imported ?? null)
  const positions = $derived(imported ?? info?.original ?? null)
  const myProblems = $derived(problems.filter((p) => p.id === `portrait:${portraitId}`))

  $effect(() => {
    const id = portraitId
    error = ''
    info = null
    missing = false
    api.portrait(id).then((i) => {
      if (id === portraitId) info = i
    }).catch(() => {
      if (id === portraitId) missing = true
    })
  })

  async function importFile(file: File | undefined) {
    if (!file) return
    busy = true
    error = ''
    try {
      const r = await api.importPortrait(portraitId, file)
      onproblems(r.problems)
      info = await api.portrait(portraitId)
      portraitsChanged()
    } catch (e) {
      error = e instanceof ApiError ? t(`problem.portrait.${e.detail}`) : String(e)
    } finally {
      busy = false
      if (fileInput) fileInput.value = ''
    }
  }

  async function addFile(file: File | undefined) {
    if (!file) return
    await adding(() => api.addPortrait(file))
    if (newInput) newInput.value = ''
  }

  async function adding(call: () => Promise<{ id: number; entry: PortraitImport; problems: Problem[] }>) {
    busy = true
    error = ''
    try {
      const r = await call()
      onproblems(r.problems)
      portraitsChanged()
      browsing = null
      onnew?.(r.id, r.entry.name ?? '')
    } catch (e) {
      error = e instanceof ApiError ? t(`problem.portrait.${e.detail}`) : String(e)
    } finally {
      busy = false
    }
  }

  async function importFeRepo(e: FeRepoEntry) {
    if (browsing === 'new') return adding(() => api.addFeRepoPortrait(e.url))
    busy = true
    error = ''
    try {
      onproblems((await api.importFeRepoPortrait(portraitId, e.url)).problems)
      info = await api.portrait(portraitId)
      portraitsChanged()
      browsing = null
    } catch (err) {
      error = err instanceof ApiError ? t(`problem.portrait.${err.detail}`) : String(err)
    } finally {
      busy = false
    }
  }

  async function remove() {
    busy = true
    const added = info?.added
    try {
      onproblems((await api.removePortrait(portraitId)).problems)
      portraitsChanged()
      if (added) {
        info = null
        missing = true
        onremoved?.(portraitId)
      } else {
        info = await api.portrait(portraitId)
      }
    } finally {
      busy = false
    }
  }

  /** The current sheet as a file (a template to draw on). */
  function download() {
    const a = document.createElement('a')
    a.href = portraitSheetUrl(portraitId)
    a.download = `portrait-${portraitId}.png`
    a.click()
  }

  async function rename(name: string) {
    const r = await api.renamePortrait(portraitId, name)
    onproblems(r.problems)
    info = { ...info!, name: r.entry.name ?? name, imported: r.entry }
    onnew?.(portraitId, r.entry.name ?? name)
  }

  async function move(part: 'mouth' | 'eyes', k: 0 | 1, value: number) {
    if (!imported) return
    const all = await api.getData<Record<string, PortraitImport>>('portraits')
    const entry = all[String(portraitId)]
    if (!entry) return
    entry[part][k] = value
    const r = await api.saveData('portraits', all)
    onproblems(r.problems)
    info = { ...info!, imported: entry }
    portraitsChanged()
  }
</script>

{#snippet addNew()}
  <div class="new">
    <span class="small"><strong>{t('portrait.new')}</strong></span>
    <span class="muted tiny">{missing ? t('portrait.newHintNone') : t('portrait.newHint')}</span>
    <div class="buttons">
      <button onclick={() => newInput?.click()} disabled={busy}>{t('portrait.newFile')}</button>
      <button onclick={() => (browsing = browsing === 'new' ? null : 'new')} class:active={browsing === 'new'}>{t('portrait.newFeRepo')}</button>
    </div>
    <input type="file" accept="image/png" hidden bind:this={newInput} onchange={(e) => addFile((e.target as HTMLInputElement).files?.[0])} />
  </div>
{/snippet}

{#if missing}
  {#if portraitId === 0}
    <p class="muted small">{t('portrait.none')}</p>
  {:else}
    <p class="bad small">{t('portrait.missing', { id: portraitId })}</p>
  {/if}
  {#if onnew}
    {@render addNew()}
    {#if error}<p class="bad small">{error}</p>{/if}
    {#if browsing}<div class="ferepo"><FeRepoBrowser initial={characterName} {busy} onpick={importFeRepo} /></div>{/if}
  {/if}
{:else}
<div class="portrait-panel">
  <div class="sheet" style="width: {128 * SCALE}px; height: {112 * SCALE}px">
    <img src={portraitSheetUrl(portraitId)} alt={info?.name ?? ''} style="width: {128 * SCALE}px; height: {112 * SCALE}px" />
    {#if positions}
      <span class="box mouth" style="left: {positions.mouth[0] * 8 * SCALE}px; top: {positions.mouth[1] * 8 * SCALE}px" title={t('portrait.mouth')}></span>
      <span class="box eyes" style="left: {positions.eyes[0] * 8 * SCALE}px; top: {positions.eyes[1] * 8 * SCALE}px" title={t('portrait.eyes')}></span>
    {/if}
  </div>
  <div class="side">
    {#if info?.added}
      <label class="small name">{t('portrait.name')}
        <input value={info.name} maxlength="40" onchange={(e) => rename((e.target as HTMLInputElement).value)} />
      </label>
      <p class="muted tiny">{t('portrait.addedHint', { id: portraitId })}</p>
    {:else}
      <p class="small">
        {#if imported}<strong>{t('portrait.imported')}</strong>{:else}{t('portrait.game', { name: info?.name ?? '' })}{/if}
      </p>
    {/if}
    {#if info?.sharedWith.length}<p class="muted small">{t('portrait.shared', { ids: info.sharedWith.join(', ') })}</p>{/if}
    <div class="buttons">
      <button onclick={() => fileInput?.click()} disabled={busy}>{t('portrait.import')}</button>
      <button onclick={() => (browsing = browsing === 'replace' ? null : 'replace')} class:active={browsing === 'replace'}>{t('ferepo.open')}</button>
      <button onclick={download}>{t('portrait.download')}</button>
      {#if info?.added}
        <button class="link" onclick={remove} disabled={busy} title={t('portrait.deleteHint')}>{t('portrait.delete')}</button>
      {:else if imported}
        <button class="link" onclick={remove} disabled={busy}>{t('portrait.reset')}</button>
      {/if}
    </div>
    <input type="file" accept="image/png" hidden bind:this={fileInput} onchange={(e) => importFile((e.target as HTMLInputElement).files?.[0])} />
    {#if onnew && info && !info.added}{@render addNew()}{/if}
    {#if imported?.source}
      <p class="small">
        {t('ferepo.from', { name: imported.source.name, authors: imported.source.authors.join(', ') || t('ferepo.unknownAuthor') })}
        <span class="badge" class:f2e={imported.source.license === 'F2E'} title={t(`ferepo.license.${imported.source.license}`)}>{imported.source.license}</span>
      </p>
    {/if}
    {#if imported}
      <div class="row">
        <NumberField label={t('portrait.mouthX')} value={imported.mouth[0]} min={0} max={8} compact onchange={(v) => move('mouth', 0, v)} />
        <NumberField label={t('portrait.mouthY')} value={imported.mouth[1]} min={0} max={8} compact onchange={(v) => move('mouth', 1, v)} />
        <NumberField label={t('portrait.eyesX')} value={imported.eyes[0]} min={0} max={8} compact onchange={(v) => move('eyes', 0, v)} />
        <NumberField label={t('portrait.eyesY')} value={imported.eyes[1]} min={0} max={8} compact onchange={(v) => move('eyes', 1, v)} />
      </div>
    {/if}
    <p class="muted tiny">{t('portrait.hint')}</p>
    {#if error}<p class="bad small">{error}</p>{/if}
    {#each myProblems as pr, k (k)}<p class="{pr.severity === 'error' ? 'bad' : 'warn'} small">{problemText(pr)}</p>{/each}
  </div>
  {#if browsing}
    <div class="ferepo"><FeRepoBrowser initial={characterName} {busy} onpick={importFeRepo} /></div>
  {/if}
</div>
{/if}

<style>
  .portrait-panel { display: flex; gap: 0.8rem; flex-wrap: wrap; align-items: flex-start; }
  .sheet { position: relative; flex-shrink: 0; background: repeating-conic-gradient(var(--border) 0% 25%, transparent 0% 50%) 50% / 16px 16px; border-radius: 4px; }
  .sheet img { image-rendering: pixelated; display: block; }
  .box { position: absolute; width: 64px; height: 32px; border: 2px solid; box-sizing: border-box; pointer-events: none; }
  .box.mouth { border-color: #e74c3c; }
  .box.eyes { border-color: #3498db; }
  .side { display: flex; flex-direction: column; gap: 0.4rem; min-width: 14rem; flex: 1; }
  .buttons { display: flex; gap: 0.6rem; align-items: center; flex-wrap: wrap; }
  .row { display: flex; gap: 0.5rem; flex-wrap: wrap; }
  .small { font-size: 0.8rem; }
  .tiny { font-size: 0.72rem; }
  .bad { color: var(--bad); }
  .warn { color: var(--warn); }
  p { margin: 0; }
  .ferepo { flex-basis: 100%; }
  .new { display: flex; flex-direction: column; gap: 0.25rem; border-top: 1px solid var(--border); padding-top: 0.4rem; }
  .name { display: flex; gap: 0.4rem; align-items: center; }
  .name input { flex: 1; max-width: 16rem; }
  .active { border-color: var(--accent); background: var(--accent-soft); }
  .badge { font-size: 0.7rem; padding: 0 0.3rem; border-radius: 4px; background: var(--warn-soft); color: var(--warn); }
  .badge.f2e { background: var(--accent-soft); color: var(--good); }
  .link { border: none; background: none; padding: 0; color: var(--accent); font: inherit; font-size: 0.8rem; }
</style>
