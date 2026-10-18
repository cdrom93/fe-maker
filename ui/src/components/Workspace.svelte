<script lang="ts">
  import { onMount } from 'svelte'
  import { api } from '../lib/api'
  import { EditableList } from '../lib/history.svelte'
  import { t } from '../lib/i18n.svelte'
  import type { Character, ClassData, ClassView, Combat, Item, Problem, ProjectInfo, Reference } from '../lib/types'
  import BuildPanel from './BuildPanel.svelte'
  import CharacterEditor from './CharacterEditor.svelte'
  import ClassEditor from './ClassEditor.svelte'
  import CombatEditor from './CombatEditor.svelte'
  import ItemEditor from './ItemEditor.svelte'
  import KeysDialog from './KeysDialog.svelte'

  let { project, onClosed }: { project: ProjectInfo; onClosed: () => void } = $props()

  type Tab = 'characters' | 'classes' | 'items' | 'combat'
  const TABS: Tab[] = ['characters', 'classes', 'items', 'combat']
  let tab = $state<Tab>('characters')
  let reference = $state<Reference | null>(null)
  let problems = $state<Problem[]>([])
  let build = $state<{ launch: boolean } | null>(null)
  let showKeys = $state(false)
  let start = $state('map')

  async function save(kind: 'characters' | 'items' | 'classes' | 'combat', data: unknown) {
    problems = (await api.saveData(kind, data)).problems
  }

  const lists = {
    characters: new EditableList<Character>((r) => save('characters', r)),
    classes: new EditableList<ClassData>((r) => save('classes', r)),
    items: new EditableList<Item>((r) => save('items', r)),
    // The combat data is a single object, kept as a one-element list for undo/autosave.
    combat: new EditableList<Combat>((r) => save('combat', r[0])),
  }
  const allLists = Object.values(lists)

  const classes = $derived<ClassView[]>(
    reference ? lists.classes.records.map((c) => ({ ...c, ...reference!.classFacts[c.id] })) : [],
  )
  const errors = $derived(problems.filter((p) => p.severity === 'error'))
  const warnings = $derived(problems.filter((p) => p.severity === 'warning'))
  const saving = $derived(allLists.some((l) => l.saving))
  const active = $derived(lists[tab])

  onMount(async () => {
    const [ref, chars, cls, items, combat, probs, testOpts] = await Promise.all([
      api.reference(),
      api.getData<Character[]>('characters'),
      api.getData<ClassData[]>('classes'),
      api.getData<Item[]>('items'),
      api.getData<Combat>('combat'),
      api.problems(),
      api.testOptions(),
    ])
    start = testOpts.start
    reference = ref
    lists.characters.load(chars)
    lists.classes.load(cls)
    lists.items.load(items)
    lists.combat.load([combat])
    problems = probs.problems
  })

  const flushAll = () => Promise.all(allLists.map((l) => l.flush()))

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
      active.undo()
    } else if (key === 'y' || (key === 'z' && e.shiftKey)) {
      e.preventDefault()
      active.redo()
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
    <button onclick={() => active.undo()} disabled={!active.canUndo} title="Ctrl+Z">↶ {t('ws.undo')}</button>
    <button onclick={() => active.redo()} disabled={!active.canRedo} title="Ctrl+Y">↷ {t('ws.redo')}</button>
    <button onclick={() => startBuild(false)} disabled={errors.length > 0}>{t('ws.exportPatch')}</button>
    <label class="check" title={t('ws.startHint')}>
      {t('ws.start')}
      <select value={start} onchange={async (e) => (start = (await api.setTestOptions({ start: (e.target as HTMLSelectElement).value })).start)}>
        <option value="map">{t('ws.start.map')}</option>
        <option value="menu">{t('ws.start.menu')}</option>
        <option value="normal">{t('ws.start.normal')}</option>
      </select>
    </label>
    <button class="primary" onclick={() => startBuild(true)} disabled={errors.length > 0}>▶ {t('ws.test')}</button>
    <button onclick={() => (showKeys = true)}>🎮 {t('keys.title')}</button>
    <button onclick={close}>{t('ws.close')}</button>
  </div>
</div>

{#if errors.length || warnings.length}
  <p class="summary">
    {#if errors.length}<span class="bad">{t('ws.problems', { n: errors.length })}</span>{/if}
    {#if warnings.length}<span class="warn">{t('ws.warnings', { n: warnings.length })}</span>{/if}
  </p>
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
    <CharacterEditor list={lists.characters} {classes} {reference} {problems} />
  {:else if tab === 'classes'}
    <ClassEditor list={lists.classes} {classes} {reference} {problems} />
  {:else if tab === 'items'}
    <ItemEditor list={lists.items} {reference} {problems} />
  {:else}
    <CombatEditor list={lists.combat} {classes} {reference} {problems} />
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
  .summary { display: flex; gap: 1rem; margin: 0 0 0.75rem; font-size: 0.9rem; }
  .bad { color: var(--bad); }
  .warn { color: var(--warn); }
  .tabs { display: flex; gap: 0.25rem; border-bottom: 1px solid var(--border); margin-bottom: 1rem; overflow-x: auto; }
  .tabs button { border: none; border-bottom: 2px solid transparent; border-radius: 0; background: none; padding: 0.5rem 1rem; white-space: nowrap; }
  .tabs button.active { border-bottom-color: var(--accent); font-weight: 600; }
  .badge { margin-left: 0.4rem; background: var(--bad); color: var(--panel); border-radius: 999px; padding: 0 0.45em; font-size: 0.75rem; }
</style>
