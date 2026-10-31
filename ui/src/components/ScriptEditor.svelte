<script lang="ts">
  // Visual editor of an event script (server: decomp/events.py): one block per command, with a form
  // for the commands FE Maker knows; the others are kept as they are and can be moved or removed.
  import { untrack } from 'svelte'
  import Help from './Help.svelte'
  import { api } from '../lib/api'
  import type { EditableList } from '../lib/history.svelte'
  import { problemText, t } from '../lib/i18n.svelte'
  import type { Character, DialoguesData, EventCommand, EventsReference, Memory, Problem } from '../lib/types'
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
    GiveItem: '🎁', ChangeStat: '💪', MNC2: '🚪', LABEL: '🏷️', GOTO: '↪️', BEQ: '🔀', BNE: '🔀', BGE: '🔀', BGT: '🔀', BLE: '🔀', BLT: '🔀', CALL: '📞',
  }
  // Memory slots of the event engine (server: events.COMMANDS, kind "slot"): checks write their result in C.
  const SLOTS = ['0', '1', '2', '3', '4', '5', '6', '7', '8', '9', 'A', 'B', 'C', 'D'].map((s) => `EVT_SLOT_${s}`)
  const BRANCHES = ['GOTO', 'BEQ', 'BNE', 'BGE', 'BGT', 'BLE', 'BLT']
  // Ready-made conditions: a check, a branch past the block when it fails, and the block's end label.
  const CONDITIONS = ['if:alive', 'if:memory', 'if:notMemory', 'if:flag', 'if:turn']
  // Memories: the player's past choices, named here; their flag numbers stay out of sight (server: events.MEMORY_FLAGS).
  const MEMORY_ACTIONS = ['ask', 'memory:set', 'memory:forget']
  const STATS = ['hp', 'pow', 'skl', 'spd', 'def', 'res', 'lck', 'con', 'mov']
  const NEW_MEMORY = 'new'

  let reference = $state<EventsReference | null>(null)
  let original = $state<EventCommand[]>([])
  let file = $state('')
  let error = $state('')
  let groups = $state<string[]>([])
  let groupOrigins = $state<{ name: string; origin: string }[]>([])
  let selected = $state<number | null>(null)
  let adding = $state('')
  /** The memory whose name is being typed (its flag). */
  let renaming = $state<number | null>(null)

  const commands = $derived<EventCommand[]>(list.records[0]?.scripts?.[name] ?? original)
  const edited = $derived(!!list.records[0]?.scripts?.[name])
  const named = $derived(characters.filter((c) => c.id.startsWith('CHARACTER_')))
  const charName = (id: string) => characters.find((c) => c.id === id)?.name || id.replace('CHARACTER_', '')
  const itemName = (id: string) => reference?.items.find((i) => i.id === id)?.name || id.replace('ITEM_', '')
  const pretty = (constant: string, prefix: string) =>
    constant.replace(prefix, '').toLowerCase().replace(/_/g, ' ').replace(/^\w/, (c) => c.toUpperCase())
  const memories = $derived(list.records[0]?.memories ?? [])
  const memoryName = (flag: string) => memories.find((m) => String(m.flag) === flag.trim())?.name
  const isMemoryCommand = (c: EventCommand) => ['ENUT', 'ENUF', 'CHECK_EVENTID'].includes(c.op) && memoryName(c.args?.[0] ?? '') !== undefined
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

  /** A memory to add with the next save, with a name to change; null when all its numbers are taken. */
  function freshMemory(): Memory | null {
    const [first, last] = reference?.memoryFlags ?? [0, -1]
    for (let flag = first; flag <= last; flag++) {
      if (!memories.some((m) => m.flag === flag)) return { flag, name: t('ev.memory.default', { n: memories.length + 1 }) }
    }
    return null
  }

  function save(next: EventCommand[], memory?: Memory | null) {
    const same = JSON.stringify(next) === JSON.stringify(original)
    list.update(0, (d) => {
      if (memory) (d.memories ??= []).push({ ...memory })
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

  function setArg(i: number, k: number, value: string, memory?: Memory | null) {
    save(commands.map((c, n) => (n === i ? { ...c, args: (c.args ?? []).map((a, j) => (j === k ? value : a)) } : c)), memory)
  }

  function pickMemory(i: number, k: number, value: string) {
    if (value !== NEW_MEMORY) return setArg(i, k, value)
    const memory = freshMemory()
    if (!memory) return
    setArg(i, k, String(memory.flag), memory)
    renaming = memory.flag
  }

  function renameMemory(flag: number, name: string) {
    renaming = null
    if (!name.trim()) return
    list.update(0, (d) => {
      const memory = d.memories?.find((m) => m.flag === flag)
      if (memory) memory.name = name.trim()
    })
  }

  const focused = (input: HTMLInputElement) => {
    input.focus()
    input.select()
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
      slot: op === 'SVAL' ? 'EVT_SLOT_1' : 'EVT_SLOT_C', item: reference?.items[0]?.id ?? '0', stat: 'pow', amount: '1',
      chapter: `0x${(chapter + 1).toString(16)}`,
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
    // CHECK_EVENTID leaves 1 when the flag is set: "not" skips the block then
    return [check, { op: kind === 'if:notMemory' ? 'BNE' : 'BEQ', args: [label, 'EVT_SLOT_C', 'EVT_SLOT_0'] }, { op: 'LABEL', args: [label] }]
  }

  /** A question of the player, Yes / No: "yes" is kept as a new memory, for later scenes to look at. */
  function ask(at: number) {
    const memory = freshMemory()
    if (!memory) return
    const label = `0x${nextLabel().toString(16)}`
    withNewMessage((ref) => [
      ...commands.slice(0, at),
      { op: 'Text', args: [ref] },
      { op: 'SVAL', args: ['EVT_SLOT_1', '1'] },
      { op: 'BNE', args: [label, 'EVT_SLOT_C', 'EVT_SLOT_1'] },
      { op: 'ENUT', args: [String(memory.flag)] },
      { op: 'LABEL', args: [label] },
      ...commands.slice(at),
    ], { question: true, memory })
    selected = null   // what follows comes after the question
    openStep = at + 3
    renaming = memory.flag
    adding = ''
  }

  /** New command after the selected one, else before the script's end (NoFade, ENDA). */
  function add() {
    if (!adding) return
    let at = selected !== null ? selected + 1 : commands.length
    // before the end of the scene: nothing runs once the chapter changes
    if (selected === null) while (at > 0 && ['NoFade', 'ENDA', '', ...CHANGE_OPS].includes(commands[at - 1].op)) at--
    if (adding === 'ask') return ask(at)
    const remembering = adding.includes('emory')
    const memory = remembering && !memories.length ? freshMemory() : null
    const flag = String(memory?.flag ?? memories.at(-1)?.flag ?? '')
    if (remembering && !flag) return
    const op = adding === 'memory:set' ? 'ENUT' : adding === 'memory:forget' ? 'ENUF' : adding
    const added = CONDITIONS.includes(op) ? condition(op) : [fresh(op)]
    if (remembering) added[0].args = [flag]
    // what a condition on someone holds is usually for them
    const about = inCondition ? commands.slice(0, at).reverse().find((c) => c.op === 'CHECK_ALIVE')?.args?.[0] : undefined
    if ((adding === 'GiveItem' || adding === 'ChangeStat') && about) added[0].args![0] = about
    save([...commands.slice(0, at), ...added, ...commands.slice(at)], memory)
    if (memory) renaming = memory.flag
    // a condition: select its branch, the next command added goes inside it
    selected = at + added.length - (CONDITIONS.includes(adding) ? 2 : 1)
    openStep = at
    adding = ''
  }

  /** A new message of the project for a script (an empty conversation to write), and the commands
   *  using it, saved together (one undo step). */
  function withNewMessage(build: (ref: string) => EventCommand[], extra: { question?: boolean; memory?: Memory } = {}) {
    const key = `s${Date.now().toString(36)}`
    const next = build(`${NEW_MESSAGE}${key}`)
    list.update(0, (d) => {
      d.quotes ??= []
      d.quotes.push({ kind: 'scene', key, chapter, a: '', steps: [], ...(extra.question ? { question: true } : {}) })
      if (extra.memory) (d.memories ??= []).push({ ...extra.memory })
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

  const chapterTitle = (v: string) => reference?.chapters.find((n) => n.index === Number(v))?.title || v

  /** The values a command's step shows: names rather than constants. */
  function summary(c: EventCommand): string {
    const spec = reference?.commands[c.op] ?? []
    return spec.flatMap((a, k) => {
      const v = c.args?.[k] ?? ''
      if (a.kind === 'character') return [charName(v)]
      if (a.kind === 'item') return [itemName(v)]
      if (a.kind === 'stat') return [t(`stat.${v}`)]
      if (a.kind === 'chapter') return [chapterTitle(v)]
      if (a.kind === 'amount') return [Number(v) > 0 ? `+${Number(v)}` : v]
      if (a.kind === 'group') return [v.replace('UnitDef_Event_', '')]
      if (a.kind === 'song') return [pretty(v, 'SONG_')]
      if (a.kind === 'background') return [pretty(v, 'BG_')]
      if (a.kind === 'x' || a.kind === 'y') return [v]
      if (a.kind === 'flag' && memoryName(v) !== undefined) return [memoryName(v)!]
      return []
    }).join(', ')
  }

  /** The sentence of a condition made by `condition()`, whose block runs when it holds. */
  function readyMade(start: number, end: number): string | null {
    const [check, branch] = [commands[start], commands[end]]
    if (isMemoryCommand(check) && ['BEQ', 'BNE'].includes(branch.op) && branch.args?.[1] === 'EVT_SLOT_C' && branch.args?.[2] === 'EVT_SLOT_0') {
      return t(branch.op === 'BEQ' ? 'ev.simple.ifMemory' : 'ev.simple.ifNotMemory', { name: summary(check) })
    }
    if (check.op === 'CHECK_ALIVE' && branch.op === 'BEQ' && branch.args?.[1] === 'EVT_SLOT_C' && branch.args?.[2] === 'EVT_SLOT_0') {
      return t('ev.simple.ifAlive', { name: summary(check) })
    }
    if (check.op === 'CHECK_TURNS' && branch.op === 'BLT' && commands[start + 1]?.op === 'SVAL') {
      return t('ev.simple.ifTurn', { n: commands[start + 1].args?.[1] ?? '' })
    }
    return null
  }

  /** The test of a question's answer, made by `ask()`. */
  const isYes = (i: number) => {
    const [value, branch] = [commands[i], commands[i + 1]]
    return value.op === 'SVAL' && value.args?.[1] === '1' && branch?.op === 'BNE'
      && branch.args?.[1] === 'EVT_SLOT_C' && branch.args?.[2] === value.args?.[0]
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
          if (message && commands[i].op.startsWith('Text')) break   // one step per dialogue
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
        out.push({ start: i, end, icon: '❓', text: readyMade(i, end) ?? t('ev.simple.if', { what: detail ? `${what} (${detail})` : what }), message: '' })
        i = end + 1
      } else if (isYes(i)) {
        out.push({ start: i, end: i + 1, icon: '❓', text: t('ev.simple.ifYes'), message: '' })
        i += 2
      } else if (TECHNICAL.has(c.op)) {
        i++
      } else {
        const detail = summary(c)
        out.push({ start: i, end: i, icon: ICONS[c.op] ?? '•', text: detail ? `${commandLabel(c)} : ${detail}` : commandLabel(c), message: '' })
        i++
      }
    }
    return out
  })
  const hiddenCount = $derived(commands.length - steps.reduce((n, s) => n + s.end - s.start + 1, 0))

  function openOf(s: Step) {
    openStep = openStep === s.start ? null : s.start
    selected = openStep === null ? null : s.end
  }

  /** A condition without anything in its block yet. */
  const isEmpty = (s: Step) => BRANCHES.includes(commands[s.end]?.op) && s.end > s.start
    && labels.get(labelNumber(commands[s.end].args?.[0] ?? '')) === s.end + 1
  const inCondition = $derived(selected !== null && (BRANCHES.includes(commands[selected]?.op) || depths[selected] > 0))
  // The simple view leaves out what only the detailed view explains.
  const offered = $derived((reference?.addable ?? []).filter((op) => advanced
    || !(TECHNICAL.has(op) || BRANCHES.includes(op) || op.startsWith('CHECK_') || ['CALL', 'ENUT', 'ENUF'].includes(op))))
  const conditions = $derived(advanced ? CONDITIONS : CONDITIONS.filter((c) => c !== 'if:flag'))

  // Dragging a line of the simple view (ticket 119): what it takes along, and where it would land.
  let dragged = $state<Step | null>(null)
  let dropAt = $state<number | null>(null)
  /** Where added commands end: the commands of the script's end stay last. */
  const scriptEnd = $derived.by(() => {
    let at = commands.length
    while (at > 0 && ['NoFade', 'ENDA', '', ...CHANGE_OPS].includes(commands[at - 1].op)) at--
    return at
  })
  /** The last command that goes with a step: a condition's block, a dialogue's question, the wait after a move. */
  function stepLast(s: Step): number {
    let end = s.end
    if (isYes(end + 1)) end += 2
    if (BRANCHES.includes(commands[end]?.op)) {
      const to = labels.get(labelNumber(commands[end].args?.[0] ?? ''))
      if (to !== undefined && to > end) end = to
    }
    while (['ENUN', ''].includes(commands[end + 1]?.op)) end++
    return end
  }
  function dragOver(e: DragEvent, s: Step) {
    if (!dragged || isYes(s.start)) return
    e.preventDefault()
    const box = (e.currentTarget as HTMLElement).getBoundingClientRect()
    dropAt = e.clientY < box.top + box.height / 2 ? s.start : Math.min(stepLastInside(s) + 1, scriptEnd)
  }
  /** After a condition's line is the top of its block; after any other line, the command that follows it. */
  const stepLastInside = (s: Step) => {
    let end = s.end
    while (['ENUN', ''].includes(commands[end + 1]?.op)) end++
    return end
  }
  /** The end of a condition's block, a line of its own: above it is inside the block, below it is outside. */
  function dragOverEnd(e: DragEvent, label: number) {
    if (!dragged) return
    e.preventDefault()
    const box = (e.currentTarget as HTMLElement).getBoundingClientRect()
    dropAt = e.clientY < box.top + box.height / 2 ? label : label + 1
  }
  /** The blocks that end after each step (by its start), innermost first. */
  const blockEnds = $derived.by(() => {
    const out = new Map<number, { label: number; depth: number; text: string }[]>()
    for (const s of steps) {
      const to = BRANCHES.includes(commands[s.end]?.op) ? labels.get(labelNumber(commands[s.end].args?.[0] ?? '')) : undefined
      if (to === undefined || to <= s.end + 1) continue
      const last = steps.filter((r) => r.start < to).at(-1)!
      out.set(last.start, [...(out.get(last.start) ?? []), { label: to, depth: depths[s.start] + 1, text: s.text.replace(/\s*:\s*$/, '') }]
        .sort((a, b) => a.label - b.label))
    }
    return out
  })
  /** Where the next command goes: at the end of a block, or just after it. */
  function addAt(at: number) {
    selected = at
    openStep = null
  }
  function dropStep() {
    if (dragged && dropAt !== null) {
      const [from, last] = [dragged.start, stepLast(dragged)]
      if (dropAt < from || dropAt > last + 1) {
        const taken = commands.slice(from, last + 1)
        const rest = [...commands.slice(0, from), ...commands.slice(last + 1)]
        rest.splice(dropAt > last ? dropAt - taken.length : dropAt, 0, ...taken)
        save(rest)
        selected = null
        openStep = null
      }
    }
    dragged = null
    dropAt = null
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
  const commandLabel = (c: EventCommand) => (isMemoryCommand(c) ? t(`ev.memory.${c.op}`) : label(c.op))
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
    <button class="link small" onclick={() => setAdvanced(!advanced)}>{advanced ? t('ev.simple.toSimple') : t('ev.simple.toDetail', { n: hiddenCount })}</button>
    <Help text={advanced ? t('ev.hint') : t('ev.simple.hint')} />
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
              <span class="op">{ICONS[c.op] ?? '•'} {commandLabel(c)}</span>
              {#each spec as a, k (k)}
                {@const v = c.args?.[k] ?? ''}
                <label class="arg">
                  <span class="tiny muted">{isMemoryCommand(c) ? t('ev.memory.name') : t(`ev.arg.${a.name}`)}</span>
                  {#if isMemoryCommand(c) && renaming === Number(v)}
                    <input use:focused value={memoryName(v)} aria-label={t('ev.memory.name')}
                      onchange={(e) => renameMemory(Number(v), (e.target as HTMLInputElement).value)}
                      onblur={() => (renaming = null)}
                      onkeydown={(e) => e.key === 'Enter' && (e.target as HTMLInputElement).blur()} />
                  {:else if isMemoryCommand(c)}
                    <span class="inline">
                      <select value={v} onchange={(e) => pickMemory(i, k, (e.target as HTMLSelectElement).value)}>
                        {#each memories as m (m.flag)}<option value={String(m.flag)}>{m.name}</option>{/each}
                        <option value={NEW_MEMORY}>{t('ev.memory.new')}</option>
                      </select>
                      <button class="link" onclick={() => (renaming = Number(v))} title={t('ev.memory.rename')}>✎</button>
                    </span>
                  {:else if a.kind === 'song' && reference}
                    <select value={v} onchange={(e) => setArg(i, k, (e.target as HTMLSelectElement).value)}>
                      {#if !reference.songs.includes(v)}<option value={v}>{v}</option>{/if}
                      {#each reference.songs as s (s)}<option value={s}>{pretty(s, 'SONG_')}</option>{/each}
                    </select>
                  {:else if a.kind === 'background' && reference}
                    <select value={v} onchange={(e) => setArg(i, k, (e.target as HTMLSelectElement).value)}>
                      {#if !reference.backgrounds.includes(v)}<option value={v}>{v}</option>{/if}
                      {#each reference.backgrounds as b (b)}<option value={b}>{pretty(b, 'BG_')}</option>{/each}
                    </select>
                  {:else if a.kind === 'item' && reference}
                    <span class="inline">
                      <select value={v} onchange={(e) => setArg(i, k, (e.target as HTMLSelectElement).value)}>
                        {#if !reference.items.some((n) => n.id === v)}<option value={v}>{v}</option>{/if}
                        {#each reference.items as n (n.id)}<option value={n.id}>{n.name || n.id}</option>{/each}
                      </select>
                      <Mention kind="items" id={v}><span class="open">↗</span></Mention>
                    </span>
                  {:else if a.kind === 'chapter' && reference}
                    <select value={String(Number(v))} onchange={(e) => setArg(i, k, `0x${Number((e.target as HTMLSelectElement).value).toString(16)}`)}>
                      {#each reference.chapters as n (n.index)}<option value={String(n.index)}>{n.title || n.index}</option>{/each}
                    </select>
                  {:else if a.kind === 'stat'}
                    <select value={v} onchange={(e) => setArg(i, k, (e.target as HTMLSelectElement).value)}>
                      {#each STATS as stat (stat)}<option value={stat}>{t(`stat.${stat}`)}</option>{/each}
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
                    <input class:short={['x', 'y', 'frames', 'number', 'amount'].includes(a.kind)} value={v} onchange={(e) => setArg(i, k, (e.target as HTMLInputElement).value)} />
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
        <li class="step" class:in-block={depths[s.start] > 0} class:active={openStep === s.start} class:dragged={dragged === s} class:drop-before={dropAt === s.start}
            class:drop-after={dropAt !== null && dropAt !== s.start && dropAt === stepLastInside(s) + 1} style:margin-left="{depths[s.start] * 1.2}rem"
            draggable={!isYes(s.start)} role="listitem"
            ondragstart={(e) => { dragged = s; e.dataTransfer?.setData('text/plain', s.text) }}
            ondragover={(e) => dragOver(e, s)} ondrop={(e) => { e.preventDefault(); dropStep() }}
            ondragend={() => { dragged = null; dropAt = null }}>
          <span class="grip" aria-hidden="true" title={t('ev.simple.drag')}>⋮⋮</span>
          <button class="row" onclick={() => openOf(s)} title={t('ev.simple.open')}>
            <span>{s.icon}</span> <span class="what">{s.text}</span>
          </button>
          {#if s.message}<button class="link" onclick={() => onopenmessage(s.message)} title={t('ev.openMessage')}>{t('ev.simple.edit')}</button>{/if}
          <button class="danger" onclick={() => removeStep(s)} title={t('dlg.remove')}>✕</button>
        </li>
        {#if openStep === s.start}
          {#each commands.slice(s.start, s.end + 1) as c, k (k)}
            {#if s.end === s.start || !BRANCHES.includes(c.op)}{@render block(c, s.start + k)}{/if}
          {/each}
        {/if}
        {#if isEmpty(s)}
          {@const label = labels.get(labelNumber(commands[s.end].args?.[0] ?? ''))!}
          <li class="muted small nothing in-block" class:drop-before={dropAt === label} class:drop-after={dropAt === label + 1} role="listitem"
              style:margin-left="{(depths[s.start] + 1) * 1.2}rem" ondragover={(e) => dragOverEnd(e, label)} ondrop={(e) => { e.preventDefault(); dropStep() }}>{t('ev.simple.emptyCondition')}</li>
        {/if}
        {#each blockEnds.get(s.start) ?? [] as b (b.label)}
          <li class="block-end in-block tiny muted" class:active={selected === b.label - 1 || selected === b.label} class:drop-before={dropAt === b.label} class:drop-after={dropAt === b.label + 1}
              role="listitem" style:margin-left="{b.depth * 1.2}rem" ondragover={(e) => dragOverEnd(e, b.label)} ondrop={(e) => { e.preventDefault(); dropStep() }}>
            <span class="what">{t('ev.simple.blockEnd', { what: b.text })}</span>
            <button class="link" onclick={() => addAt(b.label - 1)}>{t('ev.simple.addInside')}</button>
            <button class="link" onclick={() => addAt(b.label)}>{t('ev.simple.addAfterBlock')}</button>
          </li>
        {/each}
      {/each}
      {#if !steps.length}<li class="muted small">{t('ev.simple.empty')}</li>{/if}
      {#if dragged}
        <li class="muted small nothing drop-end" class:drop-before={dropAt === scriptEnd} role="listitem"
            ondragover={(e) => { e.preventDefault(); dropAt = scriptEnd }} ondrop={(e) => { e.preventDefault(); dropStep() }}>{t('ev.simple.dropEnd')}</li>
      {/if}
    {/if}
  </ol>
  <datalist id="ev-groups">{#each groups as g (g)}<option value={g}></option>{/each}</datalist>
  <datalist id="ev-scripts">{#each reference?.scripts ?? [] as s (s)}<option value={s}></option>{/each}</datalist>

  {#if reference}
    <div class="add">
      <select bind:value={adding} aria-label={t('ev.add')}>
        <option value="">{t('ev.add')}</option>
        <optgroup label={t('ev.conditions')}>
          {#each conditions as op (op)}<option value={op}>❓ {t(`ev.${op.replace(':', '.')}`)}</option>{/each}
        </optgroup>
        <optgroup label={t('ev.memories')}>
          {#each MEMORY_ACTIONS as op (op)}<option value={op}>{t(`ev.${op.replace(':', '.')}`)}</option>{/each}
        </optgroup>
        <optgroup label={t('ev.commands')}>
          {#each offered as op (op)}<option value={op}>{ICONS[op] ?? ''} {label(op)}</option>{/each}
        </optgroup>
      </select>
      <button onclick={add} disabled={!adding}>＋ {commands[selected ?? -1]?.op === 'LABEL' && !inCondition ? t('ev.addAfterBlock') : inCondition ? t('ev.addInside') : selected !== null ? t('ev.addAfter', { n: selected + 1 }) : t('ev.addEnd')}</button>
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
  .blocks li.step[draggable='true'] { cursor: grab; }
  .blocks li.dragged { opacity: 0.5; }
  .blocks li.in-block { border-left: 3px solid var(--accent); }
  .blocks li.nothing.in-block { border-left-style: solid; }
  .blocks li.block-end { align-items: center; justify-content: flex-end; border-style: dashed; border-left-style: solid; background: none; padding: 0.1rem 0.4rem; }
  .block-end .what { flex: 1; }
  .blocks li.drop-before { box-shadow: 0 -2px 0 var(--accent); }
  .blocks li.drop-after { box-shadow: 0 2px 0 var(--accent); }
  .grip { color: var(--muted); font-size: 0.8rem; letter-spacing: -0.15rem; user-select: none; }
  .step[draggable='false'] .grip { visibility: hidden; }
  .blocks li.nothing { border-style: dashed; background: none; }
  .row { flex: 1; display: flex; gap: 0.4rem; align-items: center; min-width: 0; border: none; background: none; padding: 0.15rem; text-align: left; font-weight: 600; }
  .what { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .step .danger { padding: 0 0.35rem; font-size: 0.8rem; }
  .open { font-size: 0.8rem; }
  .simple { display: flex; align-items: center; gap: 0.5rem; flex-wrap: wrap; }
  .quote { max-width: 18rem; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
</style>
