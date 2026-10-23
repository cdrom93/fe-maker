<script module lang="ts">
  import type { MapLayout } from '../lib/types'

  /** Draws the current brush metatile on a small canvas. */
  export function drawBrush(canvas: HTMLCanvasElement, params: { m: number; sheet: HTMLImageElement; layout: MapLayout }) {
    function draw(p: typeof params) {
      const ctx = canvas.getContext('2d')
      if (!ctx) return
      ctx.imageSmoothingEnabled = false
      ctx.clearRect(0, 0, canvas.width, canvas.height)
      ctx.drawImage(p.sheet, (p.m % p.layout.columns) * 16, Math.floor(p.m / p.layout.columns) * 16, 16, 16, 0, 0, canvas.width, canvas.height)
    }
    draw(params)
    return { update: draw }
  }
</script>

<script lang="ts">
  import { onMount } from 'svelte'
  import { appContext } from '../lib/appContext.svelte'
  import { api, mapTilesetUrl } from '../lib/api'
  import type { EditableList } from '../lib/history.svelte'
  import { t } from '../lib/i18n.svelte'
  import { followFocus, useNavigator } from '../lib/navigation.svelte'
  import type { ChapterInfo, MapInfo, MapsData, Problem } from '../lib/types'
  import Mention from './Mention.svelte'
  import RecordList from './RecordList.svelte'

  let { list, problems }: { list: EditableList<MapsData>; problems: Problem[] } = $props()

  type Tool = 'pen' | 'rect' | 'fill' | 'pick'
  const TOOLS: { id: Tool; icon: string }[] = [
    { id: 'pen', icon: '✏️' },
    { id: 'rect', icon: '▭' },
    { id: 'fill', icon: '🪣' },
    { id: 'pick', icon: '💧' },
  ]
  const PALETTE_COLUMNS = 8
  const TILE = 16 // metatile size in the game

  let maps = $state<(MapInfo & { name: string })[]>([])
  let chapters = $state<ChapterInfo[]>([])
  let selected = $state(0)
  let layout = $state<MapLayout | null>(null)
  let sheet = $state<HTMLImageElement | null>(null)
  let tool = $state<Tool>('pen')
  let brush = $state(0)
  let zoom = $state(2)
  let showGrid = $state(true)
  let showTerrain = $state(false)
  let terrainFilter = $state<number | null>(null)
  let hover = $state<{ x: number; y: number } | null>(null)
  // Cells being painted (one stroke or rectangle); saved as one undo step when the mouse is released.
  let draft = $state<number[][] | null>(null)
  let rectStart = $state<{ x: number; y: number } | null>(null)
  let mapCanvas = $state<HTMLCanvasElement>()
  let paletteCanvas = $state<HTMLCanvasElement>()

  const info = $derived(maps[selected])
  const painted = $derived(info ? list.records[0]?.layouts?.[info.id] : undefined)
  const rows = $derived(draft ?? painted?.rows ?? layout?.rows ?? [])
  const width = $derived(rows[0]?.length ?? 0)
  const height = $derived(rows.length)
  const cell = $derived(TILE * zoom)
  const mapProblems = $derived(info ? problems.filter((p) => p.kind === 'maps' && p.id === info.id) : [])
  const chapterTitle = (i: number) => chapters[i]?.title || chapters[i]?.id || String(i)

  // Palette: one copy of each metatile, optionally only those of one terrain.
  const paletteTiles = $derived(
    layout ? [...layout.terrains.keys()].filter((m) => !layout!.duplicates[m] && (terrainFilter === null || layout!.terrains[m] === terrainFilter)) : [],
  )
  // Terrains present on the map, most frequent first (legend and palette filter).
  const mapTerrains = $derived.by(() => {
    if (!layout) return []
    const count = new Map<number, number>()
    for (const row of rows) for (const m of row) count.set(layout.terrains[m], (count.get(layout.terrains[m]) ?? 0) + 1)
    return [...count.entries()].sort((a, b) => b[1] - a[1]).map(([id]) => id)
  })
  const allTerrains = $derived(layout ? [...new Set(layout.terrains.filter((_, m) => !layout!.duplicates[m]))].sort((a, b) => a - b) : [])

  const nav = useNavigator()
  followFocus('maps', nav, () => maps.map((m) => m.id), (i) => load(i))

  $effect(() => {
    appContext.detail = info ? `${info.id}${hover ? ` · ${hover.x}, ${hover.y}` : ''}` : ''
    return () => (appContext.detail = '')
  })

  onMount(async () => {
    const [all, chapterList] = await Promise.all([api.maps(), api.chapters()])
    chapters = chapterList
    // A map is named after the story chapters that use it.
    maps = all.map((m) => {
      const titles = [...new Set(m.chapters.map((i) => chapterList[i]?.title).filter(Boolean))]
      return { ...m, name: titles.join(' / ') || m.id }
    })
    // Opened from a link (e.g. a chapter): the map list was not loaded yet.
    const asked = nav.focus?.kind === 'maps' ? maps.findIndex((m) => m.id === nav.focus!.id) : -1
    if (maps.length) await load(Math.max(0, asked))
  })

  async function load(index: number) {
    selected = index
    draft = null
    rectStart = null
    hover = null
    terrainFilter = null
    const id = maps[index].id
    const [data, img] = await Promise.all([api.map(id), loadImage(mapTilesetUrl(id))])
    if (maps[selected]?.id !== id) return
    layout = data
    sheet = img
    // Start with the map's most common tile (usually its ground).
    const count = new Map<number, number>()
    for (const row of data.rows) for (const c of row) count.set(c, (count.get(c) ?? 0) + 1)
    brush = [...count.entries()].sort((a, b) => b[1] - a[1])[0]?.[0] ?? 0
  }

  function loadImage(url: string): Promise<HTMLImageElement> {
    return new Promise((resolve, reject) => {
      const img = new Image()
      img.onload = () => resolve(img)
      img.onerror = reject
      img.src = url
    })
  }

  // Terrain overlay colors: close to what the terrain looks like (others get a distinct hue).
  const TERRAIN_COLORS: Record<number, string> = {
    0: '0 0 0', 1: '155 227 107', 2: '224 194 122', 3: '230 126 34', 4: '160 90 30', 5: '211 84 0', 6: '243 156 18', 7: '243 156 18',
    8: '192 57 43', 48: '192 57 43', 10: '142 68 173', 11: '155 89 182', 35: '155 89 182', 12: '30 132 73', 13: '20 90 50',
    14: '247 220 111', 15: '244 208 63', 16: '52 152 219', 17: '160 82 45', 18: '93 46 12', 19: '185 119 14', 20: '185 119 14',
    52: '185 119 14', 21: '27 79 114', 22: '46 134 193', 23: '189 195 199', 25: '127 140 141', 50: '127 140 141', 26: '66 73 73',
    27: '112 123 124', 28: '166 172 175', 29: '86 101 115', 30: '110 44 0', 31: '241 196 15', 32: '212 172 13', 33: '212 172 13',
    34: '146 43 33', 36: '236 240 241', 37: '149 165 166', 55: '149 165 166', 38: '77 86 86', 47: '214 234 248', 49: '110 75 58',
    53: '174 214 241', 54: '11 31 51', 60: '93 173 226',
  }
  const terrainColor = (id: number, alpha = 0.55) =>
    id in TERRAIN_COLORS ? `rgb(${TERRAIN_COLORS[id]} / ${alpha})` : `hsl(${(id * 47) % 360} 75% 50% / ${alpha})`
  // Clear names from the locales: the in-game ones are short and ambiguous (two "Wall", "Mntn").
  const terrainName = (id: number) => t(`terrain.${id}`)

  function drawTile(ctx: CanvasRenderingContext2D, m: number, x: number, y: number, size: number) {
    if (!sheet || !layout) return
    const sx = (m % layout.columns) * TILE
    const sy = Math.floor(m / layout.columns) * TILE
    ctx.drawImage(sheet, sx, sy, TILE, TILE, x, y, size, size)
  }

  // Map canvas
  $effect(() => {
    const ctx = mapCanvas?.getContext('2d')
    if (!ctx || !layout || !sheet) return
    ctx.imageSmoothingEnabled = false
    ctx.clearRect(0, 0, width * cell, height * cell)
    rows.forEach((row, y) => row.forEach((m, x) => drawTile(ctx, m, x * cell, y * cell, cell)))
    if (showTerrain) {
      rows.forEach((row, y) => row.forEach((m, x) => {
        ctx.fillStyle = terrainColor(layout!.terrains[m])
        ctx.fillRect(x * cell, y * cell, cell, cell)
      }))
    }
    if (showGrid) {
      ctx.strokeStyle = 'rgb(0 0 0 / 0.25)'
      ctx.lineWidth = 1
      ctx.beginPath()
      for (let x = 1; x < width; x++) {
        ctx.moveTo(x * cell + 0.5, 0)
        ctx.lineTo(x * cell + 0.5, height * cell)
      }
      for (let y = 1; y < height; y++) {
        ctx.moveTo(0, y * cell + 0.5)
        ctx.lineTo(width * cell, y * cell + 0.5)
      }
      ctx.stroke()
    }
    // Brush preview under the mouse, or the rectangle being drawn.
    const area = rectStart && hover ? rectOf(rectStart, hover) : hover && tool !== 'pick' && tool !== 'fill' ? { x0: hover.x, y0: hover.y, x1: hover.x, y1: hover.y } : null
    if (area) {
      ctx.globalAlpha = rectStart ? 1 : 0.6
      for (let y = area.y0; y <= area.y1; y++) for (let x = area.x0; x <= area.x1; x++) drawTile(ctx, brush, x * cell, y * cell, cell)
      ctx.globalAlpha = 1
    }
    if (hover) {
      ctx.strokeStyle = '#fff'
      ctx.lineWidth = 2
      const a = area ?? { x0: hover.x, y0: hover.y, x1: hover.x, y1: hover.y }
      ctx.strokeRect(a.x0 * cell + 1, a.y0 * cell + 1, (a.x1 - a.x0 + 1) * cell - 2, (a.y1 - a.y0 + 1) * cell - 2)
    }
  })

  // Palette canvas
  const PALETTE_CELL = 32
  $effect(() => {
    const ctx = paletteCanvas?.getContext('2d')
    if (!ctx || !layout || !sheet) return
    ctx.imageSmoothingEnabled = false
    ctx.clearRect(0, 0, paletteCanvas!.width, paletteCanvas!.height)
    paletteTiles.forEach((m, i) => {
      const x = (i % PALETTE_COLUMNS) * PALETTE_CELL
      const y = Math.floor(i / PALETTE_COLUMNS) * PALETTE_CELL
      drawTile(ctx, m, x, y, PALETTE_CELL)
      if (m === brush) {
        ctx.strokeStyle = '#fff'
        ctx.lineWidth = 3
        ctx.strokeRect(x + 1.5, y + 1.5, PALETTE_CELL - 3, PALETTE_CELL - 3)
        ctx.strokeStyle = '#000'
        ctx.lineWidth = 1
        ctx.strokeRect(x + 0.5, y + 0.5, PALETTE_CELL - 1, PALETTE_CELL - 1)
      }
    })
  })

  function cellAt(e: MouseEvent): { x: number; y: number } | null {
    if (!mapCanvas) return null
    const r = mapCanvas.getBoundingClientRect()
    const x = Math.floor((e.clientX - r.left) / cell)
    const y = Math.floor((e.clientY - r.top) / cell)
    return x >= 0 && y >= 0 && x < width && y < height ? { x, y } : null
  }

  function rectOf(a: { x: number; y: number }, b: { x: number; y: number }) {
    return { x0: Math.min(a.x, b.x), y0: Math.min(a.y, b.y), x1: Math.max(a.x, b.x), y1: Math.max(a.y, b.y) }
  }

  const copyRows = () => rows.map((r) => [...r])

  let last: { x: number; y: number } | null = null

  /** Paint a cell, and the cells between it and the previous one (the mouse can skip cells). */
  function paint(p: { x: number; y: number }) {
    if (!draft) return
    const from = last ?? p
    const steps = Math.max(Math.abs(p.x - from.x), Math.abs(p.y - from.y))
    for (let k = 0; k <= steps; k++) {
      const x = Math.round(from.x + ((p.x - from.x) * k) / (steps || 1))
      const y = Math.round(from.y + ((p.y - from.y) * k) / (steps || 1))
      if (draft[y][x] !== brush) draft[y][x] = brush
    }
    last = p
  }

  function floodFill(start: { x: number; y: number }) {
    const next = copyRows()
    const target = next[start.y][start.x]
    if (target === brush) return
    const stack = [start]
    while (stack.length) {
      const { x, y } = stack.pop()!
      if (x < 0 || y < 0 || x >= width || y >= height || next[y][x] !== target) continue
      next[y][x] = brush
      stack.push({ x: x + 1, y }, { x: x - 1, y }, { x, y: y + 1 }, { x, y: y - 1 })
    }
    commit(next)
  }

  function onDown(e: MouseEvent) {
    const p = cellAt(e)
    if (!p) return
    e.preventDefault()
    // Right click or Alt+click: take the tile under the mouse, whatever the tool.
    if (e.button === 2 || e.altKey || tool === 'pick') {
      brush = rows[p.y][p.x]
      return
    }
    if (e.button !== 0) return
    if (tool === 'fill') return floodFill(p)
    draft = copyRows()
    last = null
    if (tool === 'rect') rectStart = p
    else paint(p)
  }

  function onMove(e: MouseEvent) {
    hover = cellAt(e)
    if (hover && draft && tool === 'pen' && e.buttons & 1) paint(hover)
  }

  function onUp() {
    if (!draft) return
    if (rectStart && hover) {
      const a = rectOf(rectStart, hover)
      for (let y = a.y0; y <= a.y1; y++) for (let x = a.x0; x <= a.x1; x++) draft[y][x] = brush
    }
    const result = $state.snapshot(draft) as number[][]
    draft = null
    rectStart = null
    commit(result)
  }

  /** Save painted cells as one undo step. A map painted back to the original is no longer stored. */
  function commit(next: number[][]) {
    if (!info || !layout) return
    const id = info.id
    const same = JSON.stringify(next) === JSON.stringify(layout.rows)
    if (same && !painted) return
    list.update(0, (d) => {
      d.layouts ??= {}
      if (same) delete d.layouts[id]
      else d.layouts[id] = { rows: next }
    })
  }

  function reset() {
    if (!info) return
    const id = info.id
    list.update(0, (d) => {
      if (d.layouts) delete d.layouts[id]
    })
  }

  function pickFromPalette(e: MouseEvent) {
    const r = paletteCanvas!.getBoundingClientRect()
    const i = Math.floor((e.clientY - r.top) / PALETTE_CELL) * PALETTE_COLUMNS + Math.floor((e.clientX - r.left) / PALETTE_CELL)
    if (i >= 0 && i < paletteTiles.length) {
      brush = paletteTiles[i]
      if (tool === 'pick') tool = 'pen'
    }
  }

  const changedCells = $derived(
    painted && layout ? painted.rows.reduce((n, row, y) => n + row.filter((m, x) => m !== layout!.rows[y]?.[x]).length, 0) : 0,
  )
