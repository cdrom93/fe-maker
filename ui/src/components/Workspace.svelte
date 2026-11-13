<script lang="ts">
  import { note } from '../lib/activity'
  import { onDestroy, onMount, tick } from 'svelte'
  import { appContext, resetAppContext } from '../lib/appContext.svelte'
  import { api, type DataKind } from '../lib/api'
  import { projectView } from '../lib/appContext.svelte'
  import { magicSplit } from '../lib/magic.svelte'
  import { skillsOption } from '../lib/skills.svelte'
  import { EditableList } from '../lib/history.svelte'
  import { problemText, t } from '../lib/i18n.svelte'
  import { type Focus, type NavKind, provideNavigator } from '../lib/navigation.svelte'
  import type { ChaptersData, DialoguesData, MapsData, Character, ClassData, ClassView, Combat, Item, Problem, ProjectInfo, Reference } from '../lib/types'
  import BuildPanel from './BuildPanel.svelte'
  import ChapterEditor from './ChapterEditor.svelte'
  import ChapterFlow from './ChapterFlow.svelte'
  import CharacterEditor from './CharacterEditor.svelte'
  import ClassEditor from './ClassEditor.svelte'
  import DialogueEditor from './DialogueEditor.svelte'
  import CombatEditor from './CombatEditor.svelte'
  import ItemEditor from './ItemEditor.svelte'
  import GameOptions from './GameOptions.svelte'
  import MusicLibraryPage from './MusicLibrary.svelte'
  import { fileMenu } from '../lib/filemenu.svelte'
  import ProjectIdentityDialog from './ProjectIdentityDialog.svelte'
  import MapEditor from './MapEditor.svelte'
  import AddChapter from './AddChapter.svelte'
  import Mention from './Mention.svelte'

  let { project, onClosed, onRenamed }: { project: ProjectInfo; onClosed: () => void; onRenamed: () => void } = $props()

  $effect(() => {
    projectView.showOriginal = project.meta.showOriginal !== false
    magicSplit.on = !!(project.meta.gameOptions as Record<string, unknown> | undefined)?.strMagSplit
    skillsOption.on = !!(project.meta.gameOptions as Record<string, unknown> | undefined)?.skills
  })
  $effect(() => {
    document.documentElement.classList.toggle('hide-original', !projectView.showOriginal)
    return () => document.documentElement.classList.remove('hide-original')
  })

  type Tab = NavKind
  // The work follows the story: the campaign, then a chapter (its units, map and dialogues), then the game's lists.
  const TABS: Tab[] = ['flow', 'chapters', 'characters', 'classes', 'items', 'combat', 'music', 'options']
  const CHAPTER_VIEWS: Tab[] = ['chapters', 'maps', 'dialogues']
  const startsBlank = firstTab() === 'options'
  let tab = $state<Tab>(startsBlank ? 'options' : 'flow')

  /** A project just created blank opens on what it keeps of the game. */
  function firstTab(): Tab {
    try {
      const asked = sessionStorage.getItem('fe-maker.first-tab')
      sessionStorage.removeItem('fe-maker.first-tab')
      return asked === 'options' ? 'options' : 'flow'
    } catch {
      return 'flow'
    }
  }
  let reference = $state<Reference | null>(null)
  let problems = $state<Problem[]>([])
  let build = $state<{ launch: boolean } | null>(null)
  /** ticket 174: the Rename and Save as dialogs */
  let identity = $state<'rename' | 'saveAs' | null>(null)
  let start = $state('map')
  let focus = $state<Focus | null>(null)

  $effect(() => {
    appContext.tab = tab
    note(`tab ${tab}`)
    appContext.detail = ''
  })
  onDestroy(resetAppContext)

  // One chapter at a time: its units, map and dialogues stay on it.
  let chapterList = $state<{ index: number; id: string; title: string; map: string | null; hidden?: boolean }[]>([])
  let currentChapter = $state<number | null>(null)
  /** The editors of the Chapters tab read their lists once: a new chapter opens them again. */
  let added = $state(0)
  $effect(() => {
    const id = appContext.recordId
    if (!id) return
    if (tab === 'maps') currentChapter = chapterList.find((c) => c.map === id)?.index ?? currentChapter
    else if ((tab === 'chapters' || tab === 'dialogues' || tab === 'flow') && /^\d+$/.test(id)) currentChapter = Number(id)
  })

  function openChapterView(view: Tab, index = currentChapter) {
    const chapter = chapterList.find((c) => c.index === index)
    navigator.open(view, chapter ? (view === 'maps' ? chapter.map : String(chapter.index)) : null)
  }

  /** The project's actions go in the app's top bar (ticket 145): one line less on every screen. */
  function toHeader(node: HTMLElement) {
    document.getElementById('header-actions')?.appendChild(node)
    return { destroy: () => node.remove() }
  }

  const navigator = {
    open(kind: NavKind, id: string | null = null) {
      tab = kind
      focus = { kind, id, n: (focus?.n ?? 0) + 1 }
    },
    get focus() {
      return focus
    },
  }
  provideNavigator(navigator)

  // "Back" (ticket 62): the places seen, a place being a tab and its record.
  type Place = { tab: Tab; id: string }
  let trail = $state<Place[]>([])
  let ahead = $state<Place[]>([])   // the places left by Back, for Forward (ticket 36)
  let changes = $state<HTMLDetailsElement>()
  let here: Place = { tab: 'characters', id: '' }
  let settle: ReturnType<typeof setTimeout> | undefined
  $effect(() => {
    const place = { tab, id: appContext.recordId }
    clearTimeout(settle)
    // A little later: a tab first shows its first record, then the one asked for.
    settle = setTimeout(() => {
      if (place.tab === here.tab && place.id === here.id) return
      if (place.tab !== here.tab || here.id) trail = [...trail, here].slice(-50)
      ahead = []
      here = place
    }, 150)
  })
  onDestroy(() => clearTimeout(settle))

  function back() {
    const place = trail.at(-1)
    if (!place) return
    trail = trail.slice(0, -1)
    ahead = [...ahead, here].slice(-50)
    here = place
    navigator.open(place.tab, place.id || null)
  }

  function forward() {
    const place = ahead.at(-1)
    if (!place) return
    ahead = ahead.slice(0, -1)
    trail = [...trail, here].slice(-50)
    here = place
    navigator.open(place.tab, place.id || null)
  }

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
    dialogues: new EditableList<DialoguesData>((r) => save('dialogues', r[0])),
  }
  const allLists = Object.values(lists)
  /** The latest changes of all the tabs. */
  const allSteps = $derived(Object.entries(lists)
    .flatMap(([name, list]) => (list.steps as { name: string; time: string; order: number }[])
      .map((s, index) => ({ ...s, index, list: list as { undoTo: (step: number) => void }, tab: name as Tab })))
    .sort((a, b) => b.order - a.order))

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
          // a class the project adds has its model's animations and gender, and is listed with the used ones
          const facts = reference!.classFacts[c.id] ?? { ...reference!.classFacts[c.model ?? ''], usedInGame: true }
          return { ...c, ...facts, usedInGame: facts.usedInGame || usedInProject.has(c.id) }
        })
      : [],
  )
  const errors = $derived(problems.filter((p) => p.severity === 'error'))
  const warnings = $derived(problems.filter((p) => p.severity === 'warning'))
  const saving = $derived(allLists.some((l) => l.saving))
  // the story flow edits the dialogues' scripts: its undo is theirs
  const active = $derived(tab === 'options' || tab === 'music' ? undefined : lists[tab === 'flow' ? 'dialogues' : tab])

  /** A class's battle animations changed: the weapons each class animates and the problems follow (ticket 50). */
  async function refreshAnimated() {
    const [ref, probs] = await Promise.all([api.reference(), api.problems()])
    reference = ref
    problems = probs.problems
  }

  onMount(() => loadAll())

  /** All the project's data (again after a change made by the server, such as an added chapter). */
  async function loadAll() {
    const [ref, chars, cls, items, combat, chaptersData, mapsData, dialoguesData, probs, testOpts, allChapters] = await Promise.all([
      api.reference(),
      api.getData<Character[]>('characters'),
      api.getData<ClassData[]>('classes'),
      api.getData<Item[]>('items'),
      api.getData<Combat>('combat'),
      api.getData<ChaptersData>('chapters'),
      api.getData<MapsData>('maps'),
      api.getData<DialoguesData>('dialogues'),
      api.problems(),
      api.testOptions(),
      api.chapters(),
    ])
    chapterList = allChapters
    start = testOpts.start
    reference = ref
    lists.characters.load(chars)
    lists.classes.load(cls)
    lists.items.load(items)
    lists.combat.load([combat])
    lists.chapters.load([chaptersData])
    lists.maps.load([mapsData])
    lists.dialogues.load([dialoguesData])
    problems = probs.problems
  }

  const flushAll = () => Promise.all(allLists.map((l) => l.flush()))

  /** Display name of a record mentioned by a problem. */
  function recordName(kind: Problem['kind'], id: string): string {
    if (kind === 'combat') return t('ws.combat')
    if (kind === 'chapters') return (/^\d+$/.test(id) ? chapterList.find((c) => String(c.index) === id)?.title : '') || id.replace('UnitDef_Event_', '')
    if (kind === 'maps') return id
    if (kind === 'dialogues' && id.startsWith('new')) return t('dlg.newQuotes')
    if (kind === 'dialogues' && id.startsWith('script:')) return t('dlg.aSequence')
    if (kind === 'dialogues' && id.startsWith('support')) return t('dlg.supports')
    if (kind === 'dialogues') return t('dlg.message', { id: `0x${Number(id.split('#')[0]).toString(16).toUpperCase()}` })
    const record = (lists[kind].records as { id: string; name: string }[]).find((r) => r.id === id)
    return record?.name || id || t(`ws.${kind}`)
  }

  async function startBuild(launch: boolean) {
    await flushAll()
    build = { launch }
  }

  /** Test from a chapter's map ("Test this chapter"), or from the start of the game. */
  async function testFrom(index: number) {
    const opts = await api.setTestOptions({ start: 'map', chapter: index })
    start = opts.start
    await startBuild(true)
  }

  async function testFromStart() {
    await api.setTestOptions({ chapter: 0 })
    await startBuild(true)
  }

  async function close() {
    await flushAll()
    await api.closeProject()
    onClosed()
  }

  // The File menu, top left in the app's bar, acts on this project.
  const commands = {
    flush: flushAll,
    saveAs: () => (identity = 'saveAs'),
    rename: () => (identity = 'rename'),
    openFolder: () => api.revealProject(),
    exportPatch: () => startBuild(false),
    canExport: () => errors.length === 0,
    close,
  }
  fileMenu.project = commands
  // Another project opened from the File menu: its Workspace is created before this one is destroyed, so only
  // clear the commands if they are still ours (ticket 35: the menu had lost the new project's commands).
  onDestroy(() => {
    if (fileMenu.project === commands) fileMenu.project = null
  })

  /** The browser's own "back" and "forward" (the mouse's side buttons, Alt + arrows, ticket 36) are "Back" and
   * "Forward": the page sits on a middle entry of its history, between two guard entries; going to either one calls
   * Back or Forward, then the browser is sent back to the middle one, so the page is never left. (The forward
   * button's own mouse event does not reach the page in every browser.) */
  function armHistory() {
    if (history.state?.feMaker === 'middle') return
    history.replaceState({ feMaker: 'back' }, '')
    history.pushState({ feMaker: 'middle' }, '')
    history.pushState({ feMaker: 'forward' }, '')
    history.back()
  }
  function onPopState(e: PopStateEvent) {
    const at = e.state?.feMaker
    if (at === 'back') {
      history.forward()
      back()
    } else if (at === 'forward') {
      history.back()
      forward()
    }
  }
  onMount(armHistory)

  function onKey(e: KeyboardEvent) {
    if (fileMenu.keysOpen || identity || !(e.ctrlKey || e.metaKey)) return
    const key = e.key.toLowerCase()
    if (key === 's') {
      e.preventDefault()   // the browser's own "save the page"
      flushAll()
    } else if (key === 'z' && !e.shiftKey) {
      e.preventDefault()
      active?.undo()
    } else if (key === 'y' || (key === 'z' && e.shiftKey)) {
      e.preventDefault()
      active?.redo()
    }
  }
