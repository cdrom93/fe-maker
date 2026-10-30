<script lang="ts">
  import Help from './Help.svelte'
  import { onMount, tick, type Snippet } from 'svelte'
  import { appContext } from '../lib/appContext.svelte'
  import { api, chapterMapUrl } from '../lib/api'
  import type { EditableList } from '../lib/history.svelte'
  import { t } from '../lib/i18n.svelte'
  import { followFocus, useNavigator } from '../lib/navigation.svelte'
  import type { ChapterInfo, ChapterLink, ChaptersData, DialogueScene, DialoguesData, EventCommand, Objective, UnitGroup } from '../lib/types'
  import Mention from './Mention.svelte'

  // The campaign (tickets 31, 39; interface mockups of 25/10/2026): chapters as cards with their map,
  // and how each one leads to the next. Each chapter's scripts end with a command that starts the next
  // one (server: decomp/story.py). Edited scripts are kept with the dialogues' scripts.
  // chapterList: the project's chapter edits (objectives, unit groups), shown over the game's in the sheet
  let { list, chapterList, ontest, onreload, todo, todoCount }: {
    list: EditableList<DialoguesData>; chapterList: EditableList<ChaptersData>
    /** "Test this chapter": a test build that starts on it */
    ontest: (index: number) => void
    /** load the project's data again (after a chapter is added) */
    onreload: () => Promise<void>
    /** the project's problems, as listed under the header ("To do for this project") */
    todo?: Snippet
    todoCount?: { errors: number; warnings: number }
  } = $props()

  const NODE_W = 200
  const NODE_H = 184
  const ROW = 250   // a step of the story, top to bottom
  const COL = 230   // branches side by side
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
  /** each chapter's ending scene, where a chapter that leads nowhere gets its link */
  let endings = $state<(string | null)[]>([])
  let selected = $state<number | null>(0)
  let error = $state('')
  /** false: the project goes from chapter to chapter without the world map (ticket 39) */
  let worldMap = $state(true)

  onMount(() => loadFlow())

  // Back to this page ("Back" button): its chapter again.
  followFocus('flow', useNavigator(), () => chapters.map((c) => String(c.index)), (i) => (selected = i))

  async function loadFlow() {
    // an older server has no world map option: the world map stays
    const [all, info, wm, free] = await Promise.all([api.chapters(), api.chapterLinks(), api.worldMap().catch(() => ({ worldMap: true })),
      api.freeChapters().catch(() => ({ free: 0 }))])
    chapters = all
    original = info.links
    kinds = info.kinds
    toChapter = info.toChapter
    endings = info.endings
    worldMap = wm.worldMap
    freeChapters = free.free
  }

  // A new chapter after the selected one (server: newchapter.py, a free slot of the game's chapters).
  let freeChapters = $state(0)
  let adding = $state(false)
  let newTitle = $state('')
  let newWidth = $state(15)
  let newHeight = $state(10)
  let addError = $state('')

  // Music imported for the selected chapter's player phase (server: decomp/music.py).
  let music = $state<Record<string, { key: string; name?: string }>>({})
  let musicError = $state('')

  $effect(() => {
    const i = selected
    music = {}
    musicError = ''
    if (i !== null && i >= 0) api.chapterMusic(i).then((m) => { if (selected === i) music = m }).catch(() => {})
  })

  async function importMusic(file: File | undefined) {
    if (!file || selected === null) return
    musicError = ''
    try {
      await api.importChapterMusic(selected, file)
      music = await api.chapterMusic(selected)
    } catch (e) {
      musicError = String(e).includes('notAMidi') ? t('flow.music.notAMidi') : String(e)
    }
  }

  async function removeMusic() {
    if (selected === null) return
    await api.removeChapterMusic(selected, 'bluePhase')
    music = await api.chapterMusic(selected)
  }

  /** A chapter that leads nowhere: its ending scene goes to `to`, or ends the game (mirrors story.with_next). */
  async function linkTo(to: number | 'title') {
    const name = selected === null ? null : endings[selected]
    if (!name) return
    error = ''
    try {
      const commands = list.records[0]?.scripts?.[name] ?? (await api.eventScript(name)).commands
      let at = commands.length
      while (at > 0 && ['ENDA', 'NoFade', ''].includes(commands[at - 1].op)) at--
      const change = to === 'title' ? { op: 'MNTS', args: ['0'] } : { op: 'MNC2', args: [`0x${to.toString(16)}`] }
      const next = [...commands.slice(0, at), change, ...commands.slice(at)]
      list.update(0, (d) => {
        d.scripts ??= {}
        d.scripts[name] = next
      })
    } catch (e) {
      error = String(e)
    }
  }

  /** A chapter the project adds changes title (its text and its title picture, written at build time). */
  function rename(value: string) {
    const name = value.trim()
    if (selected === null) return
    const index = selected
    chapterList.update(0, (d) => {
      const titles: Record<string, string> = { ...d.titles, [index]: name }
      if (!name) delete titles[index]   // empty: the game's title again
      d.titles = titles
    })
    if (name) chapters = chapters.map((c) => (c.index === index ? { ...c, title: name } : c))
    else chapterList.flush().then(loadFlow)
  }

  async function addChapter() {
    if (selected === null || selected < 0) return
    addError = ''
    try {
      await list.flush()
      await chapterList.flush()
      const { index } = await api.newChapter(selected, newWidth, newHeight, newTitle)
      await onreload()
      await loadFlow()
      selected = index
      adding = false
      newTitle = ''
    } catch (e) {
      const code = String(e).match(/(noFreeChapter|badMapSize)/)?.[1]
      addError = code ? t(`flow.add.${code}`) : String(e)
    }
  }

  async function setWorldMap(on: boolean) {
    error = ''
    try {
      worldMap = (await api.setWorldMap(on)).worldMap
    } catch (e) {
      error = String(e)
    }
  }

  /** The selected chapter's sheet, as in the mockup: objective, units, scenes (loaded when it is picked). */
  // The game's objective and groups as loaded; the project's edits are applied in `view` (like ChapterEditor).
  let loaded = $state<{ index: number; objective: Objective | null; groups: UnitGroup[]; scenes: string[] } | null>(null)
  $effect(() => {
    const i = selected
    if (i === null || i === END || !chapters[i]) return
    Promise.all([
      api.chapterObjective(i).catch(() => null),
      api.chapterUnits(i).catch(() => null),
      api.chapterDialogues(i).catch(() => null),
    ]).then(([objective, units, dialogues]) => {
      if (selected !== i) return
      loaded = { index: i, objective, groups: units?.groups ?? [], scenes: [...new Set((dialogues?.scenes ?? []).map(sceneLabel))] }
    })
  })
  /** Objective and fighting units of a chapter, with the project's edits (sheet and graph cards). */
  function summarize(index: number, original: Objective | null, groups: Pick<UnitGroup, 'name' | 'origin' | 'units'>[]) {
    const edits = chapterList.records[0]
    const objective = original ? { ...original, ...(edits?.objectives?.[String(index)] ?? {}) } : null
    const newGroups = Object.entries(edits?.newGroups ?? {}).filter(([, g]) => g.chapter === index).map(([name]) => name)
    const fighting = [
      ...groups.filter((g) => g.origin !== 'cutscene').map((g) => edits?.unitGroups?.[g.name] ?? g.units),
      ...newGroups.map((name) => edits?.unitGroups?.[name] ?? []),
    ].flat()
    return {
      objective,
      allies: fighting.filter((u) => u.side !== 'enemy').length,
      enemies: fighting.filter((u) => u.side === 'enemy').length,
    }
  }
  const sheet = $derived(loaded ? { index: loaded.index, scenes: loaded.scenes, ...summarize(loaded.index, loaded.objective, loaded.groups) } : null)
  // every chapter's card (one request; an older server without the route shows no summary)
  let overview = $state<Awaited<ReturnType<typeof api.chaptersOverview>>>({})
  $effect(() => {
    api.chaptersOverview().then((o) => (overview = o)).catch(() => {})
  })
  const cards = $derived(Object.fromEntries(Object.entries(overview).map(([i, o]) => [i, summarize(Number(i), o.objective, o.groups)])))

  function sceneLabel(s: DialogueScene): string {
    const key = `dlg.trigger.${s.trigger.kind}`
    const text = t(key, { n: s.trigger.turn ?? '', a: s.trigger.a ?? '', b: s.trigger.b ?? '', x: s.trigger.x ?? '', y: s.trigger.y ?? '' })
    return text === key ? s.script : text
  }

  /** How a link really goes: without the world map, MNCH goes straight to its chapter. */
  const shownKind = (l: ChapterLink) => (!worldMap && l.kind === 'worldMap' ? 'direct' : l.kind)

  $effect(() => {
    appContext.detail = selected !== null && selected >= 0 ? title(selected) : ''
    appContext.recordId = selected !== null ? String(selected) : ''
    return () => {
      appContext.detail = ''
      appContext.recordId = ''
    }
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
    return original.map((ls, i) => {
      const ending = endings[i]
      // an ending scene without a link yet can get one here (ticket 55)
      const scripts = [...new Set([...ls.map((l) => l.script), ...(ending && edited[ending] ? [ending] : [])])]
      return scripts.flatMap((s) => {
        const mine = ls.filter((l) => l.script === s)
        return edited[s] ? linksOf(s, s === ending, edited[s]) : mine
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
    const width = widest * COL + PAD * 2
    const pos = new Map<number, { x: number; y: number }>()
    for (const [d, r] of rows) {
      const left = (width - r.length * COL) / 2
      r.forEach((n, i) => pos.set(n, { x: left + i * COL + (COL - NODE_W) / 2, y: PAD + d * ROW }))
    }
    const edges: { from: number; to: number; link: ChapterLink }[] = []
    for (const n of order) {
      if (n === END) continue
      for (const l of links[n] ?? []) {
        const to = l.kind === 'ending' ? END : l.to
        if (to !== null && pos.has(to)) edges.push({ from: n, to, link: l })
      }
    }
    const unreached = chapters.filter((c) => c.title && !c.hidden && !depth.has(c.index)).map((c) => c.index)
    return { pos, edges, width, height: PAD * 2 + (rows.size ? Math.max(...rows.keys()) + 1 : 1) * ROW, unreached }
  })

  // Zoom with the wheel around the pointer, move by dragging the background, as in CAD programs (ticket 76).
  let scroller = $state<HTMLElement>()
  let zoom = $state(1)
  let dragging: { x: number; y: number; left: number; top: number } | null = null

  $effect(() => {
    const el = scroller
    if (!el) return
    const wheel = (e: WheelEvent) => {
      e.preventDefault()
      const next = Math.min(2, Math.max(0.2, zoom * (e.deltaY < 0 ? 1.15 : 1 / 1.15)))
      const box = el.getBoundingClientRect()
      const x = e.clientX - box.left
      const y = e.clientY - box.top
      const left = ((el.scrollLeft + x) * next) / zoom - x
      const top = ((el.scrollTop + y) * next) / zoom - y
      zoom = next
      tick().then(() => el.scrollTo(left, top))
    }
    el.addEventListener('wheel', wheel, { passive: false })
    return () => el.removeEventListener('wheel', wheel)
  })

  function startDrag(e: PointerEvent) {
    if (!scroller || (e.target as HTMLElement).closest('button')) return
    dragging = { x: e.clientX, y: e.clientY, left: scroller.scrollLeft, top: scroller.scrollTop }
    scroller.setPointerCapture(e.pointerId)
  }
  function drag(e: PointerEvent) {
    if (dragging && scroller) scroller.scrollTo(dragging.left - e.clientX + dragging.x, dragging.top - e.clientY + dragging.y)
  }
  const endDrag = () => (dragging = null)

  function edgePath(from: { x: number; y: number }, to: { x: number; y: number }): string {
    const x1 = from.x + NODE_W / 2
    const y1 = from.y + NODE_H
    const x2 = to.x + NODE_W / 2
    const y2 = to.y
    if (y2 > y1) {
      const m = (y1 + y2) / 2
      return `M${x1},${y1} C${x1},${m} ${x2},${m} ${x2},${y2}`
    }
    // back to an earlier chapter: around the right of the cards
    const side = Math.max(from.x, to.x) + NODE_W + 30
    return `M${from.x + NODE_W},${from.y + NODE_H / 2} C${side},${from.y + NODE_H / 2} ${side},${to.y + NODE_H / 2} ${to.x + NODE_W},${to.y + NODE_H / 2}`
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
        <h2>{t('flow.title')} <Help text={t('flow.hint')} /></h2>
      </div>
      <label class="switch-row">
        <input type="checkbox" checked={worldMap} onchange={(e) => setWorldMap((e.target as HTMLInputElement).checked)} />
        <strong>{t('flow.worldMapOption')}</strong> <Help text={worldMap ? t('flow.worldMapOn') : t('flow.worldMapOff')} />
      </label>
    </div>
    <div class="legend small">
      {#if worldMap}<span><svg width="34" height="10"><line x1="0" y1="5" x2="34" y2="5" class="edge worldMap" /></svg> {t('flow.kind.worldMap')}</span>{/if}
      <span><svg width="34" height="10"><line x1="0" y1="5" x2="34" y2="5" class="edge direct" /></svg> {t('flow.kind.direct')}</span>
      <span><svg width="34" height="10"><line x1="0" y1="5" x2="34" y2="5" class="edge noSave" /></svg> {t('flow.kind.noSave')}</span>
      <span><svg width="34" height="10"><line x1="0" y1="5" x2="34" y2="5" class="edge other" /></svg> {t('flow.otherScript')}</span>
    </div>
    <p class="muted tiny zoom-hint"><Help text={t('flow.zoomHint')} /> <button class="link" onclick={() => (zoom = 1)}>{Math.round(zoom * 100)} %</button></p>
    <div class="graph-scroll" bind:this={scroller} role="presentation" onpointerdown={startDrag} onpointermove={drag} onpointerup={endDrag} onpointercancel={endDrag}>
      {#if chapters.length}
        <div style="width: {(graph.width + NODE_W / 2) * zoom}px; height: {(graph.height + NODE_H) * zoom}px">
        <div class="graph" style="width: {graph.width + NODE_W / 2}px; height: {graph.height + NODE_H}px; transform: scale({zoom})">
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
                <span class="card-title">{title(n)}</span>
              {:else}
                <span class="thumb"><img class="pixel" src={chapterMapUrl(n)} alt="" loading="lazy" /></span>
                <span class="card-num">{t('flow.chapterNumber', { n })}</span>
                <span class="card-title">{title(n)}</span>
                {#if cards[n]}
                  <span class="card-sum">
                    {#if cards[n].objective}<span class="card-goal">{t(`objective.type.${cards[n].objective!.type}`)}</span>{/if}
                    <span class="mini ally" title={t('flow.allies', { n: cards[n].allies })}>{cards[n].allies}</span>
                    <span class="mini enemy" title={t('flow.enemies', { n: cards[n].enemies })}>{cards[n].enemies}</span>
                  </span>
                {/if}
              {/if}
            </button>
          {/each}
        </div>
        </div>
      {:else}
        <p class="muted">…</p>
      {/if}
    </div>
    {#if todo && todoCount}
      <div class="todo">
        <h4>{t('flow.todo')}</h4>
        {#if todoCount.errors || todoCount.warnings}
          <Help text={t('flow.todoHint', { errors: todoCount.errors, warnings: todoCount.warnings })} />
          {@render todo()}
        {:else}
          <p class="muted small">{t('flow.todoNone')}</p>
        {/if}
      </div>
    {/if}
    {#if graph.unreached.length}
      <details class="unreached">
        <summary class="small">{t('flow.unreached', { n: graph.unreached.length })} <Help text={t('flow.unreachedHint')} /></summary>
        <div class="chips">
          {#each graph.unreached as n (n)}<button class:active={selected === n} onclick={() => (selected = n)}>{title(n)}</button>{/each}
        </div>
      </details>
    {/if}
  </section>

  {#if selected !== null && selected !== END && chapters[selected]}
    {@const mine = links[selected] ?? []}
    <section class="panel detail">
      <span class="card-num">{t('flow.chapterNumber', { n: selected })}</span>
      <h2 class="sheet-title">{title(selected)}</h2>
      <label class="rename">{t('flow.add.title')}
        <input value={chapters[selected].title} maxlength="40" title={t('flow.renameHint')} onchange={(e) => rename((e.target as HTMLInputElement).value)} />
      </label>
      <img class="pixel detail-map" src={chapterMapUrl(selected)} alt="" />
      <ol class="work">
        {#if chapters[selected].map}<li><Mention kind="maps" id={chapters[selected].map}>{t('flow.step.map')}</Mention></li>{/if}
        <li><Mention kind="chapters" id={String(selected)}>{t('flow.step.units')}</Mention></li>
        <li><Mention kind="dialogues" id={String(selected)}>{t('flow.step.dialogues')}</Mention></li>
        <li><button class="play" onclick={() => selected !== null && ontest(selected)} title={t('flow.testHint')}>▶ {t('flow.test')}</button></li>
      </ol>
      {#if sheet?.index === selected}
        <div class="sheet-block">
          <h4>{t('flow.objective')}</h4>
          <div class="goal">
            {sheet.objective ? t(`objective.type.${sheet.objective.type}`) : '…'}{sheet.objective?.type === 'defense' ? ` · ${t('flow.turns', { n: sheet.objective.turns })}` : ''}
          </div>
          <div class="chips">
            <span class="chip ally">{t('flow.allies', { n: sheet.allies })}</span>
            <span class="chip enemy">{t('flow.enemies', { n: sheet.enemies })}</span>
          </div>
        </div>
        {#if sheet.scenes.length}
          <div class="sheet-block">
            <h4>{t('flow.scenes')}</h4>
            {#each sheet.scenes as s (s)}
              <Mention kind="dialogues" id={String(selected)}><span class="scene">{s}</span></Mention>
            {/each}
          </div>
        {/if}
      {/if}
      <div class="music">
        <h4>{t('flow.music.title')} <Help text={t('flow.music.hint')} /></h4>
        {#if music.bluePhase}
          <span class="small">{music.bluePhase.name}</span>
          <button class="link" onclick={removeMusic}>{t('flow.music.reset')}</button>
        {:else}
          <span class="muted small">{t('flow.music.game')}</span>
        {/if}
        <label class="small">{t('flow.music.import')}
          <input type="file" accept=".mid,.midi,audio/midi" onchange={(e) => importMusic((e.target as HTMLInputElement).files?.[0])} />
        </label>
        {#if musicError}<p class="bad small">{musicError}</p>{/if}
      </div>
      <div class="add-chapter">
        {#if adding}
          <label>{t('flow.add.title')} <input bind:value={newTitle} maxlength="40" /></label>
          <label>{t('flow.add.width')} <input type="number" bind:value={newWidth} min="15" max="64" /></label>
          <label>{t('flow.add.height')} <input type="number" bind:value={newHeight} min="10" max="64" /></label>
          <button class="primary" onclick={addChapter}>{t('flow.add.confirm')}</button>
          <button class="link" onclick={() => (adding = false)}>{t('flow.add.cancel')}</button>
          <p class="tiny muted">{t('flow.add.hint', { n: freeChapters })}</p>
        {:else}
          <button onclick={() => (adding = true)} disabled={!freeChapters} title={t('flow.add.hint', { n: freeChapters })}>+ {t('flow.add.button')}</button>
        {/if}
        {#if addError}<p class="bad small">{addError}</p>{/if}
      </div>
      <h4>{t('flow.next')}</h4>
      {#if !mine.length}
        <p class="muted small">{t('flow.noNext')}</p>
        {#if endings[selected]}
          <label class="small">{t('flow.linkTo')}
            <select value="" onchange={(e) => { const v = (e.target as HTMLSelectElement).value; if (v !== '') linkTo(Number(v)) }}>
              <option value="">{t('flow.linkChoose')}</option>
              {#each chapters.filter((c) => !c.hidden) as c (c.index)}<option value={c.index}>{c.index} · {c.title || c.id}</option>{/each}
            </select>
          </label>
          <button class="small" onclick={() => linkTo('title')} title={t('flow.endGameHint')}>{t('flow.endGame')}</button>
        {/if}
      {/if}
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
            <!-- a direct link to chapter 2 or later needs the whole project without the world map (ticket 39) -->
            <button class="small" onclick={() => setWorldMap(false)}>{t('flow.makeDirect')}</button>
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
      <Help text={t('flow.editHint')} />
    </section>
  {/if}
</div>

<style>
  .flow { display: grid; grid-template-columns: minmax(0, 1fr) 340px; gap: 1rem; align-items: start; }
  .small { font-size: 0.8rem; }
  .tiny { font-size: 0.72rem; }
  .bad { color: var(--bad); }
  .warn { color: var(--warn); margin: 0.3rem 0 0; }
  h2, h4 { margin: 0 0 0.4rem; }
  h4 { margin-top: 0.8rem; font-size: 0.85rem; }
  p { margin: 0 0 0.4rem; }
  .legend { display: flex; flex-wrap: wrap; gap: 0.3rem 1rem; margin-bottom: 0.4rem; }
  .legend span { display: inline-flex; align-items: center; gap: 0.35rem; }
  .graph-scroll { overflow: auto; height: calc(100vh - 260px); min-height: 24rem; cursor: grab; border: 1px solid var(--border); border-radius: 8px; background: var(--panel-2); }
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
  .graph { position: relative; transform-origin: 0 0; }
  .zoom-hint { margin: 0.2rem 0; }
  .work { margin: 0.6rem 0; padding-left: 1.3rem; display: flex; flex-direction: column; gap: 0.35rem; font-weight: 700; }
  .graph svg { position: absolute; inset: 0; }
  .card { position: absolute; display: flex; flex-direction: column; gap: 0.3rem; padding: 0.5rem; text-align: left; border: 3px solid var(--border); border-radius: var(--radius-big); background: var(--panel); overflow: hidden; }
  .card:hover:not(.active) { border-color: var(--accent); }
  .card.active { border-color: var(--accent); box-shadow: 0 6px 18px rgb(44 91 166 / 0.25); }
  .card.end { border-color: var(--warn); justify-content: center; }
  .thumb { display: block; height: 92px; border-radius: 8px; overflow: hidden; background: var(--panel-2); flex: none; }
  .thumb img { width: 100%; height: 100%; object-fit: cover; display: block; }
  .card-num { font-size: 0.7rem; font-weight: 800; color: var(--muted); text-transform: uppercase; letter-spacing: 0.06em; }
  .todo { margin-top: 1rem; }
  .todo h4 { margin: 0 0 0.3rem; }
  .card-sum { display: flex; align-items: center; gap: 0.3rem; font-size: 0.72rem; font-weight: 700; white-space: nowrap; }
  .card-goal { overflow: hidden; text-overflow: ellipsis; flex: 1; min-width: 0; }
  .mini { padding: 0 0.4rem; border-radius: 999px; }
  .mini.ally { background: var(--accent-soft); color: var(--accent); }
  .mini.enemy { background: var(--bad-soft); color: var(--bad); }
  .card-title { font-size: 0.9rem; font-weight: 800; line-height: 1.2; overflow: hidden; display: -webkit-box; -webkit-line-clamp: 2; line-clamp: 2; -webkit-box-orient: vertical; }
  .sheet-title { font-size: 1.4rem; margin: 0.1rem 0 0.6rem; }
  .sheet-block { display: flex; flex-direction: column; gap: 0.35rem; margin-bottom: 0.7rem; }
  .sheet-block h4 { margin: 0; }
  .goal { padding: 0.55rem 0.75rem; border-radius: var(--radius); background: var(--panel-2); border: 1px solid var(--border); font-weight: 800; }
  .chip { padding: 0.2rem 0.6rem; border-radius: 6px; font-size: 0.8rem; font-weight: 700; }
  .chip.ally { background: var(--accent-soft); color: var(--accent); }
  .chip.enemy { background: var(--bad-soft); color: var(--bad); }
  .scene { display: block; padding: 0.45rem 0.7rem; border: 1px solid var(--border); border-radius: var(--radius); font-weight: 700; font-size: 0.85rem; }
  .sheet-buttons { display: flex; flex-wrap: wrap; gap: 0.5rem; margin-bottom: 0.8rem; }
  .big-link { display: inline-flex; align-items: center; min-height: 40px; padding: 0 0.9rem; border-radius: var(--radius); border: 2px solid var(--accent); color: var(--accent); font-weight: 800; }
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
  .add-chapter { display: flex; flex-wrap: wrap; gap: 0.4rem; align-items: center; margin: 0.6rem 0; }
  .add-chapter label { display: flex; gap: 0.3rem; align-items: center; font-size: 0.85rem; }
  .add-chapter input[type='number'] { width: 4rem; }
  .music { margin: 0.6rem 0; display: flex; flex-wrap: wrap; gap: 0.4rem; align-items: center; }
  .music h4, .music p { flex-basis: 100%; margin: 0; }
  .rename { display: flex; gap: 0.4rem; align-items: center; font-size: 0.85rem; margin-bottom: 0.4rem; }
  .rename input { flex: 1; min-width: 0; }
</style>
