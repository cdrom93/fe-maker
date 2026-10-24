<script lang="ts">
  import { t } from '../lib/i18n.svelte'

  let {
    abilities,
    fromClass,
    onchange,
    convoy,
  }: {
    abilities: string[]
    fromClass: string[]
    onchange: (abilities: string[]) => void
    /** character sheets: "Opens the convoy", shown next to the convoy carrier */
    convoy?: { on: boolean; onchange: (on: boolean) => void }
  } = $props()

  // Common abilities, grouped by meaning. Weapon locks are not here: weapons are
  // reserved from the item editor and FE Maker manages the engine locks itself.
  const GROUPS: [string, string[]][] = [
    ['role', ['lord', 'boss', 'female', 'promoted', 'supply']],
    ['movement', ['mounted', 'pegasus', 'wyvern', 'canto']],
    ['talents', ['steal', 'thiefSkills', 'dance', 'play', 'summon', 'critBonus', 'lethality', 'lock3']],
  ]
  // Rare engine abilities, hidden unless asked for.
  const ADVANCED = [
    'mountedAid', 'ballista', 'maxLevel10', 'unselectable', 'magicSeal',
    'triangleAttackPegasi', 'triangleAttackArmors', 'negateLethality', 'bit23',
  ]

  // Show the advanced section open when one of its abilities is in use.
  let showAdvanced = $state(false)
  const advancedUsed = $derived(ADVANCED.some((k) => abilities.includes(k) || fromClass.includes(k)))

  function toggle(key: string, on: boolean) {
    onchange(on ? [...abilities, key] : abilities.filter((a) => a !== key))
  }
</script>

{#snippet ability(key: string)}
  {@const inherited = fromClass.includes(key)}
  <label class="ability" class:inherited>
    <input type="checkbox" checked={inherited || abilities.includes(key)} disabled={inherited} onchange={(e) => toggle(key, (e.target as HTMLInputElement).checked)} />
    <span>
      <span class="name">{t(`ability.${key}`)}{#if inherited}<span class="muted tag"> · {t('ability.fromClassShort')}</span>{/if}</span>
      <span class="muted desc">{t(`ability.desc.${key}`)}</span>
    </span>
  </label>
{/snippet}

<section class="panel">
  <h3>{t('ability.title')}</h3>
  {#if fromClass.length}<p class="muted small">{t('ability.hint')}</p>{/if}
  <div class="groups">
    {#each GROUPS as [group, keys] (group)}
      <div>
        <h4>{t(`ability.group.${group}`)}</h4>
        {#each keys as key (key)}
          {@render ability(key)}
          {#if key === 'supply' && convoy}
            <label class="ability">
              <input type="checkbox" checked={convoy.on} onchange={(e) => convoy.onchange((e.target as HTMLInputElement).checked)} />
              <span>
                <span class="name">📦 {t('field.convoyAccess')}</span>
                <span class="muted desc">{t('field.convoyAccessHint')}</span>
              </span>
            </label>
          {/if}
        {/each}
      </div>
    {/each}
  </div>
  <details open={showAdvanced || advancedUsed} ontoggle={(e) => (showAdvanced = (e.target as HTMLDetailsElement).open)}>
    <summary>{t('ability.group.advanced')}</summary>
    <div class="groups advanced">
      {#each ADVANCED as key (key)}{@render ability(key)}{/each}
    </div>
  </details>
</section>

<style>
  .groups { display: grid; grid-template-columns: repeat(auto-fill, minmax(230px, 1fr)); gap: 0.5rem 1rem; }
  h4 { margin: 0 0 0.3rem; font-size: 0.8rem; color: var(--muted); text-transform: uppercase; letter-spacing: 0.04em; }
  .ability { flex-direction: row; align-items: flex-start; gap: 0.45rem; color: var(--text); padding: 0.2rem 0; }
  .ability input { margin-top: 0.2rem; flex-shrink: 0; }
  .ability > span { display: flex; flex-direction: column; }
  .name { font-size: 0.88rem; }
  .desc { font-size: 0.75rem; line-height: 1.25; }
  .inherited { opacity: 0.7; }
  .tag { font-size: 0.75rem; }
  details { margin-top: 0.75rem; }
  summary { cursor: pointer; font-size: 0.85rem; color: var(--muted); }
  .advanced { margin-top: 0.5rem; }
  .small { font-size: 0.8rem; margin: 0 0 0.5rem; }
</style>
