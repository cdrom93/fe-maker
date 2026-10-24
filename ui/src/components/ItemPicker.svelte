<script lang="ts">
  // Item list with icons and a search field (ticket 17), in place of a plain <select>.
  import { itemIconUrl } from '../lib/api'
  import { t } from '../lib/i18n.svelte'
  import type { Item } from '../lib/types'

  let {
    value,
    items,
    extra = [],
    disabled = false,
    label = '',
    icon = true,
    onchange,
  }: {
    value: string
    items: Item[]
    /** Choices before the items: "none", "gold"... */
    extra?: { value: string; label: string }[]
    disabled?: boolean
    label?: string
    /** Icon of the chosen item on the button (off when a link to the item sheet shows it next to it). */
    icon?: boolean
    onchange: (value: string) => void
  } = $props()

  let open = $state(false)
  let query = $state('')
  let active = $state(0)
  let root = $state<HTMLDivElement>()
  let search = $state<HTMLInputElement>()
  let listEl = $state<HTMLUListElement>()

  const fold = (s: string) => s.normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase()
  const current = $derived(items.find((i) => i.id === value))
  const currentExtra = $derived(extra.find((e) => e.value === value))
  type Choice = { value: string; label: string; item?: Item }
  const choices = $derived.by<Choice[]>(() => {
    const q = fold(query.trim())
    const all: Choice[] = [
      ...extra,
      ...items.map((i) => ({ value: i.id, label: i.name || i.id, item: i })),
    ]
    if (!q) return all
    return all.filter((c) => fold(c.label).includes(q) || (c.item && (fold(c.item.id).includes(q) || fold(t(`wtype.${c.item.weaponType}`)).includes(q))))
  })

  function toggle() {
    if (disabled) return
    open = !open
    if (open) {
      query = ''
      active = Math.max(0, choices.findIndex((c) => c.value === value))
      queueMicrotask(() => {
        search?.focus()
        listEl?.querySelector('.active')?.scrollIntoView({ block: 'nearest' })
      })
    }
  }

  function pick(c: Choice) {
    open = false
    if (c.value !== value) onchange(c.value)
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
  <button type="button" class="current" {disabled} onclick={toggle} aria-haspopup="listbox" aria-expanded={open} aria-label={label || undefined}>
    {#if icon}{#if current}<img class="pixel" src={itemIconUrl(current.iconId)} alt="" />{:else}<span class="blank"></span>{/if}{/if}
    <span class="name">{current ? current.name || current.id : (currentExtra?.label ?? value)}</span>
    <span class="caret">▾</span>
  </button>
  {#if open}
    <div class="popup">
      <input bind:this={search} bind:value={query} placeholder={t('items.search')} oninput={() => (active = 0)} onkeydown={key} />
      <ul role="listbox" bind:this={listEl}>
        {#each choices as c, i (c.value)}
          <li role="option" aria-selected={c.value === value} class:active={i === active} class:chosen={c.value === value}>
            <button type="button" onclick={() => pick(c)} onmouseenter={() => (active = i)}>
              {#if c.item}<img class="pixel" src={itemIconUrl(c.item.iconId)} alt="" loading="lazy" />{:else}<span class="blank"></span>{/if}
              <span class="name">{c.label}</span>
              {#if c.item && c.item.weaponType !== 'item'}<span class="type">{t(`wtype.${c.item.weaponType}`)}</span>{/if}
            </button>
          </li>
        {:else}
          <li class="empty">{t('items.noMatch')}</li>
        {/each}
      </ul>
    </div>
  {/if}
</div>

<style>
  .picker { position: relative; min-width: 0; }
  .current { display: flex; align-items: center; gap: 0.35rem; width: 100%; min-width: 11rem; text-align: left; padding: 0.15rem 0.4rem; }
  .current .name { flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .caret { color: var(--muted); font-size: 0.75rem; }
  .pixel { width: 16px; height: 16px; image-rendering: pixelated; flex-shrink: 0; }
  .blank { display: inline-block; width: 16px; height: 16px; flex-shrink: 0; }
  .popup { position: absolute; z-index: 30; top: calc(100% + 2px); left: 0; width: max(100%, 16rem); background: var(--panel, var(--bg)); border: 1px solid var(--border); border-radius: 6px; box-shadow: 0 4px 14px rgb(0 0 0 / 0.35); padding: 0.3rem; }
  .popup input { width: 100%; box-sizing: border-box; margin-bottom: 0.25rem; }
  ul { list-style: none; margin: 0; padding: 0; max-height: 18rem; overflow-y: auto; }
  li button { display: flex; align-items: center; gap: 0.4rem; width: 100%; text-align: left; border: none; background: none; padding: 0.15rem 0.3rem; font: inherit; color: inherit; border-radius: 4px; }
  li.active button { background: var(--accent-soft); }
  li.chosen button { font-weight: 600; }
  li .name { flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .type { color: var(--muted); font-size: 0.75rem; }
  .empty { color: var(--muted); padding: 0.3rem; font-size: 0.85rem; }
</style>
