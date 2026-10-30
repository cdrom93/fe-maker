<script lang="ts">
  // What starts a scene of the game, as a sentence whose words are choices: the turn and side, or who talks to whom.
  import { t } from '../lib/i18n.svelte'
  import type { Character, DialogueScene } from '../lib/types'

  type Trigger = DialogueScene['trigger']
  let { trigger, characters, charName, onchange }: {
    trigger: Trigger
    characters: Character[]
    charName: (id: string) => string
    onchange: (change: Partial<Trigger>) => void
  } = $props()

  const SIDES = [['FACTION_BLUE', 'player'], ['FACTION_RED', 'enemy'], ['FACTION_GREEN', 'ally']]
  const named = $derived(characters.filter((c) => c.id.startsWith('CHARACTER_')))
  const stop = (e: Event) => e.stopPropagation()
</script>

{#snippet who(field: 'a' | 'b')}
  <select class="word" value={trigger[field]} onclick={stop} onchange={(e) => onchange({ [field]: (e.target as HTMLSelectElement).value })}>
    {#if !named.some((c) => c.id === trigger[field])}<option value={trigger[field]}>{charName(trigger[field] ?? '')}</option>{/if}
    {#each named as c (c.id)}<option value={c.id}>{charName(c.id)}</option>{/each}
  </select>
{/snippet}

<span class="phrase">
  {#if trigger.kind === 'turn'}
    {t('dlg.phrase.turn')}
    <input class="word number" type="number" min="1" max="99" value={Number(trigger.turn) || 1} onclick={stop}
           onchange={(e) => onchange({ turn: String(Math.max(1, Math.min(99, Number((e.target as HTMLInputElement).value) || 1))) })} />
    <select class="word" value={trigger.faction || 'FACTION_BLUE'} onclick={stop} onchange={(e) => onchange({ faction: (e.target as HTMLSelectElement).value })}>
      {#each SIDES as [faction, side] (faction)}<option value={faction}>{t(`dlg.phase.${side}`)}</option>{/each}
    </select>
  {:else}
    {@render who('a')} {t('dlg.phrase.talk')} {@render who('b')}
  {/if}
</span>

<style>
  .phrase { display: inline-flex; flex-wrap: wrap; align-items: center; gap: 0.25rem; font-size: 0.8rem; font-weight: 700; }
  .word {
    width: auto; max-width: 9rem; min-height: 0; padding: 0 0.15rem; font: inherit; color: var(--accent);
    background: transparent; border: 0; border-bottom: 1px dashed var(--accent); border-radius: 0; cursor: pointer;
  }
  .word:hover, .word:focus { background: var(--panel-2); outline: none; }
  .number { width: 2.6rem; cursor: text; }
</style>
