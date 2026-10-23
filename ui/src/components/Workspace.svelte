<script lang="ts">
  import { onDestroy, onMount } from 'svelte'
  import { appContext, resetAppContext } from '../lib/appContext.svelte'
  import { api, type DataKind } from '../lib/api'
  import { EditableList } from '../lib/history.svelte'
  import { problemText, t } from '../lib/i18n.svelte'
  import { type Focus, type NavKind, provideNavigator } from '../lib/navigation.svelte'
  import type { ChaptersData, MapsData, Character, ClassData, ClassView, Combat, Item, Problem, ProjectInfo, Reference } from '../lib/types'
  import BuildPanel from './BuildPanel.svelte'
  import ChapterEditor from './ChapterEditor.svelte'
  import CharacterEditor from './CharacterEditor.svelte'
  import ClassEditor from './ClassEditor.svelte'
  import CombatEditor from './CombatEditor.svelte'
  import ItemEditor from './ItemEditor.svelte'
  import KeysDialog from './KeysDialog.svelte'
  import MapEditor from './MapEditor.svelte'
  import Mention from './Mention.svelte'

  let { project, onClosed }: { project: ProjectInfo; onClosed: () => void } = $props()

  type Tab = NavKind
  const TABS: Tab[] = ['characters', 'classes', 'items', 'combat', 'chapters', 'maps']
  let tab = $state<Tab>('characters')
  let reference = $state<Reference | null>(null)
  let problems = $state<Problem[]>([])
  let build = $state<{ launch: boolean } | null>(null)
  let showKeys = $state(false)
  let start = $state('map')
  let simplePrologue = $state(true)
  let focus = $state<Focus | null>(null)

  $effect(() => {
    appContext.tab = tab
    appContext.detail = ''
  })
  onDestroy(resetAppContext)

  provideNavigator({
    open(kind: NavKind, id: string | null = null) {
      tab = kind
      focus = { kind, id, n: (focus?.n ?? 0) + 1 }
    },
    get focus() {
      return focus
    },
  })

  async function save(kind: DataKind, data: unknown) {
    problems = (await api.saveData(kind, data)).problems
  }

  const lists = {
    characters: new EditableList<Character>((r) => save('characters', r)),
    classes: new EditableList<ClassData>((r) => save('classes', r)),
    items: new EditableList<Item>((r) => save('items', r)),
    // The combat data is a single object, kept as a one-element list for undo/autosave.
    combat: new EditableList<Combat>((r) => save('combat', r[0])),
    chapters: new EditableList<ChaptersData>((r) => save('chapters', r[0])),
    maps: new EditableList<MapsData>((r) => save('maps', r[0])),
  }
  const allLists = Object.values(lists)

  // Classes the project uses (characters, generic units of edited chapters, and their promotions):
  // they count as used even if the original game never used them.
  const usedInProject = $derived.by(() => {
    const used = new Set<string>(lists.characters.records.map((c) => c.class))
    for (const units of Object.values(lists.chapters.records[0]?.unitGroups ?? {})) {
      for (const u of units) if (!u.character.startsWith('CHARACTER_')) used.add(u.class)
    }
    const promotions = new Map(lists.classes.records.map((k) => [k.id, k.promotions]))
    const todo = [...used]
    while (todo.length) {
      for (const next of promotions.get(todo.pop()!) ?? []) {
        if (!used.has(next)) {
          used.add(next)
          todo.push(next)
        }
      }
    }
    return used
  })

  const classes = $derived<ClassView[]>(
    reference
      ? lists.classes.records.map((c) => {
          const facts = reference!.classFacts[c.id]
          return { ...c, ...facts, usedInGame: facts.usedInGame || usedInProject.has(c.id) }
        })
      : [],
  )
  const errors = $derived(problems.filter((p) => p.severity === 'error'))
  const warnings = $derived(problems.filter((p) => p.severity === 'warning'))
  const saving = $derived(allLists.some((l) => l.saving))
  const active = $derived(lists[tab])

  onMount(async () => {
    const [ref, chars, cls, items, combat, chaptersData, mapsData, probs, testOpts] = await Promise.all([
      api.reference(),
      api.getData<Character[]>('characters'),
      api.getData<ClassData[]>('classes'),
      api.getData<Item[]>('items'),
      api.getData<Combat>('combat'),
      api.getData<ChaptersData>('chapters'),
      api.getData<MapsData>('maps'),
      api.problems(),
      api.testOptions(),
    ])
    start = testOpts.start
    simplePrologue = testOpts.simplePrologue
    reference = ref
    lists.characters.load(chars)
    lists.classes.load(cls)
    lists.items.load(items)
    lists.combat.load([combat])
    lists.chapters.load([chaptersData])
    lists.maps.load([mapsData])
    problems = probs.problems
  })

  const flushAll = () => Promise.all(allLists.map((l) => l.flush()))

  /** Display name of a record mentioned by a problem. */
  function recordName(kind: Problem['kind'], id: string): string {
    if (kind === 'combat') return t('ws.combat')
    if (kind === 'chapters') return id.replace('UnitDef_Event_', '')
    if (kind === 'maps') return id
    const record = (lists[kind].records as { id: string; name: string }[]).find((r) => r.id === id)
    return record?.name || id || t(`ws.${kind}`)
  }

  async function startBuild(launch: boolean) {
    await flushAll()
    build = { launch }
  }

  async function close() {
    await flushAll()
    await api.closeProject()
    onClosed()
  }

  function onKey(e: KeyboardEvent) {
    if (showKeys || !(e.ctrlKey || e.metaKey)) return
    const key = e.key.toLowerCase()
    if (key === 'z' && !e.shiftKey) {
      e.preventDefault()
      active?.undo()
    } else if (key === 'y' || (key === 'z' && e.shiftKey)) {
      e.preventDefault()
      active?.redo()
    }
  }
