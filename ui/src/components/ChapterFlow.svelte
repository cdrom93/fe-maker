<script lang="ts">
  import { onMount } from 'svelte'
  import { appContext } from '../lib/appContext.svelte'
  import { api, chapterMapUrl } from '../lib/api'
  import type { EditableList } from '../lib/history.svelte'
  import { t } from '../lib/i18n.svelte'
  import type { ChapterInfo, ChapterLink, DialoguesData, EventCommand } from '../lib/types'
  import Mention from './Mention.svelte'

  // The campaign (tickets 31, 39; interface mockups of 25/10/2026): chapters as cards with their map,
  // and how each one leads to the next. Each chapter's scripts end with a command that starts the next
  // one (server: decomp/story.py). Edited scripts are kept with the dialogues' scripts.
  let { list }: { list: EditableList<DialoguesData> } = $props()

  const NODE_W = 200
  const NODE_H = 164
  const ROW = 190
  const COL = 270
  const PAD = 24
  const END = -1 // the game's ending, drawn as a last node
  /** commands offered for a link, by kind */
  const OPS: { op: string; kind: ChapterLink['kind'] }[] = [
    { op: 'MNCH', kind: 'worldMap' }, { op: 'MNC2', kind: 'direct' }, { op: 'MNC3', kind: 'noSave' }, { op: 'MNC4', kind: 'ending' },
  ]

  let chapters = $state<ChapterInfo[]>([])
  let original = $state<ChapterLink[][]>([])
  let kinds = $state<Record<string, ChapterLink['kind']>>({})
  let toChapter = $state<string[]>([])
  let selected = $state<number | null>(0)
  let error = $state('')
  /** false: the project goes from chapter to chapter without the world map (ticket 39) */
  let worldMap = $state(true)

  onMount(async () => {
    // an older server has no world map option: the world map stays
    const [all, info, wm] = await Promise.all([api.chapters(), api.chapterLinks(), api.worldMap().catch(() => ({ worldMap: true }))])
    chapters = all
    original = info.links
    kinds = info.kinds
    toChapter = info.toChapter
    worldMap = wm.worldMap
  })

  async function setWorldMap(on: boolean) {
    error = ''
    try {
      worldMap = (await api.setWorldMap(on)).worldMap
    } catch (e) {
      error = String(e)
    }
  }

  /** How a link really goes: without the world map, MNCH goes straight to its chapter. */
  const shownKind = (l: ChapterLink) => (!worldMap && l.kind === 'worldMap' ? 'direct' : l.kind)

  $effect(() => {
    appContext.detail = selected !== null && selected >= 0 ? title(selected) : ''
    return () => (appContext.detail = '')
  })

  const title = (i: number) => (i === END ? t('flow.end') : chapters[i]?.title || chapters[i]?.id || `#${i}`)

  /** Links of a script's commands (mirrors story.links). */
  function linksOf(script: string, ending: boolean, commands: EventCommand[]): ChapterLink[] {
    const out: ChapterLink[] = []
    commands.forEach((c, at) => {
      const kind = kinds[c.op]
      if (!kind) return
      let to: number | null = null
      if (toChapter.includes(c.op)) {
        const n = Number(c.args?.[0])
        if (!Number.isInteger(n) || (n & 0xffff) === 0xffff) return
        to = n & 0xffff
      }
      out.push({ script, ending, at, op: c.op, kind, to })
    })
    return out
  }

  // The game's links, with the scripts edited since the page was loaded read again.
  const links = $derived.by(() => {
    const edited = list.records[0]?.scripts ?? {}
    return original.map((ls) => {
      const scripts = [...new Set(ls.map((l) => l.script))]
      return scripts.flatMap((s) => {
        const mine = ls.filter((l) => l.script === s)
        return edited[s] ? linksOf(s, mine[0].ending, edited[s]) : mine
      })
    })
  })

  // Layout: rows by distance from the prologue (first time a chapter is reached), the chapter's
  // ending scene first; chapters reached from nowhere are listed apart.
  const graph = $derived.by(() => {
    const depth = new Map<number, number>()
    const order: number[] = []
    if (chapters.length) {
      depth.set(0, 0)
      order.push(0)
      for (let k = 0; k < order.length; k++) {
        const from = order[k]
        if (from === END) continue
        const next = [...(links[from] ?? [])].sort((a, b) => Number(b.ending) - Number(a.ending))
        for (const l of next) {
          const to = l.kind === 'ending' ? END : l.to
          if (to === null || depth.has(to) || (to !== END && !chapters[to])) continue
          depth.set(to, depth.get(from)! + 1)
          order.push(to)
        }
      }
    }
    // the ending at the bottom
    if (depth.has(END)) depth.set(END, Math.max(...depth.values()) + 1)
    const rows = new Map<number, number[]>()
    for (const n of order) rows.set(depth.get(n)!, [...(rows.get(depth.get(n)!) ?? []), n])
    // left to right, like the mockup's campaign: one column per step, branches stacked
    const widest = Math.max(1, ...[...rows.values()].map((r) => r.length))
    const height = widest * ROW + PAD * 2
    const pos = new Map<number, { x: number; y: number }>()
    for (const [d, r] of rows) {
      const top = PAD
      r.forEach((n, i) => pos.set(n, { x: PAD + d * COL, y: top + i * ROW + (ROW - NODE_H) / 2 }))
    }
    const edges: { from: number; to: number; link: ChapterLink }[] = []
    for (const n of order) {
      if (n === END) continue
      for (const l of links[n] ?? []) {
        const to = l.kind === 'ending' ? END : l.to
        if (to !== null && pos.has(to)) edges.push({ from: n, to, link: l })
      }
    }
    const unreached = chapters.filter((c) => c.title && !depth.has(c.index)).map((c) => c.index)
    return { pos, edges, width: PAD * 2 + (rows.size ? Math.max(...rows.keys()) + 1 : 1) * COL, height, unreached }
  })

  function edgePath(from: { x: number; y: number }, to: { x: number; y: number }): string {
    const x1 = from.x + NODE_W
    const y1 = from.y + NODE_H / 2
    const x2 = to.x
    const y2 = to.y + NODE_H / 2
    if (x2 > x1) {
      const m = (x1 + x2) / 2
      return `M${x1},${y1} C${m},${y1} ${m},${y2} ${x2},${y2}`
    }
    // back to an earlier chapter: around the bottom of the cards
    const side = Math.max(from.y, to.y) + NODE_H + 30
    return `M${from.x + NODE_W / 2},${from.y + NODE_H} C${from.x + NODE_W / 2},${side} ${to.x + NODE_W / 2},${side} ${to.x + NODE_W / 2},${to.y + NODE_H}`
  }

  const incoming = $derived(selected === null ? [] : links.flatMap((ls, i) => ls.filter((l) => (l.kind === 'ending' ? END : l.to) === selected).map((l) => ({ from: i, link: l }))))

  /** Change where a command leads, or how (world map, straight, without saving, game ending). */
  async function setLink(link: ChapterLink, change: { op?: string; to?: number }) {
    error = ''
    try {
      const edited = list.records[0]?.scripts?.[link.script]
      const commands: EventCommand[] = structuredClone($state.snapshot(edited ?? (await api.eventScript(link.script)).commands)) as EventCommand[]
      const c = commands[link.at]
      if (!c || !kinds[c.op]) return
      let op = change.op ?? c.op
      // MoveToChapter is the game's other name of MNCH: kept as written when it stays a world map link
      if (op === 'MNCH' && c.op === 'MoveToChapter') op = c.op
      const to = change.to ?? link.to ?? 0
      commands[link.at] = toChapter.includes(op) ? { op, args: [`0x${to.toString(16)}`] } : { op }
      list.update(0, (d) => {
        d.scripts ??= {}
        d.scripts[link.script] = commands
      })
    } catch (e) {
      error = String(e)
    }
  }

  const kindOp = (l: ChapterLink) => OPS.find((o) => o.kind === l.kind)?.op ?? l.op
