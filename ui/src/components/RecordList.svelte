<script lang="ts" generics="T extends { id: string; name: string }">
  import { type Snippet, tick, untrack } from 'svelte'
  import { appContext } from '../lib/appContext.svelte'
  import { t } from '../lib/i18n.svelte'

  let {
    records,
    selected,
    onselect,
    filter = () => true,
    secondary,
    secondaryLabel = '',
    problemIds,
    icon,
    suffix,
    extraFilter,
    actions,
  }: {
    records: T[]
    selected: number
    onselect: (index: number) => void
    filter?: (r: T) => boolean
    /** Records that are rarely needed: listed after the others, in a folded section. */
    secondary?: (r: T) => boolean
    /** Title of the folded section; {n} = number of records in it. */
    secondaryLabel?: string
    problemIds: Set<string>
    icon?: Snippet<[T]>
    suffix?: Snippet<[T]>
    extraFilter?: Snippet
    /** Buttons under the search (add a record...). */
    actions?: Snippet
  } = $props()

  let query = $state('')
  let showSecondary = $state(false)

  const visible = $derived(
    records
      .map((r, i) => ({ r, i }))
      .filter(({ r }) => filter(r))
      .filter(({ r }) => {
        const q = query.trim().toLowerCase()
        return !q || r.name.toLowerCase().includes(q) || r.id.toLowerCase().includes(q)
      }),
  )
  const main = $derived(secondary ? visible.filter(({ r }) => !secondary(r)) : visible)
  const rest = $derived(secondary ? visible.filter(({ r }) => secondary(r)) : [])
  // A search shows its results wherever they are.
  const restOpen = $derived(showSecondary || (query.trim() !== '' && rest.length > 0))

  let listEl = $state<HTMLDivElement>()

  // When the selection changes (e.g. opened from a link elsewhere), make sure it is
  // visible: clear a search that hides it, open the folded section if it is there,
  // then scroll it into view.
  $effect(() => {
    const index = selected // the only dependency: typing a search must not trigger this
    untrack(() => {
      if (!visible.some((v) => v.i === index) && query) query = ''
      if (secondary && records[index] && secondary(records[index])) showSecondary = true
    })
    tick().then(() => listEl?.querySelector('button.selected')?.scrollIntoView({ block: 'nearest' }))
  })

  // Tell feedback tickets which record is open.
  $effect(() => {
    const r = records[selected]
    appContext.record = r ? (r.name && r.name !== r.id ? `${r.name} (${r.id})` : r.id) : ''
    return () => (appContext.record = '')
  })
</script>

{#snippet row(r: T, i: number)}
  <li>
    <button class:selected={i === selected} onclick={() => onselect(i)}>
      {#if icon}{@render icon(r)}{/if}
      <span class="name">{r.name || r.id}{#if suffix} {@render suffix(r)}{/if}</span>
      {#if problemIds.has(r.id)}<span class="dot" aria-label="!">!</span>{/if}
    </button>
  </li>
{/snippet}

<div class="list panel">
  <input type="search" bind:value={query} placeholder={t('ws.search')} aria-label={t('ws.search')} />
  {#if extraFilter}{@render extraFilter()}{/if}
  {#if actions}<div class="actions">{@render actions()}</div>{/if}
  <div class="scroll" bind:this={listEl}>
    <ul>
      {#each main as { r, i } (r.id)}{@render row(r, i)}{/each}
    </ul>
    {#if rest.length}
      <button class="section" aria-expanded={restOpen} onclick={() => (showSecondary = !restOpen)}>
        <span class="chevron" class:open={restOpen}>▸</span>
        {secondaryLabel.replace('{n}', String(rest.length))}
      </button>
      {#if restOpen}
        <ul class="secondary">
          {#each rest as { r, i } (r.id)}{@render row(r, i)}{/each}
        </ul>
      {/if}
    {/if}
  </div>
</div>

<style>
  .list { padding: 0.5rem; display: flex; flex-direction: column; gap: 0.5rem; min-height: 0; }
  .scroll { overflow-y: auto; max-height: calc(100vh - 260px); }
  ul { list-style: none; margin: 0; padding: 0; }
  .actions { display: flex; gap: 0.4rem; flex-wrap: wrap; }
  li button {
    display: flex; align-items: center; gap: 0.5rem; width: 100%;
    border: none; background: none; padding: 0.3rem 0.4rem; text-align: left; border-radius: 6px;
  }
  li button:hover { background: var(--panel-2); }
  li button.selected { background: var(--accent-soft); }
  .name { flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .dot { color: var(--bad); font-weight: 700; }
  .section {
    display: flex; align-items: center; gap: 0.4rem; width: 100%; margin-top: 0.4rem;
    border: none; border-top: 1px solid var(--border); border-radius: 0; background: none;
    padding: 0.5rem 0.4rem 0.3rem; color: var(--muted); font-size: 0.82rem; text-align: left;
  }
  .chevron { display: inline-block; transition: transform 0.15s; }
  .chevron.open { transform: rotate(90deg); }
  .secondary li button { opacity: 0.85; }
  @media (max-width: 800px) { .scroll { max-height: 240px; } }
</style>
