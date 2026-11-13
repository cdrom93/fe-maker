<script lang="ts">
  import { hideBroken } from '../lib/hideBroken'
  import Help from './Help.svelte'
  import { onMount, untrack } from 'svelte'
  import { aiPreset } from '../lib/ai'
  import { OBJECTIVE_ICONS } from '../lib/objectiveIcons'
  import { appContext } from '../lib/appContext.svelte'
  import { api, chapterMapUrl, itemIconUrl, mapSpriteUrl } from '../lib/api'
  import type { EditableList } from '../lib/history.svelte'
  import { followFocus, useNavigator } from '../lib/navigation.svelte'
  import { problemText, t } from '../lib/i18n.svelte'
  import { statLabel, withMagic } from '../lib/magic.svelte'
  import type { ChapterInfo, ChapterUnits, ChaptersData, Character, ClassView, DialogueScene, Item, LevelBonus, MapUnit, MapsData, NewGroup, Objective, ObjectiveEdit, Problem, UnitGroup } from '../lib/types'
  import AiPanel from './AiPanel.svelte'
  import GenderSign from './GenderSign.svelte'
  import Mention from './Mention.svelte'
  import ItemPicker from './ItemPicker.svelte'
  import ClassPicker from './ClassPicker.svelte'
  import NumberField from './NumberField.svelte'
  import ChapterMusic from './ChapterMusic.svelte'
  import ChapterTitle from './ChapterTitle.svelte'
  import ObjectivePanel from './ObjectivePanel.svelte'
  import RecordList from './RecordList.svelte'

  let {
    list,
    maps,
    characters,
    gameLevels,
    classes,
    items,
    problems,
  }: {
    list: EditableList<ChaptersData>
    /** painted map layouts: the map shown is the project's one */
    maps: MapsData | undefined
    characters: Character[]
    gameLevels: Record<string, number>
    classes: ClassView[]
    items: Item[]
    problems: Problem[]
  } = $props()

  const CELL = 32 // 16 px tiles shown at x2
  const ITEM_SLOTS = 4
  /** 'night' (the game's WEATHER_NIGHT) is an unfinished blue backdrop that flickers on other screens (ticket 163):
   *  offered only to a chapter that already has it. */
  const WEATHERS = ['fine', 'clouds', 'rain', 'snow', 'snowstorm', 'sandstorm', 'flames']
  const LAST_BATTLE_BG_SET = 0x14
  const GROUP_SPRITES = 10
  const SHOWN_STATS = $derived(withMagic(['hp', 'pow', 'skl', 'spd', 'def', 'res', 'lck']))   // Magic: strMagSplit
  // The game's weapon type icons follow the item icons, in the weapon type order (0x70 + type, src/statscreen.c).
  const WTYPE_ICON = 0x70
  const RANK_TYPES = ['sword', 'lance', 'axe', 'bow', 'staff', 'anima', 'light', 'dark']
  const GENERIC = '0x80' // first generic character id: no name, portrait or personal data

  // Several chapters share an internal id in the original game: list them by index.
  let chapters = $state<(ChapterInfo & { name: string; code: string })[]>([])
  let selected = $state(0)
  let data = $state<ChapterUnits | null>(null)
  let hidden = $state<Record<string, boolean>>({})
  let picked = $state<{ group: string; index: number } | null>(null)
  let loading = $state(false)
  let dragging = $state<{ group: string; index: number } | null>(null)
  let mapEl = $state<HTMLDivElement>()
  let openGroup = $state<string | null>(null)
  /** The turn picked in the timeline (0: the start): the map shows the units there at that turn (ticket 153). */
  let focusTurn = $state<number | null>(null)
  let showCutscenes = $state(false)
  /** the map's change shown under the units */
  let shownChange = $state<number | null>(null)
  let unitStats = $state<Record<string, number> | null>(null)
  let unitRanks = $state<Record<string, string>>({})

  const chapter = $derived(chapters[selected])

  const convoyEdit = $derived(chapter ? list.records[0]?.convoy?.[String(chapter.index)] : undefined)

  /** Convoy available in this chapter (ticket 29); the game's value is not stored. */
  function setConvoy(on: boolean) {
    if (!chapter) return
    const key = String(chapter.index)
    const same = on === chapter.convoy
    list.update(0, (c) => {
      c.convoy ??= {}
      if (same) delete c.convoy[key]
      else c.convoy[key] = on
    })
  }
  const prepEdit = $derived(chapter ? list.records[0]?.prep?.[String(chapter.index)] : undefined)

  /** Preparations screen before the battle (ticket 107); the default value is not stored. */
  function setPrep(on: boolean) {
    if (!chapter) return
    const key = String(chapter.index)
    const same = on === chapter.prep
    list.update(0, (c) => {
      c.prep ??= {}
      if (same) delete c.prep[key]
      else c.prep[key] = on
    })
  }
  const fogEdit = $derived(chapter ? list.records[0]?.fog?.[String(chapter.index)] : undefined)
  const fog = $derived(fogEdit ?? chapter?.fog ?? 0)

  /** Fog of war: the units' vision range (0: no fog); the game's value is not stored. */
  function setFog(level: number) {
    if (!chapter) return
    const key = String(chapter.index)
    const same = level === chapter.fog
    list.update(0, (c) => {
      c.fog ??= {}
      if (same) delete c.fog[key]
      else c.fog[key] = level
    })
  }
  // Weather, battle background and the camera's first cell: the game's values are not stored.
  const lookEdit = <K extends 'weather' | 'battleBg' | 'camera'>(field: K) =>
    chapter ? (list.records[0]?.[field] as Record<string, ChapterInfo[K]> | undefined)?.[String(chapter.index)] : undefined
  function setLook<K extends 'weather' | 'battleBg' | 'camera'>(field: K, value: ChapterInfo[K]) {
    if (!chapter) return
    const key = String(chapter.index)
    const same = JSON.stringify(value) === JSON.stringify(chapter[field])
    list.update(0, (c) => {
      const stored = ((c as unknown as Record<string, unknown>)[field] ??= {}) as Record<string, unknown>
      if (same) delete stored[key]
      else stored[key] = value
    })
  }
  const weather = $derived(lookEdit('weather') ?? chapter?.weather ?? 'fine')
  const battleBg = $derived(lookEdit('battleBg') ?? chapter?.battleBg ?? 0)
  const camera = $derived(lookEdit('camera') ?? chapter?.camera ?? [0, 0])
  let pickingCamera = $state(false)
  /** The camera is picked on the map, above the folded settings. */
  function pickCamera() {
    pickingCamera = !pickingCamera
    pickingSeize = false
    if (pickingCamera) mapEl?.scrollIntoView({ behavior: 'smooth', block: 'center' })
  }
  /** What the folded settings hold, in a few words. */
  const settingsSummary = $derived(chapter ? [
    t(`weather.${weather}`),
    battleBg === 0 ? t('chapter.battleBgDefault') : t('chapter.battleBgSet', { n: battleBg }),
    ...((convoyEdit ?? chapter.convoy) ? [t('chapter.convoy')] : []),
    ...(fog > 0 ? [t('chapter.fog')] : []),
  ].join(' · ') : '')
  /** Battle background sets with the game's chapters that use them. */
  const battleBgSets = $derived(Array.from({ length: LAST_BATTLE_BG_SET + 1 }, (_, n) => {
    const users = [...new Set(chapters.filter((c) => c.battleBg === n && c.title).map((c) => c.title))]
    return { n, users: users.slice(0, 3).join(', ') + (users.length > 3 ? '…' : '') }
  }))
  const wallHpEdit = $derived(chapter ? list.records[0]?.wallHp?.[String(chapter.index)] : undefined)

  /** HP of the map's cracked walls; the game's value is not stored. */
  function setWallHp(hp: number) {
    if (!chapter) return
    const key = String(chapter.index)
    const same = hp === chapter.wallHp
    list.update(0, (c) => {
      c.wallHp ??= {}
      if (same) delete c.wallHp[key]
      else c.wallHp[key] = hp
    })
  }
  const levelBonus = $derived(chapter ? (list.records[0]?.levelBonus?.[String(chapter.index)] ?? chapter.levelBonus) : undefined)
  const levelBonusEdited = $derived(chapter ? list.records[0]?.levelBonus?.[String(chapter.index)] !== undefined : false)
  /** The game's values are not stored. */
  function setLevelBonus(mode: keyof LevelBonus, n: number) {
    if (!chapter || !levelBonus) return
    const key = String(chapter.index)
    const next = { ...$state.snapshot(levelBonus), [mode]: n }
    const same = (Object.keys(next) as (keyof LevelBonus)[]).every((m) => next[m] === chapter.levelBonus[m])
    list.update(0, (c) => {
      c.levelBonus ??= {}
      if (same) delete c.levelBonus[key]
      else c.levelBonus[key] = next
    })
  }
  // The map image changes with the project's painting of this chapter's layout.
  const mapVersion = $derived.by(() => {
    const rows = chapter?.map ? maps?.layouts?.[chapter.map]?.rows : undefined
    if (!rows) return ''
    let h = 0
    for (const row of rows) for (const m of row) h = (h * 31 + m + 1) | 0
    return (h >>> 0).toString(36)
  })

  // The chapter's groups, and the reinforcements made in the project.
  const newGroups = $derived(Object.entries(list.records[0]?.newGroups ?? {}).filter(([, g]) => g.chapter === chapter?.index))
  const groups = $derived<UnitGroup[]>([
    ...(data?.groups ?? []).map((g) => ({ ...g, turn: list.records[0]?.groupTurns?.[g.name]?.turn ?? g.turn })),
    ...newGroups.map(([name, g]) => ({ name, origin: g.scene ? ('scene' as const) : ('turn' as const), turn: g.scene ? null : g.turn, units: [], edited: true, new: true })),
  ])
  const openNew = $derived(openGroup ? list.records[0]?.newGroups?.[openGroup] : undefined)
  /** One of the game's reinforcement groups, open: its turn can change (ticket 109). */
  const openTurnGroup = $derived(!openNew ? groups.find((g) => g.name === openGroup && g.origin === 'turn') : undefined)
  const clearedChapter = $derived(!!chapter && !!list.records[0]?.cleared?.includes(chapter.index))

  /** A new group only scenes bring (their command "Faire venir un groupe d'unités"): empty, to fill on the map. */
  function addSceneGroup() {
    if (!chapter) return
    const taken = new Set(Object.keys(list.records[0]?.newGroups ?? {}))
    let n = 0
    while (taken.has(`UnitDef_FEM_${chapter.index}_${n}`)) n++
    const name = `UnitDef_FEM_${chapter.index}_${n}`
    const index = chapter.index
    list.update(0, (c) => {
      c.newGroups ??= {}
      c.newGroups[name] = { chapter: index, turn: 1, phase: 'enemy', scene: true }
      c.unitGroups[name] = []
    })
    hidden[name] = false
    openGroup = name
    picked = null
  }

  /** New reinforcements: one copy of the chapter's first enemy (or a generic unit), at turn 2. */
  function addReinforcements() {
    if (!chapter) return
    const taken = new Set(Object.keys(list.records[0]?.newGroups ?? {}))
    let n = 0
    while (taken.has(`UnitDef_FEM_${chapter.index}_${n}`)) n++
    const name = `UnitDef_FEM_${chapter.index}_${n}`
    const enemy = battleGroups.flatMap((g) => unitsOf(g.name)).find((u) => u.side === 'enemy')
    const [x, y] = freeTileNear(enemy?.endX ?? 0, enemy?.endY ?? 0)
    const unit: MapUnit = enemy
      ? { ...(structuredClone($state.snapshot(enemy)) as MapUnit), slot: null, copyOf: null, fixedPath: false, x, y, endX: x, endY: y }
      : { slot: null, copyOf: null, level: 1, autolevel: true, items: [], ai: [0, 0, 0, 0], side: 'enemy', character: GENERIC,
          class: classes.find((k) => k.usedInGame)?.id ?? classes[0]?.id ?? '', x, y, endX: x, endY: y }
    const index = chapter.index
    list.update(0, (c) => {
      c.newGroups ??= {}
      c.newGroups[name] = { chapter: index, turn: 2, phase: 'enemy' }
      c.unitGroups[name] = [unit]
    })
    hidden[name] = false
    openGroup = name
    picked = { group: name, index: 0 }
  }

  /** A copy of a group as new reinforcements (ticket 42): same units and places, one turn later. */
  function duplicateGroup(source: string) {
    if (!chapter) return
    const taken = new Set(Object.keys(list.records[0]?.newGroups ?? {}))
    let n = 0
    while (taken.has(`UnitDef_FEM_${chapter.index}_${n}`)) n++
    const name = `UnitDef_FEM_${chapter.index}_${n}`
    const units = unitsOf(source).map(
      (u) => ({ ...(structuredClone($state.snapshot(u)) as MapUnit), slot: null, copyOf: null, fixedPath: false }),
    )
    const from = groups.find((g) => g.name === source)
    const fromNew = list.records[0]?.newGroups?.[source]
    const phase: NewGroup['phase'] = fromNew?.phase ?? (units.length && units.every((u) => u.side === 'ally') ? 'ally' : 'enemy')
    const turn = Math.min(99, (fromNew?.turn ?? (from?.origin === 'turn' ? from.turn ?? 1 : 1)) + 1)
    const index = chapter.index
    list.update(0, (c) => {
      c.newGroups ??= {}
      c.newGroups[name] = { chapter: index, turn, phase }
      c.unitGroups[name] = units
    })
    hidden[name] = false
    openGroup = name
    picked = null
  }

  function editNewGroup(name: string, change: Partial<NewGroup>) {
    list.update(0, (c) => {
      if (c.newGroups?.[name]) Object.assign(c.newGroups[name], change)
    })
  }

  function editGroupTurn(name: string, change: { turn?: number; phase?: NewGroup['phase'] }) {
    if (!chapter) return
    const index = chapter.index
    list.update(0, (c) => {
      c.groupTurns ??= {}
      c.groupTurns[name] = { ...c.groupTurns[name], chapter: index, ...change }
    })
  }

  function removeNewGroup(name: string) {
    openGroup = null
    picked = null
    list.update(0, (c) => {
      delete c.newGroups?.[name]
      delete c.unitGroups[name]
    })
  }

  const nav = useNavigator()
  followFocus('chapters', nav, () => chapters.map((c) => c.id), (i) => load(i))
  // Groups whose units only appear in a cutscene before the battle (other map).
  // In the order of play: the first units, then the turns.
  const turnOf = (g: ChapterUnits['groups'][number]) => (g.origin === 'turn' ? (g.turn ?? 99) : 0)
  const battleGroups = $derived(groups.filter((g) => g.origin !== 'cutscene' && g.origin !== 'scene').sort((a, b) => turnOf(a) - turnOf(b)))
  /** Groups the project made for its scenes, with the scenes that bring them. */
  const sceneGroups = $derived(groups.filter((g) => g.origin === 'scene'))
  let sceneLabels = $state<Record<string, string>>({})
  /** Events made in the Dialogues tab, as the server names them in loadedBy. */
  const NEW_EVENT_LABELS: Record<string, string> = { 'new:turn': 'dlg.addTurn', 'new:area': 'dlg.addArea', 'new:flag': 'dlg.addFlag' }
  const broughtBy = (name: string) => (data?.loadedBy?.[name] ?? []).map((s) => NEW_EVENT_LABELS[s] ? t(NEW_EVENT_LABELS[s]) : sceneLabels[s] ?? s)
  // One row per turn where units come: the start, then each reinforcement turn (ticket 153).
  const turnRows = $derived.by(() => {
    const rows = new Map<number, typeof battleGroups>()
    for (const g of battleGroups) rows.set(turnOf(g), [...(rows.get(turnOf(g)) ?? []), g])
    return [...rows].map(([turn, list]) => ({ turn, groups: list }))
  })
  // A chapter rewritten from scratch (newchapter.py) loses the game's scenes: their groups, emptied, are left out.
  const cutsceneGroups = $derived(groups.filter((g) => g.origin === 'cutscene' && !(clearedChapter && !unitsOf(g.name).length)))
  const pickedOrigin = $derived(picked ? groups.find((g) => g.name === picked!.group)?.origin : undefined)
  const edits = $derived(list.records[0]?.unitGroups ?? {})

  // Objective: the original one, overridden by the project's edit.
  let originalObjective = $state<Objective | null>(null)
  let pickingSeize = $state(false)
  const objectiveKey = $derived(chapter ? String(chapter.index) : '')
  const objectiveEdit = $derived(list.records[0]?.objectives?.[objectiveKey])
  const objective = $derived(originalObjective ? { ...originalObjective, ...(objectiveEdit ?? {}) } : null)
  const objectiveProblems = $derived(problems.filter((p) => p.kind === 'chapters' && p.id === `objective#${objectiveKey}`))

  function editObjective(change: Partial<ObjectiveEdit>) {
    if (!objective) return
    const key = objectiveKey
    const base: ObjectiveEdit = {
      type: objective.type, seize: objective.seize, seizeLabel: objective.seizeLabel, turns: objective.turns, statusText: objective.statusText, boss: objective.boss,
    }
    list.update(0, (c) => {
      c.objectives ??= {}
      c.objectives[key] = $state.snapshot({ ...base, ...change }) as ObjectiveEdit
    })
  }

  function resetObjective() {
    const key = objectiveKey
    list.update(0, (c) => {
      if (c.objectives) delete c.objectives[key]
    })
  }

  // The area being drawn ("reach an area" objective): dragged from one corner to the other, as in AreaPicker.svelte.
  let areaDrag = $state<{ x: number; y: number; x2: number; y2: number } | null>(null)
  const drawingArea = $derived(pickingSeize && objective?.type === 'area')

  function tileAt(e: MouseEvent): [number, number] {
    const rect = mapEl!.getBoundingClientRect()
    return [Math.max(0, Math.min(data!.width - 1, Math.floor((e.clientX - rect.left) / CELL))),
            Math.max(0, Math.min(data!.height - 1, Math.floor((e.clientY - rect.top) / CELL)))]
  }

  function areaDown(e: PointerEvent) {
    if (!drawingArea || !mapEl || !data) return
    e.preventDefault()
    const [x, y] = tileAt(e)
    areaDrag = { x, y, x2: x, y2: y }
    mapEl.setPointerCapture(e.pointerId)
  }

  function areaMove(e: PointerEvent) {
    if (!areaDrag) return
    const [x, y] = tileAt(e)
    areaDrag = { ...areaDrag, x2: x, y2: y }
  }

  function areaUp() {
    const a = areaDrag
    if (!a) return
    areaDrag = null
    editObjective({ area: { x1: Math.min(a.x, a.x2), y1: Math.min(a.y, a.y2), x2: Math.max(a.x, a.x2), y2: Math.max(a.y, a.y2) } })
    pickingSeize = false
  }

  /** Map click while choosing the tile to seize, or the two corners of the area to reach. */
  function pickTile(e: MouseEvent) {
    if ((!pickingSeize && !pickingCamera) || !mapEl || !data) return
    const rect = mapEl.getBoundingClientRect()
    const x = Math.max(0, Math.min(data.width - 1, Math.floor((e.clientX - rect.left) / CELL)))
    const y = Math.max(0, Math.min(data.height - 1, Math.floor((e.clientY - rect.top) / CELL)))
    if (pickingCamera) {
      setLook('camera', [x, y])
      pickingCamera = false
      return
    }
    if (objective?.type === 'area') return   // drawn by dragging (areaDown...)
    editObjective({ seize: [{ x, y }] })
    pickingSeize = false
  }
  const charById = $derived(new Map(characters.map((c) => [c.id, c])))
  const classById = $derived(new Map(classes.map((k) => [k.id, k])))
  const itemById = $derived(new Map(items.map((i) => [i.id, i])))
  const weapons = $derived(items)

  /** Units of a group: the project's version once edited, the original otherwise. */
  function unitsOf(name: string): MapUnit[] {
    return edits[name] ?? groups.find((g) => g.name === name)?.units ?? []
  }
  const unit = $derived(picked ? unitsOf(picked.group)[picked.index] : undefined)
  $effect(() => {
    if (!unit) return
    let stale = false
    api.unitStats({ character: unit.character, classId: effectiveClass(unit), level: shownLevel(unit), autolevel: unit.autolevel,
                    side: unit.side, items: [...unit.items] })
      .then((r) => {
        if (!stale) [unitStats, unitRanks] = [r.stats, r.ranks]
      })
      .catch(() => {
        if (!stale) [unitStats, unitRanks] = [null, {}]
      })
    return () => {
      stale = true
    }
  })

  // On the map: where the picked unit can go (blue), strike (red) and use its staves (green, ticket 157),
  // or all the enemies' danger zone.
  let danger = $state(false)
  let reach = $state<{ move: [number, number][]; strike: [number, number][]; heal: [number, number][] }>({ move: [], strike: [], heal: [] })
  const asked = $derived.by(() => {
    const shown = danger ? groups.flatMap((g) => unitsOf(g.name)).filter((u) => u.side === 'enemy') : unit ? [unit] : []
    return JSON.stringify(shown.map((u) => ({ classId: effectiveClass(u), x: u.endX, y: u.endY, items: u.items,
                                              ai: u.side === 'enemy' && Array.isArray(u.ai) ? u.ai : undefined,
                                              mag: !danger && unitStats ? (unitStats.mag ?? unitStats.pow) : 0 })))
  })
  $effect(() => {
    const body = JSON.parse(asked)
    const index = chapter?.index
    if (index === undefined || !body.length) {
      reach = { move: [], strike: [], heal: [] }
      return
    }
    api.chapterReach(index, body).then((r) => {
      if (index === chapter?.index) reach = r
    }).catch(() => {})
  })
  // Selecting a unit (on the map) shows its group's list if a list is open. Only a new
  // selection triggers this: opening another group must not bring the old one back.
  $effect(() => {
    const group = picked?.group
    untrack(() => {
      if (group && openGroup && openGroup !== group) openGroup = group
    })
  })

  function toggleGroup(name: string) {
    openGroup = openGroup === name ? null : name
    if (openGroup && picked && picked.group !== openGroup) picked = null
  }

  // Tell feedback tickets which unit is open.
  $effect(() => {
    appContext.detail = unit && picked ? `${picked.group} #${picked.index} · ${unitName(unit)} · ${classById.get(effectiveClass(unit))?.name ?? effectiveClass(unit)}` : ''
    return () => (appContext.detail = '')
  })

  const unitProblems = $derived(
    picked ? problems.filter((p) => p.kind === 'chapters' && p.id === `${picked!.group}#${picked!.index}`) : [],
  )

  onMount(async () => {
    const all = await api.chapters()
    chapters = all.filter((c) => !c.hidden).map((c) => ({ ...c, code: c.id, id: String(c.index), name: c.title || c.id }))
    // Opened from a link (e.g. the map editor): the chapter list was not loaded yet.
    const asked = nav.focus?.kind === 'chapters' ? chapters.findIndex((c) => c.id === nav.focus!.id) : -1
    if (chapters.length) await load(Math.max(0, asked))
  })

  /** Its text and its title picture are written at build time; empty: the game's title again. */
  async function rename(name: string) {
    const index = chapter.index
    list.update(0, (d) => {
      const titles: Record<string, string> = { ...d.titles, [index]: name }
      if (!name) delete titles[index]
      d.titles = titles
    })
    if (!name) await list.flush()
    const title = name || ((await api.chapters()).find((c) => c.index === index)?.title ?? '')
    chapters = chapters.map((c) => (c.index === index ? { ...c, title, name: title || c.code } : c))
  }

  async function load(index: number) {
    selected = index
    picked = null
    openGroup = null
    focusTurn = null
    shownChange = null
    pickingSeize = false
    pickingCamera = false
    loading = true
    data = null
    originalObjective = null
    try {
      api.chapterObjective(chapters[index].index).then((o) => {
        if (selected === index) originalObjective = o
      })
      api.chapterDialogues(chapters[index].index).then((d) => {
        if (selected === index) sceneLabels = Object.fromEntries(d.scenes.map((sc) => [sc.script, sceneLabel(sc)]))
      }).catch(() => {})
      data = await api.chapterUnits(chapters[index].index)
      hidden = Object.fromEntries(groups.map((g) => [g.name, g.origin === 'cutscene']))
    } finally {
      loading = false
    }
  }

  /** Edit a group's units; the first edit of a group copies it into the project. */
  function editGroup(group: string, change: (units: MapUnit[]) => void) {
    const original = unitsOf(group)
    list.update(0, (c) => {
      if (!c.unitGroups[group]) c.unitGroups[group] = structuredClone($state.snapshot(original)) as MapUnit[]
      change(c.unitGroups[group])
    })
  }

  function editUnit(group: string, index: number, change: (u: MapUnit) => void) {
    editGroup(group, (units) => change(units[index]))
  }

  /** Nearest tile, from (x, y), where no unit of the chapter starts. */
  function freeTileNear(x: number, y: number): [number, number] {
    if (!data) return [x, y]
    const taken = new Set(battleGroups.flatMap((g) => unitsOf(g.name).map((u) => `${u.endX},${u.endY}`)))
    const seen = new Set<string>()
    const queue: [number, number][] = [[x, y]]
    while (queue.length) {
      const [cx, cy] = queue.shift()!
      const key = `${cx},${cy}`
      if (seen.has(key) || cx < 0 || cy < 0 || cx >= data.width || cy >= data.height) continue
      seen.add(key)
      if (!taken.has(key)) return [cx, cy]
      queue.push([cx + 1, cy], [cx - 1, cy], [cx, cy + 1], [cx, cy - 1])
    }
    return [x, y]
  }

  /** Add a copy of a unit (by default the group's last one) on a free tile next to it. */
  function addUnit(group: string, template?: MapUnit) {
    const current = unitsOf(group)
    const base = template ?? current[current.length - 1]
    const origin = groups.find((g) => g.name === group)?.origin
    const [x, y] = freeTileNear(base?.endX ?? Math.floor((data?.width ?? 2) / 2), base?.endY ?? Math.floor((data?.height ?? 2) / 2))
    const unit: MapUnit = base
      ? { ...(structuredClone($state.snapshot(base)) as MapUnit), slot: null, copyOf: base.slot ?? base.copyOf ?? null, fixedPath: false }
      : {
          slot: null, copyOf: null, level: 1, autolevel: origin !== 'players', items: [], ai: [0, 0, 0, 0],
          side: origin === 'players' ? 'player' : 'enemy',
          character: origin === 'players' ? (characters[0]?.id ?? GENERIC) : GENERIC,
          class: classes.find((k) => k.usedInGame)?.id ?? classes[0]?.id ?? '',
          x, y, endX: x, endY: y,
        }
    Object.assign(unit, { x, y, endX: x, endY: y })
    // A new ally is another character: the previous one's items would only be in the way (ticket 150).
    if (!template && unit.side === 'player') Object.assign(unit, { items: [], itemDrop: false })
    editGroup(group, (units) => units.push(unit))
    hidden[group] = false
    picked = { group, index: current.length }
  }

  function removeUnit(group: string, index: number) {
    editGroup(group, (units) => units.splice(index, 1))
    picked = null
  }

  function drop(e: DragEvent) {
    e.preventDefault()
    if (!dragging || !mapEl || !data) return
    const rect = mapEl.getBoundingClientRect()
    const x = Math.max(0, Math.min(data.width - 1, Math.floor((e.clientX - rect.left) / CELL)))
    const y = Math.max(0, Math.min(data.height - 1, Math.floor((e.clientY - rect.top) / CELL)))
    const { group, index } = dragging
    editUnit(group, index, (u) => {
      u.endX = x
      u.endY = y
    })
    picked = { group, index }
    dragging = null
  }

  function setItem(slot: number, id: string) {
    if (!picked) return
    editUnit(picked.group, picked.index, (u) => {
      const next = [...u.items]
      next[slot] = id
      u.items = next.filter(Boolean)
    })
  }

  /** Named characters have a sheet: their class comes from it (the only source of truth). */
  const isNamed = (u: MapUnit) => u.character.startsWith('CHARACTER_') && charById.has(u.character)
  /** A named ally's level is set on their sheet. Units that level up by themselves keep theirs (server: _with_sheet_levels). */
  const levelFromSheet = (u: MapUnit) => u.side === 'player' && isNamed(u) && !u.autolevel
  function shownLevel(u: MapUnit): number {
    const sheet = charById.get(u.character)?.level
    if (!levelFromSheet(u) || sheet === undefined) return u.level
    return u.slot === null || sheet !== gameLevels[u.character] ? Math.min(sheet, 31) : u.level
  }
  function effectiveClass(u: MapUnit): string {
    return isNamed(u) ? charById.get(u.character)!.class : u.class
  }

  function unitName(u: MapUnit): string {
    return charById.get(u.character)?.name || t('chapter.generic')
  }

  function battleUnitOf(character: string): { group: string; index: number } | null {
    for (const g of battleGroups) {
      const index = unitsOf(g.name).findIndex((u) => u.character === character)
      if (index >= 0) return { group: g.name, index }
    }
    return null
  }

  function sceneLabel(sc: DialogueScene): string {
    const tr = sc.trigger
    const key = `dlg.trigger.${tr.kind}`
    const text = t(key, { n: tr.turn ?? '', a: tr.a ?? '', b: tr.b ?? '', x: tr.x ?? '', y: tr.y ?? '' })
    return text === key ? sc.script : text
  }

  function originLabel(origin: string, turn: number | null): string {
    return origin === 'turn' ? t('chapter.origin.turn', { n: turn ?? '?' }) : t(`chapter.origin.${origin}`)
  }
