<script lang="ts">
  import { onMount } from 'svelte'
  import { api, chapterMapUrl, itemIconUrl, mapSpriteUrl } from '../lib/api'
  import type { EditableList } from '../lib/history.svelte'
  import { t } from '../lib/i18n.svelte'
  import type { ChapterInfo, ChapterUnits, ChaptersData, Character, ClassView, Item, MapUnit, Problem } from '../lib/types'
  import GenderSign from './GenderSign.svelte'
  import Mention from './Mention.svelte'
  import NumberField from './NumberField.svelte'
  import RecordList from './RecordList.svelte'

  let {
    list,
    characters,
    classes,
    items,
    problems,
  }: {
    list: EditableList<ChaptersData>
    characters: Character[]
    classes: ClassView[]
    items: Item[]
    problems: Problem[]
  } = $props()

  const CELL = 32 // 16 px tiles shown at x2
  const ITEM_SLOTS = 4

  // Several chapters share an internal id in the original game: list them by index.
  let chapters = $state<(ChapterInfo & { name: string; code: string })[]>([])
  let selected = $state(0)
  let data = $state<ChapterUnits | null>(null)
  let hidden = $state<Record<string, boolean>>({})
  let picked = $state<{ group: string; index: number } | null>(null)
  let loading = $state(false)
  let dragging = $state<{ group: string; index: number } | null>(null)
  let mapEl = $state<HTMLDivElement>()

  const chapter = $derived(chapters[selected])
  const edits = $derived(list.records[0]?.unitGroups ?? {})
  const charById = $derived(new Map(characters.map((c) => [c.id, c])))
  const classById = $derived(new Map(classes.map((k) => [k.id, k])))
  const itemById = $derived(new Map(items.map((i) => [i.id, i])))
  const weapons = $derived(items)

  /** Units of a group: the project's version once edited, the original otherwise. */
  function unitsOf(name: string): MapUnit[] {
    return edits[name] ?? data?.groups.find((g) => g.name === name)?.units ?? []
  }
  const unit = $derived(picked ? unitsOf(picked.group)[picked.index] : undefined)
  const unitProblems = $derived(
    picked ? problems.filter((p) => p.kind === 'chapters' && p.id === `${picked!.group}#${picked!.index}`) : [],
  )

  onMount(async () => {
    const all = await api.chapters()
    chapters = all.map((c) => ({ ...c, code: c.id, id: String(c.index), name: c.title || c.id }))
    if (chapters.length) await load(0)
  })

  async function load(index: number) {
    selected = index
    picked = null
    loading = true
    data = null
    try {
      data = await api.chapterUnits(chapters[index].index)
      hidden = Object.fromEntries(data.groups.map((g) => [g.name, false]))
    } finally {
      loading = false
    }
  }

  /** Edit one unit; the first edit of a group copies it into the project. */
  function editUnit(group: string, index: number, change: (u: MapUnit) => void) {
    const original = unitsOf(group)
    list.update(0, (c) => {
      if (!c.unitGroups[group]) c.unitGroups[group] = structuredClone($state.snapshot(original)) as MapUnit[]
      change(c.unitGroups[group][index])
    })
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

  function unitName(u: MapUnit): string {
    return charById.get(u.character)?.name || t('chapter.generic')
  }

  function originLabel(origin: string, turn: number | null): string {
    return origin === 'turn' ? t('chapter.origin.turn', { n: turn ?? '?' }) : t(`chapter.origin.${origin}`)
  }
</script>

<div class="editor">
  <RecordList records={chapters} {selected} onselect={(i) => load(i)} problemIds={new Set()}>
    {#snippet suffix(c: ChapterInfo & { code: string })}<span class="muted id">{c.code}</span>{/snippet}
  </RecordList>

  {#if chapter}
    <div class="detail">
      <section class="panel">
        <h2>{chapter.title || chapter.code} <span class="muted id">{chapter.code}</span></h2>
        <p class="muted small">{t('chapter.editHint')}</p>
        {#if data}
          <div class="groups">
            {#each data.groups as g (g.name)}
              <label class="check">
                <input type="checkbox" checked={!hidden[g.name]} onchange={(e) => (hidden[g.name] = !(e.target as HTMLInputElement).checked)} />
                {originLabel(g.origin, g.turn)} · {unitsOf(g.name).length}
                {#if edits[g.name]}<span class="edited">✎</span>{/if}
                <span class="muted tiny">{g.name.replace('UnitDef_Event_', '')}</span>
              </label>
            {/each}
          </div>
        {/if}
      </section>

      <div class="layout">
        <section class="panel map-panel">
          {#if loading}<p class="muted">…</p>{/if}
          {#if data && data.width}
            <div
              class="map"
              role="application"
              bind:this={mapEl}
              style="width: {data.width * CELL}px; height: {data.height * CELL}px; background-image: url({chapterMapUrl(chapter.index)})"
              ondragover={(e) => e.preventDefault()}
              ondrop={drop}
            >
              {#each data.groups as g (g.name)}
                {#if !hidden[g.name]}
                  {#each unitsOf(g.name) as u, i (i)}
                    <button
                      class="unit {u.side}"
                      class:picked={picked?.group === g.name && picked.index === i}
                      class:locked={u.fixedPath}
                      style="left: {u.endX * CELL}px; top: {u.endY * CELL}px"
                      title="{unitName(u)} · {classById.get(u.class)?.name ?? u.class} {t('chapter.levelShort')}{u.level}"
                      draggable={!u.fixedPath}
                      ondragstart={() => (dragging = { group: g.name, index: i })}
                      ondragend={() => (dragging = null)}
                      onclick={() => (picked = { group: g.name, index: i })}
                    >
                      <img src={mapSpriteUrl(u.class, u.side)} alt="" draggable="false" onerror={(e) => ((e.target as HTMLImageElement).style.visibility = 'hidden')} />
                    </button>
                  {/each}
                {/if}
              {/each}
            </div>
          {/if}
        </section>

        <section class="panel unit-panel">
          {#if unit && picked}
            {@const cls = classById.get(unit.class)}
            {@const p = picked}
            <h3>{t(`chapter.side.${unit.side}`)}</h3>
            <p class="big">
              {#if charById.has(unit.character)}<Mention kind="characters" id={unit.character}>{unitName(unit)}</Mention>{:else}{unitName(unit)} <span class="muted tiny">{unit.character}</span>{/if}
            </p>
            <label>
              <span>{t('field.class')} {#if cls}<Mention kind="classes" id={unit.class}><span class="open">↗</span></Mention>{/if}</span>
              <span class="with-sign">
                <select value={unit.class} onchange={(e) => editUnit(p.group, p.index, (u) => (u.class = (e.target as HTMLSelectElement).value))}>
                  {#each classes.filter((k) => k.usedInGame || k.id === unit.class) as k (k.id)}
                    <option value={k.id} class={k.gender ?? ''}>{k.name || k.id}{k.gender === 'male' ? ' ♂' : k.gender === 'female' ? ' ♀' : ''}</option>
                  {/each}
                </select>
                <GenderSign gender={cls?.gender} />
              </span>
            </label>
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
                <select value={id} disabled={slot > unit.items.length} onchange={(e) => setItem(slot, (e.target as HTMLSelectElement).value)}>
                  <option value="">{t('field.none')}</option>
                  {#each weapons as w (w.id)}<option value={w.id}>{w.name}</option>{/each}
                </select>
              </div>
            {/each}
            {#each unitProblems as pr, i (i)}<p class="bad small">{t(`problem.${pr.code}`, pr.params)}</p>{/each}
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
  .edited { color: var(--accent); }
  .tiny { font-size: 0.72rem; }
  .small { font-size: 0.8rem; }
  .warn { color: var(--warn); }
  .bad { color: var(--bad); }
  .open { font-size: 1rem; }
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
  .slot select { flex: 1; min-width: 0; }
  .slot img, .blank { width: 16px; height: 16px; display: inline-block; }
  @media (max-width: 1000px) { .layout { grid-template-columns: 1fr; } }
  @media (max-width: 800px) { .editor { grid-template-columns: 1fr; } }
</style>
