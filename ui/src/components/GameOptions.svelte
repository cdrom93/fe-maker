<script lang="ts">
  // Options of the built game (server: decomp/gameoptions.py): the defaults of a new save's options (the player
  // can change them in the game's Options menu) and comfort changes taken from FEBuilderGBA's patches.
  import { api } from '../lib/api'
  import { t } from '../lib/i18n.svelte'

  type Reference = { options: Record<string, number | boolean>; switches: string[]; defaults: Record<string, { game: number; values: number[] }> }

  let data = $state<Reference | null>(null)
  let error = $state('')
  let saving = $state(false)

  $effect(() => {
    api.gameOptions().then((d) => (data = d)).catch((e) => (error = String(e)))
  })

  async function set(key: string, value: number | boolean) {
    if (!data) return
    saving = true
    error = ''
    try {
      data = await api.setGameOptions({ ...data.options, [key]: value })
    } catch (e) {
      error = String(e)
    } finally {
      saving = false
    }
  }

  const value = (key: string) => (data?.options[key] ?? data?.defaults[key]?.game) as number
</script>

<div class="options">
  {#if error}<p class="bad small">{error}</p>{/if}
  {#if data}
    <section class="panel">
      <h3>{t('options.defaultsTitle')}</h3>
      <p class="muted small">{t('options.defaultsHint')}</p>
      <div class="grid">
        {#each Object.entries(data.defaults) as [key, d] (key)}
          <label>
            <span>{t(`options.${key}`)}</span>
            <select value={value(key)} disabled={saving} onchange={(e) => set(key, Number((e.target as HTMLSelectElement).value))}>
              {#each d.values as v (v)}
                <option value={v}>{t(`options.${key}.${v}`)}{v === d.game ? ` (${t('options.gameDefault')})` : ''}</option>
              {/each}
            </select>
          </label>
        {/each}
      </div>
    </section>

    <section class="panel">
      <h3>{t('options.comfortTitle')}</h3>
      <p class="muted small">{t('options.comfortHint')}</p>
      {#each data.switches as key (key)}
        <label class="switch">
          <input type="checkbox" checked={!!data.options[key]} disabled={saving} onchange={(e) => set(key, (e.target as HTMLInputElement).checked)} />
          <span><strong>{t(`options.${key}`)}</strong> <span class="muted small">{t(`options.${key}Hint`)}</span></span>
        </label>
      {/each}
    </section>
  {/if}
</div>

<style>
  .options { display: flex; flex-direction: column; gap: 1rem; max-width: 60rem; }
  .grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(14rem, 1fr)); gap: 0.75rem; }
  .grid label { display: flex; flex-direction: column; gap: 0.2rem; font-size: 0.9rem; }
  .switch { display: flex; gap: 0.5rem; align-items: flex-start; padding: 0.35rem 0; }
  .small { font-size: 0.8rem; }
  .bad { color: var(--bad); }
</style>
