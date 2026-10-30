<script lang="ts">
  import Help from './Help.svelte'
  import type { EditableList } from '../lib/history.svelte'
  import { t, problemText } from '../lib/i18n.svelte'
  import type { ClassView, Combat, Item, Problem, Reference } from '../lib/types'
  import GenderSign from './GenderSign.svelte'
  import Mention from './Mention.svelte'
  import NumberField from './NumberField.svelte'
  import TriangleDiagram from './TriangleDiagram.svelte'

  let {
    list,
    classes,
    items,
    reference,
    problems,
  }: { list: EditableList<Combat>; classes: ClassView[]; items: Item[]; reference: Reference; problems: Problem[] } = $props()

  const combat = $derived(list.records[0])
  const TRIANGLE_TYPES = ['sword', 'lance', 'axe', 'bow', 'anima', 'light', 'dark']
  const SIGN = { male: ' ♂', female: ' ♀' } as const
  const classLabel = (k: ClassView) => `${k.name || k.id}${k.gender ? SIGN[k.gender] : ''}`
  const byId = $derived(new Map(classes.map((k) => [k.id, k])))
  const mine = $derived(problems.filter((p) => p.kind === 'combat'))
  /** Weapons using each effectiveness list. */
  const usedBy = $derived.by(() => {
    const out = new Map<string, Item[]>()
    for (const it of items) if (it.effectiveness) out.set(it.effectiveness, [...(out.get(it.effectiveness) ?? []), it])
    return out
  })

  let adding = $state<Record<string, string>>({})

  function edit(change: (c: Combat) => void) {
    list.update(0, change)
  }

  // Each type beats the next one; colours of the game's weapon triangle.
  const PHYSICAL = [['sword', '#d23c3c', 'ITEM_SWORD_IRON'], ['axe', '#2f9a52', 'ITEM_AXE_IRON'], ['lance', '#2f78cf', 'ITEM_LANCE_IRON']] as const
  const MAGIC = [['anima', '#e0782a', 'ITEM_ANIMA_FIRE'], ['light', '#d9b52c', 'ITEM_LIGHT_LIGHTNING'], ['dark', '#7a4bb5', 'ITEM_DARK_FLUX']] as const
  const iconOf = (id: string) => items.find((it) => it.id === id)?.iconId
  const toTypes = (spec: typeof PHYSICAL | typeof MAGIC) => spec.map(([id, color, item]) => ({ id, color, iconId: iconOf(item) }))

  /** Bonus of attacker against defender, read from either rule of the pair. */
  function advantage(attacker: string, defender: string) {
    const direct = combat?.triangle.find((r) => r.attacker === attacker && r.defender === defender)
    if (direct) return { hit: direct.hit, damage: direct.damage }
    const reverse = combat?.triangle.find((r) => r.attacker === defender && r.defender === attacker)
    return reverse ? { hit: -reverse.hit, damage: -reverse.damage } : { hit: 0, damage: 0 }
  }

  /** Set the bonus of a pair: the reverse rule gets the opposite values. */
  function setAdvantage(attacker: string, defender: string, hit: number, damage: number) {
    edit((c) => {
      for (const [a, d, h, dm] of [[attacker, defender, hit, damage], [defender, attacker, -hit, -damage]] as const) {
        const rule = c.triangle.find((r) => r.attacker === a && r.defender === d)
        if (rule) Object.assign(rule, { hit: h, damage: dm })
        else c.triangle.push({ attacker: a, defender: d, hit: h, damage: dm })
      }
    })
  }

  function addRule() {
    edit((c) => c.triangle.push({ attacker: 'sword', defender: 'axe', hit: 15, damage: 1 }))
  }

  function addClass(listName: string) {
    const id = adding[listName]
    if (!id) return
    edit((c) => {
      if (!c.effectiveness[listName].includes(id)) c.effectiveness[listName].push(id)
    })
    adding[listName] = ''
  }
</script>