</script>

<div class="flow">
  <section class="panel graph-panel">
    <div class="head">
      <div>
        <h2>{t('flow.title')}</h2>
        <p class="muted small">{t('flow.hint')}</p>
      </div>
      <label class="switch-row">
        <input type="checkbox" checked={worldMap} onchange={(e) => setWorldMap((e.target as HTMLInputElement).checked)} />
        <span><strong>{t('flow.worldMapOption')}</strong><br /><span class="tiny">{worldMap ? t('flow.worldMapOn') : t('flow.worldMapOff')}</span></span>
      </label>
    </div>
    <div class="legend small">
      {#if worldMap}<span><svg width="34" height="10"><line x1="0" y1="5" x2="34" y2="5" class="edge worldMap" /></svg> {t('flow.kind.worldMap')}</span>{/if}
      <span><svg width="34" height="10"><line x1="0" y1="5" x2="34" y2="5" class="edge direct" /></svg> {t('flow.kind.direct')}</span>
      <span><svg width="34" height="10"><line x1="0" y1="5" x2="34" y2="5" class="edge noSave" /></svg> {t('flow.kind.noSave')}</span>
      <span><svg width="34" height="10"><line x1="0" y1="5" x2="34" y2="5" class="edge other" /></svg> {t('flow.otherScript')}</span>
    </div>
    <div class="graph-scroll">
      {#if chapters.length}
        <div class="graph" style="width: {graph.width + NODE_W / 2}px; height: {graph.height + NODE_H}px">
          <svg width={graph.width + NODE_W / 2} height={graph.height + NODE_H} aria-hidden="true">
            <defs>
              <marker id="arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse">
                <path d="M0,0 L10,5 L0,10 z" fill="context-stroke" />
              </marker>
            </defs>
            {#each graph.edges as e, k (k)}
              <path d={edgePath(graph.pos.get(e.from)!, graph.pos.get(e.to)!)} marker-end="url(#arrow)"
                    class="edge {e.link.ending ? shownKind(e.link) : 'other'}" class:lit={selected === e.from || selected === e.to}>
                <title>{title(e.from)} → {title(e.to)} · {t(`flow.kind.${shownKind(e.link)}`)} · {e.link.script}</title>
              </path>
            {/each}
          </svg>
          {#each [...graph.pos.entries()] as [n, p] (n)}
            <button class="card" class:active={selected === n} class:end={n === END} style="left: {p.x}px; top: {p.y}px; width: {NODE_W}px; height: {n === END ? 56 : NODE_H}px"
                    aria-pressed={selected === n} onclick={() => (selected = n)}>
              {#if n === END}
                <span class="card-title">🏁 {title(n)}</span>
              {:else}
                <span class="thumb"><img class="pixel" src={chapterMapUrl(n)} alt="" loading="lazy" /></span>
                <span class="card-num">{t('flow.chapterNumber', { n })}</span>
                <span class="card-title">{title(n)}</span>
              {/if}
            </button>
          {/each}
        </div>
      {:else}
        <p class="muted">…</p>
      {/if}
    </div>
    {#if graph.unreached.length}
      <details class="unreached">
        <summary class="small">{t('flow.unreached', { n: graph.unreached.length })}</summary>
        <p class="muted tiny">{t('flow.unreachedHint')}</p>
        <div class="chips">
          {#each graph.unreached as n (n)}<button class:active={selected === n} onclick={() => (selected = n)}>{title(n)}</button>{/each}
        </div>
      </details>
    {/if}
  </section>

  {#if selected !== null && selected !== END && chapters[selected]}
    {@const mine = links[selected] ?? []}
    <section class="panel detail">
      <img class="pixel detail-map" src={chapterMapUrl(selected)} alt="" />
      <h3>{title(selected)} <span class="muted tiny">#{selected}</span></h3>
      <p class="small"><Mention kind="chapters" id={String(selected)}>{t('dlg.openChapter')}</Mention> · <Mention kind="dialogues" id={String(selected)}>💬 {t('chapter.editDialogues')}</Mention></p>
      <h4>{t('flow.next')}</h4>
      {#if !mine.length}<p class="muted small">{t('flow.noNext')}</p>{/if}
      {#each mine as l, k (k)}
        <div class="link" class:secondary={!l.ending}>
          <p class="tiny muted">{l.ending ? t('flow.endingScene') : t('flow.otherScriptNamed')} · <code>{l.script}</code></p>
          <div class="row">
            <label>
              <span class="tiny">{t('flow.how')}</span>
              <select value={kindOp(l)} onchange={(e) => setLink(l, { op: (e.target as HTMLSelectElement).value })}>
                {#each OPS as o (o.op)}{#if worldMap || o.kind !== 'worldMap' || l.kind === 'worldMap'}<option value={o.op}>{t(`flow.kind.${!worldMap && o.kind === 'worldMap' ? 'direct' : o.kind}`)}</option>{/if}{/each}
                {#if !OPS.some((o) => o.kind === l.kind)}<option value={l.op}>{t(`flow.kind.${l.kind}`)}</option>{/if}
              </select>
            </label>
            {#if l.to !== null}
              <label>
                <span class="tiny">{t('flow.to')}</span>
                <select value={l.to} onchange={(e) => setLink(l, { to: Number((e.target as HTMLSelectElement).value) })}>
                  {#each chapters as c (c.index)}<option value={c.index}>{c.index} · {c.title || c.id}</option>{/each}
                </select>
              </label>
              <button class="link-button" onclick={() => (selected = l.to)} title={t('flow.goTo')}>→ {title(l.to)}</button>
            {/if}
          </div>
          {#if l.kind === 'worldMap' && worldMap}
            <p class="tiny warn">{t('flow.worldMapWarning')}</p>
            <button class="small" onclick={() => setLink(l, { op: 'MNC2' })}>{t('flow.makeDirect')}</button>
          {:else if l.kind === 'worldMap'}
            <p class="tiny muted">{t('flow.noWorldMapNote')}</p>
          {/if}
        </div>
      {/each}
      {#if error}<p class="bad small">{error}</p>{/if}
      <h4>{t('flow.previous')}</h4>
      {#if !incoming.length}<p class="muted small">{t('flow.noPrevious')}</p>{/if}
      <ul class="incoming">
        {#each incoming as i, k (k)}
          <li><button class="link-button" onclick={() => (selected = i.from)}>{title(i.from)}</button> <span class="muted tiny">{t(`flow.kind.${i.link.kind}`)}{i.link.ending ? '' : ` · ${i.link.script}`}</span></li>
        {/each}
      </ul>
      <p class="muted tiny">{t('flow.editHint')}</p>
    </section>
  {/if}
</div>

<style>
  .flow { display: grid; grid-template-columns: minmax(0, 1fr) 340px; gap: 1rem; align-items: start; }
  .small { font-size: 0.8rem; }
  .tiny { font-size: 0.72rem; }
  .bad { color: var(--bad); }
  .warn { color: var(--warn); margin: 0.3rem 0 0; }
  h2, h3, h4 { margin: 0 0 0.4rem; }
  h4 { margin-top: 0.8rem; font-size: 0.85rem; }
  p { margin: 0 0 0.4rem; }
  .legend { display: flex; flex-wrap: wrap; gap: 0.3rem 1rem; margin-bottom: 0.4rem; }
  .legend span { display: inline-flex; align-items: center; gap: 0.35rem; }
  .graph-scroll { overflow: auto; max-height: calc(100vh - 260px); border: 1px solid var(--border); border-radius: 8px; background: var(--panel-2); }
  svg { display: block; }
  .edge { fill: none; stroke: var(--muted); stroke-width: 1.6; opacity: 0.8; }
  .edge.worldMap { stroke: var(--accent); }
  .edge.direct { stroke: var(--good); }
  .edge.noSave { stroke: var(--warn); stroke-dasharray: 6 4; }
  .edge.ending { stroke: var(--warn); }
  .edge.other { stroke-dasharray: 3 4; opacity: 0.5; }
  .edge.lit { stroke-width: 3; opacity: 1; }
  .head { display: flex; flex-wrap: wrap; justify-content: space-between; gap: 0.5rem 1rem; align-items: flex-start; }
  .head > div { flex: 1 1 320px; }
  .switch-row { flex-direction: row; align-items: center; gap: 0.6rem; padding: 0.5rem 0.75rem; border: 1px solid var(--border); border-radius: var(--radius); background: var(--panel-2); color: var(--text); max-width: 340px; cursor: pointer; }
  .switch-row input { width: 1.2rem; height: 1.2rem; flex: none; }
  .graph { position: relative; }
  .graph svg { position: absolute; inset: 0; }
  .card { position: absolute; display: flex; flex-direction: column; gap: 0.3rem; padding: 0.5rem; text-align: left; border: 3px solid var(--border); border-radius: var(--radius-big); background: var(--panel); overflow: hidden; }
  .card:hover:not(.active) { border-color: var(--accent); }
  .card.active { border-color: var(--accent); box-shadow: 0 6px 18px rgb(44 91 166 / 0.25); }
  .card.end { border-color: var(--warn); justify-content: center; }
  .thumb { display: block; height: 92px; border-radius: 8px; overflow: hidden; background: var(--panel-2); flex: none; }
  .thumb img { width: 100%; height: 100%; object-fit: cover; display: block; }
  .card-num { font-size: 0.7rem; font-weight: 800; color: var(--muted); text-transform: uppercase; letter-spacing: 0.06em; }
  .card-title { font-size: 0.9rem; font-weight: 800; line-height: 1.2; overflow: hidden; display: -webkit-box; -webkit-line-clamp: 2; line-clamp: 2; -webkit-box-orient: vertical; }
  .detail-map { width: 100%; max-height: 200px; object-fit: contain; border-radius: 8px; background: var(--panel-2); margin-bottom: 0.5rem; }
  .unreached { margin-top: 0.5rem; }
  .unreached summary { cursor: pointer; }
  .chips { display: flex; flex-wrap: wrap; gap: 0.25rem; }
  .chips button { font-size: 0.78rem; padding: 0.1rem 0.45rem; }
  .chips button.active { border-color: var(--accent); background: var(--accent-soft); }
  .detail { position: sticky; top: 4rem; }
  .link { border-left: 3px solid var(--accent); padding-left: 0.5rem; margin-bottom: 0.6rem; }
  .link.secondary { border-left-color: var(--border); }
  .row { display: flex; flex-wrap: wrap; gap: 0.5rem; align-items: flex-end; }
  .row select { max-width: 13rem; }
  .link-button { border: none; background: none; padding: 0; color: var(--accent); font: inherit; font-size: 0.85rem; cursor: pointer; }
  .incoming { list-style: none; padding: 0; margin: 0; }
  code { font-size: 0.72rem; }
  @media (max-width: 1000px) { .flow { grid-template-columns: 1fr; } }
</style>
