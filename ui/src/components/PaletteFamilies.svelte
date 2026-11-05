<script lang="ts">
  // One line of 16 colours grouped by shades: the picked part recoloured with its shades, colours or groups swapped by
  // dragging. Shared by a character's battle colours and a map's colours (ticket 147).
  import Help from './Help.svelte'
  import { t } from '../lib/i18n.svelte'
  import { families as familiesOf, recolorFamily, swapColours } from '../lib/colors'

  let { colours, base, picked, hovered = $bindable(null), hint, oninput, onsave, onswap }: {
    /** the line as saved (or proposed) */
    colours: string[]
    /** the line the shades are read from (the game's), the same whatever the user paints */
    base: string[]
    /** the colour number clicked on the picture */
    picked: number | null
    /** colour numbers to show alone on the picture */
    hovered?: number[] | null
    /** shown while nothing is picked */
    hint: string
    /** the colours being chosen, at each move */
    oninput?: (colours: string[]) => void
    /** the colours chosen, when the colour window closes */
    onsave: (colours: string[]) => void
    /** two colours or groups swapped (defaults to onsave) */
    onswap?: (colours: string[]) => void
  } = $props()

  let draft = $state<string[] | null>(null)
  const shown = $derived(draft ?? colours)
  const groups = $derived(familiesOf(base))
  const family = $derived(groups.find((f) => f.includes(picked ?? -1)) ?? [])

  function set(next: string[]) {
    draft = next
    oninput?.(next)
  }
  function commit() {
    if (draft) onsave(draft)
    draft = null
  }

  /** what is being dragged, and where it would go: a family dragged swaps with a family */
  let dragged = $state<number[] | null>(null)
  let target = $state<number[] | null>(null)
  const destination = (members: number[], i: number) => ((dragged?.length ?? 0) > 1 ? members : [i])
  function over(e: DragEvent, slots: number[]) {
    if (!dragged) return
    e.preventDefault()
    target = hovered = slots
  }
  function drop(e: DragEvent, slots: number[]) {
    e.preventDefault()
    if (dragged && slots.length && !dragged.some((i) => slots.includes(i))) (onswap ?? onsave)(swapColours(shown, dragged, slots))
    dragged = target = hovered = null
  }
</script>

{#if picked !== null}
  <label class="recolor" onmouseenter={() => (hovered = family)} onmouseleave={() => (hovered = null)}>
    <input type="color" value={shown[picked]} oninput={(e) => set(recolorFamily(colours, picked!, family, (e.target as HTMLInputElement).value))}
           onchange={commit} />
    <span>{t('character.colors.family', { n: family.length })}</span>
  </label>
{:else}
  <p class="muted small hint">{hint}</p>
{/if}
<div class="swatches">
  {#each groups as members, f (f)}
    <div class="family" class:picked={members.includes(picked ?? -1)} role="group"
         ondragover={(e) => over(e, (dragged?.length ?? 0) > 1 ? members : [])}
         ondrop={(e) => drop(e, (dragged?.length ?? 0) > 1 ? members : [])}>
      {#if members.length > 1}
        <span class="grip" role="button" tabindex="-1" draggable="true" title={t('character.colors.swapFamily')}
              aria-label={t('character.colors.swapFamily')}
              ondragstart={() => (dragged = members)} ondragend={() => (dragged = target = hovered = null)}></span>
      {/if}
      {#each members as i (i)}
        <span class="swatch" class:target={target?.includes(i)} role="button" tabindex="-1" draggable="true"
              ondragstart={() => (dragged = [i])} ondragend={() => (dragged = target = hovered = null)}
              ondragover={(e) => { e.stopPropagation(); over(e, destination(members, i)) }}
              ondrop={(e) => { e.stopPropagation(); drop(e, destination(members, i)) }}>
          <input type="color" value={shown[i]} aria-label={t('character.colors.swatch', { n: i })}
                 onmouseenter={() => (hovered = [i])} onmouseleave={() => (hovered = null)}
                 oninput={(e) => set(shown.map((c, k) => (k === i ? (e.target as HTMLInputElement).value : c)))} onchange={commit} />
        </span>
      {/each}
    </div>
  {/each}
  <Help text={t('character.colors.swapHint')} />
</div>

<style>
  .swatches { display: flex; flex-wrap: wrap; align-items: center; gap: 0.6rem; }
  .swatch { display: inline-flex; border-radius: 4px; cursor: grab; }
  .swatch.target { outline: 2px solid var(--accent); outline-offset: 1px; }
  .grip { width: 7px; align-self: stretch; margin-right: 2px; cursor: grab; opacity: 0.6;
          background: radial-gradient(currentColor 1px, transparent 1.5px) 0 0 / 4px 4px; }
  .family { display: flex; gap: 0.15rem; padding: 0.15rem; border: 2px solid transparent; border-radius: 6px; }
  .family.picked { border-color: var(--accent); }
  .swatches input { width: 1.8rem; height: 1.8rem; padding: 0; border: 1px solid var(--border); border-radius: 4px; background: none; cursor: pointer; }
  .recolor { display: flex; flex-direction: row; align-items: center; gap: 0.5rem; text-align: left; }
  .recolor, .hint { min-height: 2.4rem; margin: 0; display: flex; align-items: center; }   /* a click moves nothing */
  .recolor input { width: 2.6rem; height: 2.2rem; padding: 0; border: 1px solid var(--border); border-radius: 4px; background: none; cursor: pointer; }
</style>
