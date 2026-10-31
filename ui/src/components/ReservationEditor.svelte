<script lang="ts">
  import Help from './Help.svelte'
  import { t } from '../lib/i18n.svelte'
  import type { Character, ClassView, Item } from '../lib/types'
  import GenderSign from './GenderSign.svelte'
  import Mention from './Mention.svelte'

  let {
    item,
    classes,
    characters,
    onchange,
  }: {
    item: Item
    classes: ClassView[]
    characters: Character[]
    onchange: (reservedFor: Item['reservedFor']) => void
  } = $props()

  const res = $derived(item.reservedFor)
  const byClass = $derived(new Map(classes.map((k) => [k.id, k])))
  const byChar = $derived(new Map(characters.map((c) => [c.id, c])))
  let addClass = $state('')
  let addChar = $state('')

  function update(change: (r: { characters: string[]; classes: string[] }) => void) {
    const next = { characters: [...(res?.characters ?? [])], classes: [...(res?.classes ?? [])] }
    change(next)
    onchange(next)
  }
</script>

<section class="panel">
  <h3>{t('reserve.title')}{#if res} <Help text={t('reserve.hint')} />{/if}</h3>
  <label class="check">
    <input type="checkbox" checked={res !== null} onchange={(e) => onchange((e.target as HTMLInputElement).checked ? { characters: [], classes: [] } : null)} />
    {t('reserve.toggle')}
  </label>
  {#if res}
    {#if !res.characters.length && !res.classes.length}<p class="warn small">{t('reserve.empty')}</p>{/if}
    <div class="cols">
      <div>
        <h4>{t('reserve.characters')}</h4>
        <div class="chips">
          {#each res.characters as id (id)}
            <span class="chip"><Mention kind="characters" {id}>{byChar.get(id)?.name || id}</Mention><button class="icon" title={t('combat.remove')} onclick={() => update((r) => (r.characters = r.characters.filter((x) => x !== id)))}>✕</button></span>
          {:else}<span class="muted small">{t('field.none')}</span>{/each}
        </div>
        <div class="row add">
          <select bind:value={addChar} aria-label={t('reserve.addCharacter')}>
            <option value="">{t('reserve.addCharacter')}</option>
            {#each characters.filter((c) => c.id.startsWith('CHARACTER_') && !res.characters.includes(c.id)) as c (c.id)}
              <option value={c.id}>{c.name || c.id}</option>
            {/each}
          </select>
          <button disabled={!addChar} onclick={() => { update((r) => r.characters.push(addChar)); addChar = '' }}>+</button>
        </div>
      </div>
      <div>
        <h4>{t('reserve.classes')}</h4>
        <div class="chips">
          {#each res.classes as id (id)}
            <span class="chip"><Mention kind="classes" {id}>{byClass.get(id)?.name || id}<GenderSign gender={byClass.get(id)?.gender} /></Mention><button class="icon" title={t('combat.remove')} onclick={() => update((r) => (r.classes = r.classes.filter((x) => x !== id)))}>✕</button></span>
          {:else}<span class="muted small">{t('field.none')}</span>{/each}
        </div>
        <div class="row add">
          <select bind:value={addClass} aria-label={t('reserve.addClass')}>
            <option value="">{t('reserve.addClass')}</option>
            {#each classes.filter((k) => k.usedInGame && !res.classes.includes(k.id)) as k (k.id)}
              <option value={k.id} class={k.gender ?? ''}>{k.name || k.id}{k.gender === 'male' ? ' ♂' : k.gender === 'female' ? ' ♀' : ''}</option>
            {/each}
          </select>
          <button disabled={!addClass} onclick={() => { update((r) => r.classes.push(addClass)); addClass = '' }}>+</button>
        </div>
      </div>
    </div>
  {/if}
</section>

<style>
  .warn { color: var(--warn); margin: 0; }
  .check { flex-direction: row; align-items: center; gap: 0.4rem; color: var(--text); }
  .cols { display: grid; grid-template-columns: repeat(auto-fit, minmax(240px, 1fr)); gap: 1rem; }
  h4 { margin: 0 0 0.4rem; font-size: 0.85rem; font-weight: 600; }
  .chips { display: flex; flex-wrap: wrap; gap: 0.3rem; margin-bottom: 0.5rem; }
  .chip { display: inline-flex; align-items: center; gap: 0.1rem; background: var(--panel-2); border: 1px solid var(--border); border-radius: 999px; padding: 0.1rem 0.2rem 0.1rem 0.6rem; font-size: 0.8rem; }
  .icon { border: none; background: none; padding: 0 0.3rem; color: var(--muted); }
  .icon:hover { color: var(--bad); }
  .add select { flex: 1; min-width: 0; }
  .small { font-size: 0.8rem; margin: 0.4rem 0; }
</style>
