<script lang="ts">
  // Support pairs (server: decomp/supports.py): points at the start, points per turn side by side,
  // and the C, B and A conversations. Shown in the Dialogues tab, under "Supports".
  import { portraitUrl } from '../lib/api'
  import type { EditableList } from '../lib/history.svelte'
  import { problemText, t } from '../lib/i18n.svelte'
  import type { Character, DialoguesData, DialogueScene, DialogueStep, NewQuote, Problem, SupportPair } from '../lib/types'
  import Mention from './Mention.svelte'
  import NumberField from './NumberField.svelte'

  let {
    list,
    originalPairs,
    scenes,
    characters,
    problems,
    levelPoints,
    maxPartners,
    messageId,
    firstLine,
    faceCode,
    onpick,
  }: {
    list: EditableList<DialoguesData>
    originalPairs: SupportPair[]
    scenes: DialogueScene[]
    characters: Character[]
    problems: Problem[]
    levelPoints: number[]
    maxPartners: number
    messageId: string | null
    /** first line of a message (original or edited) */
    firstLine: (id: string) => string
    /** portrait code (FID_...) of a character */
    faceCode: (character: string) => string
    onpick: (id: string) => void
  } = $props()

  const NEW = 'new:'
  const RANKS = ['C', 'B', 'A']
  const DEFAULT_BASE = 10
  const DEFAULT_GROWTH = 2

  let filter = $state('')
  let newA = $state('')
  let newB = $state('')

  const pairs = $derived<SupportPair[]>(list.records[0]?.supports ?? originalPairs)
  const quotes = $derived<NewQuote[]>(list.records[0]?.quotes ?? [])
  const named = $derived(characters.filter((c) => c.id.startsWith('CHARACTER_')))
  const byId = $derived(new Map(characters.map((c) => [c.id, c])))
  const charName = (id: string) => byId.get(id)?.name || id.replace('CHARACTER_', '')
  const key = (a: string, b: string) => [a, b].sort().join('+')
  const originalTalks = $derived(new Map(scenes.map((s) => [key(s.trigger.a ?? '', s.trigger.b ?? ''), s.messages])))
  const partnerCount = $derived.by(() => {
    const n = new Map<string, number>()
    for (const p of pairs) for (const c of [p.a, p.b]) n.set(c, (n.get(c) ?? 0) + 1)
    return n
  })
  const fold = (s: string) => s.normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase()
  const shown = $derived(
    pairs.map((p, i) => ({ p, i })).filter(({ p }) => !filter.trim() || fold(`${charName(p.a)} ${charName(p.b)}`).includes(fold(filter.trim()))),
  )

  /** Turns side by side before the C, B, A conversations can be seen (the points stop one short of
   *  each level until its conversation, which adds the last point; a level passed at the start is
   *  skipped: "–"). Same rule as supports.turns_to on the server. */
  function turns(p: SupportPair): string {
    return levelPoints
      .map((points, r) => {
        if (p.base >= points) return `${RANKS[r]} –`
        const talks = levelPoints.slice(0, r).filter((k) => p.base < k).length
        const missing = points - 1 - p.base - talks
        const n = missing <= 0 ? 0 : p.growth > 0 ? Math.ceil(missing / p.growth) : null
        return `${RANKS[r]} ${n === null ? '∞' : n}`
      })
      .join(' · ')
  }

  /** The pair's conversations: the game's messages, or the project's new quotes (rank 1-3). */
  function talks(p: SupportPair): { rank: number; id: string | null }[] {
    const original = originalTalks.get(key(p.a, p.b))
    return [1, 2, 3].map((rank) => {
      if (original) return { rank, id: original[rank - 1] ? String(original[rank - 1]) : null }
      const i = quotes.findIndex((q) => q.kind === 'support' && q.rank === rank && key(q.a, q.b ?? '') === key(p.a, p.b))
      return { rank, id: i >= 0 ? `${NEW}${i}` : null }
    })
  }

  function save(next: SupportPair[], change?: (d: DialoguesData) => void) {
    const same = JSON.stringify(next) === JSON.stringify(originalPairs)
    list.update(0, (d) => {
      if (same) delete d.supports
      else d.supports = next
      change?.(d)
    })
  }

  function edit(i: number, patch: Partial<SupportPair>) {
    save(pairs.map((p, k) => (k === i ? { ...p, ...patch } : p)))
  }

  function remove(i: number) {
    const gone = pairs[i]
    save(pairs.filter((_, k) => k !== i), (d) => {
      // Its new conversations go with it.
      d.quotes = (d.quotes ?? []).filter((q) => !(q.kind === 'support' && key(q.a, q.b ?? '') === key(gone.a, gone.b)))
    })
  }

  const faceOf = (id: string) => byId.get(id)?.portraitId ?? 0

  function add() {
    if (!newA || !newB || newA === newB) return
    const [a, b] = [newA, newB]
    const steps = (): DialogueStep[] => [
      { kind: 'face', pos: 'MidLeft', face: faceCode(a) },
      { kind: 'face', pos: 'MidRight', face: faceCode(b) },
      { kind: 'say', pos: 'MidLeft', text: '', wait: true },
      { kind: 'say', pos: 'MidRight', text: '', wait: true },
    ]
    save([...pairs, { a, b, base: DEFAULT_BASE, growth: DEFAULT_GROWTH }], (d) => {
      d.quotes ??= []
      for (const rank of [1, 2, 3]) d.quotes.push({ kind: 'support', chapter: -1, a, b, rank, steps: steps() })
    })
    newA = ''
    newB = ''
  }

  const pairProblems = (p: SupportPair) => problems.filter((pr) => pr.kind === 'dialogues' && pr.id === `support:${p.a}:${p.b}`)
  const tooMany = $derived(problems.filter((pr) => pr.kind === 'dialogues' && pr.code === 'supportTooMany'))
