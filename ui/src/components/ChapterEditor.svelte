<script lang="ts">
  import { onMount } from 'svelte'
  import { api, chapterMapUrl, itemIconUrl, mapSpriteUrl } from '../lib/api'
  import { t } from '../lib/i18n.svelte'
  import type { ChapterInfo, ChapterUnits, Character, ClassView, Item, MapUnit } from '../lib/types'
  import GenderSign from './GenderSign.svelte'
  import Mention from './Mention.svelte'
  import RecordList from './RecordList.svelte'

  let { characters, classes, items }: { characters: Character[]; classes: ClassView[]; items: Item[] } = $props()

  const CELL = 32 // 16 px tiles shown at x2

  // Several chapters share an internal id in the original game: list them by index.
  let chapters = $state<(ChapterInfo & { name: string; code: string })[]>([])
  let selected = $state(0)
  let data = $state<ChapterUnits | null>(null)
  let hidden = $state<Record<string, boolean>>({})
  let picked = $state<{ group: string; index: number } | null>(null)
  let loading = $state(false)

  const chapter = $derived(chapters[selected])
  const charById = $derived(new Map(characters.map((c) => [c.id, c])))
  const classById = $derived(new Map(classes.map((k) => [k.id, k])))
  const itemById = $derived(new Map(items.map((i) => [i.id, i])))
  const unit = $derived(picked && data ? data.groups.find((g) => g.name === picked!.group)?.units[picked.index] : undefined)

  onMount(async () => {
    const list = await api.chapters()
    chapters = list.map((c) => ({ ...c, code: c.id, id: String(c.index), name: c.title || c.id }))
    if (chapters.length) await load(0)
  })

  async function load(index: number) {
    selected = index
    picked = null
    loading = true
    data = null
    try {
      data = await api.chapterUnits(chapters[index].index)
      // Show the battle setup by default; cutscene-only groups of the opening can be shown on demand.
      hidden = Object.fromEntries(data.groups.map((g) => [g.name, false]))
    } finally {
      loading = false
    }
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
        <p class="muted small">{t('chapter.readOnly')}</p>
        {#if data}
          <div class="groups">
            {#each data.groups as g (g.name)}
              <label class="check">
                <input type="checkbox" checked={!hidden[g.name]} onchange={(e) => (hidden[g.name] = !(e.target as HTMLInputElement).checked)} />
                {originLabel(g.origin, g.turn)} · {g.units.length}
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
            <div class="map" style="width: {data.width * CELL}px; height: {data.height * CELL}px; background-image: url({chapterMapUrl(chapter.index)})">
              {#each data.groups as g (g.name)}
                {#if !hidden[g.name]}
                  {#each g.units as u, i (i)}
                    <button
                      class="unit {u.side}"
                      class:picked={picked?.group === g.name && picked.index === i}
                      style="left: {u.endX * CELL}px; top: {u.endY * CELL}px"
                      title="{unitName(u)} · {classById.get(u.class)?.name ?? u.class} {t('chapter.levelShort')}{u.level}"
                      onclick={() => (picked = { group: g.name, index: i })}
                    >
                      <img src={mapSpriteUrl(u.class, u.side)} alt="" onerror={(e) => ((e.target as HTMLImageElement).style.visibility = 'hidden')} />
                    </button>
                  {/each}
                {/if}
              {/each}
            </div>
          {/if}
        </section>

        <section class="panel unit-panel">
          {#if unit}
            {@const cls = classById.get(unit.class)}
            <h3>{t(`chapter.side.${unit.side}`)}</h3>
            <p class="big">
              {#if charById.has(unit.character)}<Mention kind="characters" id={unit.character}>{unitName(unit)}</Mention>{:else}{unitName(unit)} <span class="muted tiny">{unit.character}</span>{/if}
            </p>
            <p>
              {#if cls}<Mention kind="classes" id={unit.class}>{cls.name || cls.id}<GenderSign gender={cls.gender} /></Mention>{:else}{unit.class}{/if}
              · {t('chapter.level')} {unit.level}{unit.autolevel ? ` (${t('chapter.autolevel')})` : ''}
            </p>
            <p class="muted small">
              {t('chapter.position')} : {unit.endX}, {unit.endY}
              {#if unit.x !== unit.endX || unit.y !== unit.endY} · {t('chapter.entersFrom', { x: unit.x, y: unit.y })}{/if}
            </p>
            <h3>{t('chapter.items')}</h3>
            {#if unit.items.length}
              <ul class="items">
                {#each unit.items as id, j (j)}
                  {@const it = itemById.get(id)}
                  <li>{#if it}<Mention kind="items" {id}><img class="pixel" src={itemIconUrl(it.iconId)} alt="" />{it.name}</Mention>{:else}{id}{/if}</li>
                {/each}
              </ul>
            {:else}<p class="muted">{t('field.none')}</p>{/if}
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
  .tiny { font-size: 0.72rem; }
  .small { font-size: 0.8rem; }
  .layout { display: grid; grid-template-columns: minmax(0, 1fr) 260px; gap: 1rem; align-items: start; }
  .map-panel { overflow: auto; max-height: calc(100vh - 260px); padding: 0.5rem; }
  .map { position: relative; background-size: 100% 100%; image-rendering: pixelated; }
  .unit {
    position: absolute; width: 32px; height: 32px; padding: 0; border: none; background: none;
    display: flex; align-items: flex-end; justify-content: center; cursor: pointer;
  }
  .unit img { image-rendering: pixelated; pointer-events: none; }
  .unit:hover, .unit.picked { outline: 2px solid var(--accent); outline-offset: -2px; border-radius: 4px; }
  .unit.picked { background: rgb(255 255 255 / 0.25); }
  .big { font-size: 1.1rem; font-weight: 600; margin: 0.2rem 0; }
  .items { list-style: none; padding: 0; margin: 0; display: flex; flex-direction: column; gap: 0.25rem; }
  .items img { width: 16px; height: 16px; }
  h3 { margin-top: 0.75rem; }
  @media (max-width: 1000px) { .layout { grid-template-columns: 1fr; } }
  @media (max-width: 800px) { .editor { grid-template-columns: 1fr; } }
</style>
