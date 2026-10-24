<script lang="ts">
  // Replace a portrait of the game with a 128 x 112 sheet (server: decomp/portraits.py).
  import { api, ApiError, portraitSheetUrl } from '../lib/api'
  import { problemText, t } from '../lib/i18n.svelte'
  import { portraitsChanged } from '../lib/portraits.svelte'
  import type { PortraitImport, PortraitInfo, Problem } from '../lib/types'
  import NumberField from './NumberField.svelte'

  let { portraitId, problems, onproblems }: { portraitId: number; problems: Problem[]; onproblems: (p: Problem[]) => void } = $props()

  const SCALE = 2
  let info = $state<PortraitInfo | null>(null)
  let error = $state('')
  let busy = $state(false)
  let fileInput = $state<HTMLInputElement>()

  const imported = $derived(info?.imported ?? null)
  const positions = $derived(imported ?? info?.original ?? null)
  const myProblems = $derived(problems.filter((p) => p.id === `portrait:${portraitId}`))

  $effect(() => {
    const id = portraitId
    error = ''
    info = null
    api.portrait(id).then((i) => {
      if (id === portraitId) info = i
    }).catch(() => {})
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

  async function remove() {
    busy = true
    try {
      onproblems((await api.removePortrait(portraitId)).problems)
      info = await api.portrait(portraitId)
      portraitsChanged()
    } finally {
      busy = false
    }
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

<div class="portrait-panel">
  <div class="sheet" style="width: {128 * SCALE}px; height: {112 * SCALE}px">
    <img src={portraitSheetUrl(portraitId)} alt={info?.name ?? ''} style="width: {128 * SCALE}px; height: {112 * SCALE}px" />
    {#if positions}
      <span class="box mouth" style="left: {positions.mouth[0] * 8 * SCALE}px; top: {positions.mouth[1] * 8 * SCALE}px" title={t('portrait.mouth')}></span>
      <span class="box eyes" style="left: {positions.eyes[0] * 8 * SCALE}px; top: {positions.eyes[1] * 8 * SCALE}px" title={t('portrait.eyes')}></span>
    {/if}
  </div>
  <div class="side">
    <p class="small">
      {#if imported}<strong>{t('portrait.imported')}</strong>{:else}{t('portrait.game', { name: info?.name ?? '' })}{/if}
    </p>
    {#if info?.sharedWith.length}<p class="muted small">{t('portrait.shared', { ids: info.sharedWith.join(', ') })}</p>{/if}
    <div class="buttons">
      <button onclick={() => fileInput?.click()} disabled={busy}>🖼 {t('portrait.import')}</button>
      <a class="small" href={portraitSheetUrl(portraitId)} download={`portrait-${portraitId}.png`}>⬇ {t('portrait.download')}</a>
      {#if imported}<button class="link" onclick={remove} disabled={busy}>{t('portrait.reset')}</button>{/if}
    </div>
    <input type="file" accept="image/png" hidden bind:this={fileInput} onchange={(e) => importFile((e.target as HTMLInputElement).files?.[0])} />
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
</div>

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
  .link { border: none; background: none; padding: 0; color: var(--accent); font: inherit; font-size: 0.8rem; }
</style>