</script>

<svelte:window onmouseup={onUp} />

<div class="editor">
  <RecordList records={maps} {selected} onselect={(i) => load(i)} secondary={(m) => m.name === m.id} secondaryLabel={t('maps.otherMaps')} problemIds={new Set(problems.filter((p) => p.kind === 'maps').map((p) => p.id))}>
    {#snippet suffix(m: MapInfo)}
      {#if list.records[0]?.layouts?.[m.id]}<span class="edited" title={t('maps.edited')}> ✎</span>{/if}
      <span class="muted id">{m.width}×{m.height}</span>
    {/snippet}
  </RecordList>

  {#if info}
    <div class="detail">
      <section class="panel">
        <h2>{info.name} <span class="muted id">{info.id} · {info.width}×{info.height}</span></h2>
        <p class="muted small">
          {t('maps.usedBy')}
          {#each info.chapters as c, k (c)}{#if k}, {/if}<Mention kind="chapters" id={String(c)}>{chapterTitle(c)}</Mention>{/each}
          {#if info.chapters.length > 1}<span class="warn"> — {t('maps.shared', { n: info.chapters.length })}</span>{/if}
        </p>
        <p class="muted small">{t('maps.hint')}</p>
        {#if painted}
          <p class="small">
            <span class="edited">✎</span> {t('maps.changed', { n: changedCells })}
            <button class="link" onclick={reset}>{t('maps.reset')}</button>
          </p>
        {/if}
        {#each mapProblems as pr, i (i)}<p class="bad small">{t(`problem.${pr.code}`, pr.params)}</p>{/each}
      </section>

      <div class="layout">
        <section class="panel map-panel">
          <div class="toolbar">
            <div class="tools" role="radiogroup" aria-label={t('maps.tool')}>
              {#each TOOLS as tl (tl.id)}
                <button role="radio" aria-checked={tool === tl.id} class:active={tool === tl.id} title={t(`maps.tool.${tl.id}Hint`)} onclick={() => (tool = tl.id)}>
                  <span aria-hidden="true">{tl.icon}</span> {t(`maps.tool.${tl.id}`)}
                </button>
              {/each}
            </div>
            <label class="check"><input type="checkbox" bind:checked={showGrid} /> {t('maps.grid')}</label>
            <label class="check"><input type="checkbox" bind:checked={showTerrain} /> {t('maps.terrains')}</label>
            <label class="check">
              {t('maps.zoom')}
              <select bind:value={zoom}>
                {#each [1, 2, 3] as z (z)}<option value={z}>×{z}</option>{/each}
              </select>
            </label>
          </div>
          {#if layout && sheet}
            <div class="map-scroll">
              <canvas
                bind:this={mapCanvas}
                class:picking={tool === 'pick'}
                width={width * cell}
                height={height * cell}
                onmousedown={onDown}
                onmousemove={onMove}
                onmouseleave={() => (hover = null)}
                oncontextmenu={(e) => e.preventDefault()}
              ></canvas>
            </div>
            <p class="muted small status">
              {#if hover}
                {hover.x}, {hover.y} · {terrainName(layout.terrains[rows[hover.y][hover.x]])} <span class="tiny">#{rows[hover.y][hover.x]}</span>
              {:else}
                {t('maps.mouseHint')}
              {/if}
            </p>
            {#if showTerrain}
              <div class="legend">
                {#each mapTerrains as id (id)}
                  <button class="chip" class:active={terrainFilter === id} title={t('maps.filterTerrain')} onclick={() => (terrainFilter = terrainFilter === id ? null : id)}>
                    <span class="swatch" style="background: {terrainColor(id, 0.9)}"></span>{terrainName(id)}
                  </button>
                {/each}
              </div>
            {/if}
          {:else}
            <p class="muted">…</p>
          {/if}
        </section>

        <section class="panel palette-panel">
          <h3>{t('maps.palette')}</h3>
          {#if layout && sheet}
            <div class="brush">
              <canvas width={PALETTE_CELL} height={PALETTE_CELL} use:drawBrush={{ m: brush, sheet, layout }}></canvas>
              <div>
                <div>{terrainName(layout.terrains[brush])}</div>
                <div class="muted tiny">
                  {t('maps.tileNumber', { n: brush })}{#if layout.terrainNames[layout.terrains[brush]]} · {t('maps.gameName', { name: layout.terrainNames[layout.terrains[brush]] })}{/if}
                </div>
              </div>
            </div>
            <label>
              <span>{t('maps.terrainFilter')}</span>
              <select value={terrainFilter ?? ''} onchange={(e) => { const v = (e.target as HTMLSelectElement).value; terrainFilter = v === '' ? null : Number(v) }}>
                <option value="">{t('maps.allTerrains')}</option>
                {#each allTerrains as id (id)}<option value={id}>{terrainName(id)}</option>{/each}
              </select>
            </label>
            <div class="palette-scroll">
              <canvas
                bind:this={paletteCanvas}
                width={PALETTE_COLUMNS * PALETTE_CELL}
                height={Math.max(1, Math.ceil(paletteTiles.length / PALETTE_COLUMNS)) * PALETTE_CELL}
                onclick={pickFromPalette}
              ></canvas>
            </div>
            <p class="muted tiny">{t('maps.paletteHint')}</p>
          {/if}
        </section>
      </div>
    </div>
  {/if}
</div>

<style>
  .editor { display: grid; grid-template-columns: 260px 1fr; gap: 1rem; align-items: start; }
  .detail { display: flex; flex-direction: column; gap: 1rem; min-width: 0; }
  .id { font-size: 0.75rem; margin-left: 0.3rem; }
  .small { font-size: 0.8rem; }
  .tiny { font-size: 0.72rem; }
  .warn { color: var(--warn); }
  .bad { color: var(--bad); }
  .edited { color: var(--accent); margin-left: 0.25rem; }
  .link { border: none; background: none; padding: 0; color: var(--accent); font: inherit; margin-left: 0.4rem; }
  .layout { display: grid; grid-template-columns: minmax(0, 1fr) 290px; gap: 1rem; align-items: start; }
  .map-panel { display: flex; flex-direction: column; gap: 0.5rem; min-width: 0; padding: 0.5rem; }
  .toolbar { display: flex; flex-wrap: wrap; align-items: center; gap: 0.5rem 1rem; }
  .tools { display: flex; gap: 0.25rem; }
  .tools button { font-size: 0.85rem; padding: 0.25rem 0.55rem; }
  .tools button.active { background: var(--accent-soft); border-color: var(--accent); font-weight: 600; }
  .check { flex-direction: row; align-items: center; gap: 0.35rem; font-size: 0.85rem; color: var(--text); }
  .map-scroll { overflow: auto; max-height: calc(100vh - 300px); }
  .map-scroll canvas { display: block; cursor: crosshair; image-rendering: pixelated; }
  .map-scroll canvas.picking { cursor: copy; }
  .status { margin: 0; min-height: 1.2em; }
  .legend { display: flex; flex-wrap: wrap; gap: 0.3rem; }
  .chip { display: inline-flex; align-items: center; gap: 0.3rem; font-size: 0.78rem; padding: 0.1rem 0.45rem; border-radius: 999px; }
  .chip.active { border-color: var(--accent); background: var(--accent-soft); }
  .swatch { width: 0.75rem; height: 0.75rem; border-radius: 3px; display: inline-block; }
  .palette-panel { display: flex; flex-direction: column; gap: 0.5rem; }
  .palette-panel h3 { margin: 0; }
  .brush { display: flex; align-items: center; gap: 0.6rem; }
  .brush canvas { border: 1px solid var(--border); image-rendering: pixelated; }
  .palette-scroll { overflow-y: auto; max-height: calc(100vh - 420px); border: 1px solid var(--border); border-radius: 6px; width: fit-content; }
  .palette-scroll canvas { display: block; cursor: pointer; image-rendering: pixelated; }
  @media (max-width: 1000px) { .layout { grid-template-columns: 1fr; } }
  @media (max-width: 800px) { .editor { grid-template-columns: 1fr; } }
</style>
