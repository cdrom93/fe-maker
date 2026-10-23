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
  import { api, ApiError, itemIconUrl, mapTilesetUrl, portraitUrl } from '../lib/api'
  import type { EditableList } from '../lib/history.svelte'
  import { problemText, t } from '../lib/i18n.svelte'
  import { followFocus, useNavigator } from '../lib/navigation.svelte'
  import type { ChapterInfo, Item, MapChange, MapInfo, MapObject, MapObjectKind, MapObjects, MapObjectSettings, MapsData, Problem, TilesetEdits } from '../lib/types'
  import Mention from './Mention.svelte'
  import NumberField from './NumberField.svelte'
  import RecordList from './RecordList.svelte'

  let { list, items, problems }: { list: EditableList<MapsData>; items: Item[]; problems: Problem[] } = $props()

  type Tool = 'pen' | 'rect' | 'fill' | 'pick' | 'select'
  type Cell = { x: number; y: number }
  const TOOLS: { id: Tool; icon: string }[] = [
    { id: 'pen', icon: '✏️' },
    { id: 'rect', icon: '▭' },
    { id: 'fill', icon: '🪣' },
    { id: 'pick', icon: '💧' },
    { id: 'select', icon: '👆' },
  ]
  // Objects the engine recognizes by their terrain (server: mapobjects.py).
  const OBJECT_ICONS: Record<MapObjectKind, string> = { village: '🏘️', house: '🏠', armory: '⚔️', vendor: '🧪', chest: '🎁', door: '🚪', wall: '🧱', snag: '🪵' }
  const EVENT_KINDS: MapObjectKind[] = ['village', 'house', 'armory', 'vendor', 'chest', 'door']
  const SHOP_KINDS: MapObjectKind[] = ['armory', 'vendor']
  const MAX_SHOP_ITEMS = 20
  const ALL_TERRAIN_IDS = Array.from({ length: 0x41 }, (_, i) => i)
  const CHANGE_KINDS: MapObjectKind[] = ['village', 'chest', 'door', 'wall', 'snag']
  const GOLD = '__gold'
  // Mirrors and turns of the brush (server: tileedit.py).
  const TRANSFORMS = [
    { op: 'h', icon: '↔' },
    { op: 'v', icon: '↕' },
    { op: '180', icon: '⟲⟲' },
    { op: 'ccw', icon: '⟲' },
    { op: 'cw', icon: '⟳' },
  ]
  const MAX_GOLD = 65535
  const PALETTE_COLUMNS = 8
  const PALETTE_CELL = 32
  const TILE = 16 // metatile size in the game
  // Engine limits (server/fe_maker/validation.py, map_size_problem): one screen at least.
  const MIN_WIDTH = 15
  const MIN_HEIGHT = 10
  const MAX_SIDE = 60
  const MAX_CHANGE_ID = 127

  let maps = $state<(MapInfo & { name: string })[]>([])
  let chapters = $state<ChapterInfo[]>([])
  let selected = $state(0)
  let layout = $state<MapLayout | null>(null)
  let sheet = $state<HTMLImageElement | null>(null)
  // The map's tileset as in the game; `layout` and `sheet` add the project's mirrored and turned tiles.
  let baseLayout = $state<MapLayout | null>(null)
  let baseSheet = $state<HTMLImageElement | null>(null)
  let transformError = $state('')
  let tool = $state<Tool>('pen')
  /** What the tools paint: one tile, or a block taken from the palette or the map (right-drag). */
  let stamp = $state<number[][]>([[0]])
  const brush = $derived(stamp[0][0])
  const stampW = $derived(stamp[0].length)
  const stampH = $derived(stamp.length)
  /** Palette: one copy of each tile (by terrain), or the whole tileset sheet as in the game. */
  let paletteMode = $state<'unique' | 'sheet'>('unique')
  // Palette rectangle being dragged, and the one the current block was taken from (highlighted).
  let paletteDrag = $state<{ a: Cell; b: Cell } | null>(null)
  let palettePicked = $state<{ a: Cell; b: Cell } | null>(null)
  // Map rectangle being copied with the right button.
  let copyStart = $state<Cell | null>(null)
  let zoom = $state(2)
  let showGrid = $state(true)
  let showTerrain = $state(false)
  let showChanges = $state(true)
  let showObjects = $state(true)
  /** Show the map as it is once every object was used (open chests, closed villages...). */
  let preview = $state(false)
  let objectsInfo = $state<MapObjects | null>(null)
  /** "x,y" of the selected object */
  let selectedObject = $state<string | null>(null)
  let terrainFilter = $state<number | null>(null)
  let hover = $state<Cell | null>(null)
  /** Index of the map change being edited; null = the map itself. */
  let layer = $state<number | null>(null)
  // Cells being painted (one stroke or rectangle) in the edited grid (map or change);
  // saved as one undo step when the mouse is released.
  let draft = $state<number[][] | null>(null)
  let rectStart = $state<Cell | null>(null)
  let mapCanvas = $state<HTMLCanvasElement>()
  let paletteCanvas = $state<HTMLCanvasElement>()

  const info = $derived(maps[selected])
  const painted = $derived(info ? list.records[0]?.layouts?.[info.id] : undefined)
  const savedRows = $derived(painted?.rows ?? layout?.rows ?? [])
  const changes = $derived<MapChange[] | null>((info && list.records[0]?.changes?.[info.id]) ?? layout?.changes ?? null)
  const change = $derived(layer !== null ? changes?.[layer] : undefined)
  // What is shown: the map (being painted or not) and, when a change is edited, its tiles over it.
  const rows = $derived(!change && draft ? draft : savedRows)
  const changeRows = $derived(change ? (draft ?? change.rows) : null)
  const width = $derived(rows[0]?.length ?? 0)
  const height = $derived(rows.length)
  const cell = $derived(TILE * zoom)
  const mapProblems = $derived(info ? problems.filter((p) => p.kind === 'maps' && p.id === info.id) : [])
  // Units and seize tiles of the chapters using this map (outside the map, impassable terrain).
  const chapterProblems = $derived(info ? problems.filter((p) => p.kind === 'chapters' && p.params.map === info.id) : [])
  const sizeProblem = $derived(mapProblems.find((p) => p.field === 'size'))
  const chapterTitle = (i: number) => chapters[i]?.title || chapters[i]?.id || String(i)

  const tilesetEdits = $derived<TilesetEdits | undefined>(baseLayout ? list.records[0]?.tilesets?.[baseLayout.tileset] : undefined)
  const objectSettings = $derived<Record<string, MapObjectSettings>>((info && list.records[0]?.objects?.[info.id]) ?? {})
  const objects = $derived(objectsInfo?.objects ?? [])
  const keyOf = (o: { x: number; y: number }) => `${o.x},${o.y}`
  const selectedObj = $derived(objects.find((o) => keyOf(o) === selectedObject) ?? null)
  const itemById = $derived(new Map(items.map((i) => [i.id, i])))
  // Tiles of the used objects (preview): the change each object gets.
  const previewTiles = $derived.by(() => {
    const out = new Map<string, number>()
    if (!preview) return out
    for (const o of objects) {
      const c = o.auto ?? (o.change !== null ? changes?.find((k) => k.id === o.change) : undefined)
      c?.rows.forEach((row, j) => row.forEach((m, i) => out.set(`${c.x + i},${c.y + j}`, m)))
    }
    return out
  })

  /** Tile shown at a map cell (the edited change's tile inside its rectangle). */
  function shownTile(x: number, y: number): number {
    if (change && changeRows && x >= change.x && y >= change.y && x < change.x + change.w && y < change.y + change.h) {
      return changeRows[y - change.y][x - change.x]
    }
    if (preview && !change) {
      const used = previewTiles.get(`${x},${y}`)
      if (used !== undefined) return used
    }
    return rows[y]?.[x] ?? 0
  }

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
  const palColumns = $derived(paletteMode === 'sheet' && layout ? layout.columns : PALETTE_COLUMNS)
  const palCell = $derived(paletteMode === 'sheet' ? TILE : PALETTE_CELL)
  const palTiles = $derived(paletteMode === 'sheet' && layout ? [...layout.terrains.keys()] : paletteTiles)
  const allTerrains = $derived(layout ? [...new Set(layout.terrains.filter((_, m) => !layout!.duplicates[m]))].sort((a, b) => a - b) : [])

  const nav = useNavigator()
  followFocus('maps', nav, () => maps.map((m) => m.id), (i) => load(i))

  // Tiles added to the tileset (mirrors, turns): sheet and terrains drawn again by the server.
  let tilesetRequest = 0
  $effect(() => {
    const base = baseLayout
    const edits = tilesetEdits ? JSON.parse(JSON.stringify(tilesetEdits)) : null
    if (!info || !base) return
    const id = info.id
    const n = ++tilesetRequest
    if (!edits) {
      layout = base
      sheet = baseSheet
      return
    }
    api.mapTileset(id, edits).then(async (r) => {
      const img = await loadImage(r.sheet)
      if (n !== tilesetRequest || maps[selected]?.id !== id) return
      layout = { ...base, terrains: r.terrains, duplicates: r.duplicates }
      sheet = img
    }).catch(() => {})
  })

  /** Mirror or turn the brush, or give it another terrain; new tiles are added to the tileset (undo removes them). */
  async function transform(op: string, terrain = 0) {
    if (!info || !baseLayout) return
    const id = info.id
    const tileset = baseLayout.tileset
    transformError = ''
    try {
      const r = await api.transformTiles(id, {
        rows: $state.snapshot(stamp) as number[][], op, terrain, edits: tilesetEdits ? (JSON.parse(JSON.stringify(tilesetEdits)) as TilesetEdits) : null,
        painted: JSON.parse(JSON.stringify(list.records[0]?.layouts ?? {})),
      })
      if (maps[selected]?.id !== id) return
      if (JSON.stringify(r.edits) !== JSON.stringify(tilesetEdits ?? { metatiles: {}, tiles: {} })) {
        list.update(0, (d) => {
          d.tilesets ??= {}
          d.tilesets[tileset] = r.edits
        })
      }
      stamp = r.rows
      palettePicked = null
    } catch (e) {
      transformError = e instanceof ApiError ? t(`maps.transformError.${e.detail}`) : String(e)
    }
  }

  // Objects of the map and what the build does for them, asked again after each edit.
  let objectsRequest = 0
  $effect(() => {
    if (!info || !layout) return
    const id = info.id
    const body = JSON.parse(JSON.stringify({ rows: savedRows, changes: list.records[0]?.changes?.[id] ?? null, objects: objectSettings, tileset: tilesetEdits ?? null }))
    const timer = setTimeout(async () => {
      const n = ++objectsRequest
      try {
        const result = await api.mapObjects(id, body)
        if (n === objectsRequest && maps[selected]?.id === id) objectsInfo = result
      } catch {
        // the map is being changed: the next edit asks again
      }
    }, 150)
    return () => clearTimeout(timer)
  })

  $effect(() => {
    appContext.detail = info ? `${info.id}${change ? ` · ${t('maps.change', { id: change.id })}` : ''}${hover ? ` · ${hover.x}, ${hover.y}` : ''}` : ''
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
    layer = null
    terrainFilter = null
    objectsInfo = null
    selectedObject = null
    transformError = ''
    const id = maps[index].id
    const [data, img] = await Promise.all([api.map(id), loadImage(mapTilesetUrl(id))])
    if (maps[selected]?.id !== id) return
    baseSheet = img
    baseLayout = data
    if (!list.records[0]?.tilesets?.[data.tileset]) {
      layout = data
      sheet = img
    }
    // Start with the map's most common tile (usually its ground).
    const count = new Map<number, number>()
    for (const row of data.rows) for (const c of row) count.set(c, (count.get(c) ?? 0) + 1)
    setBrush([...count.entries()].sort((a, b) => b[1] - a[1])[0]?.[0] ?? 0)
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
    for (let y = 0; y < height; y++) for (let x = 0; x < width; x++) drawTile(ctx, shownTile(x, y), x * cell, y * cell, cell)
    if (showTerrain) {
      for (let y = 0; y < height; y++) {
        for (let x = 0; x < width; x++) {
          ctx.fillStyle = terrainColor(layout.terrains[shownTile(x, y)])
          ctx.fillRect(x * cell, y * cell, cell, cell)
        }
      }
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
    // Map changes: the edited one stands out, the rest of the map is dimmed.
    if (change) {
      ctx.fillStyle = 'rgb(0 0 0 / 0.45)'
      ctx.fillRect(0, 0, width * cell, change.y * cell)
      ctx.fillRect(0, (change.y + change.h) * cell, width * cell, (height - change.y - change.h) * cell)
      ctx.fillRect(0, change.y * cell, change.x * cell, change.h * cell)
      ctx.fillRect((change.x + change.w) * cell, change.y * cell, (width - change.x - change.w) * cell, change.h * cell)
    }
    if (showChanges || change) {
      ctx.font = `bold ${Math.max(10, cell / 2.6)}px sans-serif`
      ctx.textBaseline = 'top'
      changes?.forEach((c, i) => {
        if (layer !== null && i !== layer) return
        ctx.strokeStyle = i === layer ? '#f1c40f' : 'rgb(241 196 15 / 0.8)'
        ctx.lineWidth = i === layer ? 3 : 2
        ctx.setLineDash(i === layer ? [] : [5, 3])
        ctx.strokeRect(c.x * cell + 1.5, c.y * cell + 1.5, c.w * cell - 3, c.h * cell - 3)
        ctx.setLineDash([])
        ctx.fillStyle = 'rgb(0 0 0 / 0.65)'
        ctx.fillRect(c.x * cell + 2, c.y * cell + 2, cell / 1.6, cell / 2.2)
        ctx.fillStyle = '#f1c40f'
        ctx.fillText(String(c.id), c.x * cell + 4, c.y * cell + 3)
      })
    }
    // Objects: an icon on each one, the change FE Maker adds for new ones.
    if (showObjects && !change) {
      const size = Math.max(11, Math.round(cell * 0.5))
      ctx.font = `${size - 2}px sans-serif`
      ctx.textBaseline = 'middle'
      ctx.textAlign = 'center'
      for (const o of objects) {
        const selectedHere = keyOf(o) === selectedObject
        if (o.auto && (showChanges || selectedHere)) {
          ctx.strokeStyle = '#1abc9c'
          ctx.lineWidth = 2
          ctx.setLineDash([4, 3])
          ctx.strokeRect(o.auto.x * cell + 1.5, o.auto.y * cell + 1.5, o.auto.w * cell - 3, o.auto.h * cell - 3)
          ctx.setLineDash([])
        }
        if (selectedHere) {
          ctx.strokeStyle = '#fff'
          ctx.lineWidth = 3
          for (const [x, y] of o.cells) ctx.strokeRect(x * cell + 1.5, y * cell + 1.5, cell - 3, cell - 3)
        }
        const bx = o.x * cell + cell - size
        const by = o.y * cell
        ctx.fillStyle = o.noAfter ? 'rgb(231 76 60 / 0.9)' : o.new ? 'rgb(22 160 133 / 0.9)' : 'rgb(0 0 0 / 0.6)'
        ctx.fillRect(bx, by, size, size)
        ctx.fillStyle = '#fff'
        ctx.fillText(OBJECT_ICONS[o.kind], bx + size / 2, by + size / 2 + 1)
      }
      ctx.textAlign = 'start'
    }
    // Units with a problem (outside the map, impassable terrain).
    ctx.strokeStyle = '#e74c3c'
    ctx.lineWidth = 3
    for (const p of chapterProblems) {
      if (typeof p.params.x === 'number' && typeof p.params.y === 'number') ctx.strokeRect(p.params.x * cell + 2.5, p.params.y * cell + 2.5, cell - 5, cell - 5)
    }
    // Preview under the mouse: the block, the rectangle being drawn, or the area being copied.
    let area = hover ? { x0: hover.x, y0: hover.y, x1: hover.x, y1: hover.y } : null
    if (copyStart && hover) {
      area = rectOf(copyStart, hover)
    } else if (rectStart && hover) {
      area = rectOf(rectStart, hover)
      const origin = { x: area.x0, y: area.y0 }
      for (let y = area.y0; y <= area.y1; y++) for (let x = area.x0; x <= area.x1; x++) if (editable({ x, y })) drawTile(ctx, stampTile(x, y, origin), x * cell, y * cell, cell)
    } else if (hover && (tool === 'pen' || tool === 'rect')) {
      area = { x0: hover.x, y0: hover.y, x1: Math.min(width, hover.x + stampW) - 1, y1: Math.min(height, hover.y + stampH) - 1 }
      ctx.globalAlpha = 0.6
      for (let y = area.y0; y <= area.y1; y++) for (let x = area.x0; x <= area.x1; x++) if (editable({ x, y })) drawTile(ctx, stampTile(x, y, hover), x * cell, y * cell, cell)
      ctx.globalAlpha = 1
    }
    if (area) {
      ctx.strokeStyle = '#fff'
      ctx.lineWidth = 2
      ctx.setLineDash(copyStart ? [6, 4] : [])
      ctx.strokeRect(area.x0 * cell + 1, area.y0 * cell + 1, (area.x1 - area.x0 + 1) * cell - 2, (area.y1 - area.y0 + 1) * cell - 2)
      ctx.setLineDash([])
    }
  })

  // Palette canvas
  $effect(() => {
    const ctx = paletteCanvas?.getContext('2d')
    if (!ctx || !layout || !sheet) return
    ctx.imageSmoothingEnabled = false
    ctx.clearRect(0, 0, paletteCanvas!.width, paletteCanvas!.height)
    palTiles.forEach((m, i) => {
      const x = (i % palColumns) * palCell
      const y = Math.floor(i / palColumns) * palCell
      drawTile(ctx, m, x, y, palCell)
      // The whole sheet keeps every tile in place: other terrains are dimmed instead of hidden.
      if (paletteMode === 'sheet' && terrainFilter !== null && layout!.terrains[m] !== terrainFilter) {
        ctx.fillStyle = 'rgb(0 0 0 / 0.6)'
        ctx.fillRect(x, y, palCell, palCell)
      }
    })
    const box = paletteDrag ?? palettePicked
    const one = stampW === 1 && stampH === 1 ? palTiles.indexOf(brush) : -1
    const r = box ? rectOf(box.a, box.b) : one >= 0 ? { x0: one % palColumns, y0: Math.floor(one / palColumns), x1: one % palColumns, y1: Math.floor(one / palColumns) } : null
    if (r) {
      const [x, y, w, h] = [r.x0 * palCell, r.y0 * palCell, (r.x1 - r.x0 + 1) * palCell, (r.y1 - r.y0 + 1) * palCell]
      ctx.strokeStyle = '#fff'
      ctx.lineWidth = 3
      ctx.strokeRect(x + 1.5, y + 1.5, w - 3, h - 3)
      ctx.strokeStyle = '#000'
      ctx.lineWidth = 1
      ctx.strokeRect(x + 0.5, y + 0.5, w - 1, h - 1)
    }
  })

  function cellAt(e: MouseEvent): Cell | null {
    if (!mapCanvas) return null
    const r = mapCanvas.getBoundingClientRect()
    const x = Math.floor((e.clientX - r.left) / cell)
    const y = Math.floor((e.clientY - r.top) / cell)
    return x >= 0 && y >= 0 && x < width && y < height ? { x, y } : null
  }

  function rectOf(a: Cell, b: Cell) {
    return { x0: Math.min(a.x, b.x), y0: Math.min(a.y, b.y), x1: Math.max(a.x, b.x), y1: Math.max(a.y, b.y) }
  }

  /** Can this map cell be painted? Editing a change: only inside its rectangle. */
  const editable = (p: Cell) => !change || (p.x >= change.x && p.y >= change.y && p.x < change.x + change.w && p.y < change.y + change.h)
  /** Map cell -> cell of the edited grid. */
  const toGrid = (p: Cell): Cell => (change ? { x: p.x - change.x, y: p.y - change.y } : p)
  const copyGrid = () => (change ? change.rows : rows).map((r) => [...r])

  const setBrush = (m: number) => {
    stamp = [[m]]
    palettePicked = null
  }
  const mod = (a: number, n: number) => ((a % n) + n) % n
  /** Tile of the block at a map cell, the pattern repeating from `origin`. */
  const stampTile = (x: number, y: number, origin: Cell) => stamp[mod(y - origin.y, stampH)][mod(x - origin.x, stampW)]

  function setCell(grid: number[][], c: Cell, m: number) {
    if (c.x < 0 || c.y < 0 || c.x >= width || c.y >= height || !editable(c)) return
    const g = toGrid(c)
    if (grid[g.y][g.x] !== m) grid[g.y][g.x] = m
  }

  let last: Cell | null = null
  let anchor: Cell = { x: 0, y: 0 }

  /** Paint the block at a cell, and between it and the previous one (the mouse can skip cells).
   *  Blocks are laid side by side from where the stroke started. */
  function paint(p: Cell) {
    if (!draft) return
    const from = last ?? p
    const steps = Math.max(Math.abs(p.x - from.x), Math.abs(p.y - from.y))
    for (let k = 0; k <= steps; k++) {
      const c = { x: Math.round(from.x + ((p.x - from.x) * k) / (steps || 1)), y: Math.round(from.y + ((p.y - from.y) * k) / (steps || 1)) }
      const ox = anchor.x + Math.floor((c.x - anchor.x) / stampW) * stampW
      const oy = anchor.y + Math.floor((c.y - anchor.y) / stampH) * stampH
      for (let j = 0; j < stampH; j++) for (let i = 0; i < stampW; i++) setCell(draft, { x: ox + i, y: oy + j }, stamp[j][i])
    }
    last = p
  }

  function floodFill(start: Cell) {
    if (!editable(start)) return
    const next = copyGrid()
    const s = toGrid(start)
    const target = next[s.y][s.x]
    if (stampW === 1 && stampH === 1 && target === brush) return
    const offset = change ? { x: change.x, y: change.y } : { x: 0, y: 0 }
    const seen = new Set<string>()
    const stack = [s]
    while (stack.length) {
      const { x, y } = stack.pop()!
      const key = `${x},${y}`
      if (seen.has(key) || y < 0 || y >= next.length || x < 0 || x >= next[y].length || next[y][x] !== target) continue
      seen.add(key)
      stack.push({ x: x + 1, y }, { x: x - 1, y }, { x, y: y + 1 }, { x, y: y - 1 })
    }
    for (const key of seen) {
      const [x, y] = key.split(',').map(Number)
      next[y][x] = stampTile(x + offset.x, y + offset.y, start)
    }
    commit(next)
  }

  function onDown(e: MouseEvent) {
    const p = cellAt(e)
    if (!p) return
    e.preventDefault()
    // Right button: take the tile under the mouse, or a block by dragging (whatever the tool).
    if (e.button === 2) {
      copyStart = p
      return
    }
    if (tool === 'select') {
      const found = objects.find((o) => o.cells.some(([x, y]) => x === p.x && y === p.y))
      selectedObject = found ? keyOf(found) : null
      return
    }
    if (e.altKey || tool === 'pick') {
      setBrush(shownTile(p.x, p.y))
      return
    }
    if (e.button !== 0) return
    if (tool === 'fill') return floodFill(p)
    draft = copyGrid()
    last = null
    anchor = p
    if (tool === 'rect') rectStart = p
    else paint(p)
  }

  function onMove(e: MouseEvent) {
    hover = cellAt(e)
    if (hover && draft && tool === 'pen' && e.buttons & 1) paint(hover)
  }

  function onUp() {
    if (paletteDrag) return pickFromPalette()
    if (copyStart) {
      const a = rectOf(copyStart, hover ?? copyStart)
      stamp = Array.from({ length: a.y1 - a.y0 + 1 }, (_, j) => Array.from({ length: a.x1 - a.x0 + 1 }, (_, i) => shownTile(a.x0 + i, a.y0 + j)))
      palettePicked = null
      copyStart = null
      if (tool === 'pick' || tool === 'fill') tool = 'pen'
      return
    }
    if (!draft) return
    if (rectStart && hover) {
      const a = rectOf(rectStart, hover)
      const origin = { x: a.x0, y: a.y0 }
      for (let y = a.y0; y <= a.y1; y++) for (let x = a.x0; x <= a.x1; x++) setCell(draft, { x, y }, stampTile(x, y, origin))
    }
    const result = $state.snapshot(draft) as number[][]
    draft = null
    rectStart = null
    commit(result)
  }

  /** Save the painted grid (map or edited change) as one undo step. */
  function commit(next: number[][]) {
    if (layer !== null && changes) {
      const i = layer
      saveChanges(changes.map((c, k) => (k === i ? { ...c, rows: next } : c)))
    } else {
      saveRows(next)
    }
  }

  /** A map painted back to the original is no longer stored. */
  function saveRows(next: number[][]) {
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

  function saveChanges(next: MapChange[]) {
    if (!info || !layout) return
    const id = info.id
    const same = JSON.stringify(next) === JSON.stringify(layout.changes)
    list.update(0, (d) => {
      d.changes ??= {}
      if (same) delete d.changes[id]
      else d.changes[id] = $state.snapshot(next) as MapChange[]
    })
  }

  function reset() {
    if (!info) return
    const id = info.id
    layer = null
    list.update(0, (d) => {
      if (d.layouts) delete d.layouts[id]
      if (d.changes) delete d.changes[id]
      if (d.objects) delete d.objects[id]
    })
  }

  /** Does the build give the object its event and change? */
  function isActive(o: MapObject): boolean {
    const own = objectSettings[keyOf(o)]
    if (own) return !own.off
    return o.new || !!o.event || !EVENT_KINDS.includes(o.kind)
  }

  /** What the object holds or says: the project's settings, else its original event, else the defaults. */
  function settingsOf(o: MapObject): MapObjectSettings {
    const own = objectSettings[keyOf(o)]
    if (own) return own
    if (o.event?.gold) return { gold: o.event.gold }
    if (o.event?.item) return { item: o.event.item }
    if (o.event?.items) return { items: o.event.items, secret: o.event.macro === 'SecretShop' }
    return objectsInfo?.defaults[o.kind] ?? {}
  }

  function setObject(o: MapObject, patch: Partial<MapObjectSettings>) {
    if (!info) return
    const id = info.id
    const key = keyOf(o)
    const base = objectSettings[key] ?? { ...(objectsInfo?.defaults[o.kind] ?? {}), ...(o.event?.gold || o.event?.item || o.event?.items ? settingsOf(o) : {}) }
    list.update(0, (d) => {
      d.objects ??= {}
      d.objects[id] ??= {}
      d.objects[id][key] = JSON.parse(JSON.stringify({ ...base, ...patch }))
    })
  }

  function resetObject(o: MapObject) {
    if (!info) return
    const id = info.id
    const key = keyOf(o)
    list.update(0, (d) => {
      if (!d.objects?.[id]) return
      delete d.objects[id][key]
      if (!Object.keys(d.objects[id]).length) delete d.objects[id]
    })
  }

  /** One line on what happens with the object in the game. */
  function objectStatus(o: MapObject): { text: string; cls: string } {
    const own = objectSettings[keyOf(o)]
    if (own?.off) return { text: t('maps.obj.off'), cls: 'muted' }
    if (o.noAfter) return { text: t('maps.obj.noAfter'), cls: 'warn' }
    if (o.new) {
      if (o.auto) return { text: t('maps.obj.auto', { id: o.auto.id }), cls: 'good' }
      if (o.change !== null) return { text: t('maps.obj.usesChange', { id: o.change }), cls: 'good' }
      if (CHANGE_KINDS.includes(o.kind)) return { text: t('maps.obj.noChange'), cls: 'warn' }
      return { text: t('maps.obj.new'), cls: 'good' }
    }
    if (own) return { text: t('maps.obj.replaced'), cls: 'good' }
    if (EVENT_KINDS.includes(o.kind) && !o.event) return { text: t('maps.obj.decor'), cls: 'muted' }
    return { text: t('maps.obj.original'), cls: 'muted' }
  }

  /** What a chest or village gives, in a few words. */
  function giftText(st: MapObjectSettings): string {
    if (st.gold) return t('maps.obj.goldAmountShort', { n: st.gold })
    if (st.item) return itemById.get(st.item)?.name ?? st.item
    if (st.items) return t('maps.obj.shopCount', { n: st.items.length })
    return ''
  }

  function setShopItem(o: MapObject, current: string[], index: number, item: string) {
    const next = [...current]
    if (item) next[index] = item
    else next.splice(index, 1)
    setObject(o, { items: next.slice(0, MAX_SHOP_ITEMS) })
  }

  /** New size: rows and columns are added or removed on the right and at the bottom; new cells get the selected tile. */
  function resize(w: number, h: number) {
    if (w === width && h === height) return
    saveRows(Array.from({ length: h }, (_, y) => Array.from({ length: w }, (_, x) => rows[y]?.[x] ?? brush)))
  }

  /** Map tiles under a rectangle (what a new or enlarged change starts from). */
  const tilesUnder = (x: number, y: number, w: number, h: number) =>
    Array.from({ length: h }, (_, j) => Array.from({ length: w }, (_, i) => rows[y + j]?.[x + i] ?? brush))

  function addChange() {
    if (!changes) return
    const id = changes.length ? Math.max(...changes.map((c) => c.id)) + 1 : 0
    const w = 2
    const h = 2
    const x = hover?.x ?? Math.max(0, Math.floor(width / 2) - 1)
    const y = hover?.y ?? Math.max(0, Math.floor(height / 2) - 1)
    const fresh: MapChange = { id, x: Math.min(x, width - w), y: Math.min(y, height - h), w, h, rows: tilesUnder(x, y, w, h) }
    saveChanges([...changes, fresh])
    layer = changes.length
    showChanges = true
  }

  function editChange(field: 'id' | 'x' | 'y' | 'w' | 'h', value: number) {
    if (layer === null || !changes || !change) return
    const c = { ...change, rows: change.rows.map((r) => [...r]) }
    c[field] = value
    if (field === 'w' || field === 'h') {
      // Keep the tiles already set; new cells start as the map under them.
      const under = tilesUnder(c.x, c.y, c.w, c.h)
      c.rows = under.map((row, j) => row.map((m, i) => change.rows[j]?.[i] ?? m))
    }
    const i = layer
    saveChanges(changes.map((k, n) => (n === i ? c : k)))
  }

  function removeChange() {
    if (layer === null || !changes) return
    const i = layer
    layer = null
    saveChanges(changes.filter((_, n) => n !== i))
  }

  function paletteCell(e: MouseEvent): Cell {
    const r = paletteCanvas!.getBoundingClientRect()
    const rowsCount = Math.ceil(palTiles.length / palColumns)
    return {
      x: Math.max(0, Math.min(palColumns - 1, Math.floor((e.clientX - r.left) / palCell))),
      y: Math.max(0, Math.min(rowsCount - 1, Math.floor((e.clientY - r.top) / palCell))),
    }
  }

  /** Mouse released on the palette: the dragged rectangle becomes the block (one tile for a click). */
  function pickFromPalette() {
    if (!paletteDrag) return
    const a = rectOf(paletteDrag.a, paletteDrag.b)
    const tileAt = (x: number, y: number) => palTiles[y * palColumns + x] ?? palTiles[palTiles.length - 1]
    stamp = Array.from({ length: a.y1 - a.y0 + 1 }, (_, j) => Array.from({ length: a.x1 - a.x0 + 1 }, (_, i) => tileAt(a.x0 + i, a.y0 + j)))
    palettePicked = stampW === 1 && stampH === 1 ? null : paletteDrag
    paletteDrag = null
    if (tool === 'pick') tool = 'pen'
  }

  const changedCells = $derived(
    painted && layout ? painted.rows.reduce((n, row, y) => n + row.filter((m, x) => m !== layout!.rows[y]?.[x]).length, 0) : 0,
  )
  const changesEdited = $derived(!!(info && list.records[0]?.changes?.[info.id]))
  const objectsEdited = $derived(!!(info && list.records[0]?.objects?.[info.id]))
</script>

<svelte:window onmouseup={onUp} />

<div class="editor">
  <RecordList records={maps} {selected} onselect={(i) => load(i)} secondary={(m) => m.name === m.id} secondaryLabel={t('maps.otherMaps')} problemIds={new Set(problems.filter((p) => p.kind === 'maps').map((p) => p.id))}>
    {#snippet suffix(m: MapInfo)}
      {#if list.records[0]?.layouts?.[m.id] || list.records[0]?.changes?.[m.id] || list.records[0]?.objects?.[m.id]}<span class="edited" title={t('maps.edited')}>✎</span>{/if}
      <span class="muted id">{m.width}×{m.height}</span>
    {/snippet}
  </RecordList>

  {#if info}
    <div class="detail">
      <section class="panel">
        <h2>{info.name} <span class="muted id">{info.id}</span></h2>
        <p class="muted small">
          {t('maps.usedBy')}
          {#each info.chapters as c, k (c)}{#if k}, {/if}<Mention kind="chapters" id={String(c)}>{chapterTitle(c)}</Mention>{/each}
          {#if info.chapters.length > 1}<span class="warn"> — {t('maps.shared', { n: info.chapters.length })}</span>{/if}
        </p>
        <p class="muted small">{t('maps.hint')}</p>
        {#if layout}
          <div class="size">
            <NumberField label={t('maps.width')} value={width} min={MIN_WIDTH} max={MAX_SIDE} compact onchange={(v) => resize(v, height)} />
            <NumberField label={t('maps.height')} value={height} min={MIN_HEIGHT} max={MAX_SIDE} compact onchange={(v) => resize(width, v)} />
            <span class="muted small">{t('maps.sizeHint')}</span>
          </div>
          {#if sizeProblem}<p class="bad small">{problemText(sizeProblem)}</p>{/if}
        {/if}
        {#if painted || changesEdited || objectsEdited}
          <p class="small">
            <span class="edited">✎</span>
            {#if painted}{t('maps.changed', { n: changedCells })}{/if}
            {#if changesEdited}{t('maps.changesEdited')}{/if}
            {#if objectsEdited}{t('maps.objectsEdited')}{/if}
            <button class="link" onclick={reset}>{t('maps.reset')}</button>
          </p>
        {/if}
        {#each mapProblems.filter((p) => p !== sizeProblem) as pr, i (i)}<p class="bad small">{problemText(pr)}</p>{/each}
        {#if chapterProblems.length}
          <div class="chapter-problems">
            {#each chapterProblems as pr, i (i)}
              <p class="{pr.severity === 'error' ? 'bad' : 'warn'} small">
                <Mention kind="chapters" id={String(pr.params.chapter)}>{chapterTitle(Number(pr.params.chapter))}</Mention> — {problemText(pr)}
              </p>
            {/each}
          </div>
        {/if}
      </section>

      <div class="layout" class:wide={paletteMode === 'sheet'}>
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
            {#if changes}<label class="check" title={t('maps.changesHint')}><input type="checkbox" bind:checked={showChanges} /> {t('maps.changes')}</label>{/if}
            <label class="check" title={t('maps.showObjectsHint')}><input type="checkbox" bind:checked={showObjects} /> {t('maps.showObjects')}</label>
            <label class="check" title={t('maps.previewHint')}><input type="checkbox" bind:checked={preview} /> {t('maps.preview')}</label>
            <label class="check">
              {t('maps.zoom')}
              <select bind:value={zoom}>
                {#each [1, 2, 3] as z (z)}<option value={z}>×{z}</option>{/each}
              </select>
            </label>
          </div>

          {#if layout}
            <div class="layers">
              <label class="check">
                {t('maps.layer')}
                <select value={layer ?? ''} onchange={(e) => { const v = (e.target as HTMLSelectElement).value; layer = v === '' ? null : Number(v) }}>
                  <option value="">{t('maps.layer.map')}</option>
                  {#each changes ?? [] as c, i (i)}
                    <option value={i}>{t('maps.change', { id: c.id })} — {c.x}, {c.y} ({c.w}×{c.h})</option>
                  {/each}
                </select>
              </label>
              {#if changes}
                <button onclick={addChange} title={t('maps.addChangeHint')}>＋ {t('maps.addChange')}</button>
              {:else}
                <span class="muted small">{t('maps.noChangeLayer')}</span>
              {/if}
            </div>
            {#if change}
              <div class="change-panel">
                <p class="muted small">{t('maps.changeEditHint')}</p>
                <div class="row">
                  <NumberField label={t('maps.changeId')} value={change.id} min={0} max={MAX_CHANGE_ID} compact onchange={(v) => editChange('id', v)} />
                  <NumberField label="X" value={change.x} min={0} max={width - 1} compact onchange={(v) => editChange('x', v)} />
                  <NumberField label="Y" value={change.y} min={0} max={height - 1} compact onchange={(v) => editChange('y', v)} />
                  <NumberField label={t('maps.width')} value={change.w} min={1} max={width} compact onchange={(v) => editChange('w', v)} />
                  <NumberField label={t('maps.height')} value={change.h} min={1} max={height} compact onchange={(v) => editChange('h', v)} />
                  <button class="danger" onclick={removeChange}>{t('maps.removeChange')}</button>
                </div>
              </div>
            {/if}
          {/if}

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
                {hover.x}, {hover.y} · {terrainName(layout.terrains[shownTile(hover.x, hover.y)])} <span class="tiny">#{shownTile(hover.x, hover.y)}</span>
                {#each (changes ?? []).filter((c) => hover && hover.x >= c.x && hover.y >= c.y && hover.x < c.x + c.w && hover.y < c.y + c.h) as c (c.id)}
                  · <span class="change-tag">{t('maps.change', { id: c.id })}</span>
                {/each}
                {#each objects.filter((o) => hover && o.cells.some(([x, y]) => x === hover!.x && y === hover!.y)) as o (keyOf(o))}
                  · {OBJECT_ICONS[o.kind]} {t(`maps.kind.${o.kind}`)}
                {/each}
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
            {@render objectsPanel()}
          {:else}
            <p class="muted">…</p>
          {/if}
        </section>

        <section class="panel palette-panel">
          <div class="palette-head">
            <h3>{t('maps.palette')}</h3>
            <div class="modes" role="radiogroup" aria-label={t('maps.palette')}>
              <button role="radio" aria-checked={paletteMode === 'unique'} class:active={paletteMode === 'unique'} onclick={() => { paletteMode = 'unique'; palettePicked = null }}>{t('maps.palette.unique')}</button>
              <button role="radio" aria-checked={paletteMode === 'sheet'} class:active={paletteMode === 'sheet'} onclick={() => { paletteMode = 'sheet'; palettePicked = null }}>{t('maps.palette.sheet')}</button>
            </div>
          </div>
          {#if layout && sheet}
            <div class="brush">
              <canvas width={PALETTE_CELL} height={PALETTE_CELL} use:drawBrush={{ m: brush, sheet, layout }}></canvas>
              <div>
                {#if stampW > 1 || stampH > 1}
                  <div>{t('maps.block', { w: stampW, h: stampH })}</div>
                  <button class="link" onclick={() => setBrush(brush)}>{t('maps.oneTile')}</button>
                {:else}
                  <div>{terrainName(layout.terrains[brush])}</div>
                  <div class="muted tiny">
                    {t('maps.tileNumber', { n: brush })}{#if tilesetEdits?.metatiles[String(brush)]} · {t('maps.addedTile')}{/if}{#if layout.terrainNames[layout.terrains[brush]]} · {t('maps.gameName', { name: layout.terrainNames[layout.terrains[brush]] })}{/if}
                  </div>
                {/if}
              </div>
            </div>
            <div class="transforms">
              <span class="small">{t('maps.transform')}</span>
              {#each TRANSFORMS as tr (tr.op)}
                <button title={t(`maps.transform.${tr.op}`)} aria-label={t(`maps.transform.${tr.op}`)} onclick={() => transform(tr.op)}>{tr.icon}</button>
              {/each}
            </div>
            <label class="check" title={t('maps.retileHint')}>
              {t('maps.retile')}
              <select value={stampW === 1 && stampH === 1 ? layout.terrains[brush] : ''} onchange={(e) => { const v = (e.target as HTMLSelectElement).value; if (v !== '') transform('terrain', Number(v)) }}>
                {#if stampW > 1 || stampH > 1}<option value="">—</option>{/if}
                {#each ALL_TERRAIN_IDS as id (id)}<option value={id}>{terrainName(id)}</option>{/each}
              </select>
            </label>
            {#if transformError}<p class="bad small">{transformError}</p>{:else}<p class="muted tiny">{t('maps.transformHint')}</p>{/if}
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
                width={palColumns * palCell}
                height={Math.max(1, Math.ceil(palTiles.length / palColumns)) * palCell}
                onmousedown={(e) => { e.preventDefault(); const c = paletteCell(e); paletteDrag = { a: c, b: c } }}
                onmousemove={(e) => { if (paletteDrag && e.buttons & 1) paletteDrag = { a: paletteDrag.a, b: paletteCell(e) } }}
              ></canvas>
            </div>
            <p class="muted tiny">{paletteMode === 'sheet' ? t('maps.sheetHint') : t('maps.paletteHint')}</p>
          {/if}
        </section>
      </div>
    </div>
  {/if}
</div>

{#snippet objectsPanel()}
  <div class="objects">
    <h3>{t('maps.objects', { n: objects.length })}</h3>
    <p class="muted small">{t('maps.objectsHint')}</p>
    {#if objectsInfo && !objectsInfo.hasChangeLayer && objects.some((o) => o.new && CHANGE_KINDS.includes(o.kind))}
      <p class="warn small">{t('maps.obj.noChangeLayer')}</p>
    {/if}
    {#if objects.length}
      <div class="object-list">
        {#each objects as o (keyOf(o))}
          {@const st = objectStatus(o)}
          {@const scripted = !!o.event?.script && !objectSettings[keyOf(o)]}
          {@const gift = EVENT_KINDS.includes(o.kind) && isActive(o) && !scripted ? giftText(settingsOf(o)) : ''}
          <button class="object" class:active={keyOf(o) === selectedObject} onclick={() => (selectedObject = selectedObject === keyOf(o) ? null : keyOf(o))}>
            <span aria-hidden="true">{OBJECT_ICONS[o.kind]}</span>
            <span>{t(`maps.kind.${o.kind}`)}</span>
            <span class="muted tiny">{o.x}, {o.y}</span>
            {#if gift}<span class="tiny">· {gift}</span>{/if}
            <span class="{st.cls} tiny status-text">{st.text}</span>
          </button>
        {/each}
      </div>
    {/if}
    {#if selectedObj}
      {@const o = selectedObj}
      {@const st = settingsOf(o)}
      {@const own = objectSettings[keyOf(o)]}
      <div class="object-panel">
        <h4>{OBJECT_ICONS[o.kind]} {t(`maps.kind.${o.kind}`)} <span class="muted tiny">{o.x}, {o.y}</span></h4>
        <p class="muted small">{t(`maps.kindHint.${o.kind}`)}</p>
        {#if EVENT_KINDS.includes(o.kind) || o.new}
          <label class="check">
            <input type="checkbox" checked={isActive(o)} onchange={(e) => setObject(o, { off: !(e.target as HTMLInputElement).checked })} />
            {t('maps.obj.active')}
          </label>
        {/if}
        {#if isActive(o)}
          {#if o.kind === 'chest'}
            <div class="row">
              <label>
                <span>{t('maps.obj.content')}</span>
                <select value={st.gold ? GOLD : (st.item ?? '')} onchange={(e) => { const v = (e.target as HTMLSelectElement).value; setObject(o, v === GOLD ? { gold: st.gold || 1000, item: undefined } : { item: v, gold: undefined }) }}>
                  <option value={GOLD}>{t('maps.obj.gold')}</option>
                  {#each items as it (it.id)}<option value={it.id}>{it.name}</option>{/each}
                </select>
              </label>
              {#if st.gold}
                <NumberField label={t('maps.obj.goldAmount')} value={st.gold} min={1} max={MAX_GOLD} compact onchange={(v) => setObject(o, { gold: v })} />
              {:else if st.item && itemById.get(st.item)}
                <Mention kind="items" id={st.item}><img class="pixel" src={itemIconUrl(itemById.get(st.item)!.iconId)} alt="" /> {itemById.get(st.item)!.name}</Mention>
              {/if}
            </div>
          {:else if SHOP_KINDS.includes(o.kind)}
            {@const wares = st.items ?? []}
            <span class="small">{t('maps.obj.wares')}</span>
            <div class="wares">
              {#each [...wares, ''] as id, i (i)}
                {#if i < MAX_SHOP_ITEMS}
                  {@const it = itemById.get(id)}
                  <div class="ware">
                    {#if it}<Mention kind="items" {id}><img class="pixel" src={itemIconUrl(it.iconId)} alt="" /></Mention>{:else}<span class="blank-icon"></span>{/if}
                    <select value={id} onchange={(e) => setShopItem(o, wares, i, (e.target as HTMLSelectElement).value)}>
                      <option value="">{i < wares.length ? t('maps.obj.removeWare') : t('maps.obj.addWare')}</option>
                      {#each items as item (item.id)}<option value={item.id}>{item.name}</option>{/each}
                    </select>
                  </div>
                {/if}
              {/each}
            </div>
            <label class="check" title={t('maps.obj.secretHint')}>
              <input type="checkbox" checked={!!st.secret} onchange={(e) => setObject(o, { secret: (e.target as HTMLInputElement).checked, items: wares })} />
              {t('maps.obj.secret')}
            </label>
          {:else if o.kind === 'village' || o.kind === 'house'}
            {#if o.event?.script && !own}
              <p class="small">
                {t('maps.obj.originalEvent', { script: o.event.script })}
                <button class="link" onclick={() => setObject(o, {})}>{t('maps.obj.replace')}</button>
              </p>
            {:else}
              {#if o.kind === 'village'}
                <div class="row">
                  <label>
                    <span>{t('maps.obj.gift')}</span>
                    <select value={st.gold ? GOLD : (st.item ?? '')} onchange={(e) => { const v = (e.target as HTMLSelectElement).value; setObject(o, v === GOLD ? { gold: st.gold || 1000, item: undefined } : { item: v, gold: undefined }) }}>
                      <option value="">{t('field.none')}</option>
                      <option value={GOLD}>{t('maps.obj.gold')}</option>
                      {#each items as it (it.id)}<option value={it.id}>{it.name}</option>{/each}
                    </select>
                  </label>
                  {#if st.gold}
                    <NumberField label={t('maps.obj.goldAmount')} value={st.gold} min={1} max={MAX_GOLD} compact onchange={(v) => setObject(o, { gold: v })} />
                  {:else if st.item && itemById.get(st.item)}
                    <Mention kind="items" id={st.item}><img class="pixel" src={itemIconUrl(itemById.get(st.item)!.iconId)} alt="" /> {itemById.get(st.item)!.name}</Mention>
                  {/if}
                </div>
              {/if}
              <span class="small">{t('maps.obj.face')}</span>
              <div class="faces" role="radiogroup" aria-label={t('maps.obj.face')}>
                {#each objectsInfo?.faces ?? [] as f (f.id)}
                  <button role="radio" aria-checked={st.face === f.id} class:active={st.face === f.id} title={f.id.replace('FID_', '')} onclick={() => setObject(o, { face: f.id })}>
                    <img src={portraitUrl(f.portrait, true)} alt={f.id} />
                  </button>
                {/each}
              </div>
              <label>
                <span>{t('maps.obj.text')}</span>
                <textarea rows="3" value={st.text ?? ''} onchange={(e) => setObject(o, { text: (e.target as HTMLTextAreaElement).value })}></textarea>
              </label>
              <p class="muted tiny">{t('maps.obj.textHint')}</p>
              {#each mapProblems.filter((p) => p.field === 'objects' && p.params.at === keyOf(o)) as pr, i (i)}<p class="bad small">{problemText(pr)}</p>{/each}
            {/if}
          {/if}
        {/if}
        {#if own}<button class="link reset" onclick={() => resetObject(o)}>{t(o.new ? 'maps.obj.resetNew' : 'maps.obj.resetOriginal')}</button>{/if}
      </div>
    {:else if objects.length}
      <p class="muted tiny">{t('maps.obj.pick')}</p>
    {/if}
  </div>
{/snippet}

<style>
  .editor { display: grid; grid-template-columns: 260px 1fr; gap: 1rem; align-items: start; }
  .detail { display: flex; flex-direction: column; gap: 1rem; min-width: 0; }
  .id { font-size: 0.75rem; margin-left: 0.3rem; }
  .small { font-size: 0.8rem; }
  .tiny { font-size: 0.72rem; }
  .warn { color: var(--warn); }
  .bad { color: var(--bad); }
  .danger { color: var(--bad); }
  .edited { color: var(--accent); margin-left: 0.25rem; }
  .link { border: none; background: none; padding: 0; color: var(--accent); font: inherit; margin-left: 0.4rem; }
  .size { display: flex; align-items: flex-end; gap: 0.75rem; flex-wrap: wrap; }
  .size .small { padding-bottom: 0.35rem; }
  .chapter-problems { margin-top: 0.4rem; }
  .chapter-problems p { margin: 0.15rem 0; }
  .layout { display: grid; grid-template-columns: minmax(0, 1fr) 290px; gap: 1rem; align-items: start; }
  .layout.wide { grid-template-columns: minmax(0, 1fr) 550px; }
  .palette-head { display: flex; align-items: center; justify-content: space-between; gap: 0.5rem; flex-wrap: wrap; }
  .modes { display: flex; gap: 0.2rem; }
  .modes button { font-size: 0.78rem; padding: 0.15rem 0.5rem; }
  .modes button.active { background: var(--accent-soft); border-color: var(--accent); font-weight: 600; }
  .map-panel { display: flex; flex-direction: column; gap: 0.5rem; min-width: 0; padding: 0.5rem; }
  .toolbar, .layers { display: flex; flex-wrap: wrap; align-items: center; gap: 0.5rem 1rem; }
  .tools { display: flex; gap: 0.25rem; }
  .tools button { font-size: 0.85rem; padding: 0.25rem 0.55rem; }
  .tools button.active { background: var(--accent-soft); border-color: var(--accent); font-weight: 600; }
  .check { flex-direction: row; align-items: center; gap: 0.35rem; font-size: 0.85rem; color: var(--text); }
  .layers button { font-size: 0.85rem; padding: 0.2rem 0.55rem; }
  .change-panel { border-left: 3px solid #f1c40f; padding-left: 0.6rem; }
  .change-panel p { margin: 0 0 0.3rem; }
  .change-panel .row { display: flex; align-items: flex-end; gap: 0.6rem; flex-wrap: wrap; }
  .change-tag { color: #b7950b; }
  .map-scroll { overflow: auto; max-height: calc(100vh - 300px); }
  .map-scroll canvas { display: block; cursor: crosshair; image-rendering: pixelated; }
  .map-scroll canvas.picking { cursor: copy; }
  .status { margin: 0; min-height: 1.2em; }
  .legend { display: flex; flex-wrap: wrap; gap: 0.3rem; }
  .chip { display: inline-flex; align-items: center; gap: 0.3rem; font-size: 0.78rem; padding: 0.1rem 0.45rem; border-radius: 999px; }
  .chip.active { border-color: var(--accent); background: var(--accent-soft); }
  .swatch { width: 0.75rem; height: 0.75rem; border-radius: 3px; display: inline-block; }
  .objects { border-top: 1px solid var(--border); padding-top: 0.5rem; display: flex; flex-direction: column; gap: 0.4rem; }
  .objects h3, .objects p, .object-panel h4 { margin: 0; }
  .object-list { display: flex; flex-direction: column; gap: 0.15rem; max-height: 220px; overflow: auto; }
  .object { display: flex; align-items: center; gap: 0.4rem; text-align: left; font-size: 0.85rem; padding: 0.2rem 0.5rem; border-color: transparent; background: none; }
  .object:hover { background: var(--accent-soft); }
  .object.active { border-color: var(--accent); background: var(--accent-soft); }
  .status-text { margin-left: auto; }
  .good { color: var(--good); }
  .object-panel { border-left: 3px solid #1abc9c; padding-left: 0.6rem; display: flex; flex-direction: column; gap: 0.4rem; }
  .object-panel .row { display: flex; align-items: flex-end; gap: 0.6rem; flex-wrap: wrap; }
  .object-panel textarea { width: 100%; max-width: 32rem; font: inherit; }
  .object-panel .reset { align-self: flex-start; margin-left: 0; }
  .wares { display: flex; flex-direction: column; gap: 0.2rem; }
  .ware { display: flex; align-items: center; gap: 0.4rem; }
  .ware select { max-width: 16rem; }
  .blank-icon { width: 16px; height: 16px; display: inline-block; }
  .faces { display: flex; flex-wrap: wrap; gap: 0.25rem; }
  .faces button { padding: 0.1rem; border-radius: 6px; line-height: 0; }
  .faces button.active { border-color: var(--accent); background: var(--accent-soft); }
  .faces img { width: 48px; height: 40px; image-rendering: pixelated; }
  .pixel { image-rendering: pixelated; vertical-align: middle; }
  .transforms { display: flex; align-items: center; gap: 0.25rem; flex-wrap: wrap; }
  .transforms button { min-width: 2rem; padding: 0.15rem 0.4rem; font-size: 0.95rem; }
  .palette-panel p { margin: 0; }
  .palette-panel { display: flex; flex-direction: column; gap: 0.5rem; }
  .palette-panel h3 { margin: 0; }
  .brush { display: flex; align-items: center; gap: 0.6rem; }
  .brush canvas { border: 1px solid var(--border); image-rendering: pixelated; }
  .palette-scroll { overflow: auto; max-width: 100%; max-height: calc(100vh - 420px); border: 1px solid var(--border); border-radius: 6px; width: fit-content; }
  .palette-scroll canvas { display: block; cursor: pointer; image-rendering: pixelated; }
  @media (max-width: 1000px) { .layout { grid-template-columns: 1fr; } }
  @media (max-width: 800px) { .editor { grid-template-columns: 1fr; } }
</style>
