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

  /** Hue, saturation and lightness, from 0 to 1. */
  function hsl(hex: string): [number, number, number] {
    const [r, g, b] = [1, 3, 5].map((i) => parseInt(hex.slice(i, i + 2), 16) / 255)
    const high = Math.max(r, g, b)
    const low = Math.min(r, g, b)
    const l = (high + low) / 2
    const d = high - low
    if (!d) return [0, 0, l]
    const h = high === r ? (g - b) / d + (g < b ? 6 : 0) : high === g ? (b - r) / d + 2 : (r - g) / d + 4
    return [h / 6, d / (1 - Math.abs(2 * l - 1)), l]
  }
  function hex(h: number, s: number, l: number): string {
    const part = (n: number) => {
      const k = (n + h * 12) % 12
      const v = l - s * Math.min(l, 1 - l) * Math.max(-1, Math.min(k - 3, 9 - k, 1))
      return Math.round(v * 255).toString(16).padStart(2, '0')
    }
    return `#${part(0)}${part(8)}${part(4)}`
  }
  const neutral = ([, s, l]: [number, number, number]) => s < 0.15 || l > 0.9 || l < 0.12
  function close(a: string, b: string): boolean {
    const [x, y] = [hsl(a), hsl(b)]
    if (neutral(x) || neutral(y)) return neutral(x) && neutral(y)
    const turn = Math.abs(x[0] - y[0])
    return Math.min(turn, 1 - turn) < 0.11
  }
  /** Colours follow each other by shades: neighbours of close hues make a family, read from the class's colours, the
   * same for every palette of this animation and whatever the user paints. */
  const families = $derived.by(() => {
    const colours = info?.base[line]
    const out: number[][] = []
    for (let i = 1; colours && i < 16; i++) {
      const last = out.at(-1)
      if (last && close(colours[last.at(-1)!], colours[i])) last.push(i)
      else out.push([i])
    }
    return out
  })
  const family = $derived(families.find((f) => f.includes(picked ?? -1)) ?? [])

  function withLine(colours: string[]): string[][] {
    return (shown ?? []).map((l, i) => (i === line ? colours : l))
  }
  function setCase(index: number, colour: string) {
    if (shown) draft = withLine(shown[line].map((c, k) => (k === index ? colour : c)))
  }
  /** The picked colour becomes `colour`, its shades follow and keep their relief. */
  function setFamily(colour: string) {
    const current = (start ?? [])[line]
    if (!current || picked === null) return
    const [h, s, l] = hsl(colour)
    const from = hsl(current[picked])[2]
    draft = withLine(current.map((c, k) => {
      if (k === picked) return colour
      if (!family.includes(k)) return c
      const own = hsl(c)[2]    // darker shades scale down to black, lighter ones up to white: their order stays
      return hex(h, s, own < from ? (l * own) / from : l + ((own - from) * (1 - l)) / (1 - from || 1))
    }))
  }
  function commit() {
    if (draft) onchange(classId, draft)
    draft = proposal = null
  }
  function keep() {
    if (proposal) onchange(classId, proposal)
    proposal = null
  }

  /** The class shown takes the portrait's colours on the side shown; the player's two lines go together. */
  let painting = $state(false)
  async function fromPortrait() {
    const wanted = key
    painting = true
    try {
      const { colours } = await api.portraitColors(classId, character.portraitId, line)
      if (wanted === key) proposal = (lines ?? []).map((l, i) => (i === line || (line === 0 && i === 4) ? colours : l))
    } finally {
      painting = false
    }
  }

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
    <button disabled={!info || painting || !character.portraitId} onclick={fromPortrait}>{t('character.colors.portrait')}</button>
    <Help text={t('character.colors.portraitHint')} />
    {#if proposal}
      <button class="primary" onclick={keep}>{t('character.colors.keep')}</button>
      <button onclick={() => (proposal = null)}>{t('character.colors.drop')}</button>
    {/if}
  </div>
  {#if shown}
    {#if picked !== null}
      <label class="recolor" onmouseenter={() => (hovered = family)} onmouseleave={() => (hovered = null)}>
        <input type="color" value={shown[line][picked]} oninput={(e) => setFamily((e.target as HTMLInputElement).value)} onchange={commit} />
        <span>{t('character.colors.family', { n: family.length })}</span>
      </label>
    {:else}
      <p class="muted small">{t('character.colors.clickSprite')}</p>
    {/if}
    <div class="swatches">
      {#each families as members, f (f)}
        <div class="family" class:picked={members.includes(picked ?? -1)}>
          {#each members as i (i)}
            <input type="color" value={shown[line][i]} aria-label={t('character.colors.swatch', { n: i })}
                   onmouseenter={() => (hovered = [i])} onmouseleave={() => (hovered = null)}
                   oninput={(e) => setCase(i, (e.target as HTMLInputElement).value)} onchange={commit} />
          {/each}
        </div>
      {/each}
    </div>
  {/if}
  {#if cls}
    <BattleAnimation classId={classId} className={cls.name} {items} wtypes={[]} preview colors={shown ?? undefined} focus={hovered}
                     onpick={(i) => (picked = i)} bind:palette={line} />
  {/if}
</div>

<style>
  .colors { display: flex; flex-direction: column; gap: 0.6rem; }
  .choice { display: flex; flex-wrap: wrap; align-items: end; gap: 0.75rem; }
  .choice label { display: flex; flex-direction: column; gap: 0.2rem; }
  .swatches { display: flex; flex-wrap: wrap; gap: 0.6rem; }
  .family { display: flex; gap: 0.15rem; padding: 0.15rem; border: 2px solid transparent; border-radius: 6px; }
  .family.picked { border-color: var(--accent); }
  .swatches input { width: 1.8rem; height: 1.8rem; padding: 0; border: 1px solid var(--border); border-radius: 4px; background: none; cursor: pointer; }
  .recolor { display: flex; flex-direction: row; align-items: center; gap: 0.5rem; text-align: left; }
  .recolor input { width: 2.6rem; height: 2.2rem; padding: 0; border: 1px solid var(--border); border-radius: 4px; background: none; cursor: pointer; }
</style>
