<script lang="ts" generics="T extends { id: string; name: string }">
  import { type Snippet, tick, untrack } from 'svelte'
  import { t } from '../lib/i18n.svelte'

  let {
    records,
    selected,
    onselect,
    filter = () => true,
    problemIds,
    icon,
    suffix,
    extraFilter,
  }: {
    records: T[]
    selected: number
    onselect: (index: number) => void
    filter?: (r: T) => boolean
    problemIds: Set<string>
    icon?: Snippet<[T]>
    suffix?: Snippet<[T]>
    extraFilter?: Snippet
  } = $props()

  let query = $state('')

  const visible = $derived(
    records
      .map((r, i) => ({ r, i }))
      .filter(({ r }) => filter(r))
      .filter(({ r }) => {
        const q = query.trim().toLowerCase()
        return !q || r.name.toLowerCase().includes(q) || r.id.toLowerCase().includes(q)
      }),
  )

  let listEl = $state<HTMLUListElement>()

  // When the selection changes (e.g. opened from a link elsewhere), make sure it is
  // visible: clear a search that hides it, then scroll it into view.
  $effect(() => {
    const index = selected // the only dependency: typing a search must not trigger this
    untrack(() => {
      if (!visible.some((v) => v.i === index) && query) query = ''
    })
    tick().then(() => listEl?.querySelector('button.selected')?.scrollIntoView({ block: 'nearest' }))
  })
</script>

<div class="list panel">
  <input type="search" bind:value={query} placeholder={t('ws.search')} aria-label={t('ws.search')} />
  {#if extraFilter}{@render extraFilter()}{/if}
  <ul bind:this={listEl}>
    {#each visible as { r, i } (r.id)}
      <li>
        <button class:selected={i === selected} onclick={() => onselect(i)}>
          {#if icon}{@render icon(r)}{/if}
          <span class="name">{r.name || r.id}{#if suffix} {@render suffix(r)}{/if}</span>
          {#if problemIds.has(r.id)}<span class="dot" aria-label="!">!</span>{/if}
        </button>
      </li>
    {/each}
  </ul>
</div>

<style>
  .list { padding: 0.5rem; display: flex; flex-direction: column; gap: 0.5rem; min-height: 0; }
  ul { list-style: none; margin: 0; padding: 0; overflow-y: auto; max-height: calc(100vh - 260px); }
  li button {
    display: flex; align-items: center; gap: 0.5rem; width: 100%;
    border: none; background: none; padding: 0.3rem 0.4rem; text-align: left; border-radius: 6px;
  }
  li button:hover { background: var(--panel-2); }
  li button.selected { background: var(--accent-soft); }
  .name { flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .dot { color: var(--bad); font-weight: 700; }
  @media (max-width: 800px) { ul { max-height: 240px; } }
</style>
