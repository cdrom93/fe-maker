<script lang="ts">
  import type { EditableList } from '../lib/history.svelte'
  import { t } from '../lib/i18n.svelte'
  import type { ClassView, Combat, Problem, Reference } from '../lib/types'
  import GenderSign from './GenderSign.svelte'
  import Mention from './Mention.svelte'
  import NumberField from './NumberField.svelte'

  let {
    list,
    classes,
    reference,
    problems,
  }: { list: EditableList<Combat>; classes: ClassView[]; reference: Reference; problems: Problem[] } = $props()

  const combat = $derived(list.records[0])
  const TRIANGLE_TYPES = ['sword', 'lance', 'axe', 'bow', 'anima', 'light', 'dark']
  const SIGN = { male: ' ♂', female: ' ♀' } as const
  const classLabel = (k: ClassView) => `${k.name || k.id}${k.gender ? SIGN[k.gender] : ''}`
  const byId = $derived(new Map(classes.map((k) => [k.id, k])))
  const mine = $derived(problems.filter((p) => p.kind === 'combat'))

  let adding = $state<Record<string, string>>({})

  function edit(change: (c: Combat) => void) {
    list.update(0, change)
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
      <h3>{t('combat.triangle')}</h3>
      <p class="muted small">{t('combat.triangleHint')}</p>
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
    </section>

    <section class="panel">
      <h3>{t('combat.effectiveness')}</h3>
      <p class="muted small">{t('combat.effectivenessHint')}</p>
      <div class="lists">
        {#each reference.effectivenessLists as name (name)}
          <fieldset>
            <legend>{t(`effectiveness.${name}`)}</legend>
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
        {#each mine as p, i (i)}<p class={p.severity}>{p.id} {p.field}: {t(`problem.${p.code}`, p.params)}</p>{/each}
      </section>
    {/if}
  </div>
{/if}

<style>
  .combat { display: flex; flex-direction: column; gap: 1rem; }
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
  .issues p { margin: 0.2rem 0; }
  .error { color: var(--bad); }
  .warning { color: var(--warn); }
</style>
