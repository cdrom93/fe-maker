<script lang="ts">
  import { untrack } from 'svelte'
  import Help from './Help.svelte'
  import { api } from '../lib/api'
  import { t } from '../lib/i18n.svelte'
  import BattleAnimation from './BattleAnimation.svelte'
  import PaletteFamilies from './PaletteFamilies.svelte'
  import { families as familiesOf } from '../lib/colors'
  import type { BattleColors, Character, ClassView, Item } from '../lib/types'

  /** A character's own colours in battle, class by class (FEBuilder's Unit Palette). */
  let { character, characters, classes, items, side = 0, onchange }: {
    character: Character; characters: Character[]; classes: ClassView[]; items: Item[]
    /** the side shown first: 0 player, 1 enemy */
    side?: number
    /** lines of colours for a class; null: the class's colours; undefined: as in the game */
    onchange: (classId: string, lines: string[][] | null | undefined, kept?: string[][]) => void
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
  /** the user's own colours, kept while another choice is in use */
  const mine = $derived(character.customColors?.[classId])
  const lines = $derived(saved === null ? info?.base : (saved ?? info?.game ?? info?.base))
  /** the colours being chosen, shown at once and saved when the colour window closes */
  let draft = $state<string[][] | null>(null)
  /** the colours drawn from the portrait, shown until the user keeps or drops them */
  let proposal = $state<string[][] | null>(null)
  const start = $derived(proposal ?? lines)
  const shown = $derived(draft ?? start)
  /** the colour number clicked on the sprite, and the numbers to show alone */
  let picked = $state<number | null>(null)
  let hovered = $state<number[] | null>(null)
  $effect(() => {
    void key
    picked = hovered = draft = proposal = null
  })

  const family = $derived(familiesOf(info?.base[line]).find((f) => f.includes(picked ?? -1)) ?? [])

  /** The player's two lines go together. */
  function withLine(colours: string[]): string[][] {
    return (shown ?? []).map((l, i) => (i === line || (line === 0 && i === 4) ? colours : l))
  }
  function save(colours: string[]) {
    onchange(classId, withLine(colours))
    draft = proposal = null
  }
  function keep() {
    if (proposal) onchange(classId, proposal)
    proposal = null
  }

  /** The class shown takes the portrait's colours on the side shown. */
  let painting = $state(false)
  async function fromPortrait() {
    const wanted = key
    painting = true
    try {
      const { colours } = await api.portraitColors(classId, character.portraitId, line)
      if (wanted === key) proposal = withLine(colours)
    } finally {
      painting = false
    }
  }

  /** A colour trial stays a trial when two colours are swapped. */
  function swapped(colours: string[]) {
    if (proposal) proposal = withLine(colours)
    else onchange(classId, withLine(colours))
  }

  const same = (a?: string[][] | null, b?: string[][] | null) => JSON.stringify(a) === JSON.stringify(b)
  const source = $derived.by(() => {
    if (saved === null || (saved === undefined && !info?.game)) return 'class'
    if (saved === undefined || same(saved, info?.game)) return 'game'
    const other = info?.others.find((o) => same(o.lines, saved))
    return other ? other.character : 'mine'
  })

  function choose(value: string) {
    const kept = source === 'mine' ? saved ?? undefined : undefined
    if (value === 'class') onchange(classId, info?.game ? null : undefined, kept)
    else if (value === 'game') onchange(classId, undefined, kept)
    else if (value === 'mine') { if (mine) onchange(classId, mine) }
    else onchange(classId, info?.others.find((o) => o.character === value)?.lines, kept)
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
        {#if source === 'mine' || mine}<option value="mine">{t('character.colors.mine')}</option>{/if}
      </select>
    </label>
    <Help text={t('character.colors.hint')} />
    <button disabled={!info || painting || !character.portraitId} onclick={fromPortrait}>{t('character.colors.portrait')}</button>
    <Help text={t('character.colors.portraitHint')} />
  </div>
  {#if proposal}
    <div class="trial">
      <button class="primary" onclick={keep}>{t('character.colors.keep')}</button>
      <button onclick={() => (proposal = null)}>{t('character.colors.drop')}</button>
    </div>
  {/if}
  {#if shown}
    <PaletteFamilies colours={start![line]} base={info?.base[line] ?? start![line]} {picked} bind:hovered
                     hint={t('character.colors.clickSprite')} oninput={(c) => (draft = withLine(c))} onsave={save} onswap={swapped} />
  {/if}
  {#if cls}
    <BattleAnimation classId={classId} className={cls.name} {items} wtypes={[]} preview colors={shown ?? undefined} focus={hovered} selected={family}
                     onpick={(i) => (picked = i)} bind:palette={line} />
  {/if}
</div>

<style>
  .colors { display: flex; flex-direction: column; gap: 0.6rem; }
  .choice { display: flex; flex-wrap: wrap; align-items: end; gap: 0.75rem; }
  .choice label { display: flex; flex-direction: column; gap: 0.2rem; }
  .trial { display: flex; gap: 0.5rem; }
</style>
