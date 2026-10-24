<script lang="ts">
  import { portraitUrl } from '../lib/api'
  import { t } from '../lib/i18n.svelte'
  import type { DialogueStep } from '../lib/types'
  import { fromDisplay, toDisplay } from '../lib/dialogueCodes'

  // A message shown as a conversation (ticket 24): lines as chat bubbles typed in place, with who
  // speaks; portraits coming in, leaving or moving as short stage directions between them.
  let {
    steps,
    stepIndex,
    facesAt,
    faceLabel,
    portraitOf,
    isLeft,
    textAreas,
    composerPos = $bindable(),
    onselect,
    onedit,
    onremove,
    onsay,
  }: {
    steps: DialogueStep[]
    stepIndex: number
    /** portrait in each slot once steps 0..i are played */
    facesAt: (i: number) => Map<string, string>
    faceLabel: (face: string) => string
    portraitOf: Map<string, number>
    /** is this slot on the left half of the screen */
    isLeft: (pos: string) => boolean
    /** the lines' text areas, by step (expression buttons write where the cursor is) */
    textAreas: Record<number, HTMLTextAreaElement>
    /** who says the next typed line (null: no portrait) */
    composerPos: string | null
    onselect: (i: number) => void
    onedit: (i: number, patch: Partial<DialogueStep>) => void
    onremove: (i: number) => void
    onsay: (text: string, pos: string | null) => void
  } = $props()

  let draft = $state('')
  const present = $derived([...facesAt(stepIndex).entries()])

  function face(i: number, pos: string | null | undefined): string | undefined {
    return pos ? facesAt(i - 1).get(pos) : undefined
  }

  function send() {
    if (!draft.trim()) return
    onsay(fromDisplay(draft), composerPos)
    draft = ''
  }

  function nameAt(i: number, pos: string | null | undefined): string {
    const f = face(i, pos)
    return f ? faceLabel(f) : t('dlg.narrator')
  }
</script>

