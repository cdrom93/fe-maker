<script lang="ts">
  import { AI_ACTION_COUNT as ACTION_COUNT, AI_GUARD_TILE as GUARD_TILE, AI_MOVE_COUNT as MOVE_COUNT, AI_NAMED_TARGETS as NAMED_TARGETS,
    AI_PRESETS as PRESETS, AI_RECOVERY_COUNT as RECOVERY_COUNT, AI_TARGET_COUNT as TARGET_COUNT, aiPreset } from '../lib/ai'
  import { t } from '../lib/i18n.svelte'

  /** The 4 AI bytes of a unit (src/cp_data.c): action, movement, target/recovery settings, flags. */
  let { ai, side, onchange }: { ai: number[] | string; side: string; onchange: (ai: number[]) => void } = $props()

  // Projects saved before the AI was editable keep the original text until the AI is edited.
  const bytes = $derived(Array.isArray(ai) ? ai : null)
  const preset = $derived(aiPreset(ai))
  let open = $state(false)

  function set(change: (b: number[]) => void) {
    const next = [...(bytes ?? [0, 0, 0, 0])]
    change(next)
    onchange(next)
  }

  const hex = (n: number) => n.toString(16).toUpperCase().padStart(2, '0')
  const targetLabel = (n: number) => (n < NAMED_TARGETS ? t(`ai.target.${n}`) : t('ai.targetN', { n }))
</script>

<h3>{t('ai.title')}</h3>
{#if side === 'player'}<p class="muted small">{t('ai.playerHint')}</p>{/if}
{#if bytes}
  <label>
    <span>{t('ai.preset')}</span>
    <select
      value={preset}
      onchange={(e) => {
        const p = PRESETS.find(([key]) => key === (e.target as HTMLSelectElement).value)
        if (p) set((b) => ((b[0] = p[1]), (b[1] = p[2])))
      }}
    >
      {#each PRESETS as [key] (key)}<option value={key}>{t(`ai.preset.${key}`)}</option>{/each}
      {#if preset === 'custom'}<option value="custom">{t('ai.preset.custom')}</option>{/if}
    </select>
  </label>
  <label class="check">
    <input type="checkbox" checked={(bytes[3] & GUARD_TILE) !== 0} onchange={(e) => set((b) => (b[3] = (e.target as HTMLInputElement).checked ? b[3] | GUARD_TILE : b[3] & ~GUARD_TILE))} />
    {t('ai.guardTile')}
  </label>
  <details bind:open>
    <summary>{t('ai.details')}</summary>
    <label>
      <span>{t('ai.action')}</span>
      <select value={bytes[0]} onchange={(e) => set((b) => (b[0] = Number((e.target as HTMLSelectElement).value)))}>
        {#each Array(ACTION_COUNT) as _, i (i)}<option value={i}>{hex(i)} · {t(`ai.action.${i}`)}</option>{/each}
        {#if bytes[0] >= ACTION_COUNT}<option value={bytes[0]}>{hex(bytes[0])} · ?</option>{/if}
      </select>
    </label>
    <label>
      <span>{t('ai.move')}</span>
      <select value={bytes[1]} onchange={(e) => set((b) => (b[1] = Number((e.target as HTMLSelectElement).value)))}>
        {#each Array(MOVE_COUNT) as _, i (i)}<option value={i}>{hex(i)} · {t(`ai.move.${i}`)}</option>{/each}
        {#if bytes[1] >= MOVE_COUNT}<option value={bytes[1]}>{hex(bytes[1])} · ?</option>{/if}
      </select>
    </label>
    <label>
      <span>{t('ai.target')}</span>
      <select value={bytes[2] >> 3} onchange={(e) => set((b) => (b[2] = (Number((e.target as HTMLSelectElement).value) << 3) | (b[2] & 0x7)))}>
        {#each Array(TARGET_COUNT) as _, i (i)}<option value={i}>{targetLabel(i)}</option>{/each}
      </select>
    </label>
    <label>
      <span>{t('ai.recovery')}</span>
      <select value={bytes[2] & 0x7} onchange={(e) => set((b) => (b[2] = (b[2] & ~0x7) | Number((e.target as HTMLSelectElement).value)))}>
        {#each Array(RECOVERY_COUNT) as _, i (i)}<option value={i}>{t(`ai.recovery.${i}`)}</option>{/each}
        {#if (bytes[2] & 0x7) >= RECOVERY_COUNT}<option value={bytes[2] & 0x7}>{bytes[2] & 0x7} · ?</option>{/if}
      </select>
    </label>
    <p class="muted tiny">{bytes.map(hex).join(' ')}</p>
  </details>
{:else}
  <p class="muted small">{t('ai.legacy')} : <code>{ai}</code></p>
{/if}

<style>
  h3 { margin: 0.5rem 0 0; }
  .check { flex-direction: row; align-items: center; gap: 0.35rem; font-size: 0.85rem; color: var(--text); }
  details { display: flex; flex-direction: column; gap: 0.5rem; }
  details[open] > summary { margin-bottom: 0.4rem; }
  details label + label { margin-top: 0.4rem; }
  summary { cursor: pointer; font-size: 0.85rem; color: var(--muted); }
  select { width: 100%; }
  .small { font-size: 0.8rem; margin: 0; }
  .tiny { font-size: 0.72rem; margin: 0.3rem 0 0; }
</style>
