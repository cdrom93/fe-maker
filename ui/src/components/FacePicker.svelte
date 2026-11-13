<script lang="ts">
  import { onMount } from 'svelte'
  import { portraitUrl } from '../lib/api'
  import { t } from '../lib/i18n.svelte'
  import type { DialogueFace } from '../lib/types'

  let {
    faces,
    label,
    first = [],
    hint = t('dlg.pickFaceHint'),
    onpick,
    onclose,
  }: {
    faces: DialogueFace[]
    label: (id: string) => string
    /** faces shown first (the chapter's speakers) */
    first?: string[]
    hint?: string
    onpick: (face: string) => void
    onclose: () => void
  } = $props()

  let query = $state('')
  let search = $state<HTMLInputElement>()
  onMount(() => search?.focus())
  const fold = (s: string) => s.normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase()
  const shown = $derived.by(() => {
    const q = fold(query.trim())
    const all = faces.filter((f) => !q || fold(label(f.id)).includes(q) || fold(f.id).includes(q))
    const ahead = (f: DialogueFace) => first.includes(f.id) || !!f.active
    return [...all.filter(ahead), ...all.filter((f) => !ahead(f))]
  })
</script>

<div class="picker" role="dialog" aria-label={t('dlg.pickFace')}>
  <div class="head">
    <input type="search" placeholder={t('dlg.searchFace')} bind:value={query} bind:this={search}
           onkeydown={(e) => { if (e.key === 'Escape') onclose(); if (e.key === 'Enter' && shown[0]) onpick(shown[0].id) }} />
    <button class="close" onclick={onclose} aria-label={t('dlg.close')}>✕</button>
  </div>
  {#if hint}<p class="muted tiny">{hint}</p>{/if}
  <div class="grid">
    {#each shown as f (f.id)}
      <button class="face" title={f.active ? t('dlg.activeFaceHint') : label(f.id)} draggable="true" onclick={() => onpick(f.id)}
              ondragstart={(e) => e.dataTransfer?.setData('text/plain', JSON.stringify({ face: f.id }))}>
        <img src={portraitUrl(f.portrait, true)} alt="" loading="lazy" />
        <span class="tiny">{label(f.id)}</span>
      </button>
    {/each}
  </div>
</div>

<style>
  .picker { border: 1px solid var(--accent); border-radius: 8px; background: var(--panel); padding: 0.5rem; display: flex; flex-direction: column; gap: 0.35rem; }
  .head { display: flex; gap: 0.4rem; }
  .head input { flex: 1; }
  .close { padding: 0 0.5rem; }
  .tiny { font-size: 0.72rem; }
  p { margin: 0; }
  .grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(72px, 1fr)); gap: 0.25rem; max-height: 260px; overflow-y: auto; }
  .face { display: flex; flex-direction: column; align-items: center; gap: 0.1rem; padding: 0.2rem; background: none; border-color: transparent; }
  .face:hover { background: var(--accent-soft); border-color: var(--accent); }
  .face img { width: 48px; height: 40px; image-rendering: pixelated; }
  .face span { max-width: 100%; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
</style>
