<script lang="ts">
  import Help from './Help.svelte'
  import SkillPicker from './SkillPicker.svelte'
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
  <SkillPicker skills={offered} placeholder={t('skill.add')} disabled={full}
    title={full ? t('skill.full', { n: skillCatalogue.maxPerSheet }) : ''} onpick={add} />
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
      <div class="grow">
        <SkillPicker skills={learnOffered} placeholder={t('skill.learnAdd')} disabled={learned.length >= LEARN_MAX}
          title={learned.length >= LEARN_MAX ? t('skill.full', { n: LEARN_MAX }) : ''} onpick={learn} />
      </div>
      <label class="level">{t('skill.atLevel')} <input type="number" min="1" max="40" bind:value={learnLevel} /></label>
    </div>
  {/if}
</section>

<style>
  .skill { display: flex; align-items: center; gap: 0.5rem; padding: 0.15rem 0; min-height: 2.2rem; }
  .skill .name { flex: 1; }
  .tag { font-size: 0.85em; }
  h4 { margin: 0.8rem 0 0.2rem; }
  .level { display: flex; align-items: center; gap: 0.3rem; white-space: nowrap; }
  .level input { width: 3.5rem; }
  .learn { display: flex; align-items: flex-end; gap: 0.5rem; }
  .learn .grow { flex: 1; min-width: 0; }
</style>
