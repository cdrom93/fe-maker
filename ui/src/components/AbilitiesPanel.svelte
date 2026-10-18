<script lang="ts">
  import { t } from '../lib/i18n.svelte'

  let {
    abilities,
    fromClass,
    lockItems,
    onchange,
  }: {
    abilities: string[]
    fromClass: string[]
    lockItems: Record<string, string[]>
    onchange: (abilities: string[]) => void
  } = $props()

  // Grouped like the in-game meaning, not the bit order (the server writes bit order).
  const GROUPS: [string, string[]][] = [
    ['movement', ['mounted', 'canto', 'mountedAid', 'pegasus', 'wyvern']],
    ['role', ['lord', 'boss', 'female', 'promoted', 'maxLevel10', 'unselectable', 'supply', 'bit23']],
    ['actions', ['steal', 'thiefSkills', 'dance', 'play', 'summon', 'ballista']],
    ['combat', ['critBonus', 'lethality', 'negateLethality', 'magicSeal', 'triangleAttackPegasi', 'triangleAttackArmors']],
    ['locks', ['lock1', 'lock2', 'lock3', 'lock4', 'lock5', 'lock6', 'lock7']],
  ]

  function toggle(key: string, on: boolean) {
    onchange(on ? [...abilities, key] : abilities.filter((a) => a !== key))
  }
</script>

<section class="panel">
  <h3>{t('ability.title')}</h3>
  <p class="muted small">{t('ability.hint')}</p>
  <div class="groups">
    {#each GROUPS as [group, keys] (group)}
      <fieldset>
        <legend>{t(`ability.group.${group}`)}</legend>
        {#each keys as key (key)}
          {@const inherited = fromClass.includes(key)}
          <label class="check" class:inherited title={inherited ? t('ability.fromClass') : undefined}>
            <input
              type="checkbox"
              checked={inherited || abilities.includes(key)}
              disabled={inherited}
              onchange={(e) => toggle(key, (e.target as HTMLInputElement).checked)}
            />
            <span>
              {t(`ability.${key}`)}
              {#if lockItems[key]}<span class="muted items" title={lockItems[key].join(', ')}>({lockItems[key].slice(0, 3).join(', ')}{lockItems[key].length > 3 ? '…' : ''})</span>{/if}
              {#if inherited}<span class="muted items">· {t('ability.fromClassShort')}</span>{/if}
            </span>
          </label>
        {/each}
      </fieldset>
    {/each}
  </div>
</section>

<style>
  .groups { display: grid; grid-template-columns: repeat(auto-fill, minmax(230px, 1fr)); gap: 0.75rem; }
  fieldset { border: 1px solid var(--border); border-radius: var(--radius); padding: 0.5rem 0.75rem; margin: 0; }
  legend { font-size: 0.8rem; color: var(--muted); padding: 0 0.25rem; }
  .check { flex-direction: row; align-items: flex-start; gap: 0.4rem; color: var(--text); font-size: 0.85rem; padding: 0.15rem 0; }
  .check input { margin-top: 0.2rem; flex-shrink: 0; }
  .inherited { opacity: 0.7; }
  .items { font-size: 0.75rem; }
  .small { font-size: 0.8rem; margin: 0 0 0.5rem; }
</style>
