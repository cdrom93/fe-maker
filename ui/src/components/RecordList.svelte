<script lang="ts" generics="T extends { id: string; name: string }">
  import type { Snippet } from 'svelte'
  import { t } from '../lib/i18n.svelte'

  let {
    records,
    selected,
    onselect,
    filter = () => true,
    problemIds,
    icon,
    extraFilter,
  }: {
    records: T[]
    selected: number
    onselect: (index: number) => void
    filter?: (r: T) => boolean
    problemIds: Set<string>
    icon: Snippet<[T]>
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
</script>

<div class="list panel">
  <input type="search" bind:value={query} placeholder={t('ws.search')} aria-label={t('ws.search')} />
  {#if extraFilter}{@render extraFilter()}{/if}
  <ul>
    {#each visible as { r, i } (r.id)}
      <li>
        <button class:selected={i === selected} onclick={() => onselect(i)}>
          {@render icon(r)}
          <span class="name">{r.name || '—'}</span>
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
