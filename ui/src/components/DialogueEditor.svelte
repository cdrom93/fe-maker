<script lang="ts">
  import { onMount } from 'svelte'
  import { appContext } from '../lib/appContext.svelte'
  import { api, portraitUrl } from '../lib/api'
  import type { EditableList } from '../lib/history.svelte'
  import { problemText, t } from '../lib/i18n.svelte'
  import { followFocus, useNavigator } from '../lib/navigation.svelte'
  import type { Character, ChapterInfo, DialogueFace, DialogueScene, DialoguesData, DialogueStep, Problem } from '../lib/types'
  import Mention from './Mention.svelte'
  import RecordList from './RecordList.svelte'

  let { list, characters, problems }: { list: EditableList<DialoguesData>; characters: Character[]; problems: Problem[] } = $props()

  // Speaker slots, left to right on the screen, with the center of the portrait in 8-pixel tiles
  // (gTalkFaceHPosLut, src/scene.c). Portraits on the left half look to the right.
  const SLOTS: { pos: string; x: number }[] = [
    { pos: 'FarFarLeft', x: -8 }, { pos: 'FarLeft', x: 3 }, { pos: 'MidLeft', x: 6 }, { pos: 'Left', x: 9 },
    { pos: 'Right', x: 21 }, { pos: 'MidRight', x: 24 }, { pos: 'FarRight', x: 27 }, { pos: 'FarFarRight', x: 38 },
  ]
  const SCREEN_W = 240
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
  let messageId = $state<string | null>(null)
  let stepIndex = $state(0)
  let showTutorials = $state(false)

  const edited = $derived(list.records[0]?.messages ?? {})
  const portraitOf = $derived(new Map(faces.map((f) => [f.id, f.portrait])))
  const steps = $derived<DialogueStep[]>(messageId ? (edited[messageId] ?? originals[messageId] ?? []) : [])
  const chapter = $derived(chapters[selected])
  const charName = (id: string) => characters.find((c) => c.id === id)?.name || id.replace('CHARACTER_', '')
  const visibleScenes = $derived(scenes.filter((s) => showTutorials || s.trigger.kind !== 'tutorial'))
  const messageProblems = $derived(messageId ? problems.filter((p) => p.kind === 'dialogues' && p.id.split('#')[0] === messageId) : [])

  const nav = useNavigator()
  followFocus('dialogues', nav, () => chapters.map((c) => c.id), (i) => load(i))

  $effect(() => {
    appContext.detail = chapter ? `${chapter.name}${messageId ? ` · ${t('dlg.message', { id: hex(messageId) })}` : ''}` : ''
    return () => (appContext.detail = '')
  })

  onMount(async () => {
    const [list_, faceList] = await Promise.all([api.chapters(), api.dialogueFaces()])
    faces = faceList
    chapters = list_.map((c) => ({ ...c, id: String(c.index), name: c.title || c.id }))
    const asked = nav.focus?.kind === 'dialogues' ? chapters.findIndex((c) => c.id === nav.focus!.id) : -1
    if (chapters.length) await load(Math.max(0, asked))
  })

  async function load(index: number) {
    selected = index
    messageId = null
    stepIndex = 0
    const data = await api.chapterDialogues(chapters[index].index)
    if (selected !== index) return
    scenes = data.scenes
    originals = data.messages
    const first = data.scenes.find((s) => s.trigger.kind !== 'tutorial') ?? data.scenes[0]
    if (first) pick(String(first.messages[0]))
  }

  function pick(id: string) {
    messageId = id
    stepIndex = 0
  }

  const hex = (id: string | number) => `0x${Number(id).toString(16).toUpperCase()}`

  /** What starts a scene, in a few words. */
  function sceneLabel(s: DialogueScene): string {
    const tr = s.trigger
    switch (tr.kind) {
      case 'turn': return t(tr.faction === 'FACTION_RED' ? 'dlg.trigger.enemyTurn' : 'dlg.trigger.turn', { n: tr.turn ?? '?' })
      case 'talk': return t('dlg.trigger.talk', { a: charName(tr.a ?? ''), b: charName(tr.b ?? '') })
      case 'village': case 'house': return t(`dlg.trigger.${tr.kind}`, { x: tr.x ?? '?', y: tr.y ?? '?' })
      default: return t(`dlg.trigger.${tr.kind}`)
    }
  }

  // ---------- editing ----------

  function save(next: DialogueStep[]) {
    if (!messageId) return
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
  const lineText = $derived(line?.text ? line.text.replace(/\[[^\]]*\]/g, '') : '')
  const speakerX = $derived(SLOTS.find((s) => s.pos === line?.pos)?.x ?? 15)
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
        <label class="check"><input type="checkbox" bind:checked={showTutorials} /> {t('dlg.showTutorials')}</label>
      </div>
      <p class="muted small">{t('dlg.hint')}</p>
      {#if chapter}<p class="small"><Mention kind="chapters" id={chapter.id}>{t('dlg.openChapter')}</Mention></p>{/if}
      {#if !visibleScenes.length}<p class="muted">{t('dlg.none')}</p>{/if}
      {#each visibleScenes as scene (scene.script)}
        <div class="scene">
          <div class="scene-title">
            <span class="kind {scene.trigger.kind}">{sceneLabel(scene)}</span>
            {#if scene.trigger.via}<span class="muted tiny" title={scene.script}>{t('dlg.via')}</span>{/if}
          </div>
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
    </section>

    {#if messageId}
      <section class="panel message-editor">
        <div class="head">
          <h3>{t('dlg.message', { id: hex(messageId) })}</h3>
          {#if edited[messageId]}<button class="link" onclick={resetMessage}>{t('dlg.reset')}</button>{/if}
        </div>

        <div class="stage" style="width: {SCREEN_W * SCALE}px; height: {160 * SCALE}px">
          {#each SLOTS as slot (slot.pos)}
            {@const fid = shown.get(slot.pos)}
            {#if fid && portraitOf.has(fid)}
              <img class="portrait" class:flip={slot.x < 15} class:speaking={line?.pos === slot.pos}
                   src={portraitUrl(portraitOf.get(fid)!, true)} alt={faceLabel(fid)}
                   style="left: {(slot.x * 8 - 48) * SCALE}px; width: {96 * SCALE}px; height: {80 * SCALE}px" />
            {/if}
          {/each}
          {#if line}
            <div class="bubble" style="left: {Math.max(4, Math.min(SCREEN_W - 196, speakerX * 8 - 96)) * SCALE}px">
              {#each lineText.split('\n\n')[0].split('\n').slice(0, 2) as l, k (k)}<div>{l}</div>{/each}
            </div>
          {/if}
        </div>

        <ol class="steps">
          {#each steps as s, i (i)}
            {@const state = facesAt(i - 1)}
            <li class:active={stepIndex === i}>
              <button class="num" onclick={() => (stepIndex = i)} title={t('dlg.showStep')}>{i + 1}</button>
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
                            onfocus={() => (stepIndex = i)} onchange={(e) => editStep(i, { text: (e.target as HTMLTextAreaElement).value })}></textarea>
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
  .bubble { position: absolute; top: 8px; width: 384px; min-height: 52px; background: #f8f4e8; color: #222; border-radius: 10px; padding: 8px 14px; font-size: 15px; line-height: 1.5; box-shadow: 0 2px 6px rgb(0 0 0 / 0.4); font-family: sans-serif; }
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
  @media (max-width: 1100px) { .detail { grid-template-columns: 1fr; } }
</style>
