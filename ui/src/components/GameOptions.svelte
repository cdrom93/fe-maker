<script lang="ts">
  // Options of the built game (server: decomp/gameoptions.py): the defaults of a new save's options (the player
  // can change them in the game's Options menu) and comfort changes taken from FEBuilderGBA's patches.
  import { api } from '../lib/api'
  import { t } from '../lib/i18n.svelte'

  type Reference = { options: Record<string, number | boolean>; switches: string[]; defaults: Record<string, { game: number; values: number[] }> }

  let { onteststart }: { /** where test builds now start */ onteststart: (start: string) => void } = $props()

  let data = $state<Reference | null>(null)
  let test = $state<{ start: string; simplePrologue: boolean } | null>(null)
  let error = $state('')
  let saving = $state(false)

  $effect(() => {
    api.gameOptions().then((d) => (data = d)).catch((e) => (error = String(e)))
    api.testOptions().then((o) => (test = o)).catch((e) => (error = String(e)))
  })

  async function setTest(change: { start?: string; simplePrologue?: boolean }) {
    error = ''
    try {
      test = await api.setTestOptions(change)
      onteststart(test.start)
    } catch (e) {
      error = String(e)
    }
  }

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
  {#if test}
    <section class="panel">
      <h3>{t('options.testTitle')}</h3>
      <p class="muted small">{t('ws.startHint')}</p>
      <div class="grid">
        <label>
          <span>{t('ws.start')}</span>
          <select value={test.start} onchange={(e) => setTest({ start: (e.target as HTMLSelectElement).value })}>
            <option value="map">{t('ws.start.map')}</option>
            <option value="menu">{t('ws.start.menu')}</option>
            <option value="normal">{t('ws.start.normal')}</option>
          </select>
        </label>
      </div>
      <label class="switch" title={t('ws.simplePrologueHint')}>
        <input type="checkbox" checked={test.simplePrologue} onchange={(e) => setTest({ simplePrologue: (e.target as HTMLInputElement).checked })} />
        <span><strong>{t('ws.simplePrologue')}</strong> <span class="muted small">{t('ws.simplePrologueHint')}</span></span>
      </label>
    </section>
  {/if}
  {#if data}
    <section class="panel">
      <h3>{t('options.defaultsTitle')}</h3>
      <p class="muted small">{t('options.defaultsHint')}</p>
      <div class="config">
        {#each Object.entries(data.defaults) as [key, d] (key)}
          <span class="option">{t(`options.${key}`)}</span>
          <div class="choices" role="radiogroup" aria-label={t(`options.${key}`)}>
            {#each d.values as v (v)}
              <button role="radio" aria-checked={value(key) === v} class:on={value(key) === v} disabled={saving}
                      title={v === d.game ? t('options.gameDefault') : undefined} onclick={() => set(key, v)}>
                {t(`options.${key}.${v}`)}{#if v === d.game}<span class="game" aria-hidden="true">•</span>{/if}
              </button>
            {/each}
          </div>
        {/each}
      </div>
      <p class="muted small">{t('options.gameDefaultHint')}</p>
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
  .switch { display: flex; flex-direction: row; gap: 0.5rem; align-items: flex-start; padding: 0.35rem 0; }
  .switch input { margin-top: 0.2rem; }
  /* Laid out like the game's Configuration menu: the option, then its choices in a row. */
  .config { display: grid; grid-template-columns: minmax(11rem, max-content) 1fr; gap: 0.35rem 1.25rem; align-items: center; }
  .option { font-weight: 700; }
  .choices { display: flex; flex-wrap: wrap; gap: 0.3rem; }
  .choices button { padding: 0.25rem 0.7rem; font-weight: 600; color: var(--muted); }
  .choices button.on { background: var(--accent-soft); border-color: var(--accent); color: var(--text); font-weight: 800; }
  .game { margin-left: 0.3rem; color: var(--accent); }
  @media (max-width: 600px) { .config { grid-template-columns: 1fr; } }
  .small { font-size: 0.8rem; }
  .bad { color: var(--bad); }
</style>
