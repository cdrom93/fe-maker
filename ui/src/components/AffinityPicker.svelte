<script lang="ts">
  // A character's affinity: a list with the game's icons, and what it brings to their supports.
  import { itemIconUrl } from '../lib/api'
  import { t } from '../lib/i18n.svelte'
  import type { AffinityBonus } from '../lib/types'
  import Help from './Help.svelte'

  const FIRST_ICON = 0x7a   // GetUnitAffinityIcon
  const ICON_PALETTE = 1    // STATSCREEN_BGPAL_EXTICONS
  const STATS = ['attack', 'defense', 'hit', 'avoid', 'crit', 'dodge'] as const

  let {
    value,
    affinities,
    bonuses,
    problem = '',
    onchange,
  }: {
    value: string | null
    affinities: string[]
    bonuses: Record<string, AffinityBonus>
    problem?: string
    onchange: (value: string | null) => void
  } = $props()

  let open = $state(false)
  let root = $state<HTMLDivElement>()
  const icon = (a: string) => itemIconUrl(FIRST_ICON + affinities.indexOf(a), ICON_PALETTE)
  /** The two partners' bonuses are added up and halved: one rank of this affinity is worth half its table value. */
  const gains = $derived(value && bonuses[value] ? STATS.filter((s) => bonuses[value!][s]).map((s) => ({ s, n: bonuses[value!][s] / 2 })) : [])

  function pick(a: string | null) {
    open = false
    if (a !== value) onchange(a)
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

<div class="affinity" title={problem}>
  <span>{t('field.affinity')} <Help text={t('field.affinityHint')} /></span>
  <div class="picker" bind:this={root}>
    <button type="button" class="current" onclick={() => (open = !open)} aria-haspopup="listbox" aria-expanded={open} aria-label={t('field.affinity')}>
      {#if value}<img class="pixel" src={icon(value)} alt="" />{/if}
      <span class="name">{value ? t(`affinity.${value}`) : t('field.noAffinity')}</span>
      <span class="caret">▾</span>
    </button>
    {#if open}
      <ul class="popup" role="listbox">
        <li role="option" aria-selected={value === null}><button type="button" class:chosen={value === null} onclick={() => pick(null)}>{t('field.noAffinity')}</button></li>
        {#each affinities as a (a)}
          <li role="option" aria-selected={value === a}>
            <button type="button" class:chosen={value === a} onclick={() => pick(a)}><img class="pixel" src={icon(a)} alt="" />{t(`affinity.${a}`)}</button>
          </li>
        {/each}
      </ul>
    {/if}
  </div>
  {#if gains.length}
    <span class="gains small">{gains.map(({ s, n }) => `${t(`affinity.bonus.${s}`)} +${n.toLocaleString()}`).join(' · ')} {t('field.affinityPerRank')}</span>
  {/if}
</div>

<style>
  .affinity { display: flex; flex-direction: column; gap: 0.25em; font-size: 0.85rem; color: var(--muted); font-weight: 600; }
  .picker { position: relative; width: fit-content; }
  .current { display: flex; align-items: center; gap: 0.4rem; min-width: 11rem; min-height: 2.25rem; text-align: left; padding: 0.15rem 0.5rem; }
  .current .name { flex: 1; color: var(--text); }
  .caret { color: var(--muted); font-size: 0.75rem; }
  img { width: 16px; height: 16px; flex-shrink: 0; }
  .popup { position: absolute; z-index: 30; top: calc(100% + 2px); left: 0; width: 100%; list-style: none; margin: 0; padding: 0.25rem; box-sizing: border-box;
    background: var(--panel); border: 1px solid var(--border); border-radius: var(--radius); box-shadow: 0 4px 16px rgb(0 0 0 / 35%); }
  .popup button { display: flex; align-items: center; gap: 0.5rem; width: 100%; min-height: 1.75rem; padding: 0.15rem 0.35rem; text-align: left; border: none; background: none; color: var(--text); }
  .popup button:hover { background: var(--accent-soft); }
  .popup button.chosen { font-weight: 800; }
  .gains { color: var(--text); font-weight: 500; }
</style>
