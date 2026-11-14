<script lang="ts">
  import { hideBroken } from '../lib/hideBroken'
  import Help from './Help.svelte'
  import { api, characterPackageUrl, portraitUrl } from '../lib/api'
  import PackageImport from './PackageImport.svelte'
  import type { EditableList } from '../lib/history.svelte'
  import { t, problemText } from '../lib/i18n.svelte'
  import type { Character, ClassStatKey, ClassView, Item, Problem, Reference, StatKey } from '../lib/types'
  import NumberField from './NumberField.svelte'
  import AbilitiesPanel from './AbilitiesPanel.svelte'
  import RecordList from './RecordList.svelte'
  import Mention from './Mention.svelte'
  import ReservedWeapons from './ReservedWeapons.svelte'
  import DescriptionField from './DescriptionField.svelte'
  import PortraitPanel from './PortraitPanel.svelte'
  import ClassPicker from './ClassPicker.svelte'
  import CharacterColors from './CharacterColors.svelte'
  import FacePicker from './FacePicker.svelte'
  import AffinityPicker from './AffinityPicker.svelte'
  import { followFocus, useNavigator } from '../lib/navigation.svelte'
  import { characterMagic, classMagic, statLabel, withMagic } from '../lib/magic.svelte'
  import { abilitiesFromSkills, skillsOption } from '../lib/skills.svelte'
  import SkillsPanel from './SkillsPanel.svelte'
  import BossTheme from './BossTheme.svelte'

  let {
    list,
    classes,
    items,
    reference,
    problems,
    onproblems,
    onimportpackage,
  }: {
    list: EditableList<Character>; classes: ClassView[]; items: Item[]; reference: Reference; problems: Problem[]
    /** problems after a change saved outside the list (an imported portrait) */
    onproblems: (p: Problem[]) => void
    /** a character's file from another project (Workspace) */
    onimportpackage: (file: File) => Promise<string[]>
  } = $props()

  const ALL_STATS: StatKey[] = ['hp', 'pow', 'skl', 'spd', 'def', 'res', 'lck', 'con']
  const ALL_GROWTHS = ['hp', 'pow', 'skl', 'spd', 'def', 'res', 'lck'] as const
  /** with Magic after Strength when it is apart (game option strMagSplit) */
  const STATS = $derived(withMagic(ALL_STATS))
  const GROWTHS = $derived(withMagic(ALL_GROWTHS))
  type Stat = StatKey | 'mag'
  const LUCK_CAP = 30 // fixed by the engine, not per class
  /** who opens the convoy, and who can seize, in the game (server: convoy.DEFAULT_OPENERS, seize.DEFAULT_SEIZERS) */
  const CONVOY_OPENERS = ['CHARACTER_EIRIKA', 'CHARACTER_EPHRAIM']

  let selected = $state(0)

  followFocus('characters', useNavigator(), () => list.records.map((c) => c.id), (i) => {
    selected = i
  })

  const ch = $derived(list.records[selected])
  const cls = $derived(classes.find((c) => c.id === ch?.class))
  const mine = $derived(problems.filter((p) => p.kind === 'characters' && p.id === ch?.id))
  const problemIds = $derived(new Set(problems.filter((p) => p.kind === 'characters' && p.severity === 'error').map((p) => p.id)))

  function problemFor(field: string): string {
    const p = mine.find((x) => x.field === field)
    return p ? problemText(p) : ''
  }

  function edit(change: (c: Character) => void) {
    list.update(selected, change)
  }

  /** Characters the project adds (server: gamedata.NEW_CHARACTER_PREFIX), the only ones that can be removed. */
  const isNew = (id: string) => id.startsWith('CHARACTER_NEW_')
  // Allies first; a new character is an enemy past the allies' entries (server: gamedata.ALLY_CHARACTER_END).
  const gameEnemies = $derived(new Set(reference.gameEnemies))
  const isEnemy = (id: string) => (isNew(id) ? parseInt(id.slice('CHARACTER_NEW_'.length), 16) >= 0x46 : gameEnemies.has(id))
  let addError = $state('')

  async function addCharacter(ally: boolean) {
    addError = ''
    try {
      const { record, replaces } = await api.newCharacter(ally)
      record.name = t(ally ? 'character.newAlly' : 'character.newEnemy')
      list.change((records) => [...records.filter((r) => r.id !== replaces), record])
      selected = list.records.length - 1
    } catch (e) {
      addError = String(e).includes('noFreeCharacter') ? t('character.noFree') : String(e)
    }
  }

  function removeCharacter() {
    if (!ch || !isNew(ch.id) || !confirm(t('character.removeConfirm', { name: ch.name }))) return
    const id = ch.id
    list.change((records) => records.filter((r) => r.id !== id))
    selected = Math.max(0, selected - 1)
  }

  let averageLevel = $state(20)
  /** Promotions chosen in the calculator, in order (a trainee class promotes twice), and the level reached after each. */
  let promoteTo = $state<string[]>([])
  let levelsAfter = $state<number[]>([])
  const levelCap = (c?: ClassView) => (c?.abilities.includes('maxLevel10') || ch?.abilities.includes('maxLevel10') ? 10 : 20)
  const reached = (level: number, c?: ClassView) => Math.min(level, levelCap(c))
  const steps = $derived.by(() => {
    const found: { options: ClassView[]; to?: ClassView; level: number }[] = []
    let from = cls
    while (from?.promotions?.length) {
      const options = from.promotions.flatMap((id) => classes.filter((c) => c.id === id))
      const i = found.length
      const to = options.find((c) => c.id === promoteTo[i])
      found.push({ options, to, level: reached(levelsAfter[i] ?? 10, to) })
      from = to
    }
    return found
  })
  /** The class of the average line: its limits are the ones shown. */
  const finalClass = $derived(steps.reduce((c, step) => step.to ?? c, cls))
  let pickingPortrait = $state(false)
  const portraitFaces = $derived(reference.portraits.flatMap((name, id) => (name ? [{ id: String(id), portrait: id }] : [])))

  /** What the character has on average: `averageLevel` in their class, then, after each promotion, the level chosen in the new one
   * (as ApplyUnitPromotion: gains, then the new class's limits; constitution comes with the class). */
  /** Magic's figures come from lib/magic (a default when the project gives none). */
  const personal = (s: Stat) => (s === 'mag' ? characterMagic(ch, cls).bases : ch.bases[s])
  const growthOf = (s: Stat) => (s === 'mag' ? characterMagic(ch, cls).growths : s === 'con' ? 0 : ch.growths[s])
  const classBase = (s: Stat, c?: ClassView) => (s === 'mag' ? classMagic(c).bases : (c?.bases[s as ClassStatKey] ?? 0))
  const classMax = (s: Stat, c?: ClassView) => (s === 'mag' ? (c ? classMagic(c).maxes : undefined) : c?.maxes[s as ClassStatKey])
  const classGain = (s: Stat, c: ClassView) => (s === 'mag' ? classMagic(c).promotionGains
    : c.promotionGains[s as Exclude<ClassStatKey, 'con'>])

  function average(s: Stat): { value: number; capped: boolean } {
    let capped = false
    const within = (value: number, c?: ClassView) => {
      const limit = s === 'lck' ? LUCK_CAP : classMax(s, c)
      capped = limit !== undefined && value >= limit
      return Math.min(value, limit ?? value)
    }
    const growth = growthOf(s)
    const start = personal(s) + classBase(s, cls)
    let value = within(start + (growth * Math.max(0, reached(averageLevel, cls) - ch.level)) / 100, cls)
    for (const { to, level } of steps) {
      if (!to) break
      if (s === 'con') value = ch.bases.con + to.bases.con
      else if (s !== 'lck') value += classGain(s, to)
      value = within(value + (growth * Math.max(0, level - 1)) / 100, to)
    }
    return { value: Number(value.toFixed(1)), capped }
  }
  /** The character's gender follows their class, when the class has one (monsters have none). */
  function setClass(id: string) {
    const gender = classes.find((c) => c.id === id)?.gender
    edit((c) => {
      c.class = id
      if (gender) c.abilities = [...c.abilities.filter((a) => a !== 'female'), ...(gender === 'female' ? ['female'] : [])]
    })
  }
  const growthSum = $derived(ch ? GROWTHS.reduce((sum, s) => sum + growthOf(s), 0) : 0)
  let colorsOpen = $state(false)

  function setColors(classId: string, lines: string[][] | null | undefined, kept?: string[][]) {
    edit((c) => {
      if (kept) c.customColors = { ...c.customColors, [classId]: kept }
      const colors = { ...c.battleColors }
      if (lines === undefined) delete colors[classId]
      else colors[classId] = lines
      if (Object.keys(colors).length) c.battleColors = colors
      else delete c.battleColors
    })
  }

  function setRank(wtype: string, rank: string) {
    edit((c) => {
      if (rank) c.weaponRanks[wtype] = rank
      else delete c.weaponRanks[wtype]
    })
  }
