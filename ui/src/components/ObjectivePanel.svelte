<script lang="ts">
  import { t, problemText } from '../lib/i18n.svelte'
  import type { Character, Objective, ObjectiveEdit, Problem } from '../lib/types'
  import Mention from './Mention.svelte'
  import NumberField from './NumberField.svelte'

  /** Objective of a chapter: what wins it and what the goal window and status screen say. */
  let {
    objective,
    edited,
    problems,
    picking = $bindable(false),
    characters,
    battleCharacters,
    originalBoss,
    onchange,
    onreset,
  }: {
    objective: Objective
    edited: boolean
    /** named characters, to choose the boss */
    characters: Character[]
    /** characters present in the chapter's battle units */
    battleCharacters: Set<string>
    originalBoss: string | null

    problems: Problem[]
    picking?: boolean
    onchange: (change: Partial<ObjectiveEdit>) => void
    onreset: () => void
  } = $props()

  const TYPES = [
    ['seize', '🏰'],
    ['defeat_all', '⚔️'],
    ['defeat_boss', '👑'],
    ['defense', '🛡️'],
    ['area', '🚩'],
  ] as const

  const tile = $derived(objective.seize[0])
  const boss = $derived(characters.find((c) => c.id === objective.boss))
  const named = $derived(characters.filter((c) => c.id.startsWith('CHARACTER_')))
  const problemFor = (field: string) => problems.find((p) => p.field === field)

  function setType(type: Objective['type']) {
    const change: Partial<ObjectiveEdit> = { type }
    if (type === 'defense' && !objective.turns) change.turns = 10
    onchange(change)
    if ((type === 'seize' && !objective.seize.length) || (type === 'area' && !objective.area)) picking = true
  }
  const protectChar = $derived(characters.find((c) => c.id === objective.protect))
</script>

