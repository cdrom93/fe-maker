<script lang="ts">
  // Options of the built game (server: decomp/gameoptions.py): the defaults of a new save's options (the player
  // can change them in the game's Options menu) and comfort changes taken from FEBuilderGBA's patches.
  import Help from './Help.svelte'
  import { api } from '../lib/api'
  import { projectView } from '../lib/appContext.svelte'
  import { magicSplit } from '../lib/magic.svelte'
  import { skillsOption } from '../lib/skills.svelte'
  import { t } from '../lib/i18n.svelte'
  import ProjectScope from './ProjectScope.svelte'

  type Reference = { options: Record<string, number | boolean | string>; groups: Record<string, string[]>; choices: Record<string, string[]>; defaults: Record<string, { game: number; values: number[] }> }

  let { onteststart, onscope, scopeFirst = false }: {
    /** where test builds now start */
    onteststart: (start: string) => void
    /** the project's lists changed */
    onscope: () => void
    /** a project just created blank starts with what it keeps */
    scopeFirst?: boolean
  } = $props()

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

  async function set(key: string, value: number | boolean | string) {
    if (!data) return
    saving = true
    error = ''
    try {
      data = await api.setGameOptions({ [key]: value })   // only the change: the server keeps the rest
      magicSplit.on = !!data.options.strMagSplit
      skillsOption.on = !!data.options.skills
    } catch (e) {
      error = String(e)
    } finally {
      saving = false
    }
  }

  async function setShowOriginal(show: boolean) {
    try {
      await api.setShowOriginal(show)
      projectView.showOriginal = show
    } catch (e) {
      error = String(e)
    }
  }

  const value = (key: string) => (data?.options[key] ?? data?.defaults[key]?.game) as number
</script>

<div class="options">
  {#if error}<p class="bad small">{error}</p>{/if}
  <!-- FE Maker's own settings, by category like the game options below (ticket 168) -->
  <section class="panel">
    <h3>{t('options.editorTitle')} <Help text={t('options.editorHint')} /></h3>
    <h4>{t('options.group.interface')}</h4>
    <label class="switch">
      <input type="checkbox" checked={projectView.showOriginal} onchange={(e) => setShowOriginal((e.target as HTMLInputElement).checked)} />
      <span><strong>{t('options.showOriginal')}</strong> <Help text={t('options.showOriginalHint')} /></span>
    </label>
    {#if test}
      <h4>{t('options.testTitle')}</h4>
      <label class="switch">
        <span><strong>{t('options.testStart')}</strong> <Help text={t('ws.startHint')} /></span>
        <select value={test.start} onchange={(e) => setTest({ start: (e.target as HTMLSelectElement).value })}>
          <option value="map">{t('ws.start.map')}</option>
          <option value="menu">{t('ws.start.menu')}</option>
          <option value="normal">{t('ws.start.normal')}</option>
        </select>
      </label>
      <label class="switch">
        <input type="checkbox" checked={test.simplePrologue} onchange={(e) => setTest({ simplePrologue: (e.target as HTMLInputElement).checked })} />
        <span><strong>{t('ws.simplePrologue')}</strong> <Help text={t('ws.simplePrologueHint')} /></span>
      </label>
    {/if}
  </section>
  {#if scopeFirst}<ProjectScope onchanged={onscope} />{/if}
  {#if data}
    <section class="panel">
      <h3>{t('options.defaultsTitle')} <Help text={`${t('options.defaultsHint')} ${t('options.gameDefaultHint')}`} /></h3>
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
    </section>

    <section class="panel">
      <h3>{t('options.comfortTitle')} <Help text={t('options.comfortHint')} /></h3>
      {#each Object.entries(data.groups) as [group, keys] (group)}
        <h4>{t(`options.group.${group}`)}</h4>
        {#each keys as key (key)}
          {#if data.choices[key]}
            <label class="switch">
              <span><strong>{t(`options.${key}`)}</strong> <Help text={t(`options.${key}Hint`)} /></span>
              <select value={data.options[key] ?? data.choices[key][0]} disabled={saving}
                      onchange={(e) => set(key, (e.target as HTMLSelectElement).value)}>
                {#each data.choices[key] as choice (choice)}<option value={choice}>{t(`options.${key}.${choice}`)}</option>{/each}
              </select>
            </label>
          {:else}
          <label class="switch">
            <input type="checkbox" checked={!!data.options[key]} disabled={saving} onchange={(e) => set(key, (e.target as HTMLInputElement).checked)} />
            <span><strong>{t(`options.${key}`)}</strong> <Help text={t(`options.${key}Hint`)} /></span>
          </label>
          {/if}
        {/each}
      {/each}
    </section>
  {/if}
  {#if !scopeFirst}<ProjectScope onchanged={onscope} />{/if}
</div>

<style>
  .options { display: flex; flex-direction: column; gap: 1rem; max-width: 60rem; }
  .switch { display: flex; flex-direction: row; gap: 0.5rem; align-items: flex-start; padding: 0.35rem 0; }
  .switch input { margin-top: 0.2rem; }
  h4 { margin: 0.8rem 0 0.1rem; font-size: 0.85rem; color: var(--muted); }
  h3 + h4 { margin-top: 0.3rem; }
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
