<script lang="ts">
  import DescriptionField from './DescriptionField.svelte'
  import Help from './Help.svelte'
  import { api, itemIconUrl } from '../lib/api'
  import type { EditableList } from '../lib/history.svelte'
  import { t, problemText } from '../lib/i18n.svelte'
  import type { Character, ClassView, Item, Problem, Reference } from '../lib/types'
  import NumberField from './NumberField.svelte'
  import Mention from './Mention.svelte'
  import ReservationEditor from './ReservationEditor.svelte'
  import { followFocus, useNavigator } from '../lib/navigation.svelte'
  import RecordList from './RecordList.svelte'

  let {
    list,
    classes,
    characters,
    reference,
    problems,
  }: {
    list: EditableList<Item>
    classes: ClassView[]
    characters: Character[]
    reference: Reference
    problems: Problem[]
  } = $props()

  let selected = $state(0)
  followFocus('items', useNavigator(), () => list.records.map((i) => i.id), (i) => (selected = i))
  const it = $derived(list.records[selected])
  const mine = $derived(problems.filter((p) => p.kind === 'items' && p.id === it?.id))
  const problemIds = $derived(new Set(problems.filter((p) => p.kind === 'items' && p.severity === 'error').map((p) => p.id)))
  const magicRange = $derived(it?.range.max === 0)
  const MAGIC_TYPES = ['anima', 'light', 'dark']
  const PROPERTIES = ['magic', 'magicSword', 'brave', 'uncounterable', 'reverseTriangle', 'negateDefense', 'unbreakable', 'unsellable',
                      'noRepair', 'negateFlying', 'negateCrit']
  const BONUS_STATS = ['hp', 'pow', 'skl', 'spd', 'def', 'res', 'lck', 'mov', 'con']
  const EFFECTS = ['poison', 'drain', 'halve', 'devil', 'petrify']
  const isWeapon = $derived(!!it && !['staff', 'item', 'dance'].includes(it.weaponType))
  const usable = $derived(!!it && ['staff', 'item'].includes(it.weaponType))
  const ranked = $derived(!!it && reference.rankableTypes.includes(it.weaponType))
  const spells = $derived(reference.spellItems.filter((id) => {
    const source = list.records.find((r) => r.id === id)
    return source && id !== it?.id && reference.rankableTypes.includes(source.weaponType) && source.weaponType !== 'staff'
  }))

  function problemFor(field: string): string {
    const p = mine.find((x) => x.field === field || x.field.startsWith(field + '.'))
    return p ? problemText(p) : ''
  }

  function edit(change: (i: Item) => void) {
    list.update(selected, change)
  }

  /** A type comes with what the engine expects of it: a tome is magic, a sword is not. */
  function setType(type: string) {
    edit((i) => {
      i.weaponType = type
      i.properties = i.properties.filter((p) => p !== 'magic').concat(MAGIC_TYPES.includes(type) ? ['magic'] : [])
    })
  }

  function setProperty(key: string, on: boolean) {
    edit((i) => (i.properties = i.properties.filter((p) => p !== key).concat(on ? [key] : [])))
  }

  function setBonus(stat: string, value: number) {
    edit((i) => {
      const { [stat]: _old, ...others } = i.statBonuses ?? {}
      const bonuses = value ? { ...others, [stat]: value } : others
      i.statBonuses = Object.keys(bonuses).length ? bonuses : null
    })
  }

  /** Weapons can be copied into new ones (server: gamedata.new_item); consumables and staves act by item number. */
  const copiable = $derived(!!it && !it.model && reference.rankableTypes.includes(it.weaponType) && it.weaponType !== 'staff')
  let addError = $state('')

  async function addWeapon() {
    if (!it) return
    addError = ''
    try {
      const record = await api.newItem(it.id)
      record.name = t('item.copyName', { name: it.name })
      list.change((records) => [...records, record])
      selected = list.records.length - 1
    } catch (e) {
      addError = String(e).includes('noFreeItem') ? t('item.noFree') : String(e)
    }
  }

  function removeWeapon() {
    if (!it?.model || !confirm(t('item.removeConfirm', { name: it.name }))) return
    const id = it.id
    list.change((records) => records.filter((r) => r.id !== id))
    selected = Math.max(0, selected - 1)
  }
</script>

