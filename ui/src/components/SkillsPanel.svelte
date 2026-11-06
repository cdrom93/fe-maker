<script lang="ts">
  import Help from './Help.svelte'
  import { t } from '../lib/i18n.svelte'
  import { gameSkills, loadSkills, offeredSkills, skillCatalogue, skillIcon } from '../lib/skills.svelte'

  let {
    skills,
    fromClass = [],
    abilities,
    classId,
    onchange,
  }: {
    /** the sheet's own skills */
    skills: string[]
    /** character sheets: the class's skills */
    fromClass?: string[]
    /** the abilities that give the game's skills (a character's: its own and its class's) */
    abilities: string[]
    classId?: string
    onchange: (skills: string[]) => void
  } = $props()

  $effect(() => { loadSkills() })

  const KINDS = ['stat', 'battle', 'order']
  const offered = $derived(offeredSkills().filter((s) => !skills.includes(s.id) && !fromClass.includes(s.id)))
  const game = $derived(gameSkills(abilities, classId))
  const full = $derived(skills.length >= skillCatalogue.maxPerSheet)

  function add(id: string) {
    if (id && !full) onchange([...skills, id])
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
</section>

<style>
  .skill { display: flex; align-items: center; gap: 0.5rem; padding: 0.15rem 0; min-height: 2.2rem; }
  .skill .name { flex: 1; }
  .tag { font-size: 0.85em; }
  select { margin-top: 0.4rem; }
</style>
