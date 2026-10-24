<script lang="ts">
  import { onMount } from 'svelte'
  import { appContext } from '../lib/appContext.svelte'
  import { api, portraitUrl } from '../lib/api'
  import type { EditableList } from '../lib/history.svelte'
  import { problemText, t } from '../lib/i18n.svelte'
  import { followFocus, useNavigator } from '../lib/navigation.svelte'
  import { layout, layoutBoxes, lineWidth } from '../lib/textLayout'
  import type { Character, ChapterInfo, DialogueFace, DialogueFont, DialogueScene, DialoguesData, DialogueStep, NewQuote, Problem, SupportPair } from '../lib/types'
  import Mention from './Mention.svelte'
  import NumberField from './NumberField.svelte'
  import RecordList from './RecordList.svelte'
  import ScriptEditor from './ScriptEditor.svelte'
  import SupportList from './SupportList.svelte'
  import TalkBubble from './TalkBubble.svelte'

  let { list, characters, problems }: { list: EditableList<DialoguesData>; characters: Character[]; problems: Problem[] } = $props()

  // Speaker slots, left to right on the screen, with the center of the portrait in 8-pixel tiles
  // (gTalkFaceHPosLut, src/scene.c). Portraits on the left half look to the right.
  const SLOTS: { pos: string; x: number }[] = [
    { pos: 'FarFarLeft', x: -8 }, { pos: 'FarLeft', x: 3 }, { pos: 'MidLeft', x: 6 }, { pos: 'Left', x: 9 },
    { pos: 'Right', x: 21 }, { pos: 'MidRight', x: 24 }, { pos: 'FarRight', x: 27 }, { pos: 'FarFarRight', x: 38 },
  ]
  const SCREEN_W = 240
  const ANY_CHAPTER = 255
  const SUPPORTS = -2 // index of the "Supports" entry of the list
  const NEW = 'new:' // id prefix of a new quote in the editor
  const SCALE = 2
  // Codes put in a line with one click (they change the face of the speaker).
  const EXPRESSIONS = [
    { code: 'ToggleSmile', icon: '😊' },
    { code: 'ToggleMouthMove', icon: '🤐' },
    { code: 'HalfCloseEyes', icon: '😑' },
    { code: 'CloseEyes', icon: '😌' },
    { code: 'OpenEyes', icon: '👀' },
    { code: 'Wink', icon: '😉' },
  ]

  let chapters = $state<(ChapterInfo & { name: string })[]>([])
  let selected = $state(0)
  let scenes = $state<DialogueScene[]>([])
  let originals = $state<Record<string, DialogueStep[]>>({})
  let faces = $state<DialogueFace[]>([])
  let font = $state<DialogueFont | null>(null)
  let supportInfo = $state<{ pairs: SupportPair[]; levelPoints: number[]; maxPartners: number } | null>(null)
  let boxIndex = $state(0)
  let messageId = $state<string | null>(null)
  /** event script shown in the visual editor (instead of a message) */
  let scriptName = $state<string | null>(null)
  let stepIndex = $state(0)
  let showTutorials = $state(false)

  const edited = $derived(list.records[0]?.messages ?? {})
  const newQuotes = $derived<NewQuote[]>(list.records[0]?.quotes ?? [])
  const portraitOf = $derived(new Map(faces.map((f) => [f.id, f.portrait])))
  const quoteIndex = $derived(messageId?.startsWith(NEW) ? Number(messageId.slice(NEW.length)) : -1)
  const steps = $derived<DialogueStep[]>(
    quoteIndex >= 0 ? (newQuotes[quoteIndex]?.steps ?? []) : messageId ? (edited[messageId] ?? originals[messageId] ?? []) : [],
  )
  const chapter = $derived(chapters[selected])
  const chapterNumber = $derived(chapter ? (chapter.index < 0 ? ANY_CHAPTER : chapter.index) : -1)
  // New quotes of this chapter, with their place in the project list.
  const chapterQuotes = $derived(newQuotes.map((q, i) => ({ q, i })).filter(({ q }) => q.chapter === chapterNumber))
  const charName = (id: string) => characters.find((c) => c.id === id)?.name || id.replace('CHARACTER_', '')
  const visibleScenes = $derived(scenes.filter((s) => showTutorials || s.trigger.kind !== 'tutorial'))
  // Problems of the message (new quotes are "new<n>" on the server).
  const problemKey = $derived(messageId?.startsWith(NEW) ? `new${messageId.slice(NEW.length)}` : messageId)
  const messageProblems = $derived(problemKey ? problems.filter((p) => p.kind === 'dialogues' && p.id.split('#')[0] === problemKey) : [])

  const nav = useNavigator()
  followFocus('dialogues', nav, () => chapters.map((c) => c.id), (i) => load(i))

  $effect(() => {
    appContext.detail = chapter ? `${chapter.name}${messageId ? ` · ${t('dlg.message', { id: hex(messageId) })}` : ''}` : ''
    return () => (appContext.detail = '')
  })

  onMount(async () => {
    const [list_, faceList, fontInfo] = await Promise.all([api.chapters(), api.dialogueFaces(), api.dialogueFont()])
    faces = faceList
    font = fontInfo
    chapters = [
      { index: -1, id: 'all', title: '', map: null, events: null, name: t('dlg.allChapters') },
      { index: SUPPORTS, id: 'supports', title: '', map: null, events: null, name: t('dlg.supports') },
      ...list_.map((c) => ({ ...c, id: String(c.index), name: c.title || c.id })),
    ]
    const asked = nav.focus?.kind === 'dialogues' ? chapters.findIndex((c) => c.id === nav.focus!.id) : -1
    if (chapters.length) await load(Math.max(0, asked))
  })

  async function load(index: number) {
    selected = index
    messageId = null
    stepIndex = 0
    const which = chapters[index].index
    let data: { scenes: DialogueScene[]; messages: Record<string, DialogueStep[]> }
    if (which === SUPPORTS) {
      const sup = await api.supportDialogues()
      supportInfo = { pairs: sup.pairs, levelPoints: sup.levelPoints, maxPartners: sup.maxPartners }
      data = sup
    } else data = which < 0 ? await api.commonDialogues() : await api.chapterDialogues(which)
    if (selected !== index) return
    scenes = data.scenes
    originals = data.messages
    const first = data.scenes.find((s) => s.trigger.kind !== 'tutorial' && s.messages.length) ?? data.scenes.find((s) => s.messages.length)
    if (first) pick(String(first.messages[0]))
  }

  function pick(id: string) {
    scriptName = null
    messageId = id
    stepIndex = 0
    boxIndex = 0
  }

  const hex = (id: string | number) => `0x${Number(id).toString(16).toUpperCase()}`

  /** What starts a scene, in a few words. */
  function sceneLabel(s: DialogueScene): string {
    const tr = s.trigger
    switch (tr.kind) {
      case 'turn': return t(tr.faction === 'FACTION_RED' ? 'dlg.trigger.enemyTurn' : 'dlg.trigger.turn', { n: tr.turn ?? '?' })
      case 'talk': return t('dlg.trigger.talk', { a: charName(tr.a ?? ''), b: charName(tr.b ?? '') })
      case 'village': case 'house': return t(`dlg.trigger.${tr.kind}`, { x: tr.x ?? '?', y: tr.y ?? '?' })
      case 'battle': return t('dlg.trigger.battle', { a: charName(tr.a ?? ''), b: tr.b ? charName(tr.b) : t('dlg.anyone') })
      case 'death': return t('dlg.trigger.death', { a: charName(tr.a ?? '') })
      default: return t(`dlg.trigger.${tr.kind}`)
    }
  }

  // ---------- editing ----------

  function save(next: DialogueStep[]) {
    if (!messageId) return
    if (quoteIndex >= 0) {
      const i = quoteIndex
      list.update(0, (d) => {
        if (d.quotes?.[i]) d.quotes[i].steps = JSON.parse(JSON.stringify(next))
      })
      return
    }
    const id = messageId
    const same = JSON.stringify(next) === JSON.stringify(originals[id])
    list.update(0, (d) => {
      d.messages ??= {}
      if (same) delete d.messages[id]
      else d.messages[id] = JSON.parse(JSON.stringify(next))
    })
  }

  function editStep(i: number, patch: Partial<DialogueStep>) {
    save(steps.map((s, k) => (k === i ? { ...s, ...patch } : s)))
  }

  function moveStep(i: number, by: number) {
    const j = i + by
    if (j < 0 || j >= steps.length) return
    const next = [...steps]
    ;[next[i], next[j]] = [next[j], next[i]]
    save(next)
    stepIndex = j
  }

  function removeStep(i: number) {
    save(steps.filter((_, k) => k !== i))
    stepIndex = Math.max(0, Math.min(stepIndex, steps.length - 2))
  }

  /** New step after the selected one; the speaker is the last one who appeared. */
  function addStep(kind: DialogueStep['kind']) {
    const at = Math.min(stepIndex + 1, steps.length)
    const state = facesAt(at - 1)
    const lastPos = [...steps.slice(0, at)].reverse().find((s) => s.pos)?.pos ?? 'MidLeft'
    const free = SLOTS.map((s) => s.pos).find((p) => !state.has(p) && p !== 'FarFarLeft' && p !== 'FarFarRight') ?? 'MidRight'
    let step: DialogueStep
    if (kind === 'face') step = { kind, pos: free, face: faces[0]?.id ?? 'FID_Eirika' }
    else if (kind === 'clear') step = { kind, pos: lastPos }
    else if (kind === 'move') step = { kind, pos: lastPos, to: free }
    else step = { kind: 'say', pos: lastPos, text: '', wait: true }
    save([...steps.slice(0, at), step, ...steps.slice(at)])
    stepIndex = at
  }

  /** First line of a message (the project's version if edited), for lists. */
  function firstLineOf(id: string): string {
    const q = id.startsWith(NEW) ? newQuotes[Number(id.slice(NEW.length))]?.steps : (edited[id] ?? originals[id])
    return q?.find((s) => s.kind === 'say')?.text?.replace(/\[[^\]]*\]/g, '').split('\n')[0] ?? ''
  }

  /** Portrait code of a character (its portrait id in the texts' list). */
  const faceOf = (pid: string) => faces.find((f) => f.portrait === characters.find((c) => c.id === pid)?.portraitId)?.id ?? faces[0]?.id ?? 'FID_Eirika'

  function addQuote(kind: NewQuote['kind']) {
    // The chapter's boss (who already has a battle quote), else the first character.
    const boss = scenes.find((s) => s.trigger.kind === 'battle')?.trigger.a
    const named = characters.filter((c) => c.id.startsWith('CHARACTER_'))
    let quote: NewQuote
    if (kind === 'turn') {
      const a = named[0]?.id ?? ''
      quote = {
        kind, chapter: chapterNumber, a, turn: 1, phase: 'player',
        steps: [{ kind: 'face', pos: 'MidLeft', face: faceOf(a) }, { kind: 'say', pos: 'MidLeft', text: '', wait: true }],
      }
    } else if (kind === 'talk') {
      const [a, b] = [named[0]?.id ?? '', named[1]?.id ?? '']
      quote = {
        kind, chapter: chapterNumber, a, b, recruit: false, both: false,
        steps: [
          { kind: 'face', pos: 'MidLeft', face: faceOf(a) }, { kind: 'face', pos: 'MidRight', face: faceOf(b) },
          { kind: 'say', pos: 'MidLeft', text: '', wait: true }, { kind: 'say', pos: 'MidRight', text: '', wait: true },
        ],
      }
    } else {
      const a = boss || named[0]?.id || ''
      quote = {
        kind, chapter: chapterNumber, a, b: '',
        steps: [{ kind: 'face', pos: 'MidLeft', face: faceOf(a) }, { kind: 'say', pos: 'MidLeft', text: '', wait: true }],
      }
    }
    const at = newQuotes.length
    list.update(0, (d) => {
      d.quotes ??= []
      d.quotes.push(quote)
    })
    pick(`${NEW}${at}`)
  }

  function quoteLabel(q: NewQuote): string {
    if (q.kind === 'battle') return t('dlg.trigger.battle', { a: charName(q.a), b: q.b ? charName(q.b) : t('dlg.anyone') })
    if (q.kind === 'death') return t('dlg.trigger.death', { a: charName(q.a) })
    if (q.kind === 'support') return t('dlg.supportTalk', { rank: 'CBA'[(q.rank ?? 1) - 1], a: charName(q.a), b: charName(q.b ?? '') })
    if (q.kind === 'turn') return t(q.phase === 'enemy' ? 'dlg.trigger.enemyTurn' : q.phase === 'ally' ? 'dlg.trigger.allyTurn' : 'dlg.trigger.turn', { n: q.turn ?? 1 })
    return t('dlg.trigger.talk', { a: charName(q.a), b: charName(q.b ?? '') }) + (q.recruit ? ` · ${t('dlg.recruits')}` : '')
  }

  function editQuote(patch: Partial<NewQuote>) {
    const i = quoteIndex
    if (i < 0) return
    list.update(0, (d) => {
      const q = d.quotes?.[i]
      if (!q) return
      // A new speaker also changes their portrait when it was the previous speaker's.
      for (const key of ['a', 'b'] as const) {
        const next = patch[key]
        if (!next) continue
        for (const s of q.steps) if (s.kind === 'face' && s.face === faceOf(q[key] ?? '')) s.face = faceOf(next)
      }
      Object.assign(q, patch)
    })
  }

  function removeQuote() {
    const i = quoteIndex
    if (i < 0) return
    messageId = null
    list.update(0, (d) => {
      d.quotes?.splice(i, 1)
    })
  }

  function resetMessage() {
    if (!messageId) return
    const id = messageId
    list.update(0, (d) => {
      if (d.messages) delete d.messages[id]
    })
  }

  let textAreas: Record<number, HTMLTextAreaElement> = {}
  /** Put an expression code where the cursor is in a line. */
  function insertCode(i: number, code: string) {
    const area = textAreas[i]
    const text = steps[i].text ?? ''
    const at = area ? area.selectionStart : text.length
    editStep(i, { text: `${text.slice(0, at)}[${code}]${text.slice(at)}` })
  }

  // ---------- preview ----------

  /** Portrait in each slot once steps 0..i are played. */
  function facesAt(i: number): Map<string, string> {
    const state = new Map<string, string>()
    for (const s of steps.slice(0, i + 1)) {
      if (s.kind === 'face' && s.pos) state.set(s.pos, s.face ?? '')
      else if (s.kind === 'clear' && s.pos) state.delete(s.pos)
      else if (s.kind === 'move' && s.pos && s.to) {
        const face = state.get(s.pos)
        state.delete(s.pos)
        if (face) state.set(s.to, face)
      }
    }
    return state
  }
  const shown = $derived(facesAt(stepIndex))
  // The line shown in the box: the selected one, or the last one before it.
  const line = $derived([...steps.slice(0, stepIndex + 1)].reverse().find((s) => s.kind === 'say') ?? null)
  // Battle quotes and last words are shown in the battle screen's narrower box.
  const inBattle = $derived(
    quoteIndex >= 0
      ? ['battle', 'death'].includes(newQuotes[quoteIndex]?.kind ?? '')
      : scenes.some((s) => ['battle', 'death'].includes(s.trigger.kind) && s.messages.some((m) => String(m) === messageId)),
  )
  const maxWidth = $derived(font ? (inBattle ? font.battleWidth : font.talkWidth) : 0)
  const boxes = $derived(font && line ? layoutBoxes(line.text ?? '', font, maxWidth) : [])
  const box = $derived(boxes[Math.min(boxIndex, boxes.length - 1)] ?? [])
  const speakerX = $derived(SLOTS.find((s) => s.pos === line?.pos)?.x ?? 15)
  /** Left of the box in tiles, as the game puts it next to its speaker (PutTalkBubble, src/scene.c). */
  const bubbleX = $derived.by(() => {
    if (!font) return 1
    const width = Math.ceil(Math.max(24, ...box.map((l) => lineWidth(l, font!))) / 8) + 2
    if (speakerX < 16) return Math.max(1, speakerX + 3 - Math.floor(width / 2))
    const tail = speakerX - 5
    return Math.floor((width + 1) / 2) + tail >= 30 ? 29 - width : tail - Math.floor(width / 2)
  })
  /** Number of boxes once laid out, when the layout changes the text. */
  function autoBoxes(text: string): number {
    if (!font || layout(text, font, maxWidth) === text) return 0
    return layoutBoxes(text, font, maxWidth).length
  }
  const faceLabel = (fid: string) => fid.replace('FID_', '').replace(/([a-z])([A-Z])/g, '$1 $2')
  const posLabel = (pos: string) => t(`dlg.pos.${pos}`)
