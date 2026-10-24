<script lang="ts">
  import { portraitUrl } from '../lib/api'
  import type { EditableList } from '../lib/history.svelte'
  import { t, problemText } from '../lib/i18n.svelte'
  import type { Character, ClassStatKey, ClassView, Item, Problem, Reference, StatKey } from '../lib/types'
  import NumberField from './NumberField.svelte'
  import AbilitiesPanel from './AbilitiesPanel.svelte'
  import RecordList from './RecordList.svelte'
  import Mention from './Mention.svelte'
  import ReservedWeapons from './ReservedWeapons.svelte'
  import PortraitPanel from './PortraitPanel.svelte'
  import ClassPicker from './ClassPicker.svelte'
  import { followFocus, useNavigator } from '../lib/navigation.svelte'

  let {
    list,
    classes,
    items,
    reference,
    problems,
    onproblems,
  }: {
    list: EditableList<Character>; classes: ClassView[]; items: Item[]; reference: Reference; problems: Problem[]
    /** problems after a change saved outside the list (an imported portrait) */
    onproblems: (p: Problem[]) => void
  } = $props()

  const STATS: StatKey[] = ['hp', 'pow', 'skl', 'spd', 'def', 'res', 'lck', 'con']
  const GROWTHS = ['hp', 'pow', 'skl', 'spd', 'def', 'res', 'lck'] as const
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
    secondary={(c) => !c.id.startsWith('CHARACTER_')}
    secondaryLabel={t('list.genericCharacters')}
    {problemIds}
  >
    {#snippet icon(c: Character)}
      <img class="pixel mini" src={portraitUrl(c.portraitId)} alt="" loading="lazy" onerror={(e) => ((e.target as HTMLImageElement).style.visibility = 'hidden')} />
    {/snippet}
  </RecordList>

  {#if ch}
    <div class="detail">
      <section class="panel identity">
        <img class="pixel portrait" src={portraitUrl(ch.portraitId)} alt={t('field.portrait')} onerror={(e) => ((e.target as HTMLImageElement).style.visibility = 'hidden')} />
        <div class="fields">
          <label title={problemFor('name')}>
            {t('field.name')}
            <input value={ch.name} class:invalid={!!problemFor('name')} oninput={(e) => edit((c) => (c.name = (e.target as HTMLInputElement).value))} />
          </label>
          <label title={problemFor('class')}>
            {t('field.class')}
            <span class="with-sign">
              <ClassPicker value={ch.class} {classes} label={t('field.class')} onchange={(v) => edit((c) => (c.class = v))} />
              <Mention kind="classes" id={ch.class}><span class="open">↗</span></Mention>
            </span>
          </label>
          {#each mine.filter((p) => p.field === 'class') as p, i (i)}<p class="{p.severity} small">{problemText(p)}</p>{/each}
          <p class="muted small">{t('field.classHint')}</p>
          <ReservedWeapons {items} characterId={ch.id} classId={ch.class} className={cls?.name ?? ''} />
          <div class="row">
            <NumberField label={t('field.portrait')} value={ch.portraitId} min={0} max={reference.portraits.length - 1} onchange={(v) => edit((c) => (c.portraitId = v))} />
            <label title={problemFor('affinity')}>
              {t('field.affinity')}
              <select
                value={ch.affinity ?? ''}
                onchange={(e) => {
                  const v = (e.target as HTMLSelectElement).value
                  edit((c) => (c.affinity = v || null))
                }}
              >
                <option value="">{t('field.none')}</option>
                {#each reference.affinities as a (a)}<option value={a}>{t(`affinity.${a}`)}</option>{/each}
              </select>
            </label>
          </div>
          <p class="small"><Mention kind="dialogues" id="supports">💞 {t('field.supportsLink')}</Mention></p>
          <details class="portrait-details">
            <summary>🖼 {ch.portraitId >= reference.firstNewPortrait && reference.portraits[ch.portraitId]
              ? t('portrait.titleNew', { id: ch.portraitId, name: reference.portraits[ch.portraitId] ?? '' })
              : t('portrait.title', { id: ch.portraitId })}</summary>
            <PortraitPanel portraitId={ch.portraitId} {problems} {onproblems} characterName={ch.name} onnew={(id, name) => {
              while (reference.portraits.length <= id) reference.portraits.push(null)
              reference.portraits[id] = name
              if (ch.portraitId !== id) edit((c) => (c.portraitId = id))
            }} onremoved={(id) => (reference.portraits[id] = null)} />
          </details>
        </div>
      </section>

      <section class="panel">
        <h3>{t('field.preview')}</h3>
        <p class="muted small">{t('field.basesHint')}</p>
        <div class="table-wrap">
          <table>
            <thead>
              <tr><th></th>{#each STATS as s (s)}<th>{t(`stat.${s}`)}</th>{/each}<th>{t('field.mov')}</th></tr>
            </thead>
            <tbody>
              <tr>
                <th>{t('field.personal')}</th>
                {#each STATS as s (s)}
                  <td>
                    <NumberField compact label="" value={ch.bases[s]} min={-128} max={127} problem={problemFor(`bases.${s}`)} onchange={(v) => edit((c) => (c.bases[s] = v))} />
                  </td>
                {/each}
                <td></td>
              </tr>
              <tr class="muted">
                <th>{t('field.classBase')}</th>
                {#each STATS as s (s)}<td>{cls?.bases[s as ClassStatKey] ?? 0}</td>{/each}
                <td>{cls?.mov ?? '?'}</td>
              </tr>
              <tr class="total">
                <th>{t('field.total')}</th>
                {#each STATS as s (s)}<td>{ch.bases[s] + (cls?.bases[s as ClassStatKey] ?? 0)}</td>{/each}
                <td>{cls?.mov ?? '?'}</td>
              </tr>
              <tr class="muted">
                <th>{t('field.max')}</th>
                {#each STATS as s (s)}<td>{s === 'lck' ? LUCK_CAP : (cls?.maxes[s as ClassStatKey] ?? '?')}</td>{/each}
                <td></td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>

      <section class="panel">
        <h3>{t('field.growths')}</h3>
        <div class="grid">
          {#each GROWTHS as s (s)}
            <NumberField label={t(`stat.${s}`)} value={ch.growths[s]} min={0} max={255} problem={problemFor(`growths.${s}`)} onchange={(v) => edit((c) => (c.growths[s] = v))} />
          {/each}
        </div>
      </section>

      <section class="panel">
        <h3>{t('field.weaponRanks')}</h3>
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
        <p class="muted small">{t('field.noAnimationHint')} {t('field.inventoryLater')}</p>
      </section>

      <AbilitiesPanel
        abilities={ch.abilities ?? []}
        fromClass={cls?.abilities ?? []}
        onchange={(abilities) => edit((c) => (c.abilities = abilities))}
        convoy={{ on: ch.convoyAccess ?? CONVOY_OPENERS.includes(ch.id), onchange: (on) => edit((c) => (c.convoyAccess = on)) }}
        seize={{ on: ch.canSeize ?? CONVOY_OPENERS.includes(ch.id), onchange: (on) => edit((c) => (c.canSeize = on)) }}
      />

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
  .portrait { width: 96px; height: 96px; background: var(--panel-2); border-radius: var(--radius); flex-shrink: 0; }
  .mini { width: 32px; height: 32px; flex-shrink: 0; }
  .fields { display: flex; flex-direction: column; gap: 0.75rem; flex: 1; min-width: 0; }
  .grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(100px, 1fr)); gap: 0.75rem; }
  .table-wrap { overflow-x: auto; }
  table { border-collapse: collapse; font-variant-numeric: tabular-nums; }
  th, td { padding: 0.2rem 0.3rem; text-align: right; }
  thead th { font-size: 0.8rem; color: var(--muted); font-weight: 600; }
  tbody th { text-align: left; font-size: 0.85rem; font-weight: 600; white-space: nowrap; }
  tr.total td { font-weight: 700; border-top: 1px solid var(--border); }
  .small { font-size: 0.8rem; margin: 0 0 0.5rem; }
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
