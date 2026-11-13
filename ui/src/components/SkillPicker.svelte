<script lang="ts">
  // The skill chooser (ticket 22): a window, as the app's other dialogs, with the categories on the left and each
  // skill's icon, name and effect on the right; a search field over names, effects and categories.
  import { t } from '../lib/i18n.svelte'
  import { skillIcon, type SkillEntry } from '../lib/skills.svelte'

  let {
    skills,
    placeholder,
    disabled = false,
    title = '',
    heading = '',
    onpick,
  }: {
    skills: SkillEntry[]
    placeholder: string
    disabled?: boolean
    title?: string
    /** the window's title, when the button shows the current skill (ticket 42); else the placeholder */
    heading?: string
    onpick: (id: string) => void
  } = $props()

  // the categories in the order of the list (skill.kind.<kind>)
  const KINDS = ['stat', 'hp', 'initiative', 'attacked', 'weapon', 'foe', 'situation', 'aura', 'battle', 'hit', 'damage', 'guard', 'status', 'items',
    'order', 'proc', 'hits', 'after', 'map', 'ai', 'menu', 'game']

  let open = $state(false)
  let query = $state('')
  let kind = $state<string | null>(null)   // the category chosen on the left; null: all of them
  let active = $state(0)
  let search = $state<HTMLInputElement>()
  let listEl = $state<HTMLUListElement>()

  const fold = (s: string) => s.normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase()
  const rank = (k: string) => (KINDS.includes(k) ? KINDS.indexOf(k) : KINDS.length)
  const choices = $derived.by(() => {
    const q = fold(query.trim())
    return skills
      .filter((s) => !kind || s.kind === kind)
      .filter((s) => !q || [t(`skill.${s.id}`), t(`skill.${s.id}Hint`), t(`skill.kind.${s.kind}`)].some((x) => fold(x).includes(q)))
      .sort((a, b) => rank(a.kind) - rank(b.kind))
  })
  // the categories present, with their number of skills
  const kinds = $derived(
    [...new Set(skills.map((s) => s.kind))].sort((a, b) => rank(a) - rank(b)).map((k) => ({ id: k, count: skills.filter((s) => s.kind === k).length })),
  )

  function show() {
    if (disabled) return
    open = true
    query = ''
    kind = null
    active = 0
    queueMicrotask(() => search?.focus())
  }

  function choose(k: string | null) {
    kind = k
    active = 0
    listEl?.scrollTo({ top: 0 })
    search?.focus()
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
</script>

<button type="button" class="opener" {disabled} {title} onclick={show}>{placeholder}</button>

{#if open}
  <!-- svelte-ignore a11y_click_events_have_key_events, a11y_no_static_element_interactions -->
  <div class="backdrop" onclick={(e) => e.target === e.currentTarget && (open = false)}>
    <div class="panel dialog" role="dialog" aria-modal="true" aria-label={heading || placeholder}>
      <div class="head">
        <h2>{heading || placeholder}</h2>
        <button type="button" onclick={() => (open = false)}>{t('build.close')}</button>
      </div>
      <input bind:this={search} bind:value={query} placeholder={t('skill.search')} oninput={() => (active = 0)} onkeydown={key} />
      <div class="body">
        <nav class="kinds">
          <button type="button" class:active={kind === null} onclick={() => choose(null)}>
            {t('skill.allKinds')} <span class="count">{skills.length}</span>
          </button>
          {#each kinds as k (k.id)}
            <button type="button" class:active={kind === k.id} onclick={() => choose(k.id)}>
              {t(`skill.kind.${k.id}`)} <span class="count">{k.count}</span>
            </button>
          {/each}
        </nav>
        <ul role="listbox" bind:this={listEl}>
          {#each choices as s, i (s.id)}
            {#if !kind && (i === 0 || choices[i - 1].kind !== s.kind)}<li class="group">{t(`skill.kind.${s.kind}`)}</li>{/if}
            <li role="option" aria-selected={i === active} class:active={i === active}>
              <button type="button" onclick={() => pick(s)} onmouseenter={() => (active = i)}>
                <img class="pixel" src={skillIcon(s.id)} alt="" loading="lazy" />
                <span class="text"><span class="name">{t(`skill.${s.id}`)}</span><span class="hint">{t(`skill.${s.id}Hint`)}</span></span>
              </button>
            </li>
          {:else}
            <li class="empty">{t('skill.noMatch')}</li>
          {/each}
        </ul>
      </div>
    </div>
  </div>
{/if}

<style>
  .opener { display: block; width: 100%; min-width: 11rem; margin-top: 0.4rem; text-align: left; padding: 0.2rem 0.5rem; }
  .backdrop { position: fixed; inset: 0; background: rgb(0 0 0 / 0.45); display: grid; place-items: center; padding: 1rem; z-index: 40; }
  .dialog { width: min(960px, 100%); height: min(720px, 90vh); display: flex; flex-direction: column; gap: 0.5rem; }
  .head { display: flex; align-items: center; justify-content: space-between; gap: 1rem; }
  .head h2 { margin: 0; font-size: 1.1rem; }
  .dialog > input { width: 100%; box-sizing: border-box; }
  .body { flex: 1; min-height: 0; display: grid; grid-template-columns: 13rem 1fr; gap: 0.75rem; }
  .kinds { display: flex; flex-direction: column; gap: 0.15rem; overflow-y: auto; }
  .kinds button { display: flex; justify-content: space-between; align-items: center; gap: 0.5rem; text-align: left; border: 1px solid transparent; background: none; padding: 0.25rem 0.5rem; border-radius: 6px; font: inherit; font-size: 0.85rem; color: inherit; }
  .kinds button.active { border-color: var(--accent); background: var(--accent-soft); }
  .count { color: var(--muted); font-size: 0.75rem; }
  ul { list-style: none; margin: 0; padding: 0; overflow-y: auto; display: grid; grid-template-columns: repeat(auto-fill, minmax(17rem, 1fr)); align-content: start; gap: 0.25rem; }
  .group { grid-column: 1 / -1; color: var(--muted); font-size: 0.75rem; font-weight: 600; padding: 0.5rem 0.3rem 0.1rem; }
  li button { display: flex; align-items: flex-start; gap: 0.5rem; width: 100%; height: 100%; text-align: left; border: 1px solid var(--border); background: none; padding: 0.4rem 0.5rem; font: inherit; color: inherit; border-radius: 6px; }
  li.active button { border-color: var(--accent); background: var(--accent-soft); }
  .pixel { width: 16px; height: 16px; image-rendering: pixelated; flex-shrink: 0; margin-top: 0.15rem; }
  .text { display: flex; flex-direction: column; min-width: 0; }
  .name { font-weight: 600; }
  .hint { color: var(--muted); font-size: 0.8rem; line-height: 1.25; }
  .empty { grid-column: 1 / -1; color: var(--muted); padding: 0.3rem; font-size: 0.85rem; }
  @media (max-width: 640px) { .body { grid-template-columns: 1fr; grid-template-rows: auto 1fr; } .kinds { flex-direction: row; flex-wrap: wrap; } }
</style>
