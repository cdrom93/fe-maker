<script lang="ts">
  // FE Maker's settings for the open project (ticket 168), in File > Options: they do not change the game.
  import Help from './Help.svelte'
  import { api } from '../lib/api'
  import { projectView } from '../lib/appContext.svelte'
  import { t } from '../lib/i18n.svelte'

  let test = $state<{ start: string; simplePrologue: boolean } | null>(null)
  let error = $state('')

  $effect(() => {
    api.testOptions().then((o) => (test = o)).catch((e) => (error = String(e)))
  })

  async function setTest(change: { start?: string; simplePrologue?: boolean }) {
    error = ''
    try {
      test = await api.setTestOptions(change)
    } catch (e) {
      error = String(e)
    }
  }

  async function setShowOriginal(show: boolean) {
    error = ''
    try {
      await api.setShowOriginal(show)
      projectView.showOriginal = show
    } catch (e) {
      error = String(e)
    }
  }
</script>

<h4>{t('options.group.interface')}</h4>
<label class="switch">
  <input type="checkbox" checked={projectView.showOriginal} onchange={(e) => setShowOriginal((e.target as HTMLInputElement).checked)} />
  <span><strong>{t('options.showOriginal')}</strong> <Help text={t('options.showOriginalHint')} /></span>
</label>
{#if test}
  <h4>{t('options.testTitle')}</h4>
  <label class="switch">
    <span><strong>{t('options.testStart')}</strong> <Help text={t('ws.startHint')} /></span>
    <select value={test.start} onchange={(e) => setTest({ start: (e.target as HTMLSelectElement).value })}>
      <option value="map">{t('ws.start.map')}</option>
      <option value="menu">{t('ws.start.menu')}</option>
      <option value="normal">{t('ws.start.normal')}</option>
    </select>
  </label>
  <label class="switch">
    <input type="checkbox" checked={test.simplePrologue} onchange={(e) => setTest({ simplePrologue: (e.target as HTMLInputElement).checked })} />
    <span><strong>{t('ws.simplePrologue')}</strong> <Help text={t('ws.simplePrologueHint')} /></span>
  </label>
{/if}
{#if error}<p class="bad">{error}</p>{/if}

<style>
  .switch { display: flex; flex-direction: row; flex-wrap: wrap; gap: 0.5rem; align-items: center; padding: 0.3rem 0; }
  .switch > span { flex: 1 1 10rem; }
  h4 { margin: 0.6rem 0 0.1rem; font-size: 0.85rem; color: var(--muted); }
  .bad { color: var(--bad); margin: 0; }
</style>
