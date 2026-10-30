<script lang="ts">
  // A new chapter after `after`, with its own empty map: on the Campaign page and in the Chapters tab's views.
  import { api } from '../lib/api'
  import { t } from '../lib/i18n.svelte'

  let { after, label, flush, onadded }: {
    after: number
    label: string
    /** save what is being edited first */
    flush: () => Promise<void>
    onadded: (index: number) => void | Promise<void>
  } = $props()

  let free = $state(0)
  let open = $state(false)
  let title = $state('')
  let width = $state(15)
  let height = $state(10)
  let error = $state('')
  let busy = $state(false)

  const refresh = () => api.freeChapters().then((r) => (free = r.free)).catch(() => {})
  $effect(() => {
    void after
    refresh()
  })

  async function add() {
    error = ''
    busy = true
    try {
      await flush()
      const { index } = await api.newChapter(after, width, height, title)
      await refresh()
      await onadded(index)
      open = false
      title = ''
    } catch (e) {
      const code = String(e).match(/(noFreeChapter|badMapSize)/)?.[1]
      error = code ? t(`flow.add.${code}`) : String(e)
    } finally {
      busy = false
    }
  }
</script>

<div class="add-chapter">
  {#if open}
    <label>{t('flow.add.title')} <input bind:value={title} maxlength="40" /></label>
    <label>{t('flow.add.width')} <input type="number" bind:value={width} min="15" max="64" /></label>
    <label>{t('flow.add.height')} <input type="number" bind:value={height} min="10" max="64" /></label>
    <button class="primary" onclick={add} disabled={busy}>{busy ? '…' : t('flow.add.confirm')}</button>
    <button class="link" onclick={() => (open = false)}>{t('flow.add.cancel')}</button>
    <p class="tiny muted">{t('flow.add.hint', { n: free })}</p>
  {:else}
    <button onclick={() => (open = true)} disabled={!free} title={t('flow.add.hint', { n: free })}>+ {label}</button>
  {/if}
  {#if error}<p class="bad small">{error}</p>{/if}
</div>

<style>
  .add-chapter { display: flex; flex-wrap: wrap; gap: 0.4rem; align-items: center; margin: 0.6rem 0; }
  .add-chapter label { display: flex; gap: 0.3rem; align-items: center; font-size: 0.85rem; }
  .add-chapter input[type='number'] { width: 4rem; }
</style>
