<script lang="ts">
  // Options of the built game (server: decomp/gameoptions.py): the defaults of a new save's options (the player
  // can change them in the game's Options menu) and comfort changes taken from FEBuilderGBA's patches.
  import Help from './Help.svelte'
  import { api } from '../lib/api'
  import { magicSplit } from '../lib/magic.svelte'
  import { skillsOption } from '../lib/skills.svelte'
  import { t } from '../lib/i18n.svelte'
  import ProjectScope from './ProjectScope.svelte'

  type Reference = { options: Record<string, number | boolean | string>; groups: Record<string, string[]>; choices: Record<string, string[]>; defaults: Record<string, { game: number; values: number[] }> }

  // FE Maker's own settings (show original, tests) are in File > Options (ProjectSettings.svelte).
  let { onscope, scopeFirst = false }: {
    /** the project's lists changed */
    onscope: () => void
    /** a project just created blank starts with what it keeps */
    scopeFirst?: boolean
  } = $props()

  let data = $state<Reference | null>(null)
  let error = $state('')
  let saving = $state(false)

  $effect(() => {
    api.gameOptions().then((d) => (data = d)).catch((e) => (error = String(e)))
  })

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

  const value = (key: string) => (data?.options[key] ?? data?.defaults[key]?.game) as number
</script>

<div class="options">
  {#if error}<p class="bad small">{error}</p>{/if}
  {#if scopeFirst}<ProjectScope onchanged={onscope} />{/if}
  {#if data}
    <section class="panel">
      <h3>{t('options.defaultsTitle')} <Help text={`${t('options.defaultsHint')} ${t('options.gameDefaultHint')}`} /></h3>
      <div class="config">
        {#each Object.entries(data.defaults).filter(([key]) => key !== 'staffDance' || data?.options.noSupportAnimations) as [key, d] (key)}
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
