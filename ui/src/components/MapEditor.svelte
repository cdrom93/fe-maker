<script module lang="ts">
  import Help from './Help.svelte'
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

  /** A whole block of tiles (a building of the game, ticket 41), one 16 px tile per cell. */
  export function drawPiece(canvas: HTMLCanvasElement, params: { rows: number[][]; sheet: HTMLImageElement; layout: MapLayout }) {
    function draw(p: typeof params) {
      const ctx = canvas.getContext('2d')
      if (!ctx) return
      ctx.imageSmoothingEnabled = false
      ctx.clearRect(0, 0, canvas.width, canvas.height)
      p.rows.forEach((row, y) => row.forEach((m, x) => {
        ctx.drawImage(p.sheet, (m % p.layout.columns) * 16, Math.floor(m / p.layout.columns) * 16, 16, 16, x * 16, y * 16, 16, 16)
      }))
    }
    draw(params)
    return { update: draw }
  }
</script>

<script lang="ts">
  import { onMount, untrack } from 'svelte'
  import { appContext } from '../lib/appContext.svelte'
  import { api, ApiError, itemIconUrl, mapTilesetUrl, portraitUrl } from '../lib/api'
  import type { EditableList } from '../lib/history.svelte'
  import { problemText, t } from '../lib/i18n.svelte'
  import { followFocus, useNavigator } from '../lib/navigation.svelte'
  import { addedTileUsage, keepUsed, withoutMetatiles } from '../lib/tileEdits'
  import type { ChapterInfo, ChaptersData, Character, DialogueFace, Item, MapChange, MapPiece, TiledMap, MapInfo, MapObject, MapObjectKind, MapObjects, MapObjectSettings, MapUnit, MapsData, ObjectiveEdit, Problem, TilesetEdits } from '../lib/types'
  import { faceName } from '../lib/faces'
  import FacePicker from './FacePicker.svelte'
  import Mention from './Mention.svelte'
  import ItemPicker from './ItemPicker.svelte'
  import NumberField from './NumberField.svelte'
  import RecordList from './RecordList.svelte'

  let { list, chapterList, items, characters, problems }: { list: EditableList<MapsData>; chapterList: EditableList<ChaptersData>; items: Item[]; characters: Character[]; problems: Problem[] } = $props()

  // Anyone can talk in a village or a house, not only the villagers (ticket 95).
  let allFaces = $state<DialogueFace[]>([])
  let pickingFace = $state(false)
  api.dialogueFaces().then((f) => (allFaces = f)).catch(() => {})
  const faceLabel = (fid: string) => faceName(fid, allFaces, characters)
  const projectFaces = $derived(allFaces.filter((f) => characters.some((c) => c.id.startsWith('CHARACTER_') && c.portraitId === f.portrait)).map((f) => f.id))

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
  /** Tiles a mirror or turn would add to the tileset (ticket 22): shown on the brush, created only once
   *  the user says so. `similar`: the game's own tiles drawn that way (ticket 18), offered instead. */
  let pendingTiles = $state<{ id: string; tileset: string; edits: TilesetEdits; rows: number[][]; similar: number[][] | null; before: number[][] } | null>(null)
  /** painting was tried while new tiles wait for an answer */
  let pendingNudge = $state(false)
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
  /** Drawing the rectangle of a map change with the mouse (ticket 23): a new one, or the edited one's. */
  let areaMode = $state<'new' | 'edit' | null>(null)
  let areaStart = $state<Cell | null>(null)
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
  /** The palette chosen in the project for this map (ticket 16), else the game's. */
  const chosenPalette = $derived<string | null>((info && list.records[0]?.palettes?.[info.id]) || null)
  /** The tile sheet chosen in the project for this map (ticket 21), else the game's. */
  const chosenBase = $derived<string | null>((info && list.records[0]?.bases?.[info.id]) || null)
  let baseError = $state('')
  /** terrains of the map the new tile sheet does not have (cells to touch up) */
  let baseMissing = $state<number[]>([])
  let loadingBase: string | null = null
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

  // Whole buildings of the game's maps drawn with the same tile sheet (ticket 41).
  let pieces = $state<MapPiece[]>([])
  let toolsOpen = $state(false)
  $effect(() => {
    if (pendingTiles) toolsOpen = true
  })
  $effect(() => {
    const id = info?.id
    const base = chosenBase
    pieces = []
    if (!id) return
    api.mapPieces(id, base).then((r) => {
      if (info?.id === id && chosenBase === base) pieces = r.pieces
    }).catch(() => {})
  })

  const nav = useNavigator()
  followFocus('maps', nav, () => maps.map((m) => m.id), (i) => load(i))

  // Tiles added to the tileset (mirrors, turns): sheet and terrains drawn again by the server.
  let tilesetRequest = 0
  $effect(() => {
    const base = baseLayout
    const shown = pendingTiles && pendingTiles.id === info?.id ? pendingTiles.edits : tilesetEdits
    const edits = shown ? JSON.parse(JSON.stringify(shown)) : null
    const palette = chosenPalette
    const tileSheet = chosenBase
    const colors = JSON.parse(JSON.stringify(list.records[0]?.paletteColors ?? {})) as NonNullable<MapsData['paletteColors']>
    if (!info || !base) return
    const id = info.id
    const n = ++tilesetRequest
    if (!edits && !palette && !colors[base.palette ?? '']) {
      layout = base
      sheet = baseSheet
      return
    }
    api.mapTileset(id, edits, palette, tileSheet, colors).then(async (r) => {
      const img = await loadImage(r.sheet)
      if (n !== tilesetRequest || maps[selected]?.id !== id) return
      layout = { ...base, terrains: r.terrains, duplicates: r.duplicates }
      sheet = img
    }).catch(() => {})
  })

  /** Mirror or turn the brush, or give it another terrain. Tiles the tileset does not have yet wait for
   *  the user's answer (ticket 22); turning them again works on the proposed ones. */
  async function transform(op: string, terrain = 0) {
    if (!info || !baseLayout) return
    const id = info.id
    const tileset = baseLayout.tileset
    transformError = ''
    pendingNudge = false
    const current = pendingTiles?.id === id ? pendingTiles : null
    const before = current?.before ?? ($state.snapshot(stamp) as number[][])
    try {
      const edits = current?.edits ?? tilesetEdits
      const r = await api.transformTiles(id, {
        rows: $state.snapshot(stamp) as number[][], op, terrain, edits: edits ? (JSON.parse(JSON.stringify(edits)) as TilesetEdits) : null,
        painted: JSON.parse(JSON.stringify(list.records[0]?.layouts ?? {})),
        bases: JSON.parse(JSON.stringify(list.records[0]?.bases ?? {})),
      })
      if (maps[selected]?.id !== id) return
      stamp = r.rows
      palettePicked = null
      const isNew = (m: number) => String(m) in r.edits.metatiles && !(tilesetEdits && String(m) in tilesetEdits.metatiles)
      pendingTiles = r.rows.flat().some(isNew)
        ? { id, tileset, edits: r.edits, rows: r.rows, similar: r.similar ?? current?.similar ?? null, before }
        : null
    } catch (e) {
      transformError = e instanceof ApiError ? t(`maps.transformError.${e.detail}`) : String(e)
    }
  }

  /** Add the proposed tiles to the tileset (undo removes them); `rows`: the block painted with them. */
  function createPending(rows?: number[][]) {
    const p = pendingTiles
    if (!p || maps[selected]?.id !== p.id) return
    const block = rows ?? p.rows
    const edits = keepUsed(p.edits, tilesetEdits, block)
    if (JSON.stringify(edits) !== JSON.stringify(tilesetEdits ?? { metatiles: {}, tiles: {} })) {
      list.update(0, (d) => {
        d.tilesets ??= {}
        d.tilesets[p.tileset] = edits
      })
    }
    stamp = block
    pendingTiles = null
    pendingNudge = false
  }

  /** Paint with the game's own tiles instead of the new ones (those still needed are created). */
  function useSimilar() {
    const p = pendingTiles
    if (!p?.similar) return
    if (p.similar.flat().some((m) => String(m) in p.edits.metatiles && !(tilesetEdits && String(m) in tilesetEdits.metatiles))) {
      createPending(p.similar)
    } else {
      stamp = p.similar
      pendingTiles = null
      pendingNudge = false
    }
  }

  function cancelPending() {
    if (!pendingTiles) return
    stamp = pendingTiles.before
    pendingTiles = null
    pendingNudge = false
  }

  // Tiles the project added to this tileset (ticket 22): where they are used, to remove the others.
  const addedSlots = $derived(tilesetEdits ? Object.keys(tilesetEdits.metatiles).sort((a, b) => Number(a) - Number(b)) : [])
  const addedUsage = $derived(
    tilesetEdits && baseLayout
      ? addedTileUsage(list.records[0], tilesetEdits, baseLayout.tileset, maps.map((m) => m.id),
                       (lid) => {
                         // a server older than the UI gives no originalTileset: its tileset then is the original one
                         const m = maps.find((n) => n.id === lid)
                         return list.records[0]?.bases?.[lid] || m?.originalTileset || m?.tileset || ''
                       })
      : new Map<string, { cells: number; maps: string[] }>(),
  )
  const mapName = (lid: string) => maps.find((m) => m.id === lid)?.name ?? lid

  function removeAdded(slots: string[]) {
    if (!tilesetEdits || !baseLayout || !slots.length) return
    const tileset = baseLayout.tileset
    const next = withoutMetatiles($state.snapshot(tilesetEdits) as TilesetEdits, slots)
    list.update(0, (d) => {
      d.tilesets ??= {}
      if (Object.keys(next.metatiles).length) d.tilesets[tileset] = next
      else delete d.tilesets[tileset]
    })
    if (stamp.flat().some((m) => slots.includes(String(m)))) setBrush(savedRows[0]?.[0] ?? 0)
  }

  // Objects of the map and what the build does for them, asked again after each edit.
  let objectsRequest = 0
  $effect(() => {
    if (!info || !layout) return
    const id = info.id
    const body = JSON.parse(JSON.stringify({
      rows: savedRows, changes: list.records[0]?.changes?.[id] ?? null, objects: objectSettings, tileset: tilesetEdits ?? null, base: chosenBase,
      offset: list.records[0]?.offsets?.[id] ?? [0, 0],
    }))
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
    maps = all.filter((m) => !m.chapters.length || m.chapters.some((i) => !chapterList[i]?.hidden)).map((m) => {
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
    areaMode = null
    areaStart = null
    terrainFilter = null
    objectsInfo = null
    selectedObject = null
    transformError = ''
    pendingTiles = null
    pendingNudge = false
    baseError = ''
    const id = maps[index].id
    const tileSheet = list.records[0]?.bases?.[id] || null
    loadingBase = tileSheet
    const [data, img] = await Promise.all([api.map(id, tileSheet), loadImage(mapTilesetUrl(id, tileSheet))])
    if (maps[selected]?.id !== id) return
    loadingBase = null
    baseSheet = img
    baseLayout = data
    if (!list.records[0]?.tilesets?.[data.tileset] && !list.records[0]?.palettes?.[id]) {
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
  /** what a terrain does in battle and to movement (from the game's tables), '' with an older server */
  function terrainEffects(id: number): string {
    const e = layout?.terrainEffects
    if (!e) return ''
    const cost = (c: number) => (c < 0 ? '✖' : String(c))
    const heal = e.heal?.[id] ? ` · ${t('maps.terrainHeal', { heal: e.heal[id] })}` : ''
    return t('maps.terrainEffects', { avoid: e.avoid[id], defense: e.defense[id], resistance: e.resistance[id], foot: cost(e.foot[id]), horse: cost(e.horse[id]) }) + heal
  }

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
    if (areaMode && hover) {
      const a = rectOf(areaStart ?? hover, hover)
      ctx.strokeStyle = '#f1c40f'
      ctx.lineWidth = 3
      ctx.setLineDash([6, 4])
      ctx.strokeRect(a.x0 * cell + 1.5, a.y0 * cell + 1.5, (a.x1 - a.x0 + 1) * cell - 3, (a.y1 - a.y0 + 1) * cell - 3)
      ctx.setLineDash([])
      area = null
    } else if (copyStart && hover) {
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

  // Terrain brushes: the tiles of the painted cells and around them are chosen as the game's maps do.
  let groundBrushes = $state<{ terrain: number; tile: number }[]>([])
  let groundBrush = $state<number | null>(null)
  let filling = $state(false)
  $effect(() => {
    const id = info?.id
    const base = chosenBase
    groundBrushes = []
    groundBrush = null
    if (!id) return
    api.mapBrushes(id, base).then((r) => {
      if (info?.id === id && chosenBase === base) groundBrushes = r.brushes
    }).catch(() => {})
  })

  // Another tile taken while new tiles wait for an answer: they are dropped.
  const setBrush = (m: number) => {
    stamp = [[m]]
    groundBrush = null
    palettePicked = null
    pendingTiles = null
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
    finish(next)
  }

  function pickGround(b: { terrain: number; tile: number }) {
    setBrush(b.tile)
    groundBrush = b.terrain
    if (tool !== 'pen' && tool !== 'rect' && tool !== 'fill') tool = 'pen'
  }

  /** The end of a stroke: with a terrain brush, the painted cells are joined to what is around them first. */
  async function finish(next: number[][]) {
    if (groundBrush === null || !info) return commit(next)
    const before = copyGrid()
    const cells: [number, number][] = []
    next.forEach((row, y) => row.forEach((m, x) => { if (m !== before[y]?.[x]) cells.push([x, y]) }))
    if (!cells.length) return
    try {
      commit((await api.mapAutotile(info.id, { rows: next, cells, base: chosenBase })).rows)
    } catch {
      commit(next)
    }
  }

  /** Patches of other grounds in the empty space (the terrain the map has most of); undo takes them back. */
  async function fillEmpty() {
    if (!info || filling) return
    filling = true
    const keep: [number, number][] = objects.map((o) => [o.x, o.y])
    for (const c of changes ?? []) {
      for (let y = c.y; y < c.y + c.h; y++) for (let x = c.x; x < c.x + c.w; x++) keep.push([x, y])
    }
    try {
      commit((await api.mapFill(info.id, { rows: copyGrid(), keep, base: chosenBase })).rows)
    } finally {
      filling = false
    }
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
    if (areaMode && e.button === 0) {
      areaStart = p
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
    if (pendingTiles) {
      pendingNudge = true
      return
    }
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
    if (areaStart) {
      const a = rectOf(areaStart, hover ?? areaStart)
      const mode = areaMode
      areaStart = null
      areaMode = null
      if (mode === 'new') newChangeAt(a.x0, a.y0, a.x1 - a.x0 + 1, a.y1 - a.y0 + 1)
      else setChangeArea(a.x0, a.y0, a.x1 - a.x0 + 1, a.y1 - a.y0 + 1)
      return
    }
    if (copyStart) {
      const a = rectOf(copyStart, hover ?? copyStart)
      stamp = Array.from({ length: a.y1 - a.y0 + 1 }, (_, j) => Array.from({ length: a.x1 - a.x0 + 1 }, (_, i) => shownTile(a.x0 + i, a.y0 + j)))
      palettePicked = null
      pendingTiles = null
      groundBrush = null
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
    finish(result)
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
      if (d.offsets) delete d.offsets[id]
      if (d.palettes) delete d.palettes[id]
      if (d.bases) delete d.bases[id]
    })
    baseMissing = []
  }

  // The tile sheet changed (chosen, undone, reset): the map is loaded again with it.
  $effect(() => {
    const wanted = chosenBase ?? baseLayout?.originalBase
    if (!baseLayout || !wanted || wanted === baseLayout.tileset || wanted === loadingBase) return
    untrack(() => load(selected))
  })

  /** Draw the map with another tile sheet of the game (ticket 21): every cell, and the cells of its
   * changes, take a tile of the same terrain (server: maps.convert_by_terrain). */
  async function setBase(to: string) {
    if (!info || !baseLayout) return
    const id = info.id
    if ((chosenBase ?? baseLayout.originalBase) === to || !confirm(t('maps.baseConfirm'))) return
    baseError = ''
    try {
      const r = await api.convertMap(id, {
        rows: $state.snapshot(savedRows) as number[][], changes: $state.snapshot(list.records[0]?.changes?.[id] ?? null) as MapChange[] | null,
        base: chosenBase, to, edits: tilesetEdits ? (JSON.parse(JSON.stringify(tilesetEdits)) as TilesetEdits) : null,
      })
      if (maps[selected]?.id !== id) return
      list.update(0, (d) => {
        d.layouts ??= {}
        d.layouts[id] = { rows: r.rows }
        if (r.changes.length) {
          d.changes ??= {}
          d.changes[id] = r.changes
        }
        d.bases ??= {}
        if (to === baseLayout!.originalBase) delete d.bases[id]
        else d.bases[id] = to
        if (d.palettes) delete d.palettes[id]
      })
      baseMissing = r.missingTerrains
    } catch (e) {
      baseError = e instanceof ApiError ? t(`problem.${e.detail}`) : String(e)
    }
  }

  // ---------- Tiled (ticket 25) ----------

  let tiledInfo = $state<{ id: string; path: string; launched: boolean } | null>(null)
  let tiledError = $state('')
  let tmxInput = $state<HTMLInputElement>()

  /** Write the map for Tiled (the project's tiled/ folder) and open it there. */
  async function openInTiled() {
    if (!info) return
    const id = info.id
    tiledError = ''
    try {
      const r = await api.exportTiled(id, {
        rows: $state.snapshot(savedRows) as number[][], changes: $state.snapshot(list.records[0]?.changes?.[id] ?? null) as MapChange[] | null,
        edits: tilesetEdits ? (JSON.parse(JSON.stringify(tilesetEdits)) as TilesetEdits) : null, palette: chosenPalette, base: chosenBase,
      })
      tiledInfo = { id, path: r.path, launched: r.launched }
    } catch (e) {
      tiledError = e instanceof ApiError ? t(`maps.tiledError.${e.detail}`) : String(e)
    }
  }

  /** The map and its changes as saved in Tiled (or in a chosen .tmx), as one undo step. */
  function applyTiled(id: string, m: TiledMap) {
    const height = m.rows.length
    const width = m.rows[0]?.length ?? 0
    if (width < MIN_WIDTH || height < MIN_HEIGHT || width > MAX_SIDE || height > MAX_SIDE) {
      tiledError = t('maps.tiledError.size', { w: width, h: height })
      return
    }
    const tileCount = layout?.terrains.length ?? 0
    if (m.rows.flat().some((c) => c >= tileCount) || m.changes.some((c) => c.rows.flat().some((x) => x >= tileCount))) {
      tiledError = t('maps.tiledError.tileOutOfRange')
      return
    }
    const fresh = m.changes.map(({ name: _name, ...c }) => c)
    list.update(0, (d) => {
      d.layouts ??= {}
      d.layouts[id] = { rows: m.rows }
      // a map without change layer in the game keeps none (the build has nowhere to put them)
      if (changes) {
        d.changes ??= {}
        d.changes[id] = fresh
      }
    })
    tiledError = ''
  }

  async function reloadFromTiled() {
    if (!info) return
    const id = info.id
    tiledError = ''
    try {
      const m = await api.importTiled(id)
      if (maps[selected]?.id === id) applyTiled(id, m)
    } catch (e) {
      tiledError = e instanceof ApiError ? t(`maps.tiledError.${e.detail}`) : String(e)
    }
  }

  async function importTmx(file: File | undefined) {
    if (!info || !file) return
    const id = info.id
    tiledError = ''
    try {
      const m = await api.readTmx(id, await file.text())
      if (maps[selected]?.id === id && confirm(t('maps.tmxConfirm', { name: file.name, w: m.rows[0]?.length ?? 0, h: m.rows.length }))) applyTiled(id, m)
    } catch (e) {
      tiledError = e instanceof ApiError ? t(`maps.tiledError.${e.detail}`) : String(e)
    }
    if (tmxInput) tmxInput.value = ''
  }

  /** Another palette of the tileset for this map (every chapter on it). */
  function setPalette(palette: string) {
    if (!info || !baseLayout) return
    const id = info.id
    const original = baseLayout.palette
    list.update(0, (d) => {
      d.palettes ??= {}
      if (palette === original) delete d.palettes[id]
      else d.palettes[id] = palette
    })
  }

  const shownPalette = $derived(layout?.palettes.find((p) => p.id === (chosenPalette ?? layout?.palette)))
  const ownColors = $derived(shownPalette ? list.records[0]?.paletteColors?.[shownPalette.id] : undefined)

  /** A color of the shown palette, for every chapter using it; back to the game's, it is no longer stored. */
  function setColor(index: number, color: string) {
    const pal = shownPalette
    if (!pal?.lines) return
    list.update(0, (d) => {
      const all = (d.paletteColors ??= {})
      const own = (all[pal.id] ??= {})
      if (color === pal.lines![Math.floor(index / 16)][index % 16]) delete own[index]
      else own[index] = color
      if (!Object.keys(own).length) delete all[pal.id]
    })
  }

  function resetColors() {
    const id = shownPalette?.id
    if (id) list.update(0, (d) => { delete d.paletteColors?.[id] })
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
      if (o.auto) {
        const text = t('maps.obj.auto', { id: o.auto.id })
        return { text: o.ruin ? `${text} · ${t('maps.obj.ruin', { id: o.ruin.id })}` : text, cls: 'good' }
      }
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
  /** Rows and columns added (or removed, below 0) on each side of the map. */
  let sides = $state({ top: 0, left: 0, right: 0, bottom: 0 })
  const newWidth = $derived(width + sides.left + sides.right)
  const newHeight = $derived(height + sides.top + sides.bottom)
  const newSizeOk = $derived(newWidth >= MIN_WIDTH && newHeight >= MIN_HEIGHT && newWidth <= MAX_SIDE && newHeight <= MAX_SIDE)
  let resizing = $state(false)

  /** The map with its sides moved. What stands on it follows when the left or top side moves: map changes,
   *  object settings, then the units and objectives of its chapters (their own undo step, in the Chapters tab). */
  async function resize() {
    if (!info || !newSizeOk || resizing) return
    const { top: dy, left: dx } = sides
    if ((dx || dy) && info.chapters.length && !confirm(t('maps.moveConfirm'))) return
    const id = info.id
    const [w, h] = [newWidth, newHeight]
    resizing = true
    try {
      if (dx || dy) await moveChapters(info.chapters, dx, dy, w, h)
      if (maps[selected]?.id !== id) return
      const next = Array.from({ length: h }, (_, y) => Array.from({ length: w }, (_, x) => rows[y - dy]?.[x - dx] ?? brush))
      if (dx || dy) {
        layer = null
        const kept = (changes ?? []).flatMap((c) => {
          const [x, y] = [Math.max(0, c.x + dx), Math.max(0, c.y + dy)]
          const [cw, ch] = [Math.min(w, c.x + dx + c.w) - x, Math.min(h, c.y + dy + c.h) - y]
          if (cw <= 0 || ch <= 0) return []
          const part = Array.from({ length: ch }, (_, j) => Array.from({ length: cw }, (_, i) => c.rows[y + j - c.y - dy][x + i - c.x - dx]))
          return [{ ...c, x, y, w: cw, h: ch, rows: part }]
        })
        saveChanges(kept)
        list.update(0, (d) => {
          const [ox, oy] = d.offsets?.[id] ?? [0, 0]
          d.offsets ??= {}
          if (ox + dx || oy + dy) d.offsets[id] = [ox + dx, oy + dy]
          else delete d.offsets[id]
          const settings = d.objects?.[id]
          if (!settings) return
          d.objects![id] = Object.fromEntries(Object.entries(settings).map(([key, value]) => {
            const [x, y] = key.split(',').map(Number)
            return [`${x + dx},${y + dy}`, value]
          }))
        })
      }
      saveRows(next)
      sides = { top: 0, left: 0, right: 0, bottom: 0 }
    } finally {
      resizing = false
    }
  }

  /** Units and objective tiles of the chapters on a map whose left or top side moved. */
  async function moveChapters(indexes: number[], dx: number, dy: number, w: number, h: number) {
    const found = await Promise.all(indexes.map(async (index) =>
      ({ index, groups: (await api.chapterUnits(index)).groups, objective: await api.chapterObjective(index) })))
    const inside = (v: number, side: number) => Math.max(0, Math.min(side - 1, v))
    // Units may start outside the map (they walk in): only what a unit's position can hold limits them.
    const onGrid = (v: number) => inside(v, 64)
    const movedUnit = (u: MapUnit): MapUnit => ({
      ...u, x: onGrid(u.x + dx), y: onGrid(u.y + dy), endX: onGrid(u.endX + dx), endY: onGrid(u.endY + dy),
    })
    chapterList.update(0, (c) => {
      const seen = new Set<string>()
      for (const { index, groups, objective } of found) {
        for (const g of groups) {
          if (seen.has(g.name) || !g.units.length) continue
          seen.add(g.name)
          c.unitGroups[g.name] = (c.unitGroups[g.name] ?? (structuredClone($state.snapshot(g.units)) as MapUnit[])).map(movedUnit)
        }
        for (const [name, group] of Object.entries(c.newGroups ?? {})) {
          if (group.chapter === index && !seen.has(name) && c.unitGroups[name]) {
            seen.add(name)
            c.unitGroups[name] = c.unitGroups[name].map(movedUnit)
          }
        }
        const key = String(index)
        const goal = c.objectives?.[key] ?? objective
        if (!goal.seize?.length && !goal.area) continue
        c.objectives ??= {}
        c.objectives[key] = {
          ...(structuredClone($state.snapshot(goal)) as ObjectiveEdit),
          seize: (goal.seize ?? []).map((s) => ({ x: inside(s.x + dx, w), y: inside(s.y + dy, h) })),
          area: goal.area ? { x1: goal.area.x1 + dx, y1: goal.area.y1 + dy, x2: goal.area.x2 + dx, y2: goal.area.y2 + dy } : goal.area,
        }
      }
    })
  }

  /** Map tiles under a rectangle (what a new or enlarged change starts from). */
  const tilesUnder = (x: number, y: number, w: number, h: number) =>
    Array.from({ length: h }, (_, j) => Array.from({ length: w }, (_, i) => rows[y + j]?.[x + i] ?? brush))

  /** "Add a change": the user draws its rectangle on the map (ticket 23). */
  function addChange() {
    if (!changes) return
    areaMode = areaMode === 'new' ? null : 'new'
    areaStart = null
  }

  function newChangeAt(x: number, y: number, w: number, h: number) {
    if (!changes) return
    const id = changes.length ? Math.max(...changes.map((c) => c.id)) + 1 : 0
    const fresh: MapChange = { id, x, y, w, h, rows: tilesUnder(x, y, w, h) }
    const at = changes.length   // `changes` is derived: it already holds the new change after saving
    saveChanges([...changes, fresh])
    layer = at
    showChanges = true
  }

  /** The edited change's rectangle drawn again: cells it already had keep their tiles, new ones start as the map. */
  function setChangeArea(x: number, y: number, w: number, h: number) {
    if (layer === null || !changes || !change) return
    const old = change
    const tileAt = (cx: number, cy: number) =>
      cx >= old.x && cy >= old.y && cx < old.x + old.w && cy < old.y + old.h ? old.rows[cy - old.y][cx - old.x] : (rows[cy]?.[cx] ?? brush)
    const c = { ...old, x, y, w, h, rows: Array.from({ length: h }, (_, j) => Array.from({ length: w }, (_, i) => tileAt(x + i, y + j))) }
    const i = layer
    saveChanges(changes.map((k, n) => (n === i ? c : k)))
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

  /** The object's "after" tiles drawn by hand (ticket 19): FE Maker's own guess, else the map, as a
   * change of the project the editor opens at once (a snag's passage can be made wider). */
  function manualAfter(o: MapObject) {
    if (!changes) return
    const xs = o.cells.map((c) => c[0])
    const ys = o.cells.map((c) => c[1])
    const x = Math.min(...xs)
    const y = Math.min(...ys)
    const w = Math.max(...xs) - x + 1
    const h = Math.max(...ys) - y + 1
    const base = o.auto ?? { x, y, w, h, rows: tilesUnder(x, y, w, h) }
    const id = changes.length ? Math.max(...changes.map((c) => c.id)) + 1 : 0
    const at = changes.length
    saveChanges([...changes, { id, x: base.x, y: base.y, w: base.w, h: base.h, rows: base.rows.map((r) => [...r]), manual: true }])
    layer = at
    showChanges = true
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
    groundBrush = null
    if (!paletteDrag) return
    const a = rectOf(paletteDrag.a, paletteDrag.b)
    const tileAt = (x: number, y: number) => palTiles[y * palColumns + x] ?? palTiles[palTiles.length - 1]
    stamp = Array.from({ length: a.y1 - a.y0 + 1 }, (_, j) => Array.from({ length: a.x1 - a.x0 + 1 }, (_, i) => tileAt(a.x0 + i, a.y0 + j)))
    palettePicked = stampW === 1 && stampH === 1 ? null : paletteDrag
    paletteDrag = null
    pendingTiles = null
    if (tool === 'pick') tool = 'pen'
  }

  const changedCells = $derived(
    painted && layout ? painted.rows.reduce((n, row, y) => n + row.filter((m, x) => m !== layout!.rows[y]?.[x]).length, 0) : 0,
  )
  const changesEdited = $derived(!!(info && list.records[0]?.changes?.[info.id]))
  const objectsEdited = $derived(!!(info && list.records[0]?.objects?.[info.id]))
  const paletteEdited = $derived(!!chosenPalette)
</script>

<svelte:window onmouseup={onUp} onkeydown={(e) => { if (e.key === 'Escape' && areaMode) { areaMode = null; areaStart = null } }} />

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
        <h2>{info.name} <span class="muted id">{info.id}</span> <Help text={t('maps.hint')} /></h2>
        <p class="muted small">
          {t('maps.usedBy')}
          {#each info.chapters as c, k (c)}{#if k}, {/if}<Mention kind="chapters" id={String(c)}>{chapterTitle(c)}</Mention>{/each}
          {#if info.chapters.length > 1}<span class="warn"> — {t('maps.shared', { n: info.chapters.length })}</span>{/if}
        </p>
        <details class="map-settings" open={!!sizeProblem}>
          <summary class="small">{t('maps.settings')}</summary>
        {#if layout}
          <div class="size">
            <span class="small current-size">{t('maps.sizeNow', { w: width, h: height })}</span>
            <NumberField label={t('maps.addTop')} value={sides.top} min={-height} max={MAX_SIDE} compact onchange={(v) => (sides.top = v)} />
            <NumberField label={t('maps.addLeft')} value={sides.left} min={-width} max={MAX_SIDE} compact onchange={(v) => (sides.left = v)} />
            <NumberField label={t('maps.addRight')} value={sides.right} min={-width} max={MAX_SIDE} compact onchange={(v) => (sides.right = v)} />
            <NumberField label={t('maps.addBottom')} value={sides.bottom} min={-height} max={MAX_SIDE} compact onchange={(v) => (sides.bottom = v)} />
            <button disabled={!newSizeOk || resizing || (newWidth === width && newHeight === height && !sides.top && !sides.left)} onclick={resize}>
              {t('maps.applySize', { w: newWidth, h: newHeight })}
            </button>
            <Help text={t('maps.sizeHint')} />
          </div>
          {#if sizeProblem}<p class="bad small">{problemText(sizeProblem)}</p>{/if}
          <details class="bases-panel">
            <summary class="small">{t('maps.base')} : {layout.bases.find((b) => b.id === (chosenBase ?? layout!.originalBase))?.name ?? (chosenBase ?? layout.originalBase)}
              {#if chosenBase}<span class="edited">✎</span>{/if} <Help text={t('maps.baseHint')} /></summary>
            <div class="bases" role="radiogroup" aria-label={t('maps.base')}>
              {#each layout.bases as b (b.id)}
                {@const names = b.chapters.map(chapterTitle)}
                {@const current = (chosenBase ?? layout.originalBase) === b.id}
                <button role="radio" aria-checked={current} class="base-choice" class:active={current} title={`${b.name} — ${names.join(', ')}`}
                        onclick={() => setBase(b.id)}>
                  <span class="thumb" style="background-image: url({mapTilesetUrl(info!.id, b.id)})"></span>
                  <strong class="tiny">{b.name}</strong>
                  <span class="tiny">{names.slice(0, 2).join(', ')}{names.length > 2 ? ` +${names.length - 2}` : ''}{b.id === layout.originalBase ? ` · ${t('maps.baseOriginal')}` : ''}</span>
                </button>
              {/each}
            </div>
          </details>
          {#if baseMissing.length}
            <p class="warn small">{t('maps.baseMissing', { terrains: baseMissing.map((m) => layout!.terrainNames[m] || `#${m}`).join(', ') })}</p>
          {/if}
          {#if baseError}<p class="bad small">{baseError}</p>{/if}
          {#if layout.palettes.length > 1}
            <div class="palettes" role="radiogroup" aria-label={t('maps.palette')}>
              <span class="small">{t('maps.palette')}</span>
              {#each layout.palettes as pal (pal.id)}
                {@const names = pal.chapters.map(chapterTitle)}
                <button role="radio" aria-checked={(chosenPalette ?? layout.palette) === pal.id} class="palette-choice"
                        class:active={(chosenPalette ?? layout.palette) === pal.id} title={`${pal.id} — ${names.join(', ')}`} onclick={() => setPalette(pal.id)}>
                  <span class="swatches">{#each pal.colors.slice(1) as c, k (k)}<span style="background: {c}"></span>{/each}</span>
                  <span class="tiny">{names.slice(0, 2).join(', ')}{names.length > 2 ? ` +${names.length - 2}` : ''}{pal.id === layout.palette ? ` · ${t('maps.paletteOriginal')}` : ''}</span>
                </button>
              {/each}
            </div>
          {/if}
        {/if}
        {#if shownPalette?.lines}
          <details class="colors-panel">
            <summary class="small">{t('maps.colors')} {#if ownColors}<span class="edited">✎</span>{/if} <Help text={t('maps.colorsHint', { n: shownPalette.chapters.length })} /></summary>
            <div class="color-lines">
              {#each shownPalette.lines as line, l (l)}
                <div class="color-line">
                  {#each line as color, k (k)}
                    {#if k}
                      <input type="color" aria-label={t('maps.colorLabel', { line: l + 1, n: k })} value={ownColors?.[l * 16 + k] ?? color}
                             onchange={(e) => setColor(l * 16 + k, (e.target as HTMLInputElement).value)} />
                    {/if}
                  {/each}
                </div>
              {/each}
            </div>
            {#if ownColors}<button class="link" onclick={resetColors}>{t('maps.colorsReset')}</button>{/if}
          </details>
        {/if}
        {#if layout}
          <div class="tiled">
            <span class="small">{t('maps.tiled')}</span>
            <button onclick={openInTiled} title={t('maps.tiledOpenHint')}>↗ {t('maps.tiledOpen')}</button>
            <button onclick={reloadFromTiled} title={t('maps.tiledReloadHint')}>↙ {t('maps.tiledReload')}</button>
            <button onclick={() => tmxInput?.click()} title={t('maps.tmxImportHint')}>{t('maps.tmxImport')}</button>
            <input type="file" accept=".tmx" hidden bind:this={tmxInput} onchange={(e) => importTmx((e.target as HTMLInputElement).files?.[0])} />
          </div>
          {#if tiledInfo?.id === info.id}
            <p class="muted tiny">{t(tiledInfo.launched ? 'maps.tiledOpened' : 'maps.tiledNotInstalled', { path: tiledInfo.path })}</p>
          {/if}
          {#if tiledError}<p class="bad small">{tiledError}</p>{/if}
        {/if}
        </details>
        {#if painted || changesEdited || objectsEdited || paletteEdited || chosenBase}
          <p class="small">
            <span class="edited">✎</span>
            {#if painted}{t('maps.changed', { n: changedCells })}{/if}
            {#if changesEdited}{t('maps.changesEdited')}{/if}
            {#if objectsEdited}{t('maps.objectsEdited')}{/if}
            {#if paletteEdited}{t('maps.paletteEdited')}{/if}
            {#if chosenBase}{t('maps.baseEdited')}{/if}
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
                <button onclick={addChange} class:active={areaMode === 'new'} title={t('maps.addChangeHint')}>＋ {t('maps.addChange')}</button>
                {#if areaMode}<span class="warn small">{t(areaMode === 'new' ? 'maps.drawNewChange' : 'maps.drawChangeArea')}</span>{/if}
              {/if}
            </div>
            {#if change}
              <div class="change-panel">
                <div class="row">
                  <NumberField label={t('maps.changeId')} value={change.id} min={0} max={MAX_CHANGE_ID} compact onchange={(v) => editChange('id', v)} />
                  <NumberField label="X" value={change.x} min={0} max={width - 1} compact onchange={(v) => editChange('x', v)} />
                  <NumberField label="Y" value={change.y} min={0} max={height - 1} compact onchange={(v) => editChange('y', v)} />
                  <NumberField label={t('maps.width')} value={change.w} min={1} max={width} compact onchange={(v) => editChange('w', v)} />
                  <NumberField label={t('maps.height')} value={change.h} min={1} max={height} compact onchange={(v) => editChange('h', v)} />
                  <button class:active={areaMode === 'edit'} onclick={() => { areaMode = areaMode === 'edit' ? null : 'edit'; areaStart = null }} title={t('maps.changeAreaHint')}>▭ {t('maps.changeArea')}</button>
                  <button class="danger" onclick={removeChange}>{t('maps.removeChange')}</button>
                  <Help text={t(change.manual ? 'maps.manualChangeHint' : 'maps.changeEditHint')} />
                </div>
              </div>
            {/if}
          {/if}

          {#if layout && sheet}
            <div class="map-scroll">
              <canvas
                bind:this={mapCanvas}
                class:picking={tool === 'pick'}
                class:area={!!areaMode}
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
                <span class="tiny muted">{terrainEffects(layout.terrains[shownTile(hover.x, hover.y)])}</span>
                {#each (changes ?? []).filter((c) => hover && hover.x >= c.x && hover.y >= c.y && hover.x < c.x + c.w && hover.y < c.y + c.h) as c (c.id)}
                  · <span class="change-tag">{t('maps.change', { id: c.id })}</span>
                {/each}
                {#each objects.filter((o) => hover && o.cells.some(([x, y]) => x === hover!.x && y === hover!.y)) as o (keyOf(o))}
                  · {OBJECT_ICONS[o.kind]} {t(`maps.kind.${o.kind}`)}
                {/each}
              {:else}
                <Help text={t('maps.mouseHint')} />
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
                  {#if terrainEffects(layout.terrains[brush])}<div class="muted tiny">{terrainEffects(layout.terrains[brush])}</div>{/if}
                {/if}
              </div>
            </div>
            {#if groundBrushes.length}
              <h4 class="small ground-title">{t('maps.ground')} <Help text={t('maps.groundHint')} /></h4>
              <div class="pieces ground">
                {#each groundBrushes as b (b.terrain)}
                  <button class="piece" class:active={groundBrush === b.terrain} onclick={() => pickGround(b)}>
                    <canvas width="16" height="16" use:drawBrush={{ m: b.tile, sheet, layout }}></canvas>
                    <span class="tiny">{terrainName(b.terrain)}</span>
                  </button>
                {/each}
              </div>
              <div class="row">
                <button class="small" disabled={filling} onclick={fillEmpty}>{filling ? t('maps.filling') : t('maps.fillEmpty')}</button>
                <Help text={t('maps.fillEmptyHint')} />
              </div>
            {/if}
            {#snippet pieceGroup(group: 'building' | 'decor')}
              {@const shown = pieces.filter((p) => p.group === group)}
              {#if shown.length}
                <details class="pieces-panel">
                  <summary class="small">{t(`maps.pieces.${group}`, { n: shown.length })} <Help text={t(`maps.pieces.${group}Hint`)} /></summary>
                  <div class="pieces">
                    {#each shown as piece, k (k)}
                      <button class="piece" class:active={stamp === piece.rows} title={piece.maps.length ? t('maps.pieceHint', { kind: t(`maps.piece.${piece.kind}`), maps: piece.maps.map(mapName).join(', ') }) : t(`maps.piece.${piece.kind}`)}
                        onclick={() => { stamp = piece.rows; groundBrush = null; palettePicked = null; pendingTiles = null; if (tool !== 'pen' && tool !== 'rect' && tool !== 'fill') tool = 'pen' }}>
                        <canvas width={piece.rows[0].length * 16} height={piece.rows.length * 16} use:drawPiece={{ rows: piece.rows, sheet: sheet!, layout: layout! }}></canvas>
                        <span class="tiny">{t(`maps.piece.${piece.kind}`)}</span>
                      </button>
                    {/each}
                  </div>
                </details>
              {/if}
            {/snippet}
            {@render pieceGroup('building')}
            {@render pieceGroup('decor')}
            <h4 class="small ground-title">{t('maps.tiles')} <Help text={paletteMode === 'sheet' ? t('maps.sheetHint') : t('maps.paletteHint')} /></h4>
            <div class="modes" role="radiogroup" aria-label={t('maps.palette')}>
              <button role="radio" aria-checked={paletteMode === 'unique'} class:active={paletteMode === 'unique'} onclick={() => { paletteMode = 'unique'; palettePicked = null }}>{t('maps.palette.unique')}</button>
              <button role="radio" aria-checked={paletteMode === 'sheet'} class:active={paletteMode === 'sheet'} onclick={() => { paletteMode = 'sheet'; palettePicked = null }}>{t('maps.palette.sheet')}</button>
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
                width={palColumns * palCell}
                height={Math.max(1, Math.ceil(palTiles.length / palColumns)) * palCell}
                onmousedown={(e) => { e.preventDefault(); const c = paletteCell(e); paletteDrag = { a: c, b: c } }}
                onmousemove={(e) => { if (paletteDrag && e.buttons & 1) paletteDrag = { a: paletteDrag.a, b: paletteCell(e) } }}
              ></canvas>
            </div>
            <details class="tile-tools" bind:open={toolsOpen}>
              <summary class="small">{t('maps.tileTools')}</summary>
            <div class="transforms">
              <span class="small">{t('maps.transform')} <Help text={t('maps.transformHint')} /></span>
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
            {#if pendingTiles && sheet}
              {@const p = pendingTiles}
              {@const fresh = new Set(p.rows.flat().filter((m) => !(tilesetEdits && String(m) in tilesetEdits.metatiles) && String(m) in p.edits.metatiles))}
              <div class="similar" class:nudge={pendingNudge}>
                <span class="small">{t('maps.pendingTiles', { n: fresh.size })}</span>
                <span class="similar-tiles">
                  {#each [...fresh].slice(0, 8) as m (m)}<canvas width={PALETTE_CELL} height={PALETTE_CELL} use:drawBrush={{ m, sheet, layout }}></canvas>{/each}
                </span>
                <span class="pending-actions">
                  <button class="primary" onclick={() => createPending()}>{t('maps.createTiles')}</button>
                  <button onclick={cancelPending}>{t('maps.cancelTiles')}</button>
                </span>
                {#if p.similar}
                  <span class="small">{t('maps.similarFound')}</span>
                  <span class="similar-tiles">
                    {#each p.similar.flat().slice(0, 8) as m, k (k)}<canvas width={PALETTE_CELL} height={PALETTE_CELL} use:drawBrush={{ m, sheet, layout }}></canvas>{/each}
                  </span>
                  <button onclick={useSimilar}>{t('maps.useSimilar')}</button>
                {/if}
                {#if pendingNudge}<span class="warn small">{t('maps.pendingNudge')}</span>{/if}
              </div>
            {/if}
            {#if transformError}<p class="bad small">{transformError}</p>{/if}
            {#if addedSlots.length}
              {@const unused = addedSlots.filter((k) => !addedUsage.has(k))}
              <details class="added-tiles">
                <summary class="small">{t('maps.addedTiles', { n: addedSlots.length })} <Help text={t('maps.addedTilesHint')} /></summary>
                <div class="added-list">
                  {#each addedSlots as k (k)}
                    {@const u = addedUsage.get(k)}
                    <div class="added" title={u ? t('maps.addedUsed', { n: u.cells, maps: u.maps.map(mapName).join(', ') }) : t('maps.addedUnused')}>
                      <button class="tile-pick" onclick={() => setBrush(Number(k))} aria-label={t('maps.tileNumber', { n: Number(k) })}>
                        <canvas width={PALETTE_CELL} height={PALETTE_CELL} use:drawBrush={{ m: Number(k), sheet, layout }}></canvas>
                      </button>
                      <span class="tiny" class:muted={!u}>{u ? `×${u.cells}` : '—'}</span>
                      <button class="remove" disabled={!!u} onclick={() => removeAdded([k])} aria-label={t('maps.removeTile')} title={u ? t('maps.addedUsed', { n: u.cells, maps: u.maps.map(mapName).join(', ') }) : t('maps.removeTile')}>✕</button>
                    </div>
                  {/each}
                </div>
                {#if unused.length}<button onclick={() => removeAdded(unused)}>{t('maps.removeUnused', { n: unused.length })}</button>{/if}
              </details>
            {/if}
            </details>
          {/if}
        </section>
      </div>
    </div>
  {/if}
</div>

{#snippet objectsPanel()}
  <div class="objects">
    <h3>{t('maps.objects', { n: objects.length })} <Help text={t('maps.objectsHint')} /></h3>
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
        {#if isActive(o) && CHANGE_KINDS.includes(o.kind) && changes}
          {@const own = o.change !== null && !o.auto ? changes.findIndex((c) => c.id === o.change) : -1}
          <p class="small">
            {#if own >= 0}
              <button class="link" onclick={() => { layer = own; showChanges = true }}>{t('maps.obj.editAfter', { id: o.change ?? 0 })}</button>
            {:else if o.new}
              <button class="link" onclick={() => manualAfter(o)}>{t(o.kind === 'snag' || o.kind === 'wall' ? 'maps.obj.manualPassage' : 'maps.obj.manualAfter')}</button>
            {/if}
          </p>
        {/if}
        {#if isActive(o)}
          {#if o.kind === 'chest'}
            <div class="row">
              <label>
                <span>{t('maps.obj.content')}</span>
                <ItemPicker icon={false} value={st.gold ? GOLD : (st.item ?? '')} {items} extra={[{ value: GOLD, label: t('maps.obj.gold') }]} label={t('maps.obj.content')}
                            onchange={(v) => setObject(o, v === GOLD ? { gold: st.gold || 1000, item: undefined } : { item: v, gold: undefined })} />
              </label>
              {#if st.gold}
                <NumberField label={t('maps.obj.goldAmount')} value={st.gold} min={1} max={MAX_GOLD} compact onchange={(v) => setObject(o, { gold: v })} />
              {:else if st.item && itemById.get(st.item)}
                <Mention kind="items" id={st.item}><img class="pixel" src={itemIconUrl(itemById.get(st.item)!.iconId)} alt={itemById.get(st.item)!.name} title={itemById.get(st.item)!.name} /></Mention>
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
                    <ItemPicker icon={false} value={id} {items} extra={[{ value: '', label: i < wares.length ? t('maps.obj.removeWare') : t('maps.obj.addWare') }]}
                                label={t('maps.obj.wares')} onchange={(v) => setShopItem(o, wares, i, v)} />
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
                    <ItemPicker icon={false} value={st.gold ? GOLD : (st.item ?? '')} {items} label={t('maps.obj.gift')}
                                extra={[{ value: '', label: t('field.none') }, { value: GOLD, label: t('maps.obj.gold') }]}
                                onchange={(v) => setObject(o, v === GOLD ? { gold: st.gold || 1000, item: undefined } : { item: v, gold: undefined })} />
                  </label>
                  {#if st.gold}
                    <NumberField label={t('maps.obj.goldAmount')} value={st.gold} min={1} max={MAX_GOLD} compact onchange={(v) => setObject(o, { gold: v })} />
                  {:else if st.item && itemById.get(st.item)}
                    <Mention kind="items" id={st.item}><img class="pixel" src={itemIconUrl(itemById.get(st.item)!.iconId)} alt={itemById.get(st.item)!.name} title={itemById.get(st.item)!.name} /></Mention>
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
                {#if st.face && !objectsInfo?.faces.some((f) => f.id === st.face)}
                  {@const other = allFaces.find((f) => f.id === st.face)}
                  {#if other}
                    <button role="radio" aria-checked="true" class="active" title={faceLabel(other.id)}><img src={portraitUrl(other.portrait, true)} alt={other.id} /></button>
                  {/if}
                {/if}
                <button class="other-face" onclick={() => (pickingFace = !pickingFace)}>{t('maps.obj.otherFace')}</button>
              </div>
              {#if pickingFace}
                <FacePicker faces={allFaces} label={faceLabel} first={projectFaces} onclose={() => (pickingFace = false)}
                  onpick={(face) => { pickingFace = false; setObject(o, { face }) }} />
              {/if}
              <label>
                <span>{t('maps.obj.text')} <Help text={t('maps.obj.textHint')} /></span>
                <textarea rows="3" value={st.text ?? ''} onchange={(e) => setObject(o, { text: (e.target as HTMLTextAreaElement).value })}></textarea>
              </label>
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
  .ground-title { margin: 0.4rem 0 0; }
  .pieces.ground { max-height: none; }
  .map-settings summary { cursor: pointer; font-weight: 700; margin-bottom: 0.4rem; }
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
  .current-size { min-width: 4.5rem; }
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
  .map-scroll canvas.area { cursor: cell; }
  .layers button.active, .change-panel button.active { background: var(--accent-soft); border-color: var(--accent); font-weight: 600; }
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
  .ware :global(.picker) { width: 16rem; }
  .blank-icon { width: 16px; height: 16px; display: inline-block; }
  .faces { display: flex; flex-wrap: wrap; gap: 0.25rem; }
  .faces button { padding: 0.1rem; border-radius: 6px; line-height: 0; }
  .faces button.active { border-color: var(--accent); background: var(--accent-soft); }
  .faces img { width: 48px; height: 40px; image-rendering: pixelated; }
  .faces .other-face { padding: 0 0.5rem; line-height: 1.2; font-size: 0.8rem; }
  .pixel { image-rendering: pixelated; vertical-align: middle; }
  .transforms { display: flex; align-items: center; gap: 0.25rem; flex-wrap: wrap; }
  .transforms button { min-width: 2rem; padding: 0.15rem 0.4rem; font-size: 0.95rem; }
  .palette-panel p { margin: 0; }
  .palette-panel { display: flex; flex-direction: column; gap: 0.5rem; }
  .palette-panel h3 { margin: 0; }
  .brush { display: flex; align-items: center; gap: 0.6rem; }
  .brush canvas { border: 1px solid var(--border); image-rendering: pixelated; }
  .pieces { display: flex; flex-wrap: wrap; gap: 0.4rem; margin-top: 0.4rem; max-height: 260px; overflow: auto; }
  .piece { display: flex; flex-direction: column; align-items: center; gap: 0.15rem; padding: 0.3rem; }
  .piece.active { outline: 2px solid var(--accent); }
  .piece canvas { image-rendering: pixelated; width: auto; height: auto; max-width: 96px; }
  .palette-scroll { overflow: auto; max-width: 100%; max-height: calc(100vh - 420px); border: 1px solid var(--border); border-radius: 6px; width: fit-content; }
  .palette-scroll canvas { display: block; cursor: pointer; image-rendering: pixelated; }
  @media (max-width: 1000px) { .layout { grid-template-columns: 1fr; } }
  @media (max-width: 800px) { .editor { grid-template-columns: 1fr; } }
  .similar { display: flex; flex-wrap: wrap; align-items: center; gap: 0.4rem; padding: 0.4rem; border: 1px solid var(--accent); border-radius: 6px; background: var(--accent-soft); }
  .similar-tiles { display: flex; gap: 2px; }
  .similar-tiles canvas { image-rendering: pixelated; }
  .similar.nudge { border-color: var(--warn); }
  .pending-actions { display: flex; gap: 0.3rem; }
  .added-tiles summary { cursor: pointer; }
  .tile-tools { margin-top: 0.4rem; }
  .tile-tools summary { cursor: pointer; }
  .added-list { display: flex; flex-wrap: wrap; gap: 0.35rem; margin: 0.35rem 0; }
  .added { display: flex; flex-direction: column; align-items: center; gap: 0.1rem; }
  .added canvas { display: block; image-rendering: pixelated; }
  .added .tile-pick { padding: 0; line-height: 0; border: 1px solid var(--border); }
  .added .remove { font-size: 0.7rem; padding: 0 0.3rem; line-height: 1.3; }
  .tiled { display: flex; flex-wrap: wrap; align-items: center; gap: 0.4rem; margin-top: 0.4rem; }
  .tiled button { font-size: 0.8rem; padding: 0.15rem 0.5rem; }
  .palettes { display: flex; flex-wrap: wrap; align-items: center; gap: 0.4rem; margin-top: 0.4rem; }
  .palette-choice { display: flex; flex-direction: column; align-items: flex-start; gap: 0.15rem; padding: 0.25rem 0.4rem; }
  .palette-choice.active { border-color: var(--accent); background: var(--accent-soft); }
  .bases-panel { margin-top: 0.4rem; }
  .bases-panel summary { cursor: pointer; }
  .bases { display: flex; flex-wrap: wrap; gap: 0.4rem; margin: 0.3rem 0; }
  .base-choice { display: flex; flex-direction: column; align-items: flex-start; gap: 0.15rem; padding: 0.25rem; }
  .base-choice.active { border-color: var(--accent); background: var(--accent-soft); }
  .base-choice .thumb { width: 96px; height: 48px; background-repeat: no-repeat; background-position: 0 0; image-rendering: pixelated; border-radius: 3px; }
  .color-lines { display: flex; flex-direction: column; gap: 2px; margin: 0.4rem 0; }
  .color-line { display: flex; flex-wrap: wrap; gap: 2px; }
  .color-line input { width: 22px; height: 22px; padding: 0; border: 1px solid var(--border); border-radius: 3px; background: none; cursor: pointer; }
  .swatches { display: flex; }
  .swatches span { width: 8px; height: 12px; }
</style>
