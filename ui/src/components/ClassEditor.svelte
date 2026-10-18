<script lang="ts">
  import type { EditableList } from '../lib/history.svelte'
  import { t } from '../lib/i18n.svelte'
  import type { ClassData, ClassStatKey, ClassView, Problem, Reference } from '../lib/types'
  import AbilitiesPanel from './AbilitiesPanel.svelte'
  import NumberField from './NumberField.svelte'
  import RecordList from './RecordList.svelte'

  let {
    list,
    classes,
    reference,
    problems,
  }: { list: EditableList<ClassData>; classes: ClassView[]; reference: Reference; problems: Problem[] } = $props()

  const STATS: ClassStatKey[] = ['hp', 'pow', 'skl', 'spd', 'def', 'res', 'con']
  const GROWTHS = ['hp', 'pow', 'skl', 'spd', 'def', 'res', 'lck'] as const
  const PROMO = ['hp', 'pow', 'skl', 'spd', 'def', 'res'] as const
  const GENDER_SIGN = { male: '♂', female: '♀' } as const

  let selected = $state(0)
  let hideUnused = $state(true)

  const cl = $derived(classes[selected])
  const mine = $derived(problems.filter((p) => p.kind === 'classes' && p.id === cl?.id))
  const problemIds = $derived(new Set(problems.filter((p) => p.kind === 'classes' && p.severity === 'error').map((p) => p.id)))
  const promoChoices = $derived(classes.filter((k) => !hideUnused || k.usedInGame || cl?.promotions.includes(k.id)))

  function problemFor(field: string): string {
    const p = mine.find((x) => x.field === field)
    return p ? t(`problem.${p.code}`, p.params) : ''
  }

  function edit(change: (c: ClassData) => void) {
    list.update(selected, change)
  }

  function label(k: ClassView): string {
    const sign = k.gender ? ` ${GENDER_SIGN[k.gender]}` : ''
    return `${k.name || k.id}${sign}`
  }

  function setPromotion(slot: number, id: string) {
    edit((c) => {
      const p = [c.promotions[0] ?? '', c.promotions[1] ?? '']
      p[slot] = id
      c.promotions = p.filter(Boolean)
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
  <RecordList records={classes} {selected} onselect={(i) => (selected = i)} filter={(k) => !hideUnused || k.usedInGame} {problemIds}>
    {#snippet icon(k: ClassView)}
      <span class="sign">{k.gender ? GENDER_SIGN[k.gender] : '·'}</span>
    {/snippet}
    {#snippet extraFilter()}
      <label class="check"><input type="checkbox" bind:checked={hideUnused} /> {t('field.hideUnusedClasses')}</label>
    {/snippet}
  </RecordList>

  {#if cl}
    <div class="detail">
      <section class="panel">
        <div class="row top">
          <label title={problemFor('name')}>
            {t('field.name')}
            <input value={cl.name} class:invalid={!!problemFor('name')} oninput={(e) => edit((c) => (c.name = (e.target as HTMLInputElement).value))} />
          </label>
          <NumberField label={t('class.mov')} value={cl.mov} min={0} max={15} problem={problemFor('mov')} onchange={(v) => edit((c) => (c.mov = v))} />
          <label>
            {t('class.movement')}
            <select value={cl.movement ?? ''} onchange={(e) => edit((c) => (c.movement = (e.target as HTMLSelectElement).value))}>
              {#each reference.movementTypes as m (m)}<option value={m}>{t(`movement.${m}`)}</option>{/each}
            </select>
          </label>
          <label>
            {t('class.terrainBonus')}
            <select value={cl.terrainBonus ?? ''} onchange={(e) => edit((c) => (c.terrainBonus = (e.target as HTMLSelectElement).value))}>
              <option value="Common">{t('class.terrain.Common')}</option>
              <option value="Fly">{t('class.terrain.Fly')}</option>
            </select>
          </label>
          <NumberField label={t('class.relativePower')} value={cl.relativePower} min={-128} max={127} problem={problemFor('relativePower')} onchange={(v) => edit((c) => (c.relativePower = v))} />
        </div>
        <p class="muted small">
          {cl.gender ? `${GENDER_SIGN[cl.gender]} · ` : ''}{t('class.animated')} : {cl.animatedWeapons.map((w) => t(`wtype.${w}`)).join(', ') || '—'}{cl.usedInGame ? '' : ` · ${t('field.unusedClass')}`}
        </p>
      </section>

      <section class="panel">
        <h3>{t('class.stats')}</h3>
        <div class="table-wrap">
          <table>
            <thead>
              <tr><th></th>{#each GROWTHS as s (s)}<th>{t(`stat.${s}`)}</th>{/each}<th>{t('stat.con')}</th></tr>
            </thead>
            <tbody>
              <tr>
                <th>{t('class.bases')}</th>
                {#each GROWTHS as s (s)}
                  <td>
                    {#if s === 'lck'}<span class="muted">—</span>{:else}
                      <NumberField compact label="" value={cl.bases[s]} min={0} max={127} problem={problemFor(`bases.${s}`)} onchange={(v) => edit((c) => (c.bases[s as ClassStatKey] = v))} />
                    {/if}
                  </td>
                {/each}
                <td><NumberField compact label="" value={cl.bases.con} min={0} max={127} problem={problemFor('bases.con')} onchange={(v) => edit((c) => (c.bases.con = v))} /></td>
              </tr>
              <tr>
                <th>{t('field.max')}</th>
                {#each GROWTHS as s (s)}
                  <td>
                    {#if s === 'lck'}<span class="muted">30</span>{:else}
                      <NumberField compact label="" value={cl.maxes[s]} min={0} max={127} problem={problemFor(`maxes.${s}`)} onchange={(v) => edit((c) => (c.maxes[s as ClassStatKey] = v))} />
                    {/if}
                  </td>
                {/each}
                <td><NumberField compact label="" value={cl.maxes.con} min={0} max={127} problem={problemFor('maxes.con')} onchange={(v) => edit((c) => (c.maxes.con = v))} /></td>
              </tr>
              <tr>
                <th>{t('class.growths')}</th>
                {#each GROWTHS as s (s)}
                  <td><NumberField compact label="" value={cl.growths[s]} min={0} max={127} problem={problemFor(`growths.${s}`)} onchange={(v) => edit((c) => (c.growths[s] = v))} /></td>
                {/each}
                <td></td>
              </tr>
              <tr>
                <th>{t('class.promotionGains')}</th>
                {#each GROWTHS as s (s)}
                  <td>
                    {#if s === 'lck'}<span class="muted">—</span>{:else}
                      <NumberField compact label="" value={cl.promotionGains[s as (typeof PROMO)[number]]} min={0} max={255} problem={problemFor(`promotionGains.${s}`)} onchange={(v) => edit((c) => (c.promotionGains[s as (typeof PROMO)[number]] = v))} />
                    {/if}
                  </td>
                {/each}
                <td></td>
              </tr>
            </tbody>
          </table>
        </div>
        <p class="muted small">{t('class.statsHint')}</p>
      </section>

      <section class="panel">
        <h3>{t('class.promotions')}</h3>
        <div class="row">
          {#each [0, 1] as slot (slot)}
            <label title={problemFor('promotions')}>
              {t('class.promotion', { n: slot + 1 })}
              <select value={cl.promotions[slot] ?? ''} onchange={(e) => setPromotion(slot, (e.target as HTMLSelectElement).value)}>
                <option value="">{t('field.none')}</option>
                {#each promoChoices as k (k.id)}<option value={k.id}>{label(k)}</option>{/each}
              </select>
            </label>
          {/each}
        </div>
      </section>

      <section class="panel">
        <h3>{t('class.weaponRanks')}</h3>
        <div class="grid">
          {#each reference.rankableTypes as w (w)}
            <label title={problemFor(`weaponRanks.${w}`)}>
              <span>{t(`wtype.${w}`)}{#if cl.animatedWeapons.length && !cl.animatedWeapons.includes(w)}<span class="noanim" title={t('field.noAnimation')}> ⚠</span>{/if}</span>
              <select value={String(cl.weaponRanks[w] ?? '')} class:invalid={!!problemFor(`weaponRanks.${w}`)} onchange={(e) => setRank(w, (e.target as HTMLSelectElement).value)}>
                <option value="">{t('field.none')}</option>
                {#each reference.ranks as r (r)}<option value={r}>{r}</option>{/each}
              </select>
            </label>
          {/each}
        </div>
        <p class="muted small">{t('class.weaponRanksHint')}</p>
      </section>

      <AbilitiesPanel abilities={cl.abilities} fromClass={[]} lockItems={reference.lockItems} onchange={(abilities) => edit((c) => (c.abilities = abilities))} />

      {#if mine.length}
        <section class="panel issues">
          {#each mine as p, i (i)}<p class={p.severity}>{p.field}: {t(`problem.${p.code}`, p.params)}</p>{/each}
        </section>
      {/if}
    </div>
  {/if}
</div>

<style>
  .editor { display: grid; grid-template-columns: 260px 1fr; gap: 1rem; align-items: start; }
  .detail { display: flex; flex-direction: column; gap: 1rem; min-width: 0; }
  .top { align-items: flex-end; }
  .sign { width: 1.2em; text-align: center; color: var(--muted); }
  .check { flex-direction: row; align-items: center; gap: 0.4rem; }
  .grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(100px, 1fr)); gap: 0.75rem; }
  .table-wrap { overflow-x: auto; }
  table { border-collapse: collapse; font-variant-numeric: tabular-nums; }
  th, td { padding: 0.2rem 0.3rem; text-align: right; }
  thead th { font-size: 0.8rem; color: var(--muted); font-weight: 600; }
  tbody th { text-align: left; font-size: 0.85rem; font-weight: 600; white-space: nowrap; }
  .small { font-size: 0.8rem; margin: 0.5rem 0 0; }
  .noanim { color: var(--warn); }
  select.invalid { border-color: var(--bad); background: var(--bad-soft); }
  .issues p { margin: 0.2rem 0; }
  .error { color: var(--bad); }
  .warning { color: var(--warn); }
  @media (max-width: 800px) { .editor { grid-template-columns: 1fr; } }
</style>
