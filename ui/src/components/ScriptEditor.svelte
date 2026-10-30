<script lang="ts">
  // Visual editor of an event script (server: decomp/events.py): one block per command, with a form
  // for the commands FE Maker knows; the others are kept as they are and can be moved or removed.
  import { untrack } from 'svelte'
  import Help from './Help.svelte'
  import { api } from '../lib/api'
  import type { EditableList } from '../lib/history.svelte'
  import { problemText, t } from '../lib/i18n.svelte'
  import type { Character, DialoguesData, EventCommand, EventsReference, Problem } from '../lib/types'
  import Mention from './Mention.svelte'

  let {
    name,
    chapter,
    list,
    characters,
    problems,
    firstLine,
    onopenmessage,
    sceneKind = '',
  }: {
    name: string
    /** chapter index (unit groups of the chapter are offered), -1 if none */
    chapter: number
    list: EditableList<DialoguesData>
    characters: Character[]
    problems: Problem[]
    /** first line of a message (to show it in its block) */
    firstLine: (id: string) => string
    /** open a message of the script in the dialogue editor (a number, or "new:<key>") */
    onopenmessage: (id: string) => void
    /** what starts the script (beginning, ending...): the opening and ending scenes can be replaced by a simple one */
    sceneKind?: string
  } = $props()

  const NEW_MESSAGE = 'new:'   // a message made for a script (server: dialogues.SCENE_MESSAGE)
  // Commands that send the player to another chapter (server: decomp/story.py)
  const CHANGE_OPS = ['MNCH', 'MNC2', 'MNC3', 'MNC4', 'MNTS', 'MoveToChapter']

  const ICONS: Record<string, string> = {
    MUSC: '🎵', MUSS: '🎵', MURE: '🎵', MUSI: '🔉', MUNO: '🔊', MUSCMID: '🎵', MUSCSLOW: '🎵',
    Text: '💬', Text_BG: '💬', TEXTSHOW: '💬', TEXTSTART: '💬', TEXTEND: '💬', TEXTCONT: '💬', REMA: '💬',
    BACG: '🖼️', SetBackground: '🖼️', FADI: '🌓', FADU: '🌓', FAWI: '🌓', FAWU: '🌓',
    LOAD1: '👥', LOAD2: '👥', LOAD3: '👥', ENUN: '⏳', MOVE: '🚶', CUMO_AT: '📍', CUMO_CHAR: '📍', CURE: '📍',
    FlashCursor: '📍', CAMERA: '🎥', CAMERA2: '🎥', CAMERA_CAHR: '🎥', STAL: '⏱️', STAL2: '⏱️', STAL3: '⏱️',
    DISA: '👋', KILL: '💀', CUSA: '🤝', CUSN: '🤝', ENUT: '🚩', ENUF: '🏳️', CLEA: '🧹', CLEE: '🧹', CLEN: '🧹',
    NoFade: '⏹️', ENDA: '⏹️',
    CHECK_ALIVE: '❓', CHECK_EXISTS: '❓', CHECK_DEPLOYED: '❓', CHECK_EVENTID: '❓', CHECK_TURNS: '❓', CHECK_HARD: '❓',
    CHECK_MODE: '❓', CHECK_ENEMIES: '❓', CHECK_MONEY: '❓', CHECK_ACTIVE: '❓', CHECK_AT: '❓', SVAL: '🔢',
    LABEL: '🏷️', GOTO: '↪️', BEQ: '🔀', BNE: '🔀', BGE: '🔀', BGT: '🔀', BLE: '🔀', BLT: '🔀', CALL: '📞',
  }
  // Memory slots of the event engine (server: events.COMMANDS, kind "slot"): checks write their result in C.
  const SLOTS = ['0', '1', '2', '3', '4', '5', '6', '7', '8', '9', 'A', 'B', 'C', 'D'].map((s) => `EVT_SLOT_${s}`)
  const BRANCHES = ['GOTO', 'BEQ', 'BNE', 'BGE', 'BGT', 'BLE', 'BLT']
  // Ready-made conditions: a check, a branch past the block when it fails, and the block's end label.
  const CONDITIONS = ['if:alive', 'if:flag', 'if:turn']

  let reference = $state<EventsReference | null>(null)
  let original = $state<EventCommand[]>([])
  let file = $state('')
  let error = $state('')
  let groups = $state<string[]>([])
  let groupOrigins = $state<{ name: string; origin: string }[]>([])
  let selected = $state<number | null>(null)
  let adding = $state('')

  const commands = $derived<EventCommand[]>(list.records[0]?.scripts?.[name] ?? original)
  const edited = $derived(!!list.records[0]?.scripts?.[name])
  const named = $derived(characters.filter((c) => c.id.startsWith('CHARACTER_')))
  const charName = (id: string) => characters.find((c) => c.id === id)?.name || id.replace('CHARACTER_', '')
  const pretty = (constant: string, prefix: string) =>
    constant.replace(prefix, '').toLowerCase().replace(/_/g, ' ').replace(/^\w/, (c) => c.toUpperCase())
  const scriptProblems = $derived(problems.filter((p) => p.kind === 'dialogues' && (p.id === `script:${name}` || p.id.startsWith(`script:${name}#`))))
  const problemsAt = (i: number) => scriptProblems.filter((p) => p.id === `script:${name}#${i}`)

  $effect(() => {
    const n = name
    error = ''
    selected = null
    const known = untrack(() => reference)
    Promise.all([known ? Promise.resolve(known) : api.eventsReference(), api.eventScript(n)])
      .then(([ref, s]) => {
        if (n !== name) return
        reference = ref
        original = s.commands
        file = s.file
      })
      .catch((e) => (error = String(e)))
  })

  $effect(() => {
    const c = chapter
    groups = []
    groupOrigins = []
    if (c >= 0) {
      api.chapterUnits(c).then((u) => {
        groups = u.groups.map((g) => g.name)
        groupOrigins = u.groups.map((g) => ({ name: g.name, origin: g.origin }))
      }).catch(() => {})
    }
  })

  function save(next: EventCommand[]) {
    const same = JSON.stringify(next) === JSON.stringify(original)
    list.update(0, (d) => {
      d.scripts ??= {}
      if (same) delete d.scripts[name]
      else d.scripts[name] = JSON.parse(JSON.stringify(next))
    })
  }

  const labelNumber = (v: string) => (/^(0x[0-9a-f]+|\d+)$/i.test(v.trim()) ? Number(v.trim()) : NaN)
  /** Block index of each LABEL number, to show where a jump goes. */
  const labels = $derived(new Map(commands.flatMap((c, i) => (c.op === 'LABEL' ? [[labelNumber(c.args?.[0] ?? ''), i] as [number, number]] : []))))
  /** Indentation of each block: the blocks a forward jump skips are inside it. */
  const depths = $derived.by(() => {
    const d = commands.map(() => 0)
    commands.forEach((c, i) => {
      if (!BRANCHES.includes(c.op)) return
      const to = labels.get(labelNumber(c.args?.[0] ?? ''))
      if (to !== undefined && to > i) for (let n = i + 1; n < to; n++) d[n]++
    })
    return d
  })
  const nextLabel = () => Math.max(-1, ...[...labels.keys()].filter((n) => !isNaN(n))) + 1

  function setArg(i: number, k: number, value: string) {
    save(commands.map((c, n) => (n === i ? { ...c, args: (c.args ?? []).map((a, j) => (j === k ? value : a)) } : c)))
  }

  function move(i: number, by: number) {
    const j = i + by
    if (j < 0 || j >= commands.length) return
    const next = [...commands]
    ;[next[i], next[j]] = [next[j], next[i]]
    save(next)
    selected = j
  }

  function remove(i: number) {
    save(commands.filter((_, n) => n !== i))
    selected = null
  }

  /** Default arguments of a new command. */
  function fresh(op: string): EventCommand {
    const spec = reference?.commands[op] ?? []
    if (!spec.length) return { op }
    const first = named[0]?.id ?? 'CHARACTER_EIRIKA'
    const defaults: Record<string, string> = {
      song: reference?.songs.find((s) => s !== 'SONG_NONE') ?? '0', background: reference?.backgrounds[0] ?? '0',
      message: '0x0', character: first, group: groups[0] ?? '0', x: '0', y: '0', frames: '60', flag: 'EVFLAG_TMP(20)',
      number: '0', speed: '0', raw: '0', label: `0x${nextLabel().toString(16)}`, script: reference?.scripts[0] ?? '0',
      slot: op === 'SVAL' ? 'EVT_SLOT_1' : 'EVT_SLOT_C',
    }
    return {
      op,
      args: spec.map((a) => (op.startsWith('LOAD') && a.name === 'flag' ? '1' : a.name === 'right' ? 'EVT_SLOT_0' : defaults[a.kind] ?? '0')),
    }
  }

  /** The commands of a ready-made condition; the commands to run go between its branch and its label. */
  function condition(kind: string): EventCommand[] {
    const label = `0x${nextLabel().toString(16)}`
    if (kind === 'if:turn') {
      return [{ op: 'CHECK_TURNS' }, { op: 'SVAL', args: ['EVT_SLOT_1', '5'] }, { op: 'BLT', args: [label, 'EVT_SLOT_C', 'EVT_SLOT_1'] },
        { op: 'LABEL', args: [label] }]
    }
    const check = kind === 'if:alive' ? fresh('CHECK_ALIVE') : fresh('CHECK_EVENTID')
    return [check, { op: 'BEQ', args: [label, 'EVT_SLOT_C', 'EVT_SLOT_0'] }, { op: 'LABEL', args: [label] }]
  }

  /** New command after the selected one, else before the script's end (NoFade, ENDA). */
  function add() {
    if (!adding) return
    let at = selected !== null ? selected + 1 : commands.length
    if (selected === null) while (at > 0 && ['NoFade', 'ENDA', ''].includes(commands[at - 1].op)) at--
    const added = CONDITIONS.includes(adding) ? condition(adding) : [fresh(adding)]
    save([...commands.slice(0, at), ...added, ...commands.slice(at)])
    // a condition: select its branch, the next command added goes inside it
    selected = at + added.length - (CONDITIONS.includes(adding) ? 2 : 1)
    adding = ''
  }

  /** A new message of the project for a script (an empty conversation to write), and the commands
   *  using it, saved together (one undo step). */
  function withNewMessage(build: (ref: string) => EventCommand[]) {
    const key = `s${Date.now().toString(36)}`
    const next = build(`${NEW_MESSAGE}${key}`)
    list.update(0, (d) => {
      d.quotes ??= []
      d.quotes.push({ kind: 'scene', key, chapter, a: '', steps: [] })
      d.scripts ??= {}
      d.scripts[name] = JSON.parse(JSON.stringify(next))
    })
  }

  function newMessageAt(i: number, k: number) {
    withNewMessage((ref) => commands.map((c, n) => (n === i ? { ...c, args: (c.args ?? []).map((a, j) => (j === k ? ref : a)) } : c)))
  }

  /** The opening or ending scene replaced by a simple one: the army back on the map (first chapter:
   *  its units), the enemies of the opening, one conversation; the ending keeps where it leads. */
  function simpleScene() {
    if (!confirm(t('ev.simpleConfirm'))) return
    withNewMessage((ref) => {
      if (sceneKind === 'ending') {
        const change = commands.filter((c) => CHANGE_OPS.includes(c.op))
        return [{ op: 'Text', args: [ref] }, ...(change.length ? change : [{ op: 'MNC2', args: ['0x1'] }]), { op: 'ENDA' }]
      }
      const out: EventCommand[] = []
      const players = groupOrigins.find((g) => g.origin === 'players')
      // LOAD2 brings the army's units to the chapter's places; the first chapter has none yet.
      if (players) out.push({ op: chapter === 0 ? 'LOAD1' : 'LOAD2', args: ['1', players.name] }, { op: 'ENUN' })
      for (const g of groupOrigins.filter((g) => g.origin === 'opening')) out.push({ op: 'LOAD1', args: ['1', g.name] }, { op: 'ENUN' })
      out.push({ op: 'Text', args: [ref] }, { op: 'NoFade' }, { op: 'ENDA' })
      return out
    })
    selected = null
  }

  // The simple view (ticket 70): a scene told as steps, the game's technical commands left out of sight; a step opens
  // on its commands, the detailed view shows them all.
  const TECHNICAL = new Set(['', '#', 'NoFade', 'ENDA', 'ENUN', 'LABEL', 'SVAL', 'STAL', 'STAL2', 'STAL3', 'CURE', 'FADI', 'FADU', 'FAWI', 'FAWU', 'GOTO'])
  const TEXT_OPS = new Set(['TEXTSTART', 'Text', 'Text_BG', 'TEXTSHOW', 'TEXTCONT', 'TEXTEND', 'REMA'])
  type Step = { start: number; end: number; icon: string; text: string; message: string }

  function readAdvanced(): boolean {
    try {
      return localStorage.getItem('fe-maker.script-detail') === '1'
    } catch {
      return false
    }
  }
  let advanced = $state(readAdvanced())
  let openStep = $state<number | null>(null)
  function setAdvanced(on: boolean) {
    advanced = on
    openStep = null
    try {
      localStorage.setItem('fe-maker.script-detail', on ? '1' : '0')
    } catch {
      // storage unavailable: the view is just not remembered
    }
  }

  /** The values a command's step shows: names rather than constants. */
  function summary(c: EventCommand): string {
    const spec = reference?.commands[c.op] ?? []
    return spec.flatMap((a, k) => {
      const v = c.args?.[k] ?? ''
      if (a.kind === 'character') return [charName(v)]
      if (a.kind === 'group') return [v.replace('UnitDef_Event_', '')]
      if (a.kind === 'song') return [pretty(v, 'SONG_')]
      if (a.kind === 'background') return [pretty(v, 'BG_')]
      if (a.kind === 'x' || a.kind === 'y') return [v]
      return []
    }).join(', ')
  }

  const steps = $derived.by(() => {
    const out: Step[] = []
    let i = 0
    while (i < commands.length) {
      const c = commands[i]
      if (TEXT_OPS.has(c.op)) {
        const start = i
        let message = ''
        while (i < commands.length && (TEXT_OPS.has(commands[i].op) || commands[i].op === '')) {
          if (commands[i].args?.length && !message) message = commands[i].args![0]
          i++
        }
        const ref = messageRef(message)
        out.push({ start, end: i - 1, icon: '💬', text: (ref && firstLine(ref)) || t('ev.op.Text'), message: ref })
      } else if (c.op.startsWith('CHECK_')) {
        let end = i
        while (end < Math.min(i + 4, commands.length - 1) && !BRANCHES.includes(commands[end].op)) end++
        const what = c.op.startsWith('CHECK_EVENTID') ? t('ev.simple.flag') : label(c.op).replace(/^[^:]*:\s*/, '')
        const detail = summary(c)
        out.push({ start: i, end, icon: '❓', text: t('ev.simple.if', { what: detail ? `${what} (${detail})` : what }), message: '' })
        i = end + 1
      } else if (TECHNICAL.has(c.op)) {
        i++
      } else {
        const detail = summary(c)
        out.push({ start: i, end: i, icon: ICONS[c.op] ?? '•', text: detail ? `${label(c.op)} : ${detail}` : label(c.op), message: '' })
        i++
      }
    }
    return out
  })
  const hiddenCount = $derived(commands.length - steps.reduce((n, s) => n + s.end - s.start + 1, 0))

  function openOf(s: Step) {
    openStep = openStep === s.start ? null : s.start
    selected = s.end
  }

  function removeStep(s: Step) {
    const branch = commands[s.end]
    const end = BRANCHES.includes(branch?.op) ? labels.get(labelNumber(branch.args?.[0] ?? '')) : undefined
    save(commands.filter((_, n) => (n < s.start || n > s.end) && n !== end))
    selected = null
    openStep = null
  }

  function resetScript() {
    list.update(0, (d) => {
      if (d.scripts) delete d.scripts[name]
    })
  }

  const label = (op: string) => (t(`ev.op.${op}`) === `ev.op.${op}` ? op : t(`ev.op.${op}`))
  const isMessage = (v: string) => /^(0x[0-9a-f]+|\d+)$/i.test(v.trim())
  /** The message a value opens: a game message by number, or a message of the project */
  const messageRef = (v: string) => (v.startsWith(NEW_MESSAGE) ? v : isMessage(v) ? String(Number(v)) : '')
