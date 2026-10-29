<script lang="ts">
  import { onMount, untrack } from 'svelte'
  import { aiPreset } from '../lib/ai'
  import { appContext } from '../lib/appContext.svelte'
  import { api, chapterMapUrl, itemIconUrl, mapSpriteUrl } from '../lib/api'
  import type { EditableList } from '../lib/history.svelte'
  import { followFocus, useNavigator } from '../lib/navigation.svelte'
  import { problemText, t } from '../lib/i18n.svelte'
  import type { ChapterInfo, ChapterUnits, ChaptersData, Character, ClassView, Item, MapUnit, MapsData, NewGroup, Objective, ObjectiveEdit, Problem, UnitGroup } from '../lib/types'
  import AiPanel from './AiPanel.svelte'
  import GenderSign from './GenderSign.svelte'
  import Mention from './Mention.svelte'
  import ItemPicker from './ItemPicker.svelte'
  import ClassPicker from './ClassPicker.svelte'
  import NumberField from './NumberField.svelte'
  import ObjectivePanel from './ObjectivePanel.svelte'
  import RecordList from './RecordList.svelte'

  let {
    list,
    maps,
    characters,
    classes,
    items,
    problems,
  }: {
    list: EditableList<ChaptersData>
    /** painted map layouts: the map shown is the project's one */
    maps: MapsData | undefined
    characters: Character[]
    classes: ClassView[]
    items: Item[]
    problems: Problem[]
  } = $props()

  const CELL = 32 // 16 px tiles shown at x2
  const ITEM_SLOTS = 4
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
  let showCutscenes = $state(false)

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
    ...(data?.groups ?? []),
    ...newGroups.map(([name, g]) => ({ name, origin: 'turn' as const, turn: g.turn, units: [], edited: true, new: true })),
  ])
  const openNew = $derived(openGroup ? list.records[0]?.newGroups?.[openGroup] : undefined)

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
  const battleGroups = $derived(groups.filter((g) => g.origin !== 'cutscene') ?? [])
  const cutsceneGroups = $derived(groups.filter((g) => g.origin === 'cutscene') ?? [])
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

  // First corner of the area being chosen ("reach an area" objective).
  let areaCorner = $state<{ x: number; y: number } | null>(null)

  /** Map click while choosing the tile to seize, or the two corners of the area to reach. */
  function pickTile(e: MouseEvent) {
    if (!pickingSeize || !mapEl || !data) return
    const rect = mapEl.getBoundingClientRect()
    const x = Math.max(0, Math.min(data.width - 1, Math.floor((e.clientX - rect.left) / CELL)))
    const y = Math.max(0, Math.min(data.height - 1, Math.floor((e.clientY - rect.top) / CELL)))
    if (objective?.type === 'area') {
      if (!areaCorner) {
        areaCorner = { x, y }
        return
      }
      const a = areaCorner
      editObjective({ area: { x1: Math.min(a.x, x), y1: Math.min(a.y, y), x2: Math.max(a.x, x), y2: Math.max(a.y, y) } })
      areaCorner = null
      pickingSeize = false
      return
    }
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
    chapters = all.map((c) => ({ ...c, code: c.id, id: String(c.index), name: c.title || c.id }))
    // Opened from a link (e.g. the map editor): the chapter list was not loaded yet.
    const asked = nav.focus?.kind === 'chapters' ? chapters.findIndex((c) => c.id === nav.focus!.id) : -1
    if (chapters.length) await load(Math.max(0, asked))
  })

  async function load(index: number) {
    selected = index
    picked = null
    openGroup = null
    pickingSeize = false
    loading = true
    data = null
    originalObjective = null
    try {
      api.chapterObjective(chapters[index].index).then((o) => {
        if (selected === index) originalObjective = o
      })
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
          slot: null, copyOf: null, level: 1, autolevel: false, items: [], ai: [0, 0, 0, 0],
          side: origin === 'players' ? 'player' : 'enemy',
          character: origin === 'players' ? (characters[0]?.id ?? GENERIC) : GENERIC,
          class: classes.find((k) => k.usedInGame)?.id ?? classes[0]?.id ?? '',
          x, y, endX: x, endY: y,
        }
    Object.assign(unit, { x, y, endX: x, endY: y })
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
        <h2>{chapter.title || chapter.code} <span class="muted id">{chapter.code}</span></h2>
        <p class="muted small">
          {t('chapter.editHint')}
          {#if chapter.map}<Mention kind="maps" id={chapter.map}>🗺 {t('chapter.editMap')}</Mention>{/if}
          <Mention kind="dialogues" id={String(chapter.index)}>💬 {t('chapter.editDialogues')}</Mention>
        </p>
        <label class="check small convoy" title={t('chapter.convoyHint')}>
          <input type="checkbox" checked={convoyEdit ?? chapter.convoy} onchange={(e) => setConvoy((e.target as HTMLInputElement).checked)} />
          📦 {t('chapter.convoy')}
          {#if convoyEdit !== undefined}<span class="edited">✎</span>{/if}
        </label>
        <label class="check small convoy" title={t('chapter.fogHint')}>
          <input type="checkbox" checked={fog > 0} onchange={(e) => setFog((e.target as HTMLInputElement).checked ? 3 : 0)} />
          🌫 {t('chapter.fog')}
          {#if fog > 0}
            <select value={fog} onchange={(e) => setFog(Number((e.target as HTMLSelectElement).value))} aria-label={t('chapter.fogRange')}>
              {#each [1, 2, 3, 4, 5, 6, 7, 8] as n (n)}<option value={n}>{t('chapter.fogRangeN', { n })}</option>{/each}
            </select>
          {/if}
          {#if fogEdit !== undefined}<span class="edited">✎</span>{/if}
        </label>
        {#if data}
          {#snippet groupChip(g: ChapterUnits['groups'][number])}
              <span class="group" class:open={openGroup === g.name}>
                <input type="checkbox" title={t('chapter.showGroup')} aria-label={t('chapter.showGroup')} checked={!hidden[g.name]} onchange={(e) => (hidden[g.name] = !(e.target as HTMLInputElement).checked)} />
                <button class="group-name" title={t('chapter.openGroup')} onclick={() => toggleGroup(g.name)}>
                  {originLabel(g.origin, g.turn)} · {unitsOf(g.name).length}
                  {#if edits[g.name]}<span class="edited">✎</span>{/if}
                  <span class="muted tiny">{g.name.replace('UnitDef_Event_', '')}</span>
                </button>
                <button class="add" title={t('chapter.addUnit')} aria-label={t('chapter.addUnit')} onclick={() => addUnit(g.name)}>＋</button>
              </span>
          {/snippet}
          <h3 class="groups-title">{t('chapter.battleGroups')}</h3>
          <div class="groups">
            {#each battleGroups as g (g.name)}{@render groupChip(g)}{/each}
            <button class="add-group" title={t('chapter.addReinforcementsHint')} onclick={addReinforcements}>＋ {t('chapter.addReinforcements')}</button>
          </div>
          {#if cutsceneGroups.length}
            <details class="cutscenes" bind:open={showCutscenes}>
              <summary>{t('chapter.cutsceneGroups', { n: cutsceneGroups.length })}</summary>
              <p class="muted small">{t('chapter.cutsceneHint')}</p>
              <div class="groups">
                {#each cutsceneGroups as g (g.name)}{@render groupChip(g)}{/each}
              </div>
            </details>
          {/if}
          {#if openGroup && groups.some((g) => g.name === openGroup)}
            {@const og = openGroup}
            <div class="group-units">
              {#if openNew}
                <div class="row new-group">
                  <NumberField label={t('dlg.turn')} value={openNew.turn} min={1} max={99} compact onchange={(v) => editNewGroup(og, { turn: v })} />
                  <label>
                    <span>{t('dlg.phase')}</span>
                    <select value={openNew.phase} onchange={(e) => editNewGroup(og, { phase: (e.target as HTMLSelectElement).value as NewGroup['phase'] })}>
                      {#each ['enemy', 'player', 'ally'] as ph (ph)}<option value={ph}>{t(`dlg.phase.${ph}`)}</option>{/each}
                    </select>
                  </label>
                  <button class="danger" onclick={() => removeNewGroup(og)}>{t('chapter.removeReinforcements')}</button>
                </div>
                <p class="muted small">{t('chapter.newGroupHint')}</p>
              {/if}
              {#if !cutsceneGroups.some((g) => g.name === og) && unitsOf(og).length}
                <button class="dup" title={t('chapter.duplicateGroupHint')} onclick={() => duplicateGroup(og)}>⧉ {t('chapter.duplicateGroup')}</button>
              {/if}
              <table>
                <thead>
                  <tr><th></th><th>{t('chapter.character')}</th><th>{t('field.class')}</th><th>{t('chapter.levelShort')}</th><th>{t('chapter.positionShort')}</th><th>{t('ai.preset')}</th></tr>
                </thead>
                <tbody>
                  {#each unitsOf(og) as u, i (i)}
                    <tr class:picked={picked?.group === og && picked.index === i} onclick={() => (picked = { group: og, index: i })}>
                      <td class="sprite"><img src={mapSpriteUrl(effectiveClass(u), u.side, true)} alt="" onerror={(e) => ((e.target as HTMLImageElement).style.visibility = 'hidden')} /></td>
                      <td><button class="link" onclick={() => (picked = { group: og, index: i })}>{unitName(u)}</button></td>
                      <td>{classById.get(effectiveClass(u))?.name ?? effectiveClass(u)}<GenderSign gender={classById.get(effectiveClass(u))?.gender} /></td>
                      <td>{u.level}</td>
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
        {#if objective}
          <ObjectivePanel {objective} edited={!!objectiveEdit} problems={objectiveProblems} bind:picking={pickingSeize} {characters}
            battleCharacters={new Set(battleGroups.flatMap((g) => unitsOf(g.name).map((u) => u.character)))}
            originalBoss={originalObjective?.boss ?? null} onchange={editObjective} onreset={resetObjective} />
        {/if}
      </section>

      <div class="layout">
        <section class="panel map-panel">
          {#if loading}<p class="muted">…</p>{/if}
          {#if data && data.width}
            <div
              class="map"
              class:picking={pickingSeize}
              role="application"
              bind:this={mapEl}
              onclickcapture={(e) => {
                if (pickingSeize) {
                  e.stopPropagation()
                  pickTile(e)
                }
              }}
              style="width: {data.width * CELL}px; height: {data.height * CELL}px; background-image: url({chapterMapUrl(chapter.index, mapVersion)})"
              ondragover={(e) => e.preventDefault()}
              ondrop={drop}
            >
              {#if objective?.type === 'area' && (objective.area || areaCorner)}
                {@const a = objective.area && !areaCorner ? objective.area : { x1: areaCorner!.x, y1: areaCorner!.y, x2: areaCorner!.x, y2: areaCorner!.y }}
                <span class="area-marker" style="left: {a.x1 * CELL}px; top: {a.y1 * CELL}px; width: {(a.x2 - a.x1 + 1) * CELL}px; height: {(a.y2 - a.y1 + 1) * CELL}px" title={t('objective.type.area')}>🚩</span>
              {/if}
              {#if objective?.type === 'seize'}
                {#each objective.seize as tile, k (k)}
                  <span class="seize-marker" style="left: {tile.x * CELL}px; top: {tile.y * CELL}px" title={t('objective.type.seize')}>🏰</span>
                {/each}
              {/if}
              {#each groups as g (g.name)}
                {#if !hidden[g.name]}
                  {#each unitsOf(g.name) as u, i (i)}
                    <button
                      class="unit {u.side}"
                      class:picked={picked?.group === g.name && picked.index === i}
                      class:dimmed={openGroup !== null && openGroup !== g.name}
                      class:locked={u.fixedPath}
                      style="left: {u.endX * CELL}px; top: {u.endY * CELL}px"
                      title="{unitName(u)} · {classById.get(effectiveClass(u))?.name ?? effectiveClass(u)} {t('chapter.levelShort')}{u.level}"
                      draggable={!u.fixedPath}
                      ondragstart={() => (dragging = { group: g.name, index: i })}
                      ondragend={() => (dragging = null)}
                      onclick={() => (picked = { group: g.name, index: i })}
                    >
                      <img src={mapSpriteUrl(effectiveClass(u), u.side)} alt="" draggable="false" onerror={(e) => ((e.target as HTMLImageElement).style.visibility = 'hidden')} />
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
            <h3>{t(`chapter.side.${unit.side}`)}</h3>
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
              <select value={unit.character} onchange={(e) => editUnit(p.group, p.index, (u) => (u.character = (e.target as HTMLSelectElement).value))}>
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
            <div class="row">
              <NumberField label={t('chapter.level')} value={unit.level} min={0} max={31} onchange={(v) => editUnit(p.group, p.index, (u) => (u.level = v))} />
              <span class="muted small">{unit.autolevel ? t('chapter.autolevelHint') : ''}</span>
            </div>
            <p class="muted small">
              {t('chapter.position')} : {unit.endX}, {unit.endY}
              {#if unit.x !== unit.endX || unit.y !== unit.endY} · {t('chapter.entersFrom', { x: unit.x, y: unit.y })}{/if}
            </p>
            {#if unit.fixedPath}<p class="warn small">{t('chapter.fixedPath')}</p>{/if}
            <h3>{t('chapter.items')}</h3>
            {#each Array(ITEM_SLOTS) as _, slot (slot)}
              {@const id = unit.items[slot] ?? ''}
              {@const it = itemById.get(id)}
              <div class="slot">
                {#if it}<Mention kind="items" {id}><img class="pixel" src={itemIconUrl(it.iconId)} alt="" /></Mention>{:else}<span class="blank"></span>{/if}
                <ItemPicker icon={false} value={id} items={weapons} extra={[{ value: '', label: t('field.none') }]} disabled={slot > unit.items.length}
                            label={t('chapter.items')} onchange={(v) => setItem(slot, v)} />
              </div>
            {/each}
            <AiPanel ai={unit.ai} side={unit.side} onchange={(ai) => editUnit(p.group, p.index, (u) => (u.ai = ai))} />
            {#each unitProblems as pr, i (i)}<p class="{pr.severity === 'error' ? 'bad' : 'warn'} small">{problemText(pr)}</p>{/each}
          {:else}
            <p class="muted">{t('chapter.pickUnit')}</p>
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
  .groups { display: flex; flex-wrap: wrap; gap: 0.3rem 1rem; }
  .check { flex-direction: row; align-items: center; gap: 0.35rem; color: var(--text); font-size: 0.85rem; }
  .groups-title { margin: 0.25rem 0 0.4rem; font-size: 0.8rem; }
  .cutscenes { margin-top: 0.6rem; }
  .cutscenes summary { cursor: pointer; font-size: 0.85rem; color: var(--muted); }
  .cutscenes[open] summary { margin-bottom: 0.3rem; }
  .cutscene-warning { background: var(--warn-soft); color: var(--warn); border-radius: 6px; padding: 0.45rem 0.6rem; font-size: 0.82rem; line-height: 1.4; }
  .cutscene-warning .link { color: inherit; text-decoration: underline; font-weight: 600; margin-left: 0.25rem; }
  .group { display: inline-flex; align-items: center; gap: 0.3rem; border-radius: 6px; padding: 0 0.2rem; }
  .group.open { background: var(--accent-soft); }
  .group-name { border: none; background: none; padding: 0.1rem 0.2rem; font-size: 0.85rem; color: var(--text); text-align: left; }
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