{#if combat}
  <div class="combat">
    <section class="panel">
      <h3>{t('combat.triangle')} <Help text={t('combat.triangleVisualHint')} /></h3>
      <div class="triangles">
        <TriangleDiagram title={t('combat.weapons')} types={toTypes(PHYSICAL)} {advantage} onchange={setAdvantage} />
        <TriangleDiagram title={t('combat.magic')} types={toTypes(MAGIC)} {advantage} onchange={setAdvantage} />
      </div>
      <details class="advanced">
      <summary>{t('combat.allRules')} <Help text={t('combat.triangleHint')} /></summary>
      <div class="table-wrap">
        <table>
          <thead>
            <tr><th>{t('combat.attacker')}</th><th>{t('combat.defender')}</th><th>{t('field.hit')}</th><th>{t('combat.damage')}</th><th></th></tr>
          </thead>
          <tbody>
            {#each combat.triangle as rule, i (i)}
              <tr>
                <td>
                  <select value={rule.attacker} onchange={(e) => edit((c) => (c.triangle[i].attacker = (e.target as HTMLSelectElement).value))}>
                    {#each TRIANGLE_TYPES as w (w)}<option value={w}>{t(`wtype.${w}`)}</option>{/each}
                  </select>
                </td>
                <td>
                  <select value={rule.defender} onchange={(e) => edit((c) => (c.triangle[i].defender = (e.target as HTMLSelectElement).value))}>
                    {#each TRIANGLE_TYPES as w (w)}<option value={w}>{t(`wtype.${w}`)}</option>{/each}
                  </select>
                </td>
                <td><NumberField compact label="" value={rule.hit} min={-128} max={127} onchange={(v) => edit((c) => (c.triangle[i].hit = v))} /></td>
                <td><NumberField compact label="" value={rule.damage} min={-128} max={127} onchange={(v) => edit((c) => (c.triangle[i].damage = v))} /></td>
                <td><button class="icon" title={t('combat.remove')} onclick={() => edit((c) => c.triangle.splice(i, 1))}>✕</button></td>
              </tr>
            {/each}
          </tbody>
        </table>
      </div>
      <button onclick={addRule}>+ {t('combat.addRule')}</button>
      </details>
    </section>

    <section class="panel">
      <h3>{t('combat.effectiveness')} <Help text={t('combat.effectivenessHint')} /></h3>
      <div class="lists">
        {#each reference.effectivenessLists as name (name)}
          <fieldset>
            <legend>{t(`effectiveness.${name}`)}</legend>
            <p class="used small">
              {#if usedBy.get(name)?.length}
                {t('combat.usedBy')}
                {#each usedBy.get(name) ?? [] as it, k (it.id)}{#if k}{', '}{/if}<Mention kind="items" id={it.id}>{it.name || it.id}</Mention>{/each}
              {:else}
                <span class="muted">{t('combat.usedByNone')}</span>
              {/if}
            </p>
            <div class="chips">
              {#each combat.effectiveness[name] ?? [] as id, j (j)}
                <span class="chip">
                  <Mention kind="classes" {id}>{byId.get(id)?.name || id}<GenderSign gender={byId.get(id)?.gender} /></Mention>
                  <button class="icon" title={t('combat.remove')} onclick={() => edit((c) => c.effectiveness[name].splice(j, 1))}>✕</button>
                </span>
              {/each}
            </div>
            <div class="row add">
              <select bind:value={adding[name]} aria-label={t('combat.addClass')}>
                <option value="">{t('combat.addClass')}</option>
                {#each classes.filter((k) => k.usedInGame && !(combat.effectiveness[name] ?? []).includes(k.id)) as k (k.id)}
                  <option value={k.id} class={k.gender ?? ''}>{classLabel(k)}</option>
                {/each}
              </select>
              <button onclick={() => addClass(name)} disabled={!adding[name]}>+</button>
            </div>
          </fieldset>
        {/each}
      </div>
    </section>

    {#if mine.length}
      <section class="panel issues">
        {#each mine as p, i (i)}<p class={p.severity}>{p.id} {p.field}: {problemText(p)}</p>{/each}
      </section>
    {/if}
  </div>
{/if}

<style>
  .combat { display: flex; flex-direction: column; gap: 1rem; }
  .triangles { display: flex; flex-wrap: wrap; gap: 1.5rem 3rem; justify-content: center; margin: 0.5rem 0 1rem; }
  .advanced summary { cursor: pointer; color: var(--muted); font-size: 0.85rem; margin-bottom: 0.5rem; }
  .table-wrap { overflow-x: auto; margin-bottom: 0.5rem; }
  table { border-collapse: collapse; }
  th, td { padding: 0.2rem 0.4rem; text-align: left; }
  thead th { font-size: 0.8rem; color: var(--muted); font-weight: 600; }
  .icon { border: none; background: none; padding: 0 0.3rem; color: var(--muted); }
  .icon:hover { color: var(--bad); }
  .lists { display: grid; grid-template-columns: repeat(auto-fill, minmax(280px, 1fr)); gap: 0.75rem; }
  fieldset { border: 1px solid var(--border); border-radius: var(--radius); padding: 0.5rem 0.75rem; margin: 0; }
  legend { font-size: 0.85rem; padding: 0 0.25rem; }
  .chips { display: flex; flex-wrap: wrap; gap: 0.3rem; margin-bottom: 0.5rem; }
  .chip { display: inline-flex; align-items: center; gap: 0.1rem; background: var(--panel-2); border: 1px solid var(--border); border-radius: 999px; padding: 0.1rem 0.2rem 0.1rem 0.6rem; font-size: 0.8rem; }
  .add select { flex: 1; }
  .small { font-size: 0.8rem; margin: 0 0 0.5rem; }
  .used { line-height: 1.5; }
  .issues p { margin: 0.2rem 0; }
  .error { color: var(--bad); }
  .warning { color: var(--warn); }
</style>