</script>

<svelte:window onkeydown={onKey} onpopstate={onPopState} />


<div class="toolbar">
  <div class="title">
    <h1>{project.name}</h1>
    <span class="muted small">{saving ? t('ws.saving') : t('ws.saved')}</span>
  </div>
  <div class="row actions" use:toHeader>
    <button onclick={back} disabled={!trail.length} title={t('ws.backHint')}>← {t('ws.back')}</button>
    <button onclick={forward} disabled={!ahead.length} title={t('ws.forwardHint')}>{t('ws.forward')} →</button>
    <button onclick={() => active?.undo()} disabled={!active?.canUndo} title="Ctrl+Z">↶ {t('ws.undo')}</button>
    {#if allSteps.length}
      <details class="changes" bind:this={changes}>
        <summary title={t('ws.changesHint')}>{t('ws.changes', { n: allSteps.length })}</summary>
        <ol>
          {#each allSteps.slice(0, 15) as s (s.order)}
            <li><button class="link" title={t('ws.changesBack')} onclick={() => { s.list.undoTo(s.index); tab = s.tab; if (changes) changes.open = false }}>
              {s.time} · {t(`ws.${s.tab}`)}{s.name ? ` · ${s.name}` : ''}
            </button></li>
          {/each}
        </ol>
      </details>
    {/if}
    <button onclick={() => active?.redo()} disabled={!active?.canRedo} title="Ctrl+Y">↷ {t('ws.redo')}</button>
    {#if CHAPTER_VIEWS.includes(tab) && currentChapter !== null}
      <button class="play" onclick={() => testFrom(currentChapter!)} disabled={errors.length > 0} title={t('flow.testHint')}>▶ {t('ws.testChapter')}</button>
    {/if}
    <button class:play={!CHAPTER_VIEWS.includes(tab) || currentChapter === null} onclick={testFromStart} disabled={errors.length > 0}>▶ {t('ws.test')}</button>
  </div>
</div>

{#snippet problemList()}
  <ul class="problems">
    {#each [...errors, ...warnings] as p, i (i)}
      {@const isRecord = p.kind !== 'combat' && p.kind !== 'chapters' && p.kind !== 'dialogues' && !!p.id}
      {@const target = p.kind === 'maps' || (p.kind === 'chapters' && /^\d+$/.test(p.id)) ? p.id : isRecord ? p.id : null}
      <li class={p.severity}>
        <Mention kind={p.kind} id={target}>{recordName(p.kind, p.id)}</Mention>
        — {problemText(p)}
      </li>
    {/each}
  </ul>
{/snippet}

{#if errors.length}
  <details class="summary">
    <summary><span class="bad">{t('ws.problems', { n: errors.length })}</span></summary>
    {@render problemList()}
  </details>
{/if}

<div class="tabs" role="tablist">
  {#each TABS as name (name)}
    {@const views = name === 'chapters' ? CHAPTER_VIEWS : [name]}
    {@const count = problems.filter((p) => views.includes(p.kind as Tab) && p.severity === 'error').length}
    {@const here = views.includes(tab)}
    <button role="tab" aria-selected={here} class:active={here} onclick={() => (name === 'chapters' ? openChapterView('chapters') : (tab = name))}>
      {t(`ws.${name}`)}{#if count}<span class="badge">{count}</span>{/if}
    </button>
  {/each}
</div>
{#if CHAPTER_VIEWS.includes(tab)}
  <div class="views" role="tablist">
    {#each CHAPTER_VIEWS as view (view)}
      <button role="tab" aria-selected={tab === view} class:active={tab === view} onclick={() => openChapterView(view)}>{t(`ws.view.${view}`)}</button>
    {/each}
    <span class="view-add">
      <AddChapter after={currentChapter ?? 0} label={t(tab === 'maps' ? 'ws.newMap' : 'flow.add.button')}
                  flush={async () => { await lists.chapters.flush(); await lists.dialogues.flush(); await lists.maps.flush() }}
                  onadded={async (index) => { await loadAll(); added++; await tick(); openChapterView(tab, index) }} />
    </span>
  </div>
{/if}

{#if reference}
  {#if tab === 'characters'}
    <CharacterEditor list={lists.characters} {classes} items={lists.items.records} {reference} {problems} onproblems={(p) => (problems = p)} />
  {:else if tab === 'classes'}
    <ClassEditor list={lists.classes} {classes} items={lists.items.records} {reference} {problems} onanimations={refreshAnimated} />
  {:else if tab === 'items'}
    <ItemEditor list={lists.items} {classes} characters={lists.characters.records} {reference} {problems} />
  {:else if tab === 'combat'}
    <CombatEditor list={lists.combat} {classes} items={lists.items.records} {reference} {problems} />
  {:else if tab === 'chapters'}
    {#key added}<ChapterEditor list={lists.chapters} maps={lists.maps.records[0]} characters={lists.characters.records} gameLevels={reference.gameLevels} {classes} items={lists.items.records} {problems} />{/key}
  {:else if tab === 'flow'}
    <ChapterFlow list={lists.dialogues} chapterList={lists.chapters} ontest={testFrom} onreload={loadAll} todo={problemList} todoCount={{ errors: errors.length, warnings: warnings.length }} />
  {:else if tab === 'maps'}
    {#key added}<MapEditor list={lists.maps} chapterList={lists.chapters} items={lists.items.records} characters={lists.characters.records} {problems} />{/key}
  {:else if tab === 'music'}
    <MusicLibraryPage />
  {:else if tab === 'options'}
    <GameOptions onscope={loadAll} scopeFirst={startsBlank} />
  {:else}
    {#key added}<DialogueEditor list={lists.dialogues} chapterList={lists.chapters} characters={lists.characters.records} {problems} />{/key}
  {/if}
{/if}

{#if identity}
  <ProjectIdentityDialog {project} mode={identity} onClose={() => (identity = null)} onSaved={onRenamed} />
{/if}

{#if build}
  <BuildPanel launch={build.launch} onClose={() => (build = null)} />
{/if}

<style>
  /* In the app's top bar (App.svelte), on its dark background */
  .actions { flex-wrap: nowrap; gap: 0.4rem; }
  .actions button:not(.play) { background: transparent; color: var(--header-text); border-color: #ffffff33; padding: 0.25em 0.7em; font-size: 0.85rem; }
  .actions button:not(.play):hover:not(:disabled) { border-color: var(--header-text); }
  .actions button.play { padding: 0.25em 0.8em; font-size: 0.85rem; }
  .actions .changes summary { color: var(--header-muted); }
  .toolbar { display: flex; justify-content: space-between; align-items: center; gap: 1rem; flex-wrap: wrap; margin-bottom: 0.75rem; }
  .title { display: flex; align-items: baseline; gap: 0.75rem; }
  .changes { position: relative; font-size: 0.8rem; align-self: center; }
  .changes summary { cursor: pointer; color: var(--muted); }
  .changes ol { position: absolute; z-index: 30; right: 0; min-width: 14rem; margin: 0.3rem 0 0; padding: 0.4rem 0.6rem; list-style: none; background: var(--panel); border: 1px solid var(--border); border-radius: var(--radius); }
  .title h1 { margin: 0; }
  .small { font-size: 0.8rem; }
  .views { display: flex; gap: 0.3rem; margin: -0.5rem 0 0.75rem; }
  .view-add { margin-left: auto; }
  .view-add :global(button) { border: 1px solid var(--border); color: var(--text); }
  .views { flex-wrap: wrap; align-items: flex-start; }
  .views button { border: none; background: none; color: var(--muted); padding: 0.35rem 0.8rem; }
  .views button.active { background: var(--accent-soft); color: var(--text); font-weight: 800; }
  .check { flex-direction: row; align-items: center; gap: 0.35rem; font-size: 0.85rem; }
  .summary { margin: 0 0 0.75rem; font-size: 0.9rem; }
  .summary summary { cursor: pointer; display: flex; gap: 1rem; }
  .problems { margin: 0.4rem 0 0; padding-left: 1.2rem; max-height: 180px; overflow-y: auto; font-size: 0.85rem; }
  .problems .error { color: var(--bad); }
  .problems .warning { color: var(--warn); }
  .bad { color: var(--bad); }
  .warn { color: var(--warn); }
  .tabs { display: flex; gap: 0.3rem; padding: 0.3rem; margin-bottom: 1rem; overflow-x: auto; background: var(--panel); border: 1px solid var(--border); border-radius: var(--radius-big); }
  .tabs button { border: none; background: none; padding: 0.55rem 1rem; white-space: nowrap; color: var(--muted); }
  .tabs button:hover:not(.active) { background: var(--panel-2); color: var(--text); }
  .tabs button.active { background: var(--header); color: var(--header-text); font-weight: 800; }
  .badge { margin-left: 0.4rem; background: var(--bad); color: var(--panel); border-radius: 999px; padding: 0 0.45em; font-size: 0.75rem; }
</style>