{#snippet bossPicker()}
    <div class="row">
      <label class="inline">
        {t('objective.boss')}
        <select value={objective.boss ?? ''} disabled={!objective.bossEditable} onchange={(e) => onchange({ boss: (e.target as HTMLSelectElement).value || null })}>
          <option value="">{t('field.none')}</option>
          {#if objective.boss && !boss}<option value={objective.boss}>{objective.boss}</option>{/if}
          <optgroup label={t('objective.inBattle')}>
            {#each named.filter((c) => battleCharacters.has(c.id)) as c (c.id)}<option value={c.id}>{c.name || c.id}</option>{/each}
          </optgroup>
          <optgroup label={t('objective.otherCharacters')}>
            {#each named.filter((c) => !battleCharacters.has(c.id)) as c (c.id)}<option value={c.id}>{c.name || c.id}</option>{/each}
          </optgroup>
        </select>
      </label>
      {#if boss}<Mention kind="characters" id={boss.id}><span class="open">↗</span></Mention>{/if}
    </div>
    {#if !objective.bossEditable}<p class="muted small">{t('objective.bossPerRoute')}</p>{/if}
    {#if !objective.boss}<p class="warn small">{t('objective.noBoss')}</p>{/if}
    {#if objective.boss && !battleCharacters.has(objective.boss)}<p class="warn small">{t('objective.bossAbsent')}</p>{/if}
    {#if boss && !boss.abilities.includes('boss')}<p class="muted small">{t('objective.bossAbility')}</p>{/if}
    {#if objective.boss && objective.boss !== originalBoss}<p class="muted small">{t('objective.bossQuote')}</p>{/if}
{/snippet}

<section class="objective">
  <div class="head">
    <h3>{t('objective.title')} {#if edited}<span class="edited">✎</span>{/if}</h3>
    {#if edited}<button class="ghost small" onclick={onreset}>{t('objective.reset')}</button>{/if}
  </div>

  {#if objective.editable}
    <div class="types" role="radiogroup" aria-label={t('objective.title')}>
      {#each TYPES as [type, icon] (type)}
        <button role="radio" aria-checked={objective.type === type} class:active={objective.type === type} onclick={() => setType(type)}>
          <span class="icon" aria-hidden="true">{icon}</span>{t(`objective.type.${type}`)}
        </button>
      {/each}
    </div>
    <p class="muted small">{t(`objective.hint.${objective.type}`)}</p>

    {#if objective.type === 'seize'}
      <div class="row">
        <span>{t('objective.tile')} : {#if tile}<strong>{tile.x}, {tile.y}</strong>{:else}<span class="bad">{t('objective.noTile')}</span>{/if}</span>
        <button class:active={picking} onclick={() => (picking = !picking)}>🎯 {picking ? t('objective.picking') : t('objective.pick')}</button>
        <label class="inline">
          {t('objective.label')}
          <select value={objective.seizeLabel} onchange={(e) => onchange({ seizeLabel: (e.target as HTMLSelectElement).value as 'throne' | 'gate' })}>
            <option value="throne">{t('objective.label.throne')}</option>
            <option value="gate">{t('objective.label.gate')}</option>
          </select>
        </label>
      </div>
    {:else if objective.type === 'defeat_boss'}
      {@render bossPicker()}
    {:else if objective.type === 'area'}
      <div class="row">
        <span>{t('objective.area')} : {#if objective.area}<strong>{objective.area.x1}, {objective.area.y1} → {objective.area.x2}, {objective.area.y2}</strong>{:else}<span class="bad">{t('objective.noTile')}</span>{/if}</span>
        <button class:active={picking} onclick={() => (picking = !picking)}>🎯 {picking ? t('objective.pickingArea') : t('objective.pickArea')}</button>
        <label class="inline">
          {t('objective.areaWho')}
          <select value={objective.areaWho ?? ''} onchange={(e) => onchange({ areaWho: (e.target as HTMLSelectElement).value })}>
            <option value="">{t('objective.anyPlayerUnit')}</option>
            {#each named.filter((c) => battleCharacters.has(c.id)) as c (c.id)}<option value={c.id}>{c.name || c.id}</option>{/each}
          </select>
        </label>
      </div>
    {:else if objective.type === 'defense'}
      <div class="row">
        <NumberField label={t('objective.turns')} value={objective.turns} min={1} max={99} problem={problemFor('turns') ? problemText(problemFor('turns')!) : ''} onchange={(v) => onchange({ turns: v })} />
        <label class="inline" title={t('objective.orBossHint')}>
          <input type="checkbox" checked={!!objective.orBoss} onchange={(e) => onchange({ orBoss: (e.target as HTMLInputElement).checked })} />
          {t('objective.orBoss')}
        </label>
      </div>
      {#if objective.orBoss}{@render bossPicker()}{/if}
    {/if}
  {:else}
    <p><strong>{t(`objective.type.${objective.type}`)}</strong></p>
    <p class="muted small">{t(`objective.readOnly.${objective.reason || 'custom'}`)}</p>
  {/if}

  {#if objective.editable}
    <div class="row">
      <label class="inline" title={t('objective.protectHint')}>
        🛡 {t('objective.protect')}
        <select value={objective.protect ?? ''} onchange={(e) => onchange({ protect: (e.target as HTMLSelectElement).value || null })}>
          <option value="">{t('field.none')}</option>
          {#if objective.protect && !protectChar}<option value={objective.protect}>{objective.protect}</option>{/if}
          {#each named.filter((c) => battleCharacters.has(c.id)) as c (c.id)}<option value={c.id}>{c.name || c.id}</option>{/each}
        </select>
      </label>
      {#if protectChar}<Mention kind="characters" id={protectChar.id}><span class="open">↗</span></Mention>{/if}
    </div>
  {/if}

  {#if objective.hasStatusText}
    <label>
      <span>{t('objective.statusText')}</span>
      <textarea rows="2" value={objective.statusText} onchange={(e) => onchange({ statusText: (e.target as HTMLTextAreaElement).value })}></textarea>
    </label>
    {#if problemFor('statusText')}{@const p = problemFor('statusText')!}<p class="{p.severity === 'error' ? 'bad' : 'warn'} small">{problemText(p)}</p>{/if}
    {#if objective.statusShared}<p class="warn small">{t('objective.statusShared', { n: objective.statusShared })}</p>{/if}
  {/if}
  {#if objective.editable && objective.eventsShared}<p class="warn small">{t('objective.eventsShared', { n: objective.eventsShared })}</p>{/if}
</section>

<style>
  .objective { display: flex; flex-direction: column; gap: 0.5rem; border-top: 1px solid var(--border); margin-top: 0.75rem; padding-top: 0.6rem; }
  .head { display: flex; align-items: center; gap: 0.75rem; }
  h3 { margin: 0; font-size: 0.8rem; }
  .edited { color: var(--accent); }
  .types { display: flex; flex-wrap: wrap; gap: 0.4rem; }
  .types button { display: inline-flex; align-items: center; gap: 0.35rem; }
  .types button.active, .row button.active { background: var(--accent-soft); border-color: var(--accent); }
  .icon { font-size: 1rem; line-height: 1; }
  .row { display: flex; align-items: center; gap: 0.75rem; flex-wrap: wrap; font-size: 0.9rem; }
  .inline { flex-direction: row; align-items: center; gap: 0.4rem; }
  textarea { width: 100%; max-width: 26em; resize: vertical; font-family: inherit; box-sizing: border-box; }
  p { margin: 0; }
  .small { font-size: 0.8rem; }
  .bad { color: var(--bad); }
  .warn { color: var(--warn); }
  .ghost { border-color: transparent; background: none; color: var(--muted); }
  .open { font-size: 1rem; }
</style>