</script>

<div class="script">
  <div class="head">
    <h3>{t('ev.title', { name })}</h3>
    {#if edited}<button class="link" onclick={resetScript}>{t('ev.reset')}</button>{/if}
  </div>
  {#if sceneKind === 'beginning' || sceneKind === 'ending'}
    <p class="simple">
      <button onclick={simpleScene}>{t('ev.simple')}</button>
      <span class="tiny muted">{t(sceneKind === 'ending' ? 'ev.simpleEndingHint' : 'ev.simpleHint')}</span>
    </p>
  {/if}
  <div class="view">
    <Help text={advanced ? t('ev.hint') : t('ev.simple.hint')} />
    <button class="link small" onclick={() => setAdvanced(!advanced)}>{advanced ? t('ev.simple.toSimple') : t('ev.simple.toDetail', { n: hiddenCount })}</button>
  </div>
  {#if error}<p class="bad small">{error}</p>{/if}
  {#each scriptProblems.filter((p) => p.id === `script:${name}`) as pr, k (k)}<p class="bad small">{problemText(pr)}</p>{/each}

  {#snippet block(c: EventCommand, i: number)}
      {#if c.op === ''}
        <li class="gap" aria-hidden="true"></li>
      {:else}
        {@const spec = reference?.commands[c.op]}
        <li class:active={selected === i} class:comment={c.op === '#'} class:raw={!spec && c.op !== '#'} style:margin-left="{depths[i] * 1.2}rem">
          <button class="num" onclick={() => (selected = selected === i ? null : i)} title={t('ev.select')}>{i + 1}</button>
          <div class="body">
            {#if c.op === '#'}
              <span class="tiny">{c.text}</span>
            {:else if spec}
              <span class="op">{ICONS[c.op] ?? '•'} {label(c.op)}</span>
              {#each spec as a, k (k)}
                {@const v = c.args?.[k] ?? ''}
                <label class="arg">
                  <span class="tiny muted">{t(`ev.arg.${a.name}`)}</span>
                  {#if a.kind === 'song' && reference}
                    <select value={v} onchange={(e) => setArg(i, k, (e.target as HTMLSelectElement).value)}>
                      {#if !reference.songs.includes(v)}<option value={v}>{v}</option>{/if}
                      {#each reference.songs as s (s)}<option value={s}>{pretty(s, 'SONG_')}</option>{/each}
                    </select>
                  {:else if a.kind === 'background' && reference}
                    <select value={v} onchange={(e) => setArg(i, k, (e.target as HTMLSelectElement).value)}>
                      {#if !reference.backgrounds.includes(v)}<option value={v}>{v}</option>{/if}
                      {#each reference.backgrounds as b (b)}<option value={b}>{pretty(b, 'BG_')}</option>{/each}
                    </select>
                  {:else if a.kind === 'character' && (v.startsWith('CHARACTER_') || !v)}
                    <span class="inline">
                      <select value={v} onchange={(e) => setArg(i, k, (e.target as HTMLSelectElement).value)}>
                        {#if v && !named.some((n) => n.id === v)}<option value={v}>{v}</option>{/if}
                        {#each named as n (n.id)}<option value={n.id}>{n.name || n.id}</option>{/each}
                      </select>
                      {#if v}<Mention kind="characters" id={v}><span class="open">↗</span></Mention>{/if}
                    </span>
                  {:else if a.kind === 'message'}
                    {@const ref = messageRef(v)}
                    <span class="inline">
                      {#if v.startsWith(NEW_MESSAGE)}
                        <span class="tag">{t('ev.newMessage')}</span>
                      {:else}
                        <input class="short" value={v} onchange={(e) => setArg(i, k, (e.target as HTMLInputElement).value)} />
                      {/if}
                      {#if ref}<button class="link" onclick={() => onopenmessage(ref)} title={t('ev.openMessage')}>💬</button>{/if}
                      <button class="link" onclick={() => newMessageAt(i, k)} title={t('ev.newMessageHint')}>＋</button>
                    </span>
                    {#if ref && firstLine(ref)}<span class="tiny muted quote">« {firstLine(ref)} »</span>{/if}
                  {:else if a.kind === 'slot'}
                    <select value={v} onchange={(e) => setArg(i, k, (e.target as HTMLSelectElement).value)}>
                      {#if !SLOTS.includes(v)}<option value={v}>{v}</option>{/if}
                      {#each SLOTS as s (s)}<option value={s}>{t(`ev.slot.${s.slice(-1)}`)}</option>{/each}
                    </select>
                  {:else if a.kind === 'label'}
                    {@const to = labels.get(labelNumber(v))}
                    <span class="inline">
                      <input class="short" value={v} onchange={(e) => setArg(i, k, (e.target as HTMLInputElement).value)} />
                      {#if c.op !== 'LABEL'}
                        {#if to !== undefined}<button class="link tiny" onclick={() => (selected = to)}>{t('ev.toBlock', { n: to + 1 })}</button>
                        {:else}<span class="bad tiny">{t('ev.noLabel')}</span>{/if}
                      {/if}
                    </span>
                  {:else if a.kind === 'script'}
                    <input value={v} list="ev-scripts" onchange={(e) => setArg(i, k, (e.target as HTMLInputElement).value)} />
                  {:else if a.kind === 'group'}
                    <input value={v} list="ev-groups" onchange={(e) => setArg(i, k, (e.target as HTMLInputElement).value)} />
                  {:else}
                    <input class:short={['x', 'y', 'frames', 'number'].includes(a.kind)} value={v} onchange={(e) => setArg(i, k, (e.target as HTMLInputElement).value)} />
                    {#if a.kind === 'frames' && /^\d+$/.test(v)}<span class="tiny muted">{(Number(v) / 60).toFixed(1)} s</span>{/if}
                    {#if a.kind === 'character' && v}<span class="tiny muted">{charName(v)}</span>{/if}
                  {/if}
                </label>
              {/each}
            {:else}
              <span class="tag" title={t('ev.rawHint')}>{t('ev.raw')}</span>
              <code>{c.op}{c.args ? `(${c.args.join(', ')})` : ''}</code>
            {/if}
            {#each problemsAt(i) as pr, k (k)}<p class="bad small">{problemText(pr)}</p>{/each}
          </div>
          <div class="actions">
            <button onclick={() => move(i, -1)} disabled={i === 0} title={t('dlg.up')}>↑</button>
            <button onclick={() => move(i, 1)} disabled={i === commands.length - 1} title={t('dlg.down')}>↓</button>
            <button class="danger" onclick={() => remove(i)} title={t('dlg.remove')}>✕</button>
          </div>
        </li>
      {/if}
  {/snippet}

  <ol class="blocks">
    {#if advanced}
      {#each commands as c, i (i)}{@render block(c, i)}{/each}
    {:else}
      {#each steps as s (s.start)}
        <li class="step" class:active={openStep === s.start} style:margin-left="{depths[s.start] * 1.2}rem">
          <button class="row" onclick={() => openOf(s)} title={t('ev.simple.open')}>
            <span>{s.icon}</span> <span class="what">{s.text}</span>
          </button>
          {#if s.message}<button class="link" onclick={() => onopenmessage(s.message)} title={t('ev.openMessage')}>{t('ev.simple.edit')}</button>{/if}
          <button class="danger" onclick={() => removeStep(s)} title={t('dlg.remove')}>✕</button>
        </li>
        {#if openStep === s.start}
          {#each commands.slice(s.start, s.end + 1) as c, k (k)}{@render block(c, s.start + k)}{/each}
        {/if}
      {/each}
      {#if !steps.length}<li class="muted small">{t('ev.simple.empty')}</li>{/if}
    {/if}
  </ol>
  <datalist id="ev-groups">{#each groups as g (g)}<option value={g}></option>{/each}</datalist>
  <datalist id="ev-scripts">{#each reference?.scripts ?? [] as s (s)}<option value={s}></option>{/each}</datalist>

  {#if reference}
    <div class="add">
      <select bind:value={adding} aria-label={t('ev.add')}>
        <option value="">{t('ev.add')}</option>
        <optgroup label={t('ev.conditions')}>
          {#each CONDITIONS as op (op)}<option value={op}>❓ {t(`ev.${op.replace(':', '.')}`)}</option>{/each}
        </optgroup>
        <optgroup label={t('ev.commands')}>
          {#each reference.addable as op (op)}<option value={op}>{ICONS[op] ?? ''} {label(op)}</option>{/each}
        </optgroup>
      </select>
      <button onclick={add} disabled={!adding}>＋ {selected !== null ? t('ev.addAfter', { n: selected + 1 }) : t('ev.addEnd')}</button>
    </div>
  {/if}
</div>

<style>
  .script { display: flex; flex-direction: column; gap: 0.5rem; min-width: 0; }
  .head { display: flex; align-items: center; justify-content: space-between; gap: 0.5rem; }
  .head h3 { margin: 0; overflow-wrap: anywhere; }
  .small { font-size: 0.8rem; }
  .tiny { font-size: 0.72rem; }
  .bad { color: var(--bad); }
  .danger { color: var(--bad); }
  p { margin: 0; }
  .link { border: none; background: none; padding: 0; color: var(--accent); font: inherit; }
  .blocks { list-style: none; margin: 0; padding: 0; display: flex; flex-direction: column; gap: 0.25rem; max-height: calc(100vh - 330px); overflow-y: auto; }
  .blocks li { display: flex; align-items: flex-start; gap: 0.4rem; padding: 0.25rem 0.3rem; border: 1px solid var(--border); border-radius: 6px; background: var(--panel); }
  .blocks li.active { border-color: var(--accent); background: var(--accent-soft); }
  .blocks li.comment { border-style: dashed; color: var(--muted); font-style: italic; }
  .blocks li.raw { background: transparent; }
  .blocks li.gap { border: none; background: none; padding: 0; height: 0.3rem; }
  .num { width: 2rem; padding: 0.1rem; font-size: 0.75rem; flex-shrink: 0; }
  .body { flex: 1; display: flex; flex-wrap: wrap; align-items: flex-end; gap: 0.3rem 0.6rem; min-width: 0; }
  .op { font-weight: 600; font-size: 0.85rem; align-self: center; }
  .arg { display: flex; flex-direction: column; gap: 0.05rem; }
  .arg input, .arg select { font-size: 0.82rem; }
  .arg input.short { width: 4.5rem; }
  .inline { display: inline-flex; align-items: center; gap: 0.3rem; }
  .tag { font-size: 0.72rem; color: var(--muted); align-self: center; }
  code { font-size: 0.78rem; overflow-wrap: anywhere; align-self: center; }
  .actions { display: flex; gap: 0.15rem; flex-shrink: 0; }
  .actions button { padding: 0 0.35rem; font-size: 0.8rem; }
  .add { display: flex; gap: 0.4rem; flex-wrap: wrap; }
  .view { display: flex; justify-content: space-between; align-items: baseline; gap: 0.75rem; }
  .blocks li.step { align-items: center; }
  .row { flex: 1; display: flex; gap: 0.4rem; align-items: center; min-width: 0; border: none; background: none; padding: 0.15rem; text-align: left; font-weight: 600; }
  .what { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .step .danger { padding: 0 0.35rem; font-size: 0.8rem; }
  .open { font-size: 0.8rem; }
  .simple { display: flex; align-items: center; gap: 0.5rem; flex-wrap: wrap; }
  .quote { max-width: 18rem; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
</style>