</script>

<svelte:window onkeydown={onKey} />

<div class="toolbar">
  <div class="title">
    <h1>{project.name}</h1>
    <span class="muted small">{saving ? t('ws.saving') : t('ws.saved')}</span>
  </div>
  <div class="row">
    <button onclick={() => active?.undo()} disabled={!active?.canUndo} title="Ctrl+Z">↶ {t('ws.undo')}</button>
    <button onclick={() => active?.redo()} disabled={!active?.canRedo} title="Ctrl+Y">↷ {t('ws.redo')}</button>
    <button onclick={() => startBuild(false)} disabled={errors.length > 0}>{t('ws.exportPatch')}</button>
    <label class="check" title={t('ws.startHint')}>
      {t('ws.start')}
      <select value={start} onchange={async (e) => (start = (await api.setTestOptions({ start: (e.target as HTMLSelectElement).value })).start)}>
        <option value="map">{t('ws.start.map')}</option>
        <option value="menu">{t('ws.start.menu')}</option>
        <option value="normal">{t('ws.start.normal')}</option>
      </select>
    </label>
    <label class="check" title={t('ws.simplePrologueHint')}>
      <input type="checkbox" checked={simplePrologue} onchange={async (e) => (simplePrologue = (await api.setTestOptions({ simplePrologue: (e.target as HTMLInputElement).checked })).simplePrologue)} />
      {t('ws.simplePrologue')}
    </label>
    <button class="primary" onclick={() => startBuild(true)} disabled={errors.length > 0}>▶ {t('ws.test')}</button>
    <button onclick={() => (showKeys = true)}>🎮 {t('keys.title')}</button>
    <button onclick={close}>{t('ws.close')}</button>
  </div>
</div>

{#if errors.length || warnings.length}
  <details class="summary">
    <summary>
      {#if errors.length}<span class="bad">{t('ws.problems', { n: errors.length })}</span>{/if}
      {#if warnings.length}<span class="warn">{t('ws.warnings', { n: warnings.length })}</span>{/if}
    </summary>
    <ul class="problems">
      {#each [...errors, ...warnings] as p, i (i)}
        {@const isRecord = p.kind !== 'combat' && p.kind !== 'chapters' && !!p.id}
        {@const target = p.kind === 'maps' ? p.id : isRecord ? p.id : null}
        <li class={p.severity}>
          <Mention kind={p.kind} id={target}>{recordName(p.kind, p.id)}</Mention>
          — {problemText(p)}
        </li>
      {/each}
    </ul>
  </details>
{/if}

<div class="tabs" role="tablist">
  {#each TABS as name (name)}
    {@const count = problems.filter((p) => p.kind === name && p.severity === 'error').length}
    <button role="tab" aria-selected={tab === name} class:active={tab === name} onclick={() => (tab = name)}>
      {t(`ws.${name}`)}{#if count}<span class="badge">{count}</span>{/if}
    </button>
  {/each}
</div>

{#if reference}
  {#if tab === 'characters'}
    <CharacterEditor list={lists.characters} {classes} items={lists.items.records} {reference} {problems} />
  {:else if tab === 'classes'}
    <ClassEditor list={lists.classes} {classes} items={lists.items.records} {reference} {problems} />
  {:else if tab === 'items'}
    <ItemEditor list={lists.items} {classes} characters={lists.characters.records} {reference} {problems} />
  {:else if tab === 'combat'}
    <CombatEditor list={lists.combat} {classes} items={lists.items.records} {reference} {problems} />
  {:else if tab === 'chapters'}
    <ChapterEditor list={lists.chapters} maps={lists.maps.records[0]} characters={lists.characters.records} {classes} items={lists.items.records} {problems} />
  {:else}
    <MapEditor list={lists.maps} items={lists.items.records} {problems} />
  {/if}
{/if}

{#if showKeys}
  <KeysDialog onClose={() => (showKeys = false)} />
{/if}

{#if build}
  <BuildPanel launch={build.launch} onClose={() => (build = null)} />
{/if}

<style>
  .toolbar { display: flex; justify-content: space-between; align-items: center; gap: 1rem; flex-wrap: wrap; margin-bottom: 0.75rem; }
  .title { display: flex; align-items: baseline; gap: 0.75rem; }
  .title h1 { margin: 0; }
  .small { font-size: 0.8rem; }
  .check { flex-direction: row; align-items: center; gap: 0.35rem; font-size: 0.85rem; }
  .summary { margin: 0 0 0.75rem; font-size: 0.9rem; }
  .summary summary { cursor: pointer; display: flex; gap: 1rem; }
  .problems { margin: 0.4rem 0 0; padding-left: 1.2rem; max-height: 180px; overflow-y: auto; font-size: 0.85rem; }
  .problems .error { color: var(--bad); }
  .problems .warning { color: var(--warn); }
  .bad { color: var(--bad); }
  .warn { color: var(--warn); }
  .tabs { display: flex; gap: 0.25rem; border-bottom: 1px solid var(--border); margin-bottom: 1rem; overflow-x: auto; }
  .tabs button { border: none; border-bottom: 2px solid transparent; border-radius: 0; background: none; padding: 0.5rem 1rem; white-space: nowrap; }
  .tabs button.active { border-bottom-color: var(--accent); font-weight: 600; }
  .badge { margin-left: 0.4rem; background: var(--bad); color: var(--panel); border-radius: 999px; padding: 0 0.45em; font-size: 0.75rem; }
</style>
