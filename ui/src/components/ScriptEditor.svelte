<script lang="ts">
  // Visual editor of an event script (server: decomp/events.py): one block per command, with a form
  // for the commands FE Maker knows; the others are kept as they are and can be moved or removed.
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
  }: {
    name: string
    /** chapter index (unit groups of the chapter are offered), -1 if none */
    chapter: number
    list: EditableList<DialoguesData>
    characters: Character[]
    problems: Problem[]
    /** first line of a message (to show it in its block) */
    firstLine: (id: string) => string
    /** open a message of the script in the dialogue editor */
    onopenmessage: (id: string) => void
  } = $props()

  const ICONS: Record<string, string> = {
    MUSC: '🎵', MUSS: '🎵', MURE: '🎵', MUSI: '🔉', MUNO: '🔊', MUSCMID: '🎵', MUSCSLOW: '🎵',
    Text: '💬', Text_BG: '💬', TEXTSHOW: '💬', TEXTSTART: '💬', TEXTEND: '💬', TEXTCONT: '💬', REMA: '💬',
    BACG: '🖼️', SetBackground: '🖼️', FADI: '🌓', FADU: '🌓', FAWI: '🌓', FAWU: '🌓',
    LOAD1: '👥', LOAD2: '👥', LOAD3: '👥', ENUN: '⏳', MOVE: '🚶', CUMO_AT: '📍', CUMO_CHAR: '📍', CURE: '📍',
    FlashCursor: '📍', CAMERA: '🎥', CAMERA2: '🎥', CAMERA_CAHR: '🎥', STAL: '⏱️', STAL2: '⏱️', STAL3: '⏱️',
    DISA: '👋', KILL: '💀', CUSA: '🤝', CUSN: '🤝', ENUT: '🚩', ENUF: '🏳️', CLEA: '🧹', CLEE: '🧹', CLEN: '🧹',
    NoFade: '⏹️', ENDA: '⏹️',
  }

  let reference = $state<EventsReference | null>(null)
  let original = $state<EventCommand[]>([])
  let file = $state('')
  let error = $state('')
  let groups = $state<string[]>([])
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
    Promise.all([reference ? Promise.resolve(reference) : api.eventsReference(), api.eventScript(n)])
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
    if (c >= 0) api.chapterUnits(c).then((u) => (groups = u.groups.map((g) => g.name))).catch(() => {})
  })

  function save(next: EventCommand[]) {
    const same = JSON.stringify(next) === JSON.stringify(original)
    list.update(0, (d) => {
      d.scripts ??= {}
      if (same) delete d.scripts[name]
      else d.scripts[name] = JSON.parse(JSON.stringify(next))
    })
  }

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
      number: '0', speed: '0', raw: '0',
    }
    return { op, args: spec.map((a) => (op.startsWith('LOAD') && a.name === 'flag' ? '1' : defaults[a.kind] ?? '0')) }
  }

  /** New command after the selected one, else before the script's end (NoFade, ENDA). */
  function add() {
    if (!adding) return
    let at = selected !== null ? selected + 1 : commands.length
    if (selected === null) while (at > 0 && ['NoFade', 'ENDA', ''].includes(commands[at - 1].op)) at--
    save([...commands.slice(0, at), fresh(adding), ...commands.slice(at)])
    selected = at
    adding = ''
  }

  function resetScript() {
    list.update(0, (d) => {
      if (d.scripts) delete d.scripts[name]
    })
  }

  const label = (op: string) => (t(`ev.op.${op}`) === `ev.op.${op}` ? op : t(`ev.op.${op}`))
  const isMessage = (v: string) => /^(0x[0-9a-f]+|\d+)$/i.test(v.trim())
</script>

<div class="script">
  <div class="head">
    <h3>⚙ {t('ev.title', { name })}</h3>
    {#if edited}<button class="link" onclick={resetScript}>{t('ev.reset')}</button>{/if}
  </div>
  <p class="muted small">{t('ev.hint')} <span class="tiny">{file}</span></p>
  {#if error}<p class="bad small">{error}</p>{/if}
  {#each scriptProblems.filter((p) => p.id === `script:${name}`) as pr, k (k)}<p class="bad small">{problemText(pr)}</p>{/each}

  <ol class="blocks">
    {#each commands as c, i (i)}
      {#if c.op === ''}
        <li class="gap" aria-hidden="true"></li>
      {:else}
        {@const spec = reference?.commands[c.op]}
        <li class:active={selected === i} class:comment={c.op === '#'} class:raw={!spec && c.op !== '#'}>
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
                    <span class="inline">
                      <input class="short" value={v} onchange={(e) => setArg(i, k, (e.target as HTMLInputElement).value)} />
                      {#if isMessage(v)}<button class="link" onclick={() => onopenmessage(String(Number(v)))} title={t('ev.openMessage')}>💬</button>{/if}
                    </span>
                    {#if isMessage(v) && firstLine(String(Number(v)))}<span class="tiny muted quote">« {firstLine(String(Number(v)))} »</span>{/if}
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
    {/each}
  </ol>
  <datalist id="ev-groups">{#each groups as g (g)}<option value={g}></option>{/each}</datalist>

  {#if reference}
    <div class="add">
      <select bind:value={adding} aria-label={t('ev.add')}>
        <option value="">{t('ev.add')}</option>
        {#each reference.addable as op (op)}<option value={op}>{ICONS[op] ?? ''} {label(op)}</option>{/each}
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
  .open { font-size: 0.8rem; }
  .quote { max-width: 18rem; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
</style>
