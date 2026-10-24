<script lang="ts">
  // Class list with map sprites, gender signs and a search field (ticket 26), in place of a plain <select>.
  // Classes never used in the game come last, in their own section.
  import { mapSpriteUrl } from '../lib/api'
  import { t } from '../lib/i18n.svelte'
  import type { ClassView } from '../lib/types'
  import GenderSign from './GenderSign.svelte'

  let { value, classes, label = '', onchange }: {
    value: string
    classes: ClassView[]
    label?: string
    onchange: (value: string) => void
  } = $props()

  let open = $state(false)
  let query = $state('')
  let active = $state(0)
  let root = $state<HTMLDivElement>()
  let search = $state<HTMLInputElement>()
  let listEl = $state<HTMLUListElement>()

  const fold = (s: string) => s.normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase()
  const current = $derived(classes.find((k) => k.id === value))
  const choices = $derived.by(() => {
    const q = fold(query.trim())
    const found = q ? classes.filter((k) => fold(k.name || '').includes(q) || fold(k.id).includes(q)) : classes
    return [...found.filter((k) => k.usedInGame), ...found.filter((k) => !k.usedInGame)]
  })
  const firstUnused = $derived(choices.findIndex((k) => !k.usedInGame))

  function toggle() {
    open = !open
    if (open) {
      query = ''
      active = Math.max(0, choices.findIndex((k) => k.id === value))
      queueMicrotask(() => {
        search?.focus()
        listEl?.querySelector('.active')?.scrollIntoView({ block: 'nearest' })
      })
    }
  }

  function pick(k: ClassView) {
    open = false
    if (k.id !== value) onchange(k.id)
  }

  function key(e: KeyboardEvent) {
    if (e.key === 'ArrowDown' || e.key === 'ArrowUp') {
      e.preventDefault()
      active = Math.max(0, Math.min(choices.length - 1, active + (e.key === 'ArrowDown' ? 1 : -1)))
      queueMicrotask(() => listEl?.querySelector('.active')?.scrollIntoView({ block: 'nearest' }))
    } else if (e.key === 'Enter') {
      e.preventDefault()
      if (choices[active]) pick(choices[active])
    } else if (e.key === 'Escape') {
      open = false
    }
  }

  $effect(() => {
    if (!open) return
    const close = (e: MouseEvent) => {
      if (root && !root.contains(e.target as Node)) open = false
    }
    document.addEventListener('mousedown', close)
    return () => document.removeEventListener('mousedown', close)
  })
</script>

<div class="picker" bind:this={root}>
  <button type="button" class="current" onclick={toggle} aria-haspopup="listbox" aria-expanded={open} aria-label={label || undefined}>
    {#if current}<img class="sprite" src={mapSpriteUrl(current.id, 'blue', true)} alt="" />{/if}
    <span class="name">{current ? current.name || current.id : value}</span>
    {#if current}<GenderSign gender={current.gender} />{/if}
    <span class="caret">▾</span>
  </button>
  {#if open}
    <div class="popup">
      <input bind:this={search} bind:value={query} placeholder={t('classes.search')} oninput={() => (active = 0)} onkeydown={key} />
      <ul role="listbox" bind:this={listEl}>
        {#each choices as k, i (k.id)}
          {#if i === firstUnused}<li class="section">{t('list.unusedClassesGroup')}</li>{/if}
          <li role="option" aria-selected={k.id === value} class:active={i === active} class:chosen={k.id === value}>
            <button type="button" onclick={() => pick(k)} onmouseenter={() => (active = i)}>
              <img class="sprite" src={mapSpriteUrl(k.id, 'blue', true)} alt="" loading="lazy" />
              <span class="name">{k.name || k.id}</span>
              <GenderSign gender={k.gender} />
            </button>
          </li>
        {:else}
          <li class="empty">{t('classes.noMatch')}</li>
        {/each}
      </ul>
    </div>
  {/if}
</div>

<style>
  .picker { position: relative; min-width: 0; }
  .current { display: flex; align-items: center; gap: 0.35rem; width: 100%; min-width: 12rem; text-align: left; padding: 0.15rem 0.4rem; }
  .current .name { flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .caret { color: var(--muted); font-size: 0.75rem; }
  .sprite { width: 16px; height: 16px; object-fit: contain; image-rendering: pixelated; flex-shrink: 0; }
  .popup { position: absolute; z-index: 30; top: calc(100% + 2px); left: 0; width: max(100%, 16rem); background: var(--panel, var(--bg)); border: 1px solid var(--border); border-radius: 6px; box-shadow: 0 4px 14px rgb(0 0 0 / 0.35); padding: 0.3rem; }
  .popup input { width: 100%; box-sizing: border-box; margin-bottom: 0.25rem; }
  ul { list-style: none; margin: 0; padding: 0; max-height: 20rem; overflow-y: auto; }
  li button { display: flex; align-items: center; gap: 0.4rem; width: 100%; text-align: left; border: none; background: none; padding: 0.15rem 0.3rem; font: inherit; color: inherit; border-radius: 4px; }
  li.active button { background: var(--accent-soft); }
  li.chosen button { font-weight: 600; }
  li .name { flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .section { color: var(--muted); font-size: 0.75rem; padding: 0.35rem 0.3rem 0.1rem; border-top: 1px solid var(--border); margin-top: 0.2rem; }
  .empty { color: var(--muted); padding: 0.3rem; font-size: 0.85rem; }
</style>
