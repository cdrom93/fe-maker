<script lang="ts">
  // A character's affinity, with the game's icons, and what it brings to their supports.
  import { itemIconUrl } from '../lib/api'
  import { t } from '../lib/i18n.svelte'
  import type { AffinityBonus } from '../lib/types'
  import Help from './Help.svelte'

  const FIRST_ICON = 0x7a   // GetUnitAffinityIcon
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

  /** The two partners' bonuses are added up and halved: one rank of this affinity is worth half its table value. */
  const gains = $derived(value && bonuses[value] ? STATS.filter((s) => bonuses[value!][s]).map((s) => ({ s, n: bonuses[value!][s] / 2 })) : [])
</script>

<div class="affinity" title={problem}>
  <span class="title">{t('field.affinity')} <Help text={t('field.affinityHint')} /></span>
  <div class="choices" role="radiogroup" aria-label={t('field.affinity')}>
    <button role="radio" aria-checked={value === null} class:active={value === null} title={t('field.noAffinity')} onclick={() => onchange(null)}>{t('field.none')}</button>
    {#each affinities as a, i (a)}
      <button role="radio" aria-checked={value === a} class:active={value === a} title={t(`affinity.${a}`)} aria-label={t(`affinity.${a}`)} onclick={() => onchange(a)}>
        <img class="pixel" src={itemIconUrl(FIRST_ICON + i)} alt="" />
      </button>
    {/each}
  </div>
  {#if value}
    <span class="gains small"><strong>{t(`affinity.${value}`)}</strong>{#if gains.length} · {gains.map(({ s, n }) => `${t(`affinity.bonus.${s}`)} +${n.toLocaleString()}`).join(' · ')} {t('field.affinityPerRank')}{/if}</span>
  {/if}
</div>

<style>
  .affinity { display: flex; flex-direction: column; gap: 0.25em; font-size: 0.85rem; color: var(--muted); font-weight: 600; }
  .choices { display: flex; flex-wrap: wrap; gap: 0.2rem; }
  .choices button { display: inline-flex; align-items: center; justify-content: center; width: 2.1rem; height: 2.1rem; padding: 0; }
  .choices button.active { background: var(--accent-soft); border-color: var(--accent); }
  .choices img { width: 24px; height: 24px; }
  .gains { color: var(--text); font-weight: 500; }
</style>