</script>

<p class="muted small help">{t('sup.hint', { c: levelPoints[0], b: levelPoints[1], a: levelPoints[2], max: maxPartners })}</p>
{#each tooMany as pr (pr.id)}
  <p class="bad small"><Mention kind="characters" id={pr.id.replace('support:', '')}>{charName(pr.id.replace('support:', ''))}</Mention> — {problemText(pr)}</p>
{/each}
<div class="add">
  <select bind:value={newA} aria-label={t('sup.first')}>
    <option value="">{t('sup.first')}</option>
    {#each named as c (c.id)}<option value={c.id} disabled={(partnerCount.get(c.id) ?? 0) >= maxPartners}>{c.name || c.id}</option>{/each}
  </select>
  <select bind:value={newB} aria-label={t('sup.second')}>
    <option value="">{t('sup.second')}</option>
    {#each named as c (c.id)}
      <option value={c.id} disabled={c.id === newA || (partnerCount.get(c.id) ?? 0) >= maxPartners || pairs.some((p) => key(p.a, p.b) === key(newA, c.id))}>{c.name || c.id}</option>
    {/each}
  </select>
  <button onclick={add} disabled={!newA || !newB || newA === newB}>＋ {t('sup.add')}</button>
</div>
<input class="filter" bind:value={filter} placeholder={t('sup.filter')} />
{#each shown as { p, i } (`${p.a}+${p.b}`)}
  <div class="pair">
    <div class="who">
      <img src={portraitUrl(faceOf(p.a), true)} alt="" />
      <img src={portraitUrl(faceOf(p.b), true)} alt="" />
      <Mention kind="characters" id={p.a}>{charName(p.a)}</Mention> &amp; <Mention kind="characters" id={p.b}>{charName(p.b)}</Mention>
      <button class="remove" onclick={() => remove(i)} title={t('sup.remove')} aria-label={t('sup.remove')}>✕</button>
    </div>
    <div class="numbers">
      <NumberField label={t('sup.base')} value={p.base} min={0} max={255} compact onchange={(v) => edit(i, { base: v })} />
      <NumberField label={t('sup.growth')} value={p.growth} min={0} max={255} compact onchange={(v) => edit(i, { growth: v })} />
      <span class="muted tiny" title={t('sup.turnsHint')}>{t('sup.turns', { list: turns(p) })}</span>
    </div>
    <div class="talks">
      {#each talks(p) as tk (tk.rank)}
        {#if tk.id}
          <button class="message" class:active={messageId === tk.id} onclick={() => onpick(tk.id!)}>
            <span class="rank">{RANKS[tk.rank - 1]}</span><span class="first">{firstLine(tk.id) || '…'}</span>
          </button>
        {:else}
          <span class="muted tiny">{RANKS[tk.rank - 1]} — {t('sup.noTalk')}</span>
        {/if}
      {/each}
    </div>
    {#each pairProblems(p) as pr, k (k)}<p class="{pr.severity === 'error' ? 'bad' : 'warn'} small">{problemText(pr)}</p>{/each}
  </div>
{/each}

<style>
  .small { font-size: 0.8rem; }
  .tiny { font-size: 0.72rem; }
  .bad { color: var(--bad); }
  .warn { color: var(--warn); }
  p { margin: 0; }
  .add { display: flex; flex-wrap: wrap; gap: 0.3rem; }
  .add select { flex: 1; min-width: 7rem; }
  .filter { width: 100%; box-sizing: border-box; }
  .pair { display: flex; flex-direction: column; gap: 0.25rem; padding: 0.35rem 0.4rem; border: 1px solid var(--border); border-radius: 6px; }
  .who { display: flex; align-items: center; gap: 0.3rem; font-size: 0.85rem; font-weight: 600; }
  .who img { width: 24px; height: 20px; image-rendering: pixelated; }
  .remove { margin-left: auto; padding: 0 0.35rem; font-size: 0.75rem; color: var(--bad); }
  .numbers { display: flex; align-items: flex-end; gap: 0.5rem; flex-wrap: wrap; }
  .talks { display: flex; flex-direction: column; gap: 0.1rem; }
  .message { display: flex; align-items: center; gap: 0.4rem; text-align: left; font-size: 0.8rem; padding: 0.1rem 0.35rem; background: none; border-color: transparent; }
  .message:hover { background: var(--accent-soft); }
  .message.active { border-color: var(--accent); background: var(--accent-soft); }
  .rank { font-weight: 700; color: var(--accent); width: 1rem; }
  .first { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; flex: 1; min-width: 0; }
</style>