</script>

<div class="editor">
  <RecordList
    records={list.records}
    {selected}
    onselect={(i) => (selected = i)}
    secondary={(c) => !c.id.startsWith('CHARACTER_') || reference.namedGenerics.includes(c.id)}
    secondaryLabel={t('list.genericCharacters')}
    rank={(c) => (isEnemy(c.id) ? 1 : 0)}
    {problemIds}
  >
    {#snippet actions()}
      <button onclick={() => addCharacter(true)} title={t('character.addAllyHint')}>+ {t('character.addAlly')}</button>
      <button onclick={() => addCharacter(false)} title={t('character.addEnemyHint')}>+ {t('character.addEnemy')}</button>
      <PackageImport kind="character" onimport={onimportpackage} />
      {#if addError}<p class="bad small">{addError}</p>{/if}
    {/snippet}
    {#snippet icon(c: Character)}
      <img class="pixel mini" src={portraitUrl(c.portraitId)} alt="" loading="lazy" use:hideBroken />
    {/snippet}
  </RecordList>

  {#if ch}
    <div class="detail">
      <section class="panel identity">
        <button class="portrait-button" title={t('field.changePortrait')} onclick={() => (pickingPortrait = !pickingPortrait)}>
          <img class="pixel portrait" src={portraitUrl(ch.portraitId)} alt={t('field.portrait')} use:hideBroken />
          <span class="small">{t('field.changePortrait')}</span>
        </button>
        <div class="fields">
          {#if pickingPortrait}
            <FacePicker faces={portraitFaces} label={(id) => reference.portraits[Number(id)] ?? id} hint=""
                        onpick={(id) => { pickingPortrait = false; edit((c) => (c.portraitId = Number(id))) }} onclose={() => (pickingPortrait = false)} />
          {/if}
          <label title={problemFor('name')}>
            {t('field.name')}
            <input value={ch.name} class:invalid={!!problemFor('name')} oninput={(e) => edit((c) => (c.name = (e.target as HTMLInputElement).value))} />
          </label>
          <label title={problemFor('class')}>
            <span>{t('field.class')} <Help text={t('field.classHint')} /></span>
            <span class="with-sign">
              <ClassPicker value={ch.class} {classes} label={t('field.class')} onchange={setClass} />
              <Mention kind="classes" id={ch.class}><span class="open">↗</span></Mention>
            </span>
          </label>
          {#each mine.filter((p) => p.field === 'class') as p, i (i)}<p class="{p.severity} small">{problemText(p)}</p>{/each}
          <ReservedWeapons {items} characterId={ch.id} classId={ch.class} className={cls?.name ?? ''} />
          <div class="row top">
            <NumberField label={t('field.level')} value={ch.level} min={0} max={127} problem={problemFor('level')} onchange={(v) => edit((c) => (c.level = v))} />
            <AffinityPicker value={ch.affinity} affinities={reference.affinities} bonuses={reference.affinityBonuses} problem={problemFor('affinity')}
                            onchange={(v) => edit((c) => (c.affinity = v))} />
          </div>
          <DescriptionField value={ch.description ?? reference.descriptions.characters[ch.id] ?? ''} onchange={(text) => edit((c) => (c.description = text))} />
          <p class="small links">
            <Mention kind="dialogues" id="supports">{t('field.supportsLink')}</Mention>
            <Mention kind="dialogues" id={`death:${ch.id}`}>{t('field.lastWordsLink')}</Mention>
            <Help text={t('field.lastWordsHint')} />
          </p>
          <details class="portrait-details" open={ch.portraitId === 0}>
            <summary>{ch.portraitId >= reference.firstNewPortrait && reference.portraits[ch.portraitId]
              ? t('portrait.titleNew', { name: reference.portraits[ch.portraitId] ?? '' })
              : t('portrait.title')}</summary>
            <PortraitPanel portraitId={ch.portraitId} {problems} {onproblems} characterName={ch.name} onnew={(id, name) => {
              while (reference.portraits.length <= id) reference.portraits.push(null)
              reference.portraits[id] = name
              if (ch.portraitId !== id) edit((c) => (c.portraitId = id))
            }} onremoved={(id) => (reference.portraits[id] = null)} />
          </details>
        </div>
      </section>

      <section class="panel">
        <h3>{t('field.preview')} <Help text={t('field.basesHint')} /></h3>
        <div class="table-wrap">
          <table>
            <thead>
              <tr><th></th>{#each STATS as s (s)}<th>{statLabel(s)}</th>{/each}<th>{t('field.mov')}</th></tr>
            </thead>
            <tbody>
              <tr>
                <th>{t('field.personal')}</th>
                {#each STATS as s (s)}
                  <td>
                    <NumberField compact label="" value={personal(s)} min={-128} max={127} problem={problemFor(`bases.${s}`)} onchange={(v) => edit((c) => (c.bases[s] = v))} />
                  </td>
                {/each}
                <td></td>
              </tr>
              <tr class="muted">
                <th>{t('field.classBase')}</th>
                {#each STATS as s (s)}<td>{classBase(s, cls)}</td>{/each}
                <td>{cls?.mov ?? '?'}</td>
              </tr>
              <tr class="total">
                <th>{t('field.total')}</th>
                {#each STATS as s (s)}<td>{personal(s) + classBase(s, cls)}</td>{/each}
                <td>{cls?.mov ?? '?'}</td>
              </tr>
              <tr class="muted">
                <th>{t('field.max')}{finalClass === cls ? '' : ` · ${finalClass?.name}`}</th>
                {#each STATS as s (s)}<td>{s === 'lck' ? LUCK_CAP : (classMax(s, finalClass) ?? '?')}</td>{/each}
                <td></td>
              </tr>
              <tr class="average">
                <th>{t('field.average')}</th>
                {#each STATS as s (s)}
                  {@const a = average(s)}
                  <td class:capped={a.capped}>{a.value}</td>
                {/each}
                <td>{finalClass?.mov ?? '?'}</td>
              </tr>
            </tbody>
          </table>
        </div>
        <div class="average-of">
          <span>{t('field.averageLevel')}</span>
          <NumberField compact label="" value={reached(averageLevel, cls)} min={1} max={levelCap(cls)} onchange={(v) => (averageLevel = v)} />
          {#each steps as step, i (i)}
            <span>→</span>
            <select bind:value={() => step.to?.id ?? '', (v) => (promoteTo = [...promoteTo.slice(0, i), v])} aria-label={t('field.averageNoPromotion')}>
              <option value="">{t('field.averageNoPromotion')}</option>
              {#each step.options as c (c.id)}<option value={c.id}>{c.name}</option>{/each}
            </select>
            {#if step.to}
              <span>{t('field.averageLevel')}</span>
              <NumberField compact label="" value={step.level} min={1} max={levelCap(step.to)} onchange={(v) => { levelsAfter[i] = v }} />
            {/if}
          {/each}
          <Help text={t('field.averageHint')} />
        </div>
      </section>

      <details class="panel fold">
        <summary>{t('field.growths')}</summary>
        <div class="grid">
          {#each GROWTHS as s (s)}
            <NumberField label={statLabel(s)} value={growthOf(s)} min={0} max={255} problem={problemFor(`growths.${s}`)} onchange={(v) => edit((c) => (c.growths[s] = v))} />
          {/each}
        </div>
        <p class="small muted">{t('field.growthSum', { n: growthSum })}</p>
      </details>

      <details class="panel fold">
        <summary>{t('field.weaponRanks')} <Help text={`${t('field.noAnimationHint')} ${t('field.inventoryLater')}`} /></summary>
        <div class="grid">
          {#each reference.rankableTypes as w (w)}
            <label title={problemFor(`weaponRanks.${w}`)}>
              <span>{t(`wtype.${w}`)}{#if cls && cls.animatedWeapons.length && !cls.animatedWeapons.includes(w)}<span class="noanim" title={t('field.noAnimation')}> ⚠</span>{/if}</span>
              <select value={String(ch.weaponRanks[w] ?? '')} class:invalid={!!problemFor(`weaponRanks.${w}`)} onchange={(e) => setRank(w, (e.target as HTMLSelectElement).value)}>
                <option value="">{t('field.none')}</option>
                {#each reference.ranks as r (r)}<option value={r}>{r}</option>{/each}
              </select>
            </label>
          {/each}
        </div>
      </details>

      <details class="panel fold" ontoggle={(e) => (colorsOpen = (e.target as HTMLDetailsElement).open)}>
        <summary>{t('character.colors.title')}</summary>
        {#if colorsOpen}
          {#key ch.id}
            <CharacterColors character={ch} characters={list.records} {classes} {items} side={isEnemy(ch.id) ? 1 : 0} onchange={setColors} />
          {/key}
        {/if}
      </details>

      <details class="panel fold">
        <summary>{t('field.abilities')}</summary>
      <AbilitiesPanel
        abilities={ch.abilities ?? []}
        fromClass={cls?.abilities ?? []}
        onchange={(abilities) => edit((c) => (c.abilities = abilities))}
        convoy={{ on: ch.convoyAccess ?? CONVOY_OPENERS.includes(ch.id), onchange: (on) => edit((c) => (c.convoyAccess = on)) }}
        seize={{ on: ch.canSeize ?? CONVOY_OPENERS.includes(ch.id), onchange: (on) => edit((c) => (c.canSeize = on)) }}
        fromSkills={skillsOption.on ? abilitiesFromSkills([...(ch.skills ?? []), ...(cls?.skills ?? [])]) : []}
      />
      </details>

      <details class="panel fold">
        <summary>{t('music.bossTitle')} <Help text={t('music.bossHint')} /></summary>
        <BossTheme characterId={ch.id} />
      </details>

      {#if skillsOption.on}
        <SkillsPanel skills={ch.skills ?? []} fromClass={cls?.skills ?? []} abilities={[...(ch.abilities ?? []), ...(cls?.abilities ?? [])]}
          classId={cls?.id} characterId={ch.id} onchange={(skills) => edit((c) => (c.skills = skills))}
          learned={ch.learnedSkills ?? []} onlearnedchange={(l) => edit((c) => (c.learnedSkills = l))} />
      {/if}

      <p class="small sheet-links">
        <a href={characterPackageUrl(ch.id)} download title={t('package.export.characterHint')}>{t('package.export.character')}</a>
        {#if isNew(ch.id)}<button class="link" onclick={removeCharacter}>{t('character.remove')}</button>{/if}
      </p>

      {#if mine.length}
        <section class="panel issues">
          {#each mine as p, i (i)}
            <p class={p.severity}>{p.field}: {problemText(p)}</p>
          {/each}
        </section>
      {/if}
    </div>
  {/if}
</div>

<style>
  .editor { display: grid; grid-template-columns: 260px 1fr; gap: 1rem; align-items: start; }
  .detail { display: flex; flex-direction: column; gap: 1rem; min-width: 0; }
  .identity { display: flex; gap: 1.25rem; align-items: flex-start; }
  .row.top { align-items: flex-start; }
  .portrait-button { display: flex; flex-direction: column; align-items: center; gap: 0.3rem; flex-shrink: 0; padding: 0.3rem; background: none; border-color: transparent; }
  .portrait-button:hover .small { text-decoration: underline; }
  .portrait { width: 96px; height: 96px; background: var(--panel-2); border-radius: var(--radius); flex-shrink: 0; }
  .mini { width: 32px; height: 32px; flex-shrink: 0; }
  .fields { display: flex; flex-direction: column; gap: 0.75rem; flex: 1; min-width: 0; }
  .grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(100px, 1fr)); gap: 0.75rem; }
  td.capped { color: var(--good); font-weight: 700; }
  .average-of { display: flex; flex-wrap: wrap; align-items: center; gap: 0.4rem; margin-top: 0.5rem; }
  .table-wrap { overflow-x: auto; }
  table { border-collapse: collapse; font-variant-numeric: tabular-nums; }
  th, td { padding: 0.2rem 0.3rem; text-align: right; }
  thead th { font-size: 0.8rem; color: var(--muted); font-weight: 600; }
  tbody th { text-align: left; font-size: 0.85rem; font-weight: 600; white-space: nowrap; }
  tr.total td { font-weight: 700; border-top: 1px solid var(--border); }
  .small { font-size: 0.8rem; margin: 0 0 0.5rem; }
  .sheet-links { display: flex; gap: 1rem; align-items: center; }
  .links { display: flex; align-items: center; gap: 0.8rem; flex-wrap: wrap; }
  .issues p { margin: 0.2rem 0; }
  .noanim { color: var(--warn); }
  .open { font-size: 1.1rem; }
  select.invalid { border-color: var(--bad); background: var(--bad-soft); }
  .error { color: var(--bad); }
  .warning { color: var(--warn); }
  @media (max-width: 800px) {
    .editor { grid-template-columns: 1fr; }
    .identity { flex-direction: column; }
  }
  .portrait-details { margin-top: 0.5rem; }
  .portrait-details summary { cursor: pointer; font-size: 0.85rem; margin-bottom: 0.4rem; }
</style>
