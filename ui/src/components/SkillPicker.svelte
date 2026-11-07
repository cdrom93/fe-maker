<script lang="ts">
  // Skill list with icons, categories and a search field (batch 5: over a hundred skills), in the look of ItemPicker.
  import { t } from '../lib/i18n.svelte'
  import { skillIcon, type SkillEntry } from '../lib/skills.svelte'

  let {
    skills,
    placeholder,
    disabled = false,
    title = '',
    onpick,
  }: {
    skills: SkillEntry[]
    placeholder: string
    disabled?: boolean
    title?: string
    onpick: (id: string) => void
  } = $props()

  // the categories in the order of the list (skill.kind.<kind>)
  const KINDS = ['stat', 'hp', 'initiative', 'attacked', 'weapon', 'foe', 'situation', 'battle', 'hit', 'damage', 'guard', 'order', 'proc', 'hits',
    'map', 'menu', 'game']

  let open = $state(false)
  let query = $state('')
  let active = $state(0)
  let root = $state<HTMLDivElement>()
  let search = $state<HTMLInputElement>()
  let listEl = $state<HTMLUListElement>()

  const fold = (s: string) => s.normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase()
  const rank = (kind: string) => (KINDS.includes(kind) ? KINDS.indexOf(kind) : KINDS.length)
  const choices = $derived.by(() => {
    const q = fold(query.trim())
    return skills
      .filter((s) => !q || [t(`skill.${s.id}`), t(`skill.${s.id}Hint`), t(`skill.kind.${s.kind}`)].some((x) => fold(x).includes(q)))
      .sort((a, b) => rank(a.kind) - rank(b.kind))
  })

  function toggle() {
    if (disabled) return
    open = !open
    if (open) {
      query = ''
      active = 0
      queueMicrotask(() => search?.focus())
    }
  }

  function pick(s: SkillEntry) {
    open = false
    onpick(s.id)
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
  <button type="button" class="current" {disabled} {title} onclick={toggle} aria-haspopup="listbox" aria-expanded={open}>
    <span class="name">{placeholder}</span>
    <span class="caret">▾</span>
  </button>
  {#if open}
    <div class="popup">
      <input bind:this={search} bind:value={query} placeholder={t('skill.search')} oninput={() => (active = 0)} onkeydown={key} />
      <ul role="listbox" bind:this={listEl}>
        {#each choices as s, i (s.id)}
          {#if i === 0 || choices[i - 1].kind !== s.kind}<li class="group">{t(`skill.kind.${s.kind}`)}</li>{/if}
          <li role="option" aria-selected={i === active} class:active={i === active}>
            <button type="button" title={t(`skill.${s.id}Hint`)} onclick={() => pick(s)} onmouseenter={() => (active = i)}>
              <img class="pixel" src={skillIcon(s.id)} alt="" loading="lazy" />
              <span class="name">{t(`skill.${s.id}`)}</span>
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
  .picker { position: relative; min-width: 0; margin-top: 0.4rem; }
  .current { display: flex; align-items: center; gap: 0.35rem; width: 100%; min-width: 11rem; text-align: left; padding: 0.15rem 0.4rem; }
  .current .name { flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .caret { color: var(--muted); font-size: 0.75rem; }
  .pixel { width: 16px; height: 16px; image-rendering: pixelated; flex-shrink: 0; }
  .popup { position: absolute; z-index: 30; top: calc(100% + 2px); left: 0; width: max(100%, 16rem); background: var(--panel, var(--bg)); border: 1px solid var(--border); border-radius: 6px; box-shadow: 0 4px 14px rgb(0 0 0 / 0.35); padding: 0.3rem; }
  .popup input { width: 100%; box-sizing: border-box; margin-bottom: 0.25rem; }
  ul { list-style: none; margin: 0; padding: 0; max-height: 18rem; overflow-y: auto; }
  li button { display: flex; align-items: center; gap: 0.4rem; width: 100%; text-align: left; border: none; background: none; padding: 0.15rem 0.3rem; font: inherit; color: inherit; border-radius: 4px; }
  li.active button { background: var(--accent-soft); }
  li .name { flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .group { color: var(--muted); font-size: 0.75rem; font-weight: 600; padding: 0.35rem 0.3rem 0.1rem; }
  .empty { color: var(--muted); padding: 0.3rem; font-size: 0.85rem; }
</style>