{#snippet mini(f: string | undefined)}
  {#if f && portraitOf.has(f)}<img class="mini" src={portraitUrl(portraitOf.get(f)!, true)} alt="" />{:else}<span class="mini blank">💬</span>{/if}
{/snippet}

<div class="thread">
  {#if !steps.length}<p class="muted small">{t('dlg.emptyMessage')}</p>{/if}
  {#each steps as s, i (i)}
    {@const active = stepIndex === i}
    {#if s.kind === 'say'}
      {@const f = face(i, s.pos)}
      {@const left = !s.pos || isLeft(s.pos)}
      <div class="line" class:right={!left} class:narration={!s.pos} class:active>
        <button class="who" onclick={() => onselect(i)} title={t('dlg.showStep')}>{@render mini(f)}</button>
        <div class="bubble">
          <span class="name tiny">{nameAt(i, s.pos)}</span>
          <textarea rows={Math.max(1, (s.text ?? '').split('\n').length)} bind:this={textAreas[i]} value={toDisplay(s.text ?? '')}
                    onfocus={() => onselect(i)} onchange={(e) => onedit(i, { text: fromDisplay((e.target as HTMLTextAreaElement).value) })}></textarea>
        </div>
        <button class="remove" onclick={() => onremove(i)} title={t('dlg.remove')} aria-label={t('dlg.remove')}>✕</button>
      </div>
    {:else}
      {@const f = s.kind === 'face' ? s.face : face(i, s.pos)}
      <div class="direction" class:active>
        <button class="direction-text" onclick={() => onselect(i)} title={t('dlg.showStep')}>
          {#if s.kind !== 'code'}{@render mini(f)}{/if}
          {#if s.kind === 'face'}{t('dlg.dir.enters', { name: faceLabel(s.face ?? ''), pos: t(`dlg.pos.${s.pos}`) })}
          {:else if s.kind === 'clear'}{t('dlg.dir.leaves', { name: f ? faceLabel(f) : t(`dlg.pos.${s.pos}`) })}
          {:else if s.kind === 'move'}{t('dlg.dir.moves', { name: f ? faceLabel(f) : '?', pos: t(`dlg.pos.${s.to}`) })}
          {:else}⚙ {t(`dlg.code.${s.code}`) === `dlg.code.${s.code}` ? s.code : t(`dlg.code.${s.code}`)}{/if}
        </button>
        <button class="remove" onclick={() => onremove(i)} title={t('dlg.remove')} aria-label={t('dlg.remove')}>✕</button>
      </div>
    {/if}
    {#if active && i < steps.length - 1}<div class="insert tiny">▸ {t('dlg.insertHere')}</div>{/if}
  {/each}

  <div class="composer">
    <div class="speakers" role="radiogroup" aria-label={t('dlg.whoSpeaks')}>
      <span class="tiny muted">{t('dlg.whoSpeaks')}</span>
      {#each present as [pos, f] (pos)}
        <button role="radio" aria-checked={composerPos === pos} class:active={composerPos === pos} onclick={() => (composerPos = pos)} title={faceLabel(f)}>
          {@render mini(f)}<span class="tiny">{faceLabel(f)}</span>
        </button>
      {/each}
      <button role="radio" aria-checked={composerPos === null} class:active={composerPos === null} onclick={() => (composerPos = null)}>
        <span class="tiny">{t('dlg.narrator')}</span>
      </button>
    </div>
    <div class="type">
      <textarea rows="2" bind:value={draft} placeholder={t('dlg.typeLine')}
                onkeydown={(e) => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); send() } }}></textarea>
      <button class="primary" onclick={send} disabled={!draft.trim()}>{t('dlg.addLine')}</button>
    </div>
  </div>
</div>

<style>
  .thread { display: flex; flex-direction: column; gap: 0.35rem; max-height: calc(100vh - 520px); min-height: 240px; overflow-y: auto; padding: 0.2rem; }
  .small { font-size: 0.8rem; }
  .tiny { font-size: 0.72rem; }
  .line { display: flex; align-items: flex-start; gap: 0.4rem; }
  .line.right { flex-direction: row-reverse; }
  .line.narration { justify-content: center; }
  .who { padding: 0; background: none; border: none; line-height: 0; flex-shrink: 0; }
  .mini { width: 36px; height: 30px; image-rendering: pixelated; border-radius: 4px; background: var(--panel-2); display: inline-flex; align-items: center; justify-content: center; }
  .direction .mini { width: 24px; height: 20px; vertical-align: middle; margin-right: 0.3rem; }
  .bubble { display: flex; flex-direction: column; gap: 0.1rem; background: var(--panel-2); border: 1px solid var(--border); border-radius: 10px; padding: 0.25rem 0.5rem; max-width: 80%; min-width: 50%; }
  .line.right .bubble { align-items: flex-end; }
  .line.active .bubble { border-color: var(--accent); box-shadow: 0 0 0 1px var(--accent); }
  .line.narration .bubble { font-style: italic; }
  .name { color: var(--muted); font-weight: 600; }
  .bubble textarea { width: 100%; font: inherit; font-size: 0.9rem; background: transparent; border: none; resize: none; padding: 0; field-sizing: content; color: var(--text); }
  .bubble textarea:focus { outline: none; }
  .direction { display: flex; align-items: center; justify-content: center; gap: 0.3rem; }
  .direction-text { font-size: 0.78rem; color: var(--muted); background: none; border: 1px dashed transparent; padding: 0.1rem 0.4rem; border-radius: 999px; }
  .direction.active .direction-text { border-color: var(--accent); color: var(--text); }
  .remove { padding: 0 0.3rem; font-size: 0.7rem; background: none; border-color: transparent; color: var(--muted); visibility: hidden; align-self: center; }
  .line:hover .remove, .direction:hover .remove, .active .remove { visibility: visible; }
  .insert { color: var(--accent); text-align: center; }
  .composer { position: sticky; bottom: 0; background: var(--panel); border-top: 1px solid var(--border); padding-top: 0.4rem; display: flex; flex-direction: column; gap: 0.3rem; }
  .speakers { display: flex; flex-wrap: wrap; align-items: center; gap: 0.25rem; }
  .speakers button { display: inline-flex; align-items: center; gap: 0.25rem; padding: 0.1rem 0.35rem; }
  .speakers button.active { border-color: var(--accent); background: var(--accent-soft); font-weight: 600; }
  .speakers .mini { width: 24px; height: 20px; }
  .type { display: flex; gap: 0.4rem; align-items: stretch; }
  .type textarea { flex: 1; font: inherit; font-size: 0.9rem; }
</style>
