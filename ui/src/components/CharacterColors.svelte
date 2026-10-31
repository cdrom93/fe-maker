<script lang="ts">
  import { untrack } from 'svelte'
  import Help from './Help.svelte'
  import { api } from '../lib/api'
  import { t } from '../lib/i18n.svelte'
  import BattleAnimation from './BattleAnimation.svelte'
  import type { BattleColors, Character, ClassView, Item } from '../lib/types'

  /** A character's own colours in battle, class by class (FEBuilder's Unit Palette). */
  let { character, characters, classes, items, side = 0, onchange }: {
    character: Character; characters: Character[]; classes: ClassView[]; items: Item[]
    /** the side shown first: 0 player, 1 enemy */
    side?: number
    /** lines of colours for a class; null: the class's colours; undefined: as in the game */
    onchange: (classId: string, lines: string[][] | null | undefined) => void
  } = $props()

  /** The character's class and the ones it can reach, then any other class that has colours. */
  const choices = $derived.by(() => {
    const found = [character.class]
    for (const id of found.slice()) found.push(...(classes.find((c) => c.id === id)?.promotions ?? []))
    const second = found.flatMap((id) => classes.find((c) => c.id === id)?.promotions ?? [])
    return [...new Set([...found, ...second, ...Object.keys(character.battleColors ?? {})])]
  })
  let chosen = $state('')
  const classId = $derived(choices.includes(chosen) ? chosen : character.class)
  const cls = $derived(classes.find((c) => c.id === classId))

  let info = $state<BattleColors | null>(null)
  let line = $state(untrack(() => side))
  const key = $derived(`${character.id}/${classId}`)
  $effect(() => {
    const wanted = key
    info = null
    api.battleColors(character.id, classId).then((found) => {
      if (wanted === key) info = found
    }).catch(() => {})
  })

  const saved = $derived(character.battleColors?.[classId])
  const lines = $derived(saved === null ? info?.base : (saved ?? info?.game ?? info?.base))
  const same = (a?: string[][] | null, b?: string[][] | null) => JSON.stringify(a) === JSON.stringify(b)
  const source = $derived.by(() => {
    if (saved === null || (saved === undefined && !info?.game)) return 'class'
    if (saved === undefined || same(saved, info?.game)) return 'game'
    const other = info?.others.find((o) => same(o.lines, saved))
    return other ? other.character : 'mine'
  })

  function choose(value: string) {
    if (value === 'class') onchange(classId, info?.game ? null : undefined)
    else if (value === 'game') onchange(classId, undefined)
    else if (value !== 'mine') onchange(classId, info?.others.find((o) => o.character === value)?.lines)
  }
  function setColour(index: number, colour: string) {
    if (!lines) return
    onchange(classId, lines.map((l, i) => (i === line ? l.map((c, k) => (k === index ? colour : c)) : l)))
  }
  const nameOf = (id: string) => characters.find((c) => c.id === id)?.name || id
</script>

<div class="colors">
  <div class="choice">
    <label>
      <span>{t('field.class')}</span>
      <select bind:value={() => classId, (v) => (chosen = v)}>
        {#each choices as id (id)}<option value={id}>{classes.find((c) => c.id === id)?.name ?? id}</option>{/each}
      </select>
    </label>
    <label>
      <span>{t('character.colors.source')}</span>
      <select value={source} disabled={!info} onchange={(e) => choose((e.target as HTMLSelectElement).value)}>
        <option value="class">{t('character.colors.class')}</option>
        {#if info?.game}<option value="game">{t('character.colors.game')}</option>{/if}
        {#each info?.others ?? [] as o (o.character)}<option value={o.character}>{nameOf(o.character)}</option>{/each}
        {#if source === 'mine'}<option value="mine">{t('character.colors.mine')}</option>{/if}
      </select>
    </label>
    <Help text={t('character.colors.hint')} />
  </div>
  {#if lines}
    <div class="swatches">
      {#each lines[line].slice(1) as colour, i (i)}
        <input type="color" value={colour} aria-label={t('character.colors.swatch', { n: i + 1 })}
               onchange={(e) => setColour(i + 1, (e.target as HTMLInputElement).value)} />
      {/each}
    </div>
  {/if}
  {#if cls}
    <BattleAnimation classId={classId} className={cls.name} {items} wtypes={[]} preview colors={lines ?? undefined} bind:palette={line} />
  {/if}
</div>

<style>
  .colors { display: flex; flex-direction: column; gap: 0.6rem; }
  .choice { display: flex; flex-wrap: wrap; align-items: end; gap: 0.75rem; }
  .choice label { display: flex; flex-direction: column; gap: 0.2rem; }
  .swatches { display: flex; flex-wrap: wrap; gap: 0.25rem; }
  .swatches input { width: 1.8rem; height: 1.8rem; padding: 0; border: 1px solid var(--border); border-radius: 4px; background: none; cursor: pointer; }
</style>
