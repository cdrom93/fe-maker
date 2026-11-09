<script lang="ts">
  // FE Maker > Options…: a window with the categories on the left, like an office suite's Options window.
  import { api, ApiError } from '../lib/api'
  import { fileMenu } from '../lib/filemenu.svelte'
  import { t } from '../lib/i18n.svelte'
  import type { Status } from '../lib/types'
  import Help from './Help.svelte'
  import KeysDialog from './KeysDialog.svelte'
  import ProjectSettings from './ProjectSettings.svelte'

  let { status, onChanged, onClose }: { status: Status; onChanged: () => void; onClose: () => void } = $props()

  type Category = 'emulator' | 'project'
  let category = $state<Category>('emulator')
  let showKeys = $state(false)
  let error = $state('')
  const categories = $derived<Category[]>(fileMenu.project ? ['emulator', 'project'] : ['emulator'])

  $effect(() => { fileMenu.keysOpen = showKeys })

  /** mGBA's sound for the next tests: once set here, FE Maker writes the volume too (it stays 100 % until moved). */
  async function setSound(change: { volume?: number; mute?: boolean }) {
    error = ''
    try {
      await api.updateSettings({ volume: status.volume ?? 100, ...change })
      onChanged()
    } catch (e) {
      error = e instanceof ApiError ? e.detail : String(e)
    }
  }

  /** One mGBA setting; null gives it back to mGBA. */
  async function setOption(key: string, raw: string) {
    error = ''
    const value = raw === '' ? null : raw === 'true' ? true : raw === 'false' ? false : Number(raw)
    try {
      await api.updateSettings({ mgbaOptions: { [key]: value } })
      onChanged()
    } catch (e) {
      error = e instanceof ApiError ? e.detail : String(e)
    }
  }

  function choiceLabel(key: string, v: number | boolean): string {
    if (typeof v === 'boolean') return t(v ? 'file.yes' : 'file.no')
    if (key === 'fastForwardRatio') return v < 0 ? t('file.mgba.unbounded') : `×${v}`
    if (key === 'scale') return `×${v} (${240 * v} × ${160 * v})`
    return String(v)
  }

  function onKey(e: KeyboardEvent) {
    if (e.key === 'Escape' && !showKeys) onClose()
  }
</script>

<svelte:window onkeydown={onKey} />

<div class="backdrop" role="presentation" onclick={(e) => { if (e.target === e.currentTarget) onClose() }}>
  <div class="panel dialog" role="dialog" aria-modal="true" aria-labelledby="options-title">
    <h2 id="options-title">{t('file.options')}</h2>
    <div class="body">
      <nav class="categories" aria-label={t('file.options')}>
        {#each categories as c (c)}
          <button class:here={category === c} aria-current={category === c} onclick={() => (category = c)}>{t(`file.category.${c}`)}</button>
        {/each}
      </nav>
      <div class="settings">
        {#if category === 'emulator'}
          <h3>{t('file.category.emulator')}</h3>
          <div class="option">
            <span>{t('keys.title')}</span>
            <button onclick={() => (showKeys = true)}>{t('file.keys')}</button>
          </div>
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
          {#each Object.entries(status.mgbaChoices) as [key, values] (key)}
            <div class="option">
              <span>{t(`file.mgba.${key}`)} <Help text={t(`file.mgba.${key}Hint`)} /></span>
              <select value={key in status.mgbaOptions ? String(status.mgbaOptions[key]) : ''} aria-label={t(`file.mgba.${key}`)}
                      onchange={(e) => setOption(key, (e.target as HTMLSelectElement).value)}>
                <option value="">{t('file.mgba.default')}</option>
                {#each values as v (String(v))}<option value={String(v)}>{choiceLabel(key, v)}</option>{/each}
              </select>
            </div>
          {/each}
        {:else}
          <h3>{t('file.category.project')} <Help text={t('options.editorHint')} /></h3>
          <ProjectSettings />
        {/if}
        {#if error}<p class="bad">{error}</p>{/if}
      </div>
    </div>
    <div class="actions"><button onclick={onClose}>{t('build.close')}</button></div>
  </div>
</div>

{#if showKeys}
  <KeysDialog onClose={() => (showKeys = false)} />
{/if}

<style>
  .backdrop { position: fixed; inset: 0; background: rgb(0 0 0 / 0.45); display: grid; place-items: center; padding: 1rem; z-index: 45; }
  .dialog { width: min(720px, 100%); max-height: 90vh; overflow: auto; display: flex; flex-direction: column; gap: 0.75rem; }
  h2 { margin: 0; }
  .body { display: grid; grid-template-columns: 11rem 1fr; gap: 1rem; min-height: 16rem; }
  .categories { display: flex; flex-direction: column; gap: 0.2rem; border-right: 1px solid var(--border); padding-right: 0.75rem; }
  .categories button { text-align: left; border: none; background: none; color: var(--text); padding: 0.5rem 0.75rem; font-weight: 600; }
  .categories button:hover, .categories button.here { background: var(--accent-soft); }
  .settings h3 { margin: 0 0 0.5rem; font-size: 0.95rem; padding-bottom: 0.35rem; border-bottom: 1px solid var(--border); }
  .option { display: flex; justify-content: space-between; align-items: center; gap: 1rem; padding: 0.35rem 0; flex-wrap: wrap; }
  .option > span:first-child { font-weight: 600; }
  .sound { display: inline-flex; align-items: center; gap: 0.5rem; }
  .sound input[type='range'] { width: 10rem; }
  .pct { min-width: 3.2em; text-align: right; color: var(--muted); font-size: 0.85rem; }
  .mute { display: inline-flex; align-items: center; gap: 0.25rem; font-weight: 600; flex-direction: row; }
  .actions { display: flex; justify-content: flex-end; }
  .bad { color: var(--bad); }
  @media (max-width: 600px) {
    .body { grid-template-columns: 1fr; }
    .categories { flex-direction: row; border-right: none; border-bottom: 1px solid var(--border); padding: 0 0 0.5rem; }
  }
</style>
