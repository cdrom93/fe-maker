<script lang="ts">
  import Help from './Help.svelte'
  import { t } from '../lib/i18n.svelte'
  import { gameSkills, loadSkills, offeredSkills, skillCatalogue, skillIcon } from '../lib/skills.svelte'

  let {
    skills,
    fromClass = [],
    abilities,
    classId,
    characterId,
    onchange,
    learned = [],
    onlearnedchange,
    isClass = false,
  }: {
    /** the sheet's own skills */
    skills: string[]
    /** character sheets: the class's skills */
    fromClass?: string[]
    /** the abilities that give the game's skills (a character's: its own and its class's) */
    abilities: string[]
    classId?: string
    /** character sheets: the game skills given by the character itself (the routes' lords: Supply) */
    characterId?: string
    onchange: (skills: string[]) => void
    /** learned at a level */
    learned?: { skill: string; level: number }[]
    onlearnedchange?: (learned: { skill: string; level: number }[]) => void
    isClass?: boolean
  } = $props()

  $effect(() => { loadSkills() })

  const KINDS = ['stat', 'battle', 'order', 'proc', 'hits', 'map', 'menu', 'game']
  const game = $derived(gameSkills(abilities, classId, characterId))
  const offered = $derived(offeredSkills().filter((s) => !skills.includes(s.id) && !fromClass.includes(s.id) && !game.includes(s.id)))
  const full = $derived(skills.length >= skillCatalogue.maxPerSheet)

  function add(id: string) {
    if (id && !full) onchange([...skills, id])
  }

  const LEARN_MAX = 4
  let learnLevel = $state(10)
  const learnOffered = $derived(offeredSkills().filter((s) => !learned.some((l) => l.skill === s.id)))
  function learn(id: string) {
    if (id && learned.length < LEARN_MAX) onlearnedchange?.([...learned, { skill: id, level: learnLevel }])
  }
  function setLevel(index: number, level: number) {
    onlearnedchange?.(learned.map((l, i) => (i === index ? { ...l, level: Math.min(40, Math.max(1, level || 1)) } : l)))
  }
</script>

{#snippet row(id: string, tag: string, removable: boolean)}
  <div class="skill">
    <img class="pixel" src={skillIcon(id)} alt="" width="24" height="24" />
    <span class="name">{t(`skill.${id}`)}{#if tag}<span class="muted tag"> · {tag}</span>{/if} <Help text={t(`skill.${id}Hint`)} /></span>
    {#if removable}
      <button class="icon" title={t('skill.remove')} aria-label={t('skill.remove')} onclick={() => onchange(skills.filter((s) => s !== id))}>✕</button>
    {/if}
  </div>
{/snippet}

<section class="panel">
  <h3>{t('skill.title')} <Help text={t('skill.hint', { n: skillCatalogue.maxPerSheet })} /></h3>
  {#each skills as id (id)}{@render row(id, '', true)}{/each}
  {#each fromClass as id (id)}{@render row(id, t('skill.fromClass'), false)}{/each}
  {#each game as id (id)}{@render row(id, t('skill.fromGame'), false)}{/each}
  <select value="" disabled={full} title={full ? t('skill.full', { n: skillCatalogue.maxPerSheet }) : ''}
    onchange={(e) => { add((e.target as HTMLSelectElement).value); (e.target as HTMLSelectElement).value = '' }}>
    <option value="">{t('skill.add')}</option>
    {#each KINDS as kind (kind)}
      <optgroup label={t(`skill.kind.${kind}`)}>
        {#each offered.filter((s) => s.kind === kind) as s (s.id)}<option value={s.id}>{t(`skill.${s.id}`)}</option>{/each}
      </optgroup>
    {/each}
  </select>
  {#if onlearnedchange}
    <h4>{t('skill.learnedTitle')} <Help text={t(isClass ? 'skill.learnedClassHint' : 'skill.learnedHint', { n: LEARN_MAX })} /></h4>
    {#each learned as entry, i (entry.skill)}
      <div class="skill">
        <img class="pixel" src={skillIcon(entry.skill)} alt="" width="24" height="24" />
        <span class="name">{t(`skill.${entry.skill}`)} <Help text={t(`skill.${entry.skill}Hint`)} /></span>
        <label class="level">{t('skill.atLevel')} <input type="number" min="1" max="40" value={entry.level}
          onchange={(e) => setLevel(i, Number((e.target as HTMLInputElement).value))} /></label>
        <button class="icon" title={t('skill.remove')} aria-label={t('skill.remove')}
          onclick={() => onlearnedchange?.(learned.filter((_, j) => j !== i))}>✕</button>
      </div>
    {/each}
    <div class="learn">
      <select value="" disabled={learned.length >= LEARN_MAX} title={learned.length >= LEARN_MAX ? t('skill.full', { n: LEARN_MAX }) : ''}
        onchange={(e) => { learn((e.target as HTMLSelectElement).value); (e.target as HTMLSelectElement).value = '' }}>
        <option value="">{t('skill.learnAdd')}</option>
        {#each KINDS as kind (kind)}
          <optgroup label={t(`skill.kind.${kind}`)}>
            {#each learnOffered.filter((s) => s.kind === kind) as s (s.id)}<option value={s.id}>{t(`skill.${s.id}`)}</option>{/each}
          </optgroup>
        {/each}
      </select>
      <label class="level">{t('skill.atLevel')} <input type="number" min="1" max="40" bind:value={learnLevel} /></label>
    </div>
  {/if}
</section>

<style>
  .skill { display: flex; align-items: center; gap: 0.5rem; padding: 0.15rem 0; min-height: 2.2rem; }
  .skill .name { flex: 1; }
  .tag { font-size: 0.85em; }
  select { margin-top: 0.4rem; }
  h4 { margin: 0.8rem 0 0.2rem; }
  .level { display: flex; align-items: center; gap: 0.3rem; white-space: nowrap; }
  .level input { width: 3.5rem; }
  .learn { display: flex; align-items: center; gap: 0.5rem; }
  .learn select { flex: 1; }
</style>