</script>

<div class="editor">
  <RecordList records={chapters} {selected} onselect={(i) => load(i)} secondary={(c) => !c.title} secondaryLabel={t('list.otherChapters')} problemIds={new Set()}>
    {#snippet suffix(c: ChapterInfo & { code: string })}<span class="muted id">{c.code}</span>{/snippet}
  </RecordList>

  {#if chapter}
    <div class="detail">
      <section class="panel">
        <h2><ChapterTitle title={chapter.title || chapter.code} value={chapter.title} onrename={rename} /> <span class="muted id">{chapter.code}</span> <Help text={t('chapter.editHint')} /></h2>
        {#if objective}
          <ObjectivePanel {objective} edited={!!objectiveEdit} problems={objectiveProblems} bind:picking={pickingSeize} {characters}
            battleCharacters={new Set(battleGroups.flatMap((g) => unitsOf(g.name).map((u) => u.character)))}
            originalBoss={originalObjective?.boss ?? null} onchange={editObjective} onreset={resetObjective} />
        {/if}
      </section>

      <section class="panel">
        {#if data}
          {#snippet groupChip(g: ChapterUnits['groups'][number], short = false)}
              {@const shown = unitsOf(g.name)}
              <div class="group" class:open={openGroup === g.name}>
                <input type="checkbox" title={t('chapter.showGroup')} aria-label={t('chapter.showGroup')} checked={!hidden[g.name]} onchange={(e) => (hidden[g.name] = !(e.target as HTMLInputElement).checked)} />
                <button class="group-name" title="{t('chapter.openGroup')} ({g.name.replace('UnitDef_Event_', '')})" onclick={() => toggleGroup(g.name)}>
                  <span>{short && g.origin === 'turn' ? t('chapter.origin.turnShort') : originLabel(g.origin, g.turn)} <span class="muted tiny">{shown.length}</span>{#if edits[g.name]} <span class="edited">✎</span>{/if}</span>
                  <span class="group-sprites">
                    {#each shown.slice(0, GROUP_SPRITES) as u, i (i)}<img src={mapSpriteUrl(effectiveClass(u), u.side, true)} alt="" use:hideBroken />{/each}
                    {#if shown.length > GROUP_SPRITES}<span class="muted tiny">+{shown.length - GROUP_SPRITES}</span>{/if}
                  </span>
                </button>
                <button class="add" title={t('chapter.addUnit')} aria-label={t('chapter.addUnit')} onclick={() => addUnit(g.name)}>＋</button>
              </div>
          {/snippet}
          <h3 class="groups-title">{t('chapter.battleGroups')}</h3>
          <div class="timeline">
            {#each turnRows as row (row.turn)}
              <button class="turn" class:focus={focusTurn === row.turn} title={t('chapter.turnFocusHint')}
                      onclick={() => (focusTurn = focusTurn === row.turn ? null : row.turn)}>
                {row.turn ? t('chapter.turnRow', { n: row.turn }) : t('chapter.turnStart')}
              </button>
              <div class="groups">
                {#each row.groups as g (g.name)}{@render groupChip(g, true)}{/each}
              </div>
            {/each}
            {#if sceneGroups.length}
              <span class="turn scenes">{t('chapter.sceneRow')}</span>
              <div class="groups">
                {#each sceneGroups as g (g.name)}{@render groupChip(g)}{/each}
              </div>
            {/if}
          </div>
          <div class="row timeline-tools">
            <button class="add-group" title={t('chapter.addReinforcementsHint')} onclick={addReinforcements}>＋ {t('chapter.addReinforcements')}</button>
            <button class="add-group" title={t('chapter.addSceneGroupHint')} onclick={addSceneGroup}>＋ {t('chapter.addSceneGroup')}</button>
            <Help text={t('chapter.timelineHint')} />
          </div>
          {#if cutsceneGroups.length}
            <details class="cutscenes" bind:open={showCutscenes}>
              <summary>{t('chapter.cutsceneGroups', { n: cutsceneGroups.length })} <Help text={t('chapter.cutsceneHint')} /></summary>
              <div class="groups">
                {#each cutsceneGroups as g (g.name)}{@render groupChip(g)}{/each}
              </div>
            </details>
          {/if}
          {#if openGroup && groups.some((g) => g.name === openGroup)}
            {@const og = openGroup}
            <div class="group-units">
              {#if openNew?.scene}
                {@const by = broughtBy(og)}
                <div class="row new-group">
                  {#if by.length}
                    <span class="small">{t('chapter.broughtBy')} {#each by as label, k (k)}{k ? ', ' : ''}<Mention kind="dialogues" id={String(chapter.index)}>{label}</Mention>{/each}</span>
                  {:else}
                    <span class="warn small">{t('chapter.notBrought')}</span>
                  {/if}
                  <button class="danger" onclick={() => removeNewGroup(og)}>{t('chapter.removeSceneGroup')}</button>
                  <Help text={t('chapter.sceneGroupHint')} />
                </div>
              {:else if openNew}
                <div class="row new-group">
                  <NumberField label={t('dlg.turn')} value={openNew.turn} min={1} max={99} compact onchange={(v) => editNewGroup(og, { turn: v })} />
                  <label>
                    <span>{t('dlg.phase')}</span>
                    <select value={openNew.phase} onchange={(e) => editNewGroup(og, { phase: (e.target as HTMLSelectElement).value as NewGroup['phase'] })}>
                      {#each ['enemy', 'player', 'ally'] as ph (ph)}<option value={ph}>{t(`dlg.phase.${ph}`)}</option>{/each}
                    </select>
                  </label>
                  <button class="danger" onclick={() => removeNewGroup(og)}>{t('chapter.removeReinforcements')}</button>
                  <Help text={t('chapter.newGroupHint')} />
                </div>
              {:else if openTurnGroup}
                <div class="row new-group">
                  <NumberField label={t('dlg.turn')} value={openTurnGroup.turn ?? 1} min={1} max={99} compact onchange={(v) => editGroupTurn(og, { turn: v })} />
                  {#if clearedChapter}
                    <label>
                      <span>{t('dlg.phase')}</span>
                      <select value={list.records[0]?.groupTurns?.[og]?.phase ?? (unitsOf(og).every((u) => u.side === 'ally') ? 'ally' : 'enemy')}
                        onchange={(e) => editGroupTurn(og, { phase: (e.target as HTMLSelectElement).value as NewGroup['phase'] })}>
                        {#each ['enemy', 'player', 'ally'] as ph (ph)}<option value={ph}>{t(`dlg.phase.${ph}`)}</option>{/each}
                      </select>
                    </label>
                  {/if}
                </div>
              {/if}
              {#if !cutsceneGroups.some((g) => g.name === og) && !openNew?.scene && unitsOf(og).length}
                <button class="dup" title={t('chapter.duplicateGroupHint')} onclick={() => duplicateGroup(og)}>⧉ {t('chapter.duplicateGroup')}</button>
              {/if}
              <table>
                <thead>
                  <tr><th></th><th>{t('chapter.character')}</th><th>{t('field.class')}</th><th>{t('chapter.levelShort')}</th><th>{t('chapter.positionShort')}</th><th>{t('ai.preset')}</th></tr>
                </thead>
                <tbody>
                  {#each unitsOf(og) as u, i (i)}
                    <tr class:picked={picked?.group === og && picked.index === i} onclick={() => (picked = { group: og, index: i })}>
                      <td class="sprite"><img src={mapSpriteUrl(effectiveClass(u), u.side, true)} alt="" use:hideBroken /></td>
                      <td><button class="link" onclick={() => (picked = { group: og, index: i })}>{unitName(u)}</button></td>
                      <td>{classById.get(effectiveClass(u))?.name ?? effectiveClass(u)}<GenderSign gender={classById.get(effectiveClass(u))?.gender} /></td>
                      <td>{shownLevel(u)}</td>
                      <td>{u.endX}, {u.endY}</td>
                      <td class="muted">{t(`ai.preset.${aiPreset(u.ai)}`)}</td>
                    </tr>
                  {/each}
                </tbody>
              </table>
              {#if !unitsOf(og).length}<p class="muted small">{t('chapter.emptyGroup')}</p>{/if}
              <div class="row">
                <button onclick={() => addUnit(og)}>＋ {t('chapter.addUnitShort')}</button>
                <button onclick={() => (openGroup = null)}>{t('build.close')}</button>
              </div>
            </div>
          {/if}
          {#each problems.filter((pr) => pr.kind === 'chapters' && groups.some((g) => pr.id === `${g.name}#`)) as pr, i (i)}
            <p class="bad small">{pr.id.replace('UnitDef_Event_', '').replace('#', '')} : {problemText(pr)}</p>
          {/each}
        {/if}
      </section>

      <div class="layout">
        <section class="panel map-panel">
          {#if loading}<p class="muted">…</p>{/if}
          {#if data && data.width}
            <div class="map-tools">
              <label class="danger"><input type="checkbox" bind:checked={danger} /> {t('chapter.dangerZone')}</label>
              {#if data.changes.length}
                <label class="shown-map">
                  <span>{t('chapter.mapShown')}</span>
                  <select bind:value={shownChange}>
                    <option value={null}>{t('chapter.mapMain')}</option>
                    {#each data.changes as c (c.id)}<option value={c.id}>{t('chapter.mapChange', { id: c.id, x: c.x, y: c.y })}</option>{/each}
                  </select>
                </label>
              {:else if chapter.map}
                <span class="muted tiny">{t('chapter.noMapChange')} <Mention kind="maps" id={chapter.map}>{t('flow.openMap')}</Mention></span>
              {/if}
            </div>
            <div
              class="map"
              class:picking={pickingSeize || pickingCamera}
              onpointerdown={areaDown}
              onpointermove={areaMove}
              onpointerup={areaUp}
              role="application"
              bind:this={mapEl}
              onclickcapture={(e) => {
                if (pickingSeize || pickingCamera) {
                  e.stopPropagation()
                  pickTile(e)
                }
              }}
              style="width: {data.width * CELL}px; height: {data.height * CELL}px; background-image: url({chapterMapUrl(chapter.index, mapVersion, shownChange)})"
              ondragover={(e) => e.preventDefault()}
              ondrop={drop}
            >
              {#if objective?.type === 'area' && (objective.area || areaDrag)}
                {@const a = areaDrag
                  ? { x1: Math.min(areaDrag.x, areaDrag.x2), y1: Math.min(areaDrag.y, areaDrag.y2), x2: Math.max(areaDrag.x, areaDrag.x2), y2: Math.max(areaDrag.y, areaDrag.y2) }
                  : objective.area!}
                <span class="area-marker" style="left: {a.x1 * CELL}px; top: {a.y1 * CELL}px; width: {(a.x2 - a.x1 + 1) * CELL}px; height: {(a.y2 - a.y1 + 1) * CELL}px" title={t('objective.type.area')}><img class="pixel" src={itemIconUrl(OBJECTIVE_ICONS.area)} alt="" /></span>
              {/if}
              {#each reach.move as [x, y] (`${x},${y}`)}
                {#if !danger}<span class="reach move" style="left: {x * CELL}px; top: {y * CELL}px"></span>{/if}
              {/each}
              {#if !danger}
                {#each reach.heal as [x, y] (`${x},${y}`)}<span class="reach heal" style="left: {x * CELL}px; top: {y * CELL}px"></span>{/each}
              {/if}
              {#each danger ? [...reach.move, ...reach.strike] : reach.strike as [x, y] (`${x},${y}`)}
                <span class="reach strike" style="left: {x * CELL}px; top: {y * CELL}px"></span>
              {/each}
              {#if pickingCamera}
                <span class="camera-marker" style="left: {camera[0] * CELL}px; top: {camera[1] * CELL}px" title={t('chapter.camera')}>🎥</span>
              {/if}
              {#if objective?.type === 'seize'}
                {#each objective.seize as tile, k (k)}
                  <span class="seize-marker" style="left: {tile.x * CELL}px; top: {tile.y * CELL}px" title={t('objective.type.seize')}><img class="pixel" src={itemIconUrl(OBJECTIVE_ICONS.seize)} alt="" /></span>
                {/each}
              {/if}
              {#each groups as g (g.name)}
                {#if !hidden[g.name] && (focusTurn === null || (g.origin !== 'cutscene' && g.origin !== 'scene' && turnOf(g) <= focusTurn))}
                  {#each unitsOf(g.name) as u, i (i)}
                    <button
                      class="unit {u.side}"
                      class:picked={picked?.group === g.name && picked.index === i}
                      class:dimmed={(openGroup !== null && openGroup !== g.name) || (focusTurn !== null && turnOf(g) < focusTurn)}
                      class:locked={u.fixedPath}
                      style="left: {u.endX * CELL}px; top: {u.endY * CELL}px"
                      title="{unitName(u)} · {classById.get(effectiveClass(u))?.name ?? effectiveClass(u)} {t('chapter.levelShort')}{u.level}"
                      draggable={!u.fixedPath}
                      ondragstart={() => (dragging = { group: g.name, index: i })}
                      ondragend={() => (dragging = null)}
                      onclick={() => (picked = { group: g.name, index: i })}
                    >
                      <img src={mapSpriteUrl(effectiveClass(u), u.side)} alt="" draggable="false" use:hideBroken />
                    </button>
                  {/each}
                {/if}
              {/each}
            </div>
          {/if}
        </section>

        <section class="panel unit-panel">
          {#if unit && picked}
            {@const cls = classById.get(effectiveClass(unit))}
            {@const p = picked}
            <label>
              <span>{t('chapter.sideLabel')} <Help text={t('chapter.sideHint')} /></span>
              <select value={unit.side} onchange={(e) => editUnit(p.group, p.index, (u) => (u.side = (e.target as HTMLSelectElement).value as MapUnit['side']))}>
                {#each ['player', 'ally', 'enemy'] as side (side)}<option value={side}>{t(`chapter.side.${side}`)}</option>{/each}
              </select>
            </label>
            {#if pickedOrigin === 'cutscene'}
              {@const battle = battleUnitOf(unit.character)}
              <div class="cutscene-warning">
                {t('chapter.cutsceneUnit')}
                {#if battle}
                  <button class="link" onclick={() => { openGroup = null; hidden[battle.group] = false; picked = battle }}>{t('chapter.goToBattleUnit')}</button>
                {/if}
              </div>
            {/if}
            <p class="big">
              {#if charById.has(unit.character)}<Mention kind="characters" id={unit.character}>{unitName(unit)}</Mention>{:else}{unitName(unit)} <span class="muted tiny">{unit.character}</span>{/if}
            </p>
            <div class="actions">
              <button onclick={() => addUnit(p.group, unit)} title={t('chapter.copyHint')}>{t('chapter.duplicate')}</button>
              <button class="danger" onclick={() => removeUnit(p.group, p.index)} title={t('chapter.removeHint')}>{t('chapter.remove')}</button>
            </div>
            <label>
              <span>{t('chapter.character')} {#if charById.has(unit.character)}<Mention kind="characters" id={unit.character}><span class="open">↗</span></Mention>{/if}</span>
              <select value={unit.character} onchange={(e) => editUnit(p.group, p.index, (u) => {
                u.character = (e.target as HTMLSelectElement).value
                if (levelFromSheet(u)) u.level = Math.min(charById.get(u.character)!.level, 31)
              })}>
                {#if !charById.has(unit.character)}<option value={unit.character}>{t('chapter.generic')} ({unit.character})</option>{/if}
                {#if unit.character !== GENERIC && !charById.has(GENERIC)}<option value={GENERIC}>{t('chapter.generic')}</option>{/if}
                {#each characters as c (c.id)}<option value={c.id}>{c.name || c.id}</option>{/each}
              </select>
            </label>
            {#if isNamed(unit)}
              <div class="from-sheet">
                <span class="muted small">{t('field.class')}</span>
                <span>
                  {#if cls}<Mention kind="classes" id={cls.id}>{cls.name || cls.id}</Mention><GenderSign gender={cls.gender} />{:else}{effectiveClass(unit)}{/if}
                </span>
                <span class="muted tiny">{t('chapter.classFromSheet')} <Mention kind="characters" id={unit.character}>{unitName(unit)}</Mention></span>
              </div>
            {:else}
            <label>
              <span>{t('field.class')} {#if cls}<Mention kind="classes" id={unit.class}><span class="open">↗</span></Mention>{/if}</span>
              <span class="with-sign">
                <ClassPicker value={unit.class} {classes} label={t('field.class')} onchange={(v) => editUnit(p.group, p.index, (u) => (u.class = v))} />
              </span>
            </label>
            {/if}
            {#if levelFromSheet(unit)}
              <div class="from-sheet">
                <span class="muted small">{t('chapter.level')}</span>
                <span>{shownLevel(unit)}</span>
                <span class="muted tiny">{t('chapter.levelFromSheet')} <Mention kind="characters" id={unit.character}>{unitName(unit)}</Mention></span>
              </div>
            {:else}
            <NumberField label={t('chapter.level')} value={unit.level} min={0} max={31} onchange={(v) => editUnit(p.group, p.index, (u) => (u.level = v))} />
            {/if}
            <label class="check">
              <input type="checkbox" checked={unit.autolevel} onchange={(e) => editUnit(p.group, p.index, (u) => (u.autolevel = (e.target as HTMLInputElement).checked))} />
              {t('chapter.autolevel')} <Help text={t('chapter.autolevelHint')} />
            </label>
            <p class="muted small">
              {t('chapter.position')} : {unit.endX}, {unit.endY}
              {#if unit.slot !== null && (unit.x !== unit.endX || unit.y !== unit.endY)} · {t('chapter.entersFrom', { x: unit.x, y: unit.y })}{/if}
            </p>
            {#if unit.fixedPath}<p class="warn small">{t('chapter.fixedPath')}</p>{/if}
            {#if unitStats}
              <h3>{t(unit.autolevel ? 'chapter.statsAverage' : 'chapter.stats')} <Help text={t('chapter.statsHint')} /></h3>
              <div class="unit-stats">
                {#each SHOWN_STATS as s (s)}<span><span class="muted tiny">{statLabel(s)}</span> {unitStats[s]}</span>{/each}
              </div>
              {#if Object.keys(unitRanks).length}
                <!-- Weapon ranks, raised by the autolevel to what the items need (ticket 157) -->
                <div class="unit-ranks">
                  {#each Object.entries(unitRanks) as [w, rank] (w)}
                    <span title={t(`wtype.${w}`)}><img class="pixel" src={itemIconUrl(WTYPE_ICON + RANK_TYPES.indexOf(w))} alt={t(`wtype.${w}`)} /> {rank}</span>
                  {/each}
                  <Help text={t(unit.autolevel ? 'chapter.ranksAutoHint' : 'chapter.ranksHint')} />
                </div>
              {/if}
            {/if}
            <h3>{t('chapter.items')}{#if unit.side === 'player'} <Help text={t('chapter.allyItemsHint')} />{/if}</h3>
            {#each Array(ITEM_SLOTS) as _, slot (slot)}
              {@const id = unit.items[slot] ?? ''}
              {@const it = itemById.get(id)}
              <div class="slot">
                {#if it}<Mention kind="items" {id}><img class="pixel" src={itemIconUrl(it.iconId)} alt="" /></Mention>{:else}<span class="blank"></span>{/if}
                <ItemPicker icon={false} value={id} items={weapons} extra={[{ value: '', label: t('field.none') }]} disabled={slot > unit.items.length}
                            label={t('chapter.items')} onchange={(v) => setItem(slot, v)} />
              </div>
            {/each}
            {@const dropped = unit.items.length ? itemById.get(unit.items[unit.items.length - 1]) : undefined}
            <label class="check">
              <input type="checkbox" checked={!!unit.itemDrop} disabled={!unit.items.length && !unit.itemDrop}
                     onchange={(e) => editUnit(p.group, p.index, (u) => (u.itemDrop = (e.target as HTMLInputElement).checked))} />
              {t('chapter.itemDrop')}{#if unit.itemDrop && dropped}{' : '}<span class="dropped">{dropped.name}</span>{/if} <Help text={t('chapter.itemDropHint')} />
            </label>
            {#if isNamed(unit)}
              <p class="small quotes">
                <Mention kind="dialogues" id={`quote:battle:${chapter.index}:${unit.character}`}>{t('chapter.battleQuote')}</Mention>
                · <Mention kind="dialogues" id={`quote:death:${chapter.index}:${unit.character}`}>{t('field.lastWordsLink')}</Mention>
              </p>
            {/if}
            <AiPanel ai={unit.ai} side={unit.side} onchange={(ai) => editUnit(p.group, p.index, (u) => (u.ai = ai))} />
            {#each unitProblems as pr, i (i)}<p class="{pr.severity === 'error' ? 'bad' : 'warn'} small">{problemText(pr)}</p>{/each}
          {:else}
            <p class="muted">{t('chapter.pickUnit')}</p>
          {/if}
        </section>
      </div>

      <details class="panel settings">
        <summary>
          <h3>{t('chapter.settings')}</h3>
          <span class="muted small">{settingsSummary}</span>
        </summary>
        <div class="settings-grid">
          <div class="settings-col">
            <label class="check small convoy" title={t('chapter.convoyHint')}>
              <input type="checkbox" checked={convoyEdit ?? chapter.convoy} onchange={(e) => setConvoy((e.target as HTMLInputElement).checked)} />
              {t('chapter.convoy')}
              {#if convoyEdit !== undefined}<span class="edited">✎</span>{/if}
            </label>
            <label class="check small convoy" title={t('chapter.prepHint')}>
              <input type="checkbox" checked={prepEdit ?? chapter.prep} onchange={(e) => setPrep((e.target as HTMLInputElement).checked)} />
              {t('chapter.prep')}
              {#if prepEdit !== undefined}<span class="edited">✎</span>{/if}
            </label>
            <label class="check small convoy" title={t('chapter.fogHint')}>
              <input type="checkbox" checked={fog > 0} onchange={(e) => setFog((e.target as HTMLInputElement).checked ? 3 : 0)} />
              {t('chapter.fog')}
              {#if fog > 0}
                <select value={fog} onchange={(e) => setFog(Number((e.target as HTMLSelectElement).value))} aria-label={t('chapter.fogRange')}>
                  {#each [1, 2, 3, 4, 5, 6, 7, 8] as n (n)}<option value={n}>{t('chapter.fogRangeN', { n })}</option>{/each}
                </select>
              {/if}
              {#if fogEdit !== undefined}<span class="edited">✎</span>{/if}
            </label>
            <div class="row wall-hp">
              <NumberField label={t('chapter.wallHp')} hint={t('chapter.wallHpHint')} value={wallHpEdit ?? chapter.wallHp} min={1} max={127}
                           compact inline onchange={setWallHp} />
              {#if wallHpEdit !== undefined}<span class="edited">✎</span>{/if}
            </div>
            <div class="row wall-hp">
              <label class="small setting">
                {t('chapter.weather')}
                <select value={weather} onchange={(e) => setLook('weather', (e.target as HTMLSelectElement).value)}>
                  {#each weather === 'night' ? [...WEATHERS, 'night'] : WEATHERS as w (w)}<option value={w}>{t(`weather.${w}`)}</option>{/each}
                </select>
              </label>
              <Help text={t('chapter.weatherHint')} />
              {#if lookEdit('weather') !== undefined}<span class="edited">✎</span>{/if}
            </div>
            <div class="row wall-hp">
              <span class="small">{t('chapter.camera')} : {camera[0]}, {camera[1]}</span>
              <button class="small" class:active={pickingCamera} onclick={pickCamera}>
                {pickingCamera ? t('chapter.cameraPicking') : t('chapter.cameraPick')}
              </button>
              <Help text={t('chapter.cameraHint')} />
              {#if lookEdit('camera') !== undefined}<span class="edited">✎</span>{/if}
            </div>
            {#if levelBonus}
              <div class="row wall-hp">
                <span class="small">{t('chapter.levelBonus')}</span>
                <NumberField label={t('chapter.levelEasy')} value={levelBonus.easy} min={0} max={15} compact onchange={(v) => setLevelBonus('easy', v)} />
                <NumberField label={t('chapter.levelNormal')} value={levelBonus.normal} min={0} max={15} compact onchange={(v) => setLevelBonus('normal', v)} />
                <NumberField label={t('chapter.levelHard')} value={levelBonus.hard} min={0} max={15} compact onchange={(v) => setLevelBonus('hard', v)} />
                <Help text={t('chapter.levelBonusHint')} />
                {#if levelBonusEdited}<span class="edited">✎</span>{/if}
              </div>
            {/if}
          </div>
        </div>
        <ChapterMusic index={chapter.index} />
          <div class="bg-title">
            <span class="small">{t('chapter.battleBg')}</span>
            <Help text={t('chapter.battleBgHint')} />
            {#if lookEdit('battleBg') !== undefined}<span class="edited">✎</span>{/if}
          </div>
          <div class="bg-gallery" role="radiogroup" aria-label={t('chapter.battleBg')}>
            {#each battleBgSets as s (s.n)}
              <button role="radio" aria-checked={battleBg === s.n} class="bg-choice" class:active={battleBg === s.n}
                title={s.users || undefined} onclick={() => setLook('battleBg', s.n)}>
                <img class="pixel" src={`/api/assets/battle-bg/${s.n}`} alt="" loading="lazy" use:hideBroken />
                <span class="tiny">{s.n === 0 ? t('chapter.battleBgDefault') : t('chapter.battleBgSet', { n: s.n })}</span>
                {#if s.users}<span class="tiny muted users">{s.users}</span>{/if}
              </button>
            {/each}
          </div>
      </details>

    </div>
  {/if}
</div>

<style>
  .editor { display: grid; grid-template-columns: 260px 1fr; gap: 1rem; align-items: start; }
  .detail { display: flex; flex-direction: column; gap: 1rem; min-width: 0; }
  .id { font-size: 0.75rem; margin-left: 0.3rem; }
  .groups { display: grid; grid-template-columns: repeat(auto-fill, minmax(300px, 1fr)); gap: 0.35rem 0.6rem; }
  .map-tools { display: flex; flex-wrap: wrap; align-items: center; justify-content: space-between; gap: 0.5rem; margin-bottom: 0.4rem; }
  .map-tools select { width: auto; }
  .setting { flex-direction: row; align-items: center; gap: 0.4rem; color: var(--text); }
  .setting select { width: auto; max-width: 26rem; }
  .camera-marker {
    position: absolute; width: 32px; height: 32px; box-sizing: border-box; display: grid; place-items: center;
    border: 3px solid var(--accent); border-radius: 4px; background: var(--accent-soft); pointer-events: none; font-size: 15px;
  }
  .shown-map { flex-direction: row; align-items: center; gap: 0.4rem; font-size: 0.8rem; }
  .unit-stats { display: grid; grid-template-columns: repeat(4, 1fr); gap: 0.1rem 0.5rem; font-size: 0.85rem; }
  .unit-ranks { display: flex; flex-wrap: wrap; align-items: center; gap: 0.2rem 0.7rem; margin-top: 0.35rem; font-size: 0.85rem; font-weight: 600; }
  .unit-ranks span { display: inline-flex; align-items: center; gap: 0.2rem; }
  .unit-ranks img { width: 16px; height: 16px; }
  .dropped { color: var(--good, #2e9e5b); font-weight: 600; }
  .quotes { margin: 0; }
  .check { flex-direction: row; align-items: center; gap: 0.35rem; color: var(--text); font-size: 0.85rem; }
  .groups-title { margin: 0.25rem 0 0.4rem; font-size: 0.8rem; }
  .timeline { display: grid; grid-template-columns: max-content 1fr; gap: 0.35rem 0.75rem; align-items: start; }
  .timeline .turn { border: none; background: none; padding: 0.45rem 0.5rem; border-radius: 6px; font-weight: 700; font-size: 0.85rem; color: var(--accent); text-align: left; white-space: nowrap; }
  .timeline .turn:hover { background: var(--panel-2); }
  .timeline .turn.focus { background: var(--accent-soft); }
  .timeline .turn.scenes { cursor: default; color: var(--muted); }
  .timeline .groups { padding-bottom: 0.35rem; border-bottom: 1px solid var(--border); }
  .timeline .groups:last-child { border-bottom: none; }
  .timeline-tools { margin-top: 0.5rem; align-items: center; gap: 0.4rem; }
  .cutscenes { margin-top: 0.6rem; }
  .cutscenes summary { cursor: pointer; font-size: 0.85rem; color: var(--muted); }
  .cutscenes[open] summary { margin-bottom: 0.3rem; }
  .cutscene-warning { background: var(--warn-soft); color: var(--warn); border-radius: 6px; padding: 0.45rem 0.6rem; font-size: 0.82rem; line-height: 1.4; }
  .cutscene-warning .link { color: inherit; text-decoration: underline; font-weight: 600; margin-left: 0.25rem; }
  .group { display: flex; align-items: center; gap: 0.3rem; border: 1px solid var(--border); border-radius: 6px; padding: 0.15rem 0.3rem; min-width: 0; }
  .group.open { background: var(--accent-soft); }
  .group-name { flex: 1; min-width: 0; display: flex; flex-direction: column; gap: 0.1rem; border: none; background: none; padding: 0.1rem 0.2rem; font-size: 0.85rem; color: var(--text); text-align: left; }
  .group-sprites { display: flex; flex-wrap: wrap; align-items: center; min-height: 16px; }
  .group-sprites img { image-rendering: pixelated; max-height: 24px; }
  .group-name:hover { text-decoration: underline; }
  .group-units { margin-top: 0.75rem; border-top: 1px solid var(--border); padding-top: 0.5rem; display: flex; flex-direction: column; gap: 0.5rem; }
  .group-units table { border-collapse: collapse; width: 100%; font-size: 0.85rem; }
  .group-units th { text-align: left; font-size: 0.75rem; color: var(--muted); font-weight: 600; padding: 0.15rem 0.4rem; }
  .group-units td { padding: 0.1rem 0.4rem; vertical-align: middle; }
  .group-units tbody tr { cursor: pointer; }
  .group-units tbody tr:hover { background: var(--panel-2); }
  .group-units tr.picked { background: var(--accent-soft); }
  .group-units .sprite { width: 40px; text-align: center; }
  .group-units .sprite img { image-rendering: pixelated; max-height: 32px; vertical-align: bottom; }
  .link { border: none; background: none; padding: 0; color: var(--accent); font: inherit; }
  .unit.dimmed { opacity: 0.35; }
  .from-sheet { display: flex; flex-direction: column; gap: 0.15rem; }
  .map.picking { cursor: crosshair; }
  .map.picking .unit { pointer-events: none; }
  .area-marker { position: absolute; box-sizing: border-box; border: 3px dashed #e74c3c; background: rgb(231 76 60 / 0.15); pointer-events: none; font-size: 16px; padding: 2px; }
  .danger { margin-bottom: 0.4rem; font-size: 0.8rem; color: var(--text); }
  .area-marker img, .seize-marker img { width: 22px; height: 22px; }
  .reach { position: absolute; width: 32px; height: 32px; pointer-events: none; }
  .reach.move { background: rgb(64 128 255 / 35%); }
  .reach.strike { background: rgb(255 64 64 / 35%); }
  .reach.heal { background: rgb(64 200 96 / 40%); }
  .seize-marker {
    position: absolute; width: 32px; height: 32px; box-sizing: border-box; display: grid; place-items: center;
    border: 3px solid #f1c40f; border-radius: 4px; background: rgb(241 196 15 / 0.25); font-size: 15px; pointer-events: none;
    box-shadow: 0 0 0 1px rgb(0 0 0 / 0.5);
  }
  .add { padding: 0 0.4rem; line-height: 1.4; font-size: 0.85rem; }
  .actions { display: flex; gap: 0.5rem; }
  .actions button { flex: 1; }
  .danger { color: var(--bad); }
  .edited { color: var(--accent); }
  .settings summary { display: flex; align-items: baseline; gap: 0.8rem; cursor: pointer; list-style: none; }
  .settings summary::-webkit-details-marker { display: none; }
  .settings summary::before { content: '▸'; color: var(--muted); }
  .settings[open] summary::before { content: '▾'; }
  .settings summary h3 { margin: 0; }
  .settings[open] summary { margin-bottom: 0.8rem; }
  .settings-grid { display: flex; flex-direction: column; gap: 0.3rem; }
  .bg-title { display: flex; align-items: center; gap: 0.4rem; margin: 0.8rem 0 0.4rem; }
  .bg-gallery { display: grid; grid-template-columns: repeat(auto-fill, minmax(170px, 1fr)); gap: 0.5rem; }
  .bg-choice { display: flex; flex-direction: column; align-items: flex-start; gap: 0.15rem; padding: 0.3rem; border: 2px solid transparent; border-radius: var(--radius); background: none; text-align: left; }
  .bg-choice img { width: 100%; aspect-ratio: 240 / 104; border-radius: calc(var(--radius) - 2px); }
  .bg-choice:hover { border-color: var(--border); }
  .bg-choice.active { border-color: var(--accent); background: color-mix(in srgb, var(--accent) 15%, transparent); }
  .settings-col .row { min-height: 2rem; }
  .bg-choice .users { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; max-width: 100%; }
  .tiny { font-size: 0.72rem; }
  .small { font-size: 0.8rem; }
  .warn { color: var(--warn); }
  .bad { color: var(--bad); }
  .open { font-size: 1rem; }
  .dup { margin-bottom: 0.5rem; }
  .layout { display: grid; grid-template-columns: minmax(0, 1fr) 280px; gap: 1rem; align-items: start; }
  .map-panel { overflow: auto; max-height: calc(100vh - 260px); padding: 0.5rem; }
  .map { position: relative; background-size: 100% 100%; image-rendering: pixelated; }
  .unit {
    position: absolute; width: 32px; height: 32px; padding: 0; border: none; background: none;
    display: flex; align-items: flex-end; justify-content: center; cursor: grab;
  }
  .unit.locked { cursor: pointer; }
  .unit img { image-rendering: pixelated; pointer-events: none; }
  .unit:hover, .unit.picked { outline: 2px solid var(--accent); outline-offset: -2px; border-radius: 4px; }
  .unit.picked { background: rgb(255 255 255 / 0.25); }
  .unit-panel { display: flex; flex-direction: column; gap: 0.5rem; }
  .unit-panel h3 { margin: 0.5rem 0 0; }
  .big { font-size: 1.1rem; font-weight: 600; margin: 0; }
  .slot { display: flex; align-items: center; gap: 0.4rem; }
  .slot :global(.picker) { flex: 1; min-width: 0; }
  .slot img, .blank { width: 16px; height: 16px; display: inline-block; }
  @media (max-width: 1000px) { .layout { grid-template-columns: 1fr; } }
  @media (max-width: 800px) { .editor { grid-template-columns: 1fr; } }
  .add-group { font-size: 0.8rem; padding: 0.15rem 0.5rem; }
  .new-group { display: flex; align-items: flex-end; gap: 0.75rem; flex-wrap: wrap; margin-bottom: 0.3rem; }
  .danger { color: var(--bad); }
</style>