</script>

<div class="editor">
  <RecordList records={chapters} {selected} onselect={(i) => load(i)} problemIds={new Set()}>
    {#snippet suffix(c: ChapterInfo & { name: string })}
      {#if Object.keys(edited).length && scenes.length && chapters[selected]?.id === c.id && scenes.some((s) => s.messages.some((m) => edited[String(m)]))}<span class="edited">✎</span>{/if}
    {/snippet}
  </RecordList>

  <div class="detail">
    <section class="panel scenes">
      <div class="head">
        <h2>{chapter?.name ?? ''}</h2>
        {#if chapter?.index !== SUPPORTS}<label class="check"><input type="checkbox" bind:checked={showTutorials} /> {t('dlg.showTutorials')}</label>{/if}
      </div>
      {#if chapter?.index === SUPPORTS}
        {#if supportInfo}
          <SupportList {list} originalPairs={supportInfo.pairs} {scenes} {characters} {problems} levelPoints={supportInfo.levelPoints}
                       maxPartners={supportInfo.maxPartners} {messageId} firstLine={firstLineOf} faceCode={faceOf} onpick={pick} />
        {/if}
      {:else}
      <p class="muted small">{t('dlg.hint')}</p>
      {#if chapter && chapter.index >= 0}<p class="small"><Mention kind="chapters" id={chapter.id}>{t('dlg.openChapter')}</Mention></p>{/if}
      {#if !visibleScenes.length}<p class="muted">{t('dlg.none')}</p>{/if}
      {#if chapterQuotes.length}
        <div class="scene">
          <div class="scene-title"><span class="kind new">{t('dlg.newQuotes')}</span></div>
          {#each chapterQuotes as { q, i } (i)}
            <button class="message" class:active={messageId === `${NEW}${i}`} onclick={() => pick(`${NEW}${i}`)}>
              {#if portraitOf.has(faceOf(q.a))}<span class="faces-mini"><img src={portraitUrl(portraitOf.get(faceOf(q.a))!, true)} alt="" /></span>{/if}
              <span class="first">{quoteLabel(q)}</span>
            </button>
          {/each}
        </div>
      {/if}
      <div class="add">
        <button onclick={() => addQuote('battle')} title={t('dlg.addBattleHint')}>＋ {t('dlg.addBattle')}</button>
        <button onclick={() => addQuote('death')} title={t('dlg.addDeathHint')}>＋ {t('dlg.addDeath')}</button>
        {#if chapterNumber !== ANY_CHAPTER}
          <button onclick={() => addQuote('talk')} title={t('dlg.addTalkHint')}>＋ {t('dlg.addTalk')}</button>
          <button onclick={() => addQuote('turn')} title={t('dlg.addTurnHint')}>＋ {t('dlg.addTurn')}</button>
        {/if}
      </div>
      {#each visibleScenes as scene (scene.script)}
        <div class="scene">
          <div class="scene-title">
            <span class="kind {scene.trigger.kind}">{sceneLabel(scene)}</span>
            {#if scene.trigger.via}<span class="muted tiny" title={scene.script}>{t('dlg.via')}</span>{/if}
            <button class="script-button" class:active={scriptName === scene.script} title={t('ev.open', { name: scene.script })}
                    onclick={() => { scriptName = scene.script; messageId = null }}>⚙{#if list.records[0]?.scripts?.[scene.script]}<span class="edited">✎</span>{/if}</button>
          </div>
          {#if !scene.messages.length}<span class="muted tiny no-message">{t('dlg.noMessage')}</span>{/if}
          {#each scene.messages as m (m)}
            {@const id = String(m)}
            {@const msgSteps = edited[id] ?? originals[id] ?? []}
            {@const first = msgSteps.find((s) => s.kind === 'say')}
            {@const speakers = [...new Set(msgSteps.filter((s) => s.kind === 'face').map((s) => s.face ?? ''))].slice(0, 4)}
            <button class="message" class:active={messageId === id} onclick={() => pick(id)}>
              <span class="faces-mini">
                {#each speakers as f (f)}{#if portraitOf.has(f)}<img src={portraitUrl(portraitOf.get(f)!, true)} alt={faceLabel(f)} title={faceLabel(f)} />{/if}{/each}
              </span>
              <span class="first">{first?.text?.replace(/\[[^\]]*\]/g, '').split('\n')[0] ?? '…'}</span>
              {#if edited[id]}<span class="edited" title={t('dlg.edited')}>✎</span>{/if}
            </button>
          {/each}
        </div>
      {/each}
      {/if}
    </section>

    {#if scriptName}
      <section class="panel">
        <ScriptEditor name={scriptName} chapter={chapter?.index ?? -1} {list} {characters} {problems} firstLine={firstLineOf} onopenmessage={(id) => pick(id)} />
      </section>
    {:else if messageId}
      <section class="panel message-editor">
        <div class="head">
          {#if quoteIndex >= 0 && newQuotes[quoteIndex]?.kind === 'support'}
            <h3>{quoteLabel(newQuotes[quoteIndex])}</h3>
          {:else if quoteIndex >= 0}
            <h3>{t(`dlg.add${{ battle: 'Battle', death: 'Death', talk: 'Talk', turn: 'Turn', support: 'Talk' }[newQuotes[quoteIndex]?.kind ?? 'battle']}`)}</h3>
            <button class="link danger" onclick={removeQuote}>{t('dlg.removeQuote')}</button>
          {:else}
            <h3>{t('dlg.message', { id: hex(messageId) })}</h3>
            {#if edited[messageId]}<button class="link" onclick={resetMessage}>{t('dlg.reset')}</button>{/if}
          {/if}
        </div>
        {#if quoteIndex >= 0 && newQuotes[quoteIndex] && newQuotes[quoteIndex].kind !== 'support'}
          {@const q = newQuotes[quoteIndex]}
          <div class="quote-who">
            {#if q.kind === 'turn'}
              <NumberField label={t('dlg.turn')} value={q.turn ?? 1} min={1} max={99} compact onchange={(v) => editQuote({ turn: v })} />
              <label>
                <span>{t('dlg.phase')}</span>
                <select value={q.phase ?? 'player'} onchange={(e) => editQuote({ phase: (e.target as HTMLSelectElement).value as NewQuote['phase'] })}>
                  {#each ['player', 'enemy', 'ally'] as ph (ph)}<option value={ph}>{t(`dlg.phase.${ph}`)}</option>{/each}
                </select>
              </label>
            {:else}
            <label>
              <span>{q.kind === 'death' ? t('dlg.quoteDying') : t('dlg.quoteWho')}</span>
              <select value={q.a} onchange={(e) => editQuote({ a: (e.target as HTMLSelectElement).value })}>
                {#each characters as c (c.id)}<option value={c.id}>{c.name || c.id}</option>{/each}
              </select>
            </label>
            {#if q.kind === 'talk'}
              <label>
                <span>{t('dlg.talkTo')}</span>
                <select value={q.b ?? ''} onchange={(e) => editQuote({ b: (e.target as HTMLSelectElement).value })}>
                  {#each characters as c (c.id)}<option value={c.id}>{c.name || c.id}</option>{/each}
                </select>
              </label>
              <label class="check"><input type="checkbox" checked={!!q.recruit} onchange={(e) => editQuote({ recruit: (e.target as HTMLInputElement).checked })} /> {t('dlg.recruit', { b: charName(q.b ?? '') })}</label>
              <label class="check"><input type="checkbox" checked={!!q.both} onchange={(e) => editQuote({ both: (e.target as HTMLInputElement).checked })} /> {t('dlg.both')}</label>
            {/if}
            {#if q.kind === 'battle'}
              <label>
                <span>{t('dlg.quoteAgainst')}</span>
                <select value={q.b ?? ''} onchange={(e) => editQuote({ b: (e.target as HTMLSelectElement).value })}>
                  <option value="">{t('dlg.anyone')}</option>
                  {#each characters as c (c.id)}<option value={c.id}>{c.name || c.id}</option>{/each}
                </select>
              </label>
            {/if}
            <Mention kind="characters" id={q.a}>{charName(q.a)}</Mention>
            {/if}
          </div>
        {/if}

        <div class="stage" style="width: {SCREEN_W * SCALE}px; height: {160 * SCALE}px">
          {#each SLOTS as slot (slot.pos)}
            {@const fid = shown.get(slot.pos)}
            {#if fid && portraitOf.has(fid)}
              <img class="portrait" class:flip={slot.x < 15} class:speaking={line?.pos === slot.pos}
                   src={portraitUrl(portraitOf.get(fid)!, true)} alt={faceLabel(fid)}
                   style="left: {(slot.x * 8 - 48) * SCALE}px; width: {96 * SCALE}px; height: {80 * SCALE}px" />
            {/if}
          {/each}
          {#if line && font}
            <div class="bubble" style="left: {bubbleX * 8 * SCALE}px"><TalkBubble lines={box} {font} scale={SCALE} /></div>
            {#if boxes.length > 1}
              <div class="pager">
                <button onclick={() => (boxIndex = Math.max(0, boxIndex - 1))} disabled={boxIndex === 0} title={t('dlg.prevBox')}>‹</button>
                {t('dlg.box', { n: Math.min(boxIndex, boxes.length - 1) + 1, total: boxes.length })}
                <button onclick={() => (boxIndex = Math.min(boxes.length - 1, boxIndex + 1))} disabled={boxIndex >= boxes.length - 1} title={t('dlg.nextBox')}>›</button>
              </div>
            {/if}
          {/if}
        </div>

        <ol class="steps">
          {#each steps as s, i (i)}
            {@const state = facesAt(i - 1)}
            <li class:active={stepIndex === i}>
              <button class="num" onclick={() => { stepIndex = i; boxIndex = 0 }} title={t('dlg.showStep')}>{i + 1}</button>
              <div class="body">
                {#if s.kind === 'face'}
                  <span class="tag">{t('dlg.step.face')}</span>
                  <select value={s.face} onchange={(e) => editStep(i, { face: (e.target as HTMLSelectElement).value })}>
                    {#each faces as f (f.id)}<option value={f.id}>{faceLabel(f.id)}</option>{/each}
                  </select>
                  {#if s.face && portraitOf.has(s.face)}<img class="thumb" src={portraitUrl(portraitOf.get(s.face)!, true)} alt="" />{/if}
                  <select value={s.pos} onchange={(e) => editStep(i, { pos: (e.target as HTMLSelectElement).value })}>
                    {#each SLOTS as slot (slot.pos)}<option value={slot.pos}>{posLabel(slot.pos)}</option>{/each}
                  </select>
                {:else if s.kind === 'clear'}
                  <span class="tag">{t('dlg.step.clear')}</span>
                  <select value={s.pos} onchange={(e) => editStep(i, { pos: (e.target as HTMLSelectElement).value })}>
                    {#each SLOTS as slot (slot.pos)}<option value={slot.pos}>{posLabel(slot.pos)}{state.get(slot.pos) ? ` — ${faceLabel(state.get(slot.pos)!)}` : ''}</option>{/each}
                  </select>
                {:else if s.kind === 'move'}
                  <span class="tag">{t('dlg.step.move')}</span>
                  <select value={s.pos} onchange={(e) => editStep(i, { pos: (e.target as HTMLSelectElement).value })}>
                    {#each SLOTS as slot (slot.pos)}<option value={slot.pos}>{posLabel(slot.pos)}{state.get(slot.pos) ? ` — ${faceLabel(state.get(slot.pos)!)}` : ''}</option>{/each}
                  </select>
                  →
                  <select value={s.to} onchange={(e) => editStep(i, { to: (e.target as HTMLSelectElement).value })}>
                    {#each SLOTS as slot (slot.pos)}<option value={slot.pos}>{posLabel(slot.pos)}</option>{/each}
                  </select>
                {:else if s.kind === 'say'}
                  <div class="say-head">
                    <span class="tag">{t('dlg.step.say')}</span>
                    <select value={s.pos ?? ''} onchange={(e) => { const v = (e.target as HTMLSelectElement).value; editStep(i, { pos: v || null }) }}>
                      <option value="">{t('dlg.narrator')}</option>
                      {#each SLOTS as slot (slot.pos)}<option value={slot.pos}>{state.get(slot.pos) ? faceLabel(state.get(slot.pos)!) : '—'} ({posLabel(slot.pos)})</option>{/each}
                    </select>
                    <span class="expressions">
                      {#each EXPRESSIONS as ex (ex.code)}
                        <button title={t(`dlg.code.${ex.code}`)} onclick={() => insertCode(i, ex.code)}>{ex.icon}</button>
                      {/each}
                    </span>
                  </div>
                  <textarea rows={Math.min(8, Math.max(2, (s.text ?? '').split('\n').length))} bind:this={textAreas[i]} value={s.text ?? ''}
                            onfocus={() => { if (stepIndex !== i) boxIndex = 0; stepIndex = i }} onchange={(e) => editStep(i, { text: (e.target as HTMLTextAreaElement).value })}></textarea>
                  {@const auto = autoBoxes(s.text ?? '')}
                  {#if auto && font}
                    <p class="auto tiny">
                      ✂ {t('dlg.autoLayout', { n: auto })}
                      <button class="link" onclick={() => editStep(i, { text: layout(s.text ?? '', font!, maxWidth) })}>{t('dlg.applyLayout')}</button>
                    </p>
                  {/if}
                {:else}
                  <span class="tag code">{t(`dlg.code.${s.code}`) === `dlg.code.${s.code}` ? s.code : t(`dlg.code.${s.code}`)}</span>
                  {#if s.pos}<span class="muted tiny">{posLabel(s.pos)}</span>{/if}
                {/if}
              </div>
              <div class="actions">
                <button onclick={() => moveStep(i, -1)} disabled={i === 0} title={t('dlg.up')}>↑</button>
                <button onclick={() => moveStep(i, 1)} disabled={i === steps.length - 1} title={t('dlg.down')}>↓</button>
                <button class="danger" onclick={() => removeStep(i)} title={t('dlg.remove')}>✕</button>
              </div>
            </li>
          {/each}
        </ol>
        <div class="add">
          <button onclick={() => addStep('say')}>＋ {t('dlg.add.say')}</button>
          <button onclick={() => addStep('face')}>＋ {t('dlg.add.face')}</button>
          <button onclick={() => addStep('clear')}>＋ {t('dlg.add.clear')}</button>
          <button onclick={() => addStep('move')}>＋ {t('dlg.add.move')}</button>
        </div>
        <p class="muted tiny">{t('dlg.textHint')}</p>
        {#each messageProblems as pr, k (k)}<p class="{pr.severity === 'error' ? 'bad' : 'warn'} small">{problemText(pr)}</p>{/each}
      </section>
    {/if}
  </div>
</div>

<style>
  .editor { display: grid; grid-template-columns: 240px 1fr; gap: 1rem; align-items: start; }
  .detail { display: grid; grid-template-columns: minmax(260px, 340px) minmax(0, 1fr); gap: 1rem; align-items: start; min-width: 0; }
  .head { display: flex; align-items: center; justify-content: space-between; gap: 0.5rem; flex-wrap: wrap; }
  .head h2, .head h3 { margin: 0; }
  .small { font-size: 0.8rem; }
  .tiny { font-size: 0.72rem; }
  .bad { color: var(--bad); }
  .warn { color: var(--warn); }
  .danger { color: var(--bad); }
  .edited { color: var(--accent); margin-left: 0.25rem; }
  .link { border: none; background: none; padding: 0; color: var(--accent); font: inherit; }
  .check { flex-direction: row; align-items: center; gap: 0.35rem; font-size: 0.8rem; color: var(--text); }
  .scenes { display: flex; flex-direction: column; gap: 0.5rem; max-height: calc(100vh - 200px); overflow-y: auto; }
  .scenes p { margin: 0; }
  .scene { display: flex; flex-direction: column; gap: 0.15rem; }
  .scene-title { display: flex; align-items: baseline; gap: 0.4rem; font-size: 0.8rem; font-weight: 600; margin-top: 0.3rem; }
  .kind.beginning, .kind.ending { color: var(--accent); }
  .message { display: flex; align-items: center; gap: 0.4rem; text-align: left; font-size: 0.82rem; padding: 0.2rem 0.4rem; background: none; border-color: transparent; }
  .message:hover { background: var(--accent-soft); }
  .message.active { border-color: var(--accent); background: var(--accent-soft); }
  .first { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; flex: 1; min-width: 0; }
  .faces-mini { display: flex; flex-shrink: 0; }
  .faces-mini img { width: 24px; height: 20px; image-rendering: pixelated; margin-right: -6px; }
  .message-editor { display: flex; flex-direction: column; gap: 0.6rem; min-width: 0; }
  .stage { position: relative; overflow: hidden; background: linear-gradient(#3b4a6b, #1c2333); border-radius: 6px; max-width: 100%; flex-shrink: 0; }
  .portrait { position: absolute; bottom: 0; image-rendering: pixelated; opacity: 0.75; }
  .portrait.flip { transform: scaleX(-1); }
  .portrait.speaking { opacity: 1; }
  .bubble { position: absolute; top: 16px; }
  .pager { position: absolute; right: 6px; bottom: 6px; display: flex; align-items: center; gap: 0.3rem; font-size: 0.75rem; color: #fff; background: rgb(0 0 0 / 0.55); padding: 0.1rem 0.35rem; border-radius: 4px; }
  .pager button { padding: 0 0.35rem; font-size: 0.8rem; }
  .auto { margin: 0; color: var(--muted); display: flex; gap: 0.5rem; align-items: baseline; width: 100%; }
  .steps { list-style: none; padding: 0; margin: 0; display: flex; flex-direction: column; gap: 0.3rem; max-height: calc(100vh - 560px); min-height: 200px; overflow-y: auto; }
  .steps li { display: flex; align-items: flex-start; gap: 0.4rem; padding: 0.25rem; border-radius: 6px; border: 1px solid transparent; }
  .steps li.active { border-color: var(--accent); background: var(--accent-soft); }
  .num { width: 2rem; padding: 0.1rem; font-size: 0.75rem; flex-shrink: 0; }
  .body { flex: 1; display: flex; flex-wrap: wrap; align-items: center; gap: 0.4rem; min-width: 0; }
  .say-head { display: flex; align-items: center; gap: 0.4rem; flex-wrap: wrap; width: 100%; }
  .body textarea { width: 100%; font: inherit; font-size: 0.85rem; }
  .tag { font-size: 0.75rem; font-weight: 600; color: var(--muted); }
  .tag.code { font-weight: normal; font-style: italic; }
  .thumb { width: 36px; height: 30px; image-rendering: pixelated; }
  .expressions { display: flex; gap: 0.1rem; margin-left: auto; }
  .expressions button { padding: 0 0.3rem; font-size: 0.9rem; }
  .actions { display: flex; gap: 0.15rem; flex-shrink: 0; }
  .actions button { padding: 0 0.35rem; font-size: 0.8rem; }
  .add { display: flex; gap: 0.4rem; flex-wrap: wrap; }
  .scenes .add button { font-size: 0.78rem; padding: 0.15rem 0.45rem; }
  .kind.new { color: var(--good); }
  .no-message { padding-left: 0.4rem; }
  .script-button { margin-left: auto; padding: 0 0.3rem; font-size: 0.75rem; background: none; }
  .script-button.active { border-color: var(--accent); background: var(--accent-soft); }
  .quote-who { display: flex; align-items: flex-end; gap: 0.75rem; flex-wrap: wrap; }
  @media (max-width: 1100px) { .detail { grid-template-columns: 1fr; } }
</style>
