<script lang="ts">
  import { api, mapSpriteUrl } from '../lib/api'
  import { mapSpriteVersion } from '../lib/portraits.svelte'
  import FeRepoBrowser from './FeRepoBrowser.svelte'
  import type { EditableList } from '../lib/history.svelte'
  import { t, problemText } from '../lib/i18n.svelte'
  import type { ClassData, ClassStatKey, ClassView, Item, Problem, Reference } from '../lib/types'
  import AbilitiesPanel from './AbilitiesPanel.svelte'
  import DescriptionField from './DescriptionField.svelte'
  import BattleAnimation from './BattleAnimation.svelte'
  import GenderSign from './GenderSign.svelte'
  import NumberField from './NumberField.svelte'
  import RecordList from './RecordList.svelte'
  import Mention from './Mention.svelte'
  import ReservedWeapons from './ReservedWeapons.svelte'
  import { followFocus, useNavigator } from '../lib/navigation.svelte'

  let {
    list,
    classes,
    items,
    reference,
    problems,
    onanimations,
  }: { list: EditableList<ClassData>; classes: ClassView[]; items: Item[]; reference: Reference; problems: Problem[]; onanimations?: () => void } = $props()

  const STATS: ClassStatKey[] = ['hp', 'pow', 'skl', 'spd', 'def', 'res', 'con']
  const GROWTHS = ['hp', 'pow', 'skl', 'spd', 'def', 'res', 'lck'] as const
  const PROMO = ['hp', 'pow', 'skl', 'spd', 'def', 'res'] as const
  const GENDER_SIGN = { male: '♂', female: '♀' } as const

  let selected = $state(0)

  followFocus('classes', useNavigator(), () => classes.map((k) => k.id), (i) => {
    selected = i
  })

  const cl = $derived(classes[selected])
  const mine = $derived(problems.filter((p) => p.kind === 'classes' && p.id === cl?.id))
  const problemIds = $derived(new Set(problems.filter((p) => p.kind === 'classes' && p.severity === 'error').map((p) => p.id)))
  const usedClasses = $derived(classes.filter((k) => k.usedInGame))
  const unusedClasses = $derived(classes.filter((k) => !k.usedInGame))

  function problemFor(field: string): string {
    const p = mine.find((x) => x.field === field)
    return p ? problemText(p) : ''
  }

  function edit(change: (c: ClassData) => void) {
    list.update(selected, change)
  }

  function label(k: ClassView): string {
    const sign = k.gender ? ` ${GENDER_SIGN[k.gender]}` : ''
    return `${k.name || k.id}${sign}`
  }

  let addError = $state('')

  // Map sprites the project imports (server: decomp/mapsprites.py): class id -> key, key -> its name and source.
  let imported = $state<{ classes: Record<string, string>; sprites: Record<string, { name: string; walk?: boolean }> }>({ classes: {}, sprites: {} })
  let spriteBusy = $state(false)
  let spriteError = $state('')
  let browsing = $state(false)
  let localStand = $state<File | null>(null)
  let localWalk = $state<File | null>(null)
  const mySprite = $derived(cl ? imported.sprites[imported.classes[cl.id]] : undefined)
  /** An added class has its model's sprites until it gets its own; it may not be saved yet. */
  const spriteClass = (k: ClassView) => (imported.classes[k.id] ? k.id : (k.model ?? k.id))

  $effect(() => {
    api.getData<typeof imported>('mapsprites').then((d) => (imported = { classes: d.classes ?? {}, sprites: d.sprites ?? {} })).catch(() => {})
  })

  async function spriteChange(action: () => Promise<{ problems: Problem[] }>) {
    spriteBusy = true
    spriteError = ''
    try {
      await action()
      imported = await api.getData('mapsprites')
      mapSpriteVersion.n++
      browsing = false
      localStand = localWalk = null
    } catch (e) {
      const code = String(e).match(/(notAnImage|badStandSize|badWalkSize)/)?.[1]
      spriteError = code ? t(`mapsprite.error.${code}`) : String(e)
    } finally {
      spriteBusy = false
    }
  }

  async function addClass() {
    if (!cl) return
    addError = ''
    try {
      const record = await api.newClass(cl.id)
      record.name = t('item.copyName', { name: cl.name })
      list.change((records) => [...records, record])
      selected = list.records.length - 1
    } catch (e) {
      addError = String(e).includes('noFreeClass') ? t('class.noFree') : String(e)
    }
  }

  function removeClass() {
    if (!cl?.model || !confirm(t('class.removeConfirm', { name: cl.name }))) return
    const id = cl.id
    list.change((records) => records.filter((r) => r.id !== id))
    selected = Math.max(0, selected - 1)
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
  <RecordList records={classes} {selected} onselect={(i) => (selected = i)} secondary={(k) => !k.usedInGame} secondaryLabel={t('list.unusedClasses')} {problemIds}>
    {#snippet icon(k: ClassView)}
      <span class="sprite"><img src={mapSpriteUrl(spriteClass(k), 'player', true)} alt="" loading="lazy" onerror={(e) => ((e.target as HTMLImageElement).style.visibility = 'hidden')} /></span>
    {/snippet}
    {#snippet suffix(k: ClassView)}<GenderSign gender={k.gender} />{/snippet}
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
          {t('class.animated')} : {cl.animatedWeapons.map((w) => t(`wtype.${w}`)).join(', ') || '—'}{cl.usedInGame ? '' : ` · ${t('field.unusedClass')}`}{#if cl.gender} · {t('class.gender')} : <GenderSign gender={cl.gender} />{/if}
        </p>
        <DescriptionField value={cl.description ?? reference.descriptions.classes[cl.id] ?? reference.descriptions.classes[cl.model ?? ''] ?? ''}
                          onchange={(text) => edit((c) => (c.description = text))} />
        <ReservedWeapons {items} classId={cl.id} className={cl.name} />
        {#if cl.model}
          <p class="muted small">
            {t('class.copyOf')} <Mention kind="classes" id={cl.model}>{classes.find((k) => k.id === cl.model)?.name ?? cl.model}</Mention>
            <button class="link" onclick={removeClass}>{t('class.remove')}</button>
          </p>
        {:else}
          <p class="small">
            <button onclick={addClass} title={t('class.newFromHint')}>+ {t('class.newFrom')}</button>
            {#if addError}<span class="bad">{addError}</span>{/if}
          </p>
        {/if}
      </section>

      <section class="panel">
        <h3>{t('mapsprite.title')}</h3>
        <div class="sprite-row">
          {#each ['player', 'enemy', 'ally'] as side (side)}
            <img class="big-sprite" src={mapSpriteUrl(spriteClass(cl), side)} alt="" onerror={(e) => ((e.target as HTMLImageElement).style.visibility = 'hidden')} />
          {/each}
          <div class="sprite-info">
            {#if mySprite}
              <span class="small">{t('mapsprite.imported', { name: mySprite.name })}{mySprite.walk ? '' : ` · ${t('mapsprite.noWalk')}`}</span>
              <button class="link" disabled={spriteBusy} onclick={() => spriteChange(() => api.removeMapSprite(cl.id))}>{t('mapsprite.reset')}</button>
            {:else}
              <span class="muted small">{cl.model ? t('mapsprite.model', { name: classes.find((k) => k.id === cl.model)?.name ?? cl.model }) : t('mapsprite.game')}</span>
            {/if}
            <span class="buttons">
              <button onclick={() => (browsing = !browsing)} disabled={spriteBusy}>{t('mapsprite.ferepo')}</button>
              <label class="file">{t('mapsprite.stand')} <input type="file" accept="image/png" onchange={(e) => (localStand = (e.target as HTMLInputElement).files?.[0] ?? null)} /></label>
              <label class="file">{t('mapsprite.walk')} <input type="file" accept="image/png" onchange={(e) => (localWalk = (e.target as HTMLInputElement).files?.[0] ?? null)} /></label>
              <button disabled={!localStand || spriteBusy} onclick={() => spriteChange(() => api.importLocalMapSprite(cl.id, localStand!, localWalk))}>{t('mapsprite.import')}</button>
            </span>
            <span class="tiny muted">{t('mapsprite.hint')}</span>
            {#if spriteError}<span class="bad small">{spriteError}</span>{/if}
          </div>
        </div>
        {#if browsing}
          <FeRepoBrowser kind="mapsprites" initial={cl.name} busy={spriteBusy}
                         onpick={(e) => spriteChange(() => api.importFeRepoMapSprite(cl.id, e.url, e.walk ?? null))} />
        {/if}
      </section>

      <details class="panel fold">
        <summary>{t('class.stats')}</summary>
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
        <p class="muted small help">{t('class.statsHint')}</p>
      </details>

      <details class="panel fold">
        <summary>{t('class.promotions')}</summary>
        <div class="row">
          {#each [0, 1] as slot (slot)}
            <label title={problemFor('promotions')}>
              {t('class.promotion', { n: slot + 1 })}
              <span class="with-sign">
                <select value={cl.promotions[slot] ?? ''} onchange={(e) => setPromotion(slot, (e.target as HTMLSelectElement).value)}>
                  <option value="">{t('field.none')}</option>
                  {#each usedClasses as k (k.id)}<option value={k.id} class={k.gender ?? ''}>{label(k)}</option>{/each}
                  <optgroup label={t('list.unusedClassesGroup')}>
                    {#each unusedClasses as k (k.id)}<option value={k.id} class={k.gender ?? ''}>{label(k)}</option>{/each}
                  </optgroup>
                </select>
                <GenderSign gender={classes.find((k) => k.id === cl.promotions[slot])?.gender} />
                {#if cl.promotions[slot]}<Mention kind="classes" id={cl.promotions[slot]}><span class="open">↗</span></Mention>{/if}
              </span>
            </label>
          {/each}
        </div>
      </details>

      <details class="panel fold">
        <summary>{t('class.weaponRanks')}</summary>
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
        <p class="muted small help">{t('class.weaponRanksHint')}</p>
      </details>

      <BattleAnimation classId={cl.id} className={cl.name} {items} wtypes={[...reference.rankableTypes, 'item']} onchanged={onanimations} />

      <AbilitiesPanel abilities={cl.abilities} fromClass={[]} onchange={(abilities) => edit((c) => (c.abilities = abilities))} />

      {#if mine.length}
        <section class="panel issues">
          {#each mine as p, i (i)}<p class={p.severity}>{p.field}: {problemText(p)}</p>{/each}
        </section>
      {/if}
    </div>
  {/if}
</div>

<style>
  .editor { display: grid; grid-template-columns: 260px 1fr; gap: 1rem; align-items: start; }
  .detail { display: flex; flex-direction: column; gap: 1rem; min-width: 0; }
  .top { align-items: flex-end; }
  .check { flex-direction: row; align-items: center; gap: 0.4rem; }
  .grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(100px, 1fr)); gap: 0.75rem; }
  .table-wrap { overflow-x: auto; }
  table { border-collapse: collapse; font-variant-numeric: tabular-nums; }
  th, td { padding: 0.2rem 0.3rem; text-align: right; }
  thead th { font-size: 0.8rem; color: var(--muted); font-weight: 600; }
  tbody th { text-align: left; font-size: 0.85rem; font-weight: 600; white-space: nowrap; }
  .small { font-size: 0.8rem; margin: 0.5rem 0 0; }
  .noanim { color: var(--warn); }
  .open { font-size: 1.1rem; }
  select.invalid { border-color: var(--bad); background: var(--bad-soft); }
  .issues p { margin: 0.2rem 0; }
  .error { color: var(--bad); }
  .warning { color: var(--warn); }
  /* Trimmed map sprites, all at x2, feet on a common baseline in a fixed-width column so names line up.
     Only the few giants (wider than the column) are shrunk. */
  .sprite {
    width: 40px; min-height: 32px; flex: none;
    display: inline-flex; align-items: flex-end; justify-content: center;
  }
  .sprite img { image-rendering: pixelated; display: block; max-width: 40px; max-height: 56px; object-fit: contain; }
  @media (max-width: 800px) { .editor { grid-template-columns: 1fr; } }
  .sprite-row { display: flex; gap: 0.75rem; align-items: flex-start; flex-wrap: wrap; }
  .big-sprite { width: 48px; height: 48px; object-fit: contain; image-rendering: pixelated; background: var(--panel-2); border-radius: 6px; }
  .sprite-info { display: flex; flex-direction: column; gap: 0.3rem; flex: 1; min-width: 14rem; }
  .sprite-info .buttons { display: flex; gap: 0.4rem; flex-wrap: wrap; align-items: center; }
  .file { font-size: 0.8rem; display: flex; gap: 0.3rem; align-items: center; }
  .file input { max-width: 11rem; font-size: 0.75rem; }
</style>