<div class="editor">
  <RecordList records={list.records} {selected} onselect={(i) => (selected = i)} {problemIds}>
    {#snippet icon(i: Item)}
      <img class="pixel mini" src={itemIconUrl(i.iconId)} alt="" loading="lazy" />
    {/snippet}
  </RecordList>

  {#if it}
    <div class="detail">
      <section class="panel identity">
        <img class="pixel icon" src={itemIconUrl(it.iconId)} alt={t('field.icon')} />
        <div class="fields">
          <label title={problemFor('name')}>
            {t('field.name')}
            <input value={it.name} class:invalid={!!problemFor('name')} oninput={(e) => edit((i) => (i.name = (e.target as HTMLInputElement).value))} />
          </label>
          <DescriptionField value={it.description ?? reference.descriptions.items[it.id] ?? reference.descriptions.items[it.model ?? ''] ?? ''}
                            onchange={(text) => edit((i) => (i.description = text))} />
          {#if usable}
            <DescriptionField label={t('item.useText')} value={it.useDescription ?? reference.descriptions.itemUses[it.id] ?? ''}
                              onchange={(text) => edit((i) => (i.useDescription = text))} />
          {/if}
          {#if it.model}
            <p class="muted small">
              {t('item.copyOf')} <Mention kind="items" id={it.model}>{list.records.find((r) => r.id === it.model)?.name ?? it.model}</Mention>
              <button class="link" onclick={removeWeapon}>{t('item.remove')}</button>
            </p>
          {:else if copiable}
            <p class="small">
              <button onclick={addWeapon} title={t('item.newFromHint')}>+ {t('item.newFrom')}</button>
              {#if addError}<span class="bad">{addError}</span>{/if}
            </p>
          {/if}
          <div class="row">
            <label>
              {t('field.weaponType')}
              <select value={it.weaponType} onchange={(e) => setType((e.target as HTMLSelectElement).value)}>
                {#each reference.weaponTypes as w (w)}<option value={w}>{t(`wtype.${w}`)}</option>{/each}
              </select>
            </label>
            <label>
              {t('field.rank')}
              <select
                value={String(it.weaponRank)}
                onchange={(e) => {
                  const v = (e.target as HTMLSelectElement).value
                  edit((i) => (i.weaponRank = v === '0' ? 0 : v))
                }}
              >
                <option value="0">{t('field.none')}</option>
                {#each reference.ranks as r (r)}<option value={r}>{r}</option>{/each}
                {#if typeof it.weaponRank === 'number' && it.weaponRank !== 0}
                  <option value={String(it.weaponRank)}>{it.weaponRank}</option>
                {/if}
              </select>
            </label>
            <NumberField label={t('field.icon')} value={it.iconId} min={0} max={reference.iconCount - 1} problem={problemFor('iconId')} onchange={(v) => edit((i) => (i.iconId = v))} />
          </div>
          <label class="eff">
            <span>{t('field.effectiveness')}{#if it.effectiveness} <Mention kind="combat"><span class="open">↗</span></Mention>{/if}</span>
            <select
              value={it.effectiveness ?? ''}
              onchange={(e) => {
                const v = (e.target as HTMLSelectElement).value
                edit((i) => (i.effectiveness = v || null))
              }}
            >
              <option value="">{t('field.none')}</option>
              {#each reference.effectivenessLists as name (name)}<option value={name}>{t(`effectiveness.${name}`)}</option>{/each}
            </select>
          </label>
          {#if isWeapon}
            <label class="eff">
              <span>{t('item.effect')} <Help text={t('item.effectHint')} /></span>
              <select value={it.weaponEffect ?? ''} onchange={(e) => edit((i) => (i.weaponEffect = (e.target as HTMLSelectElement).value || null))}>
                <option value="">{t('field.none')}</option>
                {#each EFFECTS as effect (effect)}<option value={effect}>{t(`item.effect.${effect}`)}</option>{/each}
              </select>
            </label>
          {/if}
          <label class="check" title={t('field.monsterWeaponHint')}>
            <input type="checkbox" checked={it.monsterWeapon} onchange={(e) => edit((i) => (i.monsterWeapon = (e.target as HTMLInputElement).checked))} />
            {t('field.monsterWeapon')}
          </label>
        </div>
      </section>

      <section class="panel">
        <div class="grid">
          <NumberField label={t('field.might')} value={it.might} min={0} max={255} problem={problemFor('might')} onchange={(v) => edit((i) => (i.might = v))} />
          <NumberField label={t('field.hit')} value={it.hit} min={0} max={255} problem={problemFor('hit')} onchange={(v) => edit((i) => (i.hit = v))} />
          <NumberField label={t('field.crit')} value={it.crit} min={0} max={255} problem={problemFor('crit')} onchange={(v) => edit((i) => (i.crit = v))} />
          <NumberField label={t('field.weight')} value={it.weight} min={0} max={255} problem={problemFor('weight')} onchange={(v) => edit((i) => (i.weight = v))} />
          <NumberField label={t('field.uses')} value={it.uses} min={0} max={255} problem={problemFor('uses')} onchange={(v) => edit((i) => (i.uses = v))} />
          {#if ranked}
            <NumberField label={t('item.weaponExp')} hint={t('item.weaponExpHint')} value={it.weaponExp} min={0} max={255} problem={problemFor('weaponExp')}
                         onchange={(v) => edit((i) => (i.weaponExp = v))} />
          {/if}
        </div>
      </section>

      <details class="panel fold" open={!!it.statBonuses}>
        <summary>{t('item.bonuses')} <Help text={t('item.bonusesHint')} /></summary>
        <div class="grid">
          {#each BONUS_STATS as stat (stat)}
            <NumberField label={t(`stat.${stat}`)} value={it.statBonuses?.[stat] ?? 0} min={-128} max={127} problem={problemFor(`statBonuses.${stat}`)}
                         onchange={(v) => setBonus(stat, v)} />
          {/each}
        </div>
      </details>

      <details class="panel fold">
        <summary>{t('item.properties')}</summary>
        <div class="properties">
          {#each PROPERTIES as key (key)}
            <label class="check">
              <input type="checkbox" checked={it.properties.includes(key)} onchange={(e) => setProperty(key, (e.target as HTMLInputElement).checked)} />
              <span>{t(`item.prop.${key}`)} <Help text={t(`item.prop.${key}Hint`)} /></span>
            </label>
          {/each}
        </div>
        {#if isWeapon}
          <label class="eff spell">
            <span>{t('item.spell')} <Help text={t('item.spellHint')} /></span>
            <select value={it.spellFrom ?? ''} onchange={(e) => edit((i) => (i.spellFrom = (e.target as HTMLSelectElement).value || undefined))}>
              <option value="">{t('item.spellOwn')}</option>
              {#each spells as id (id)}<option value={id}>{list.records.find((r) => r.id === id)?.name ?? id}</option>{/each}
            </select>
          </label>
        {/if}
      </details>

      <ReservationEditor item={it} {classes} {characters} onchange={(r) => edit((i) => (i.reservedFor = r))} />

      <section class="panel">
        <h3>{t('field.range')}</h3>
        <div class="row">
          <NumberField compact label={t('field.rangeMin')} value={it.range.min} min={0} max={15} problem={problemFor('range')} onchange={(v) => edit((i) => (i.range.min = v))} />
          {#if !magicRange}
            <NumberField compact label={t('field.rangeMax')} value={it.range.max} min={1} max={15} problem={problemFor('range')} onchange={(v) => edit((i) => (i.range.max = v))} />
          {/if}
          <label class="check">
            <input type="checkbox" checked={magicRange} onchange={(e) => edit((i) => (i.range.max = (e.target as HTMLInputElement).checked ? 0 : Math.max(1, i.range.min)))} />
            {t('field.rangeMagic')}
          </label>
        </div>
      </section>

      <section class="panel">
        <div class="row price">
          <NumberField label={t('field.pricePerUse')} value={it.pricePerUse} min={0} max={65535} problem={problemFor('pricePerUse')} onchange={(v) => edit((i) => (i.pricePerUse = v))} />
          <div class="total">
            <span class="muted">{t('field.priceTotal')}</span>
            <strong>{(it.uses > 0 ? it.pricePerUse * it.uses : it.pricePerUse).toLocaleString()} G</strong>
          </div>
        </div>
      </section>

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
  .identity { display: flex; gap: 1.25rem; align-items: flex-start; }
  .icon { width: 48px; height: 48px; background: var(--panel-2); border-radius: 6px; padding: 4px; box-sizing: content-box; flex-shrink: 0; }
  .mini { width: 16px; height: 16px; flex-shrink: 0; }
  .fields { display: flex; flex-direction: column; gap: 0.75rem; flex: 1; min-width: 0; }
  .grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(110px, 1fr)); gap: 0.75rem; }
  .check { flex-direction: row; align-items: center; gap: 0.4rem; }
  .properties { display: grid; grid-template-columns: repeat(auto-fill, minmax(220px, 1fr)); gap: 0.5rem 1rem; }
  .spell { display: block; margin-top: 0.75rem; max-width: 26rem; }
  .open { font-size: 1rem; }
  .price { align-items: flex-end; }
  .total { display: flex; flex-direction: column; gap: 0.25rem; font-size: 0.85rem; }
  .total strong { font-size: 1.2rem; }
  .lock { margin: 0; font-size: 0.85rem; color: var(--warn); }
  .issues p { margin: 0.2rem 0; }
  .error { color: var(--bad); }
  .warning { color: var(--warn); }
  @media (max-width: 800px) {
    .editor { grid-template-columns: 1fr; }
    .identity { flex-direction: column; }
  }
</style>
