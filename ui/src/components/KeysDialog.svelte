<script lang="ts">
  import { api, ApiError } from '../lib/api'
  import { t } from '../lib/i18n.svelte'

  let { onClose }: { onClose: () => void } = $props()

  let buttons = $state<string[]>([])
  let keys = $state<Record<string, string>>({})
  let listening = $state<string | null>(null)
  let error = $state('')
  let saved = $state(false)

  api.status().then((s) => {
    buttons = s.gbaButtons
    keys = { ...s.keys }
  })

  const duplicates = $derived(
    new Set(Object.values(keys).filter((k, i, all) => all.indexOf(k) !== i)),
  )

  function keyName(e: KeyboardEvent): string {
    if (e.key === ' ') return 'Space'
    if (e.key.length === 1) return e.key.toUpperCase()
    return e.key
  }

  function label(name: string): string {
    const arrows: Record<string, string> = { ArrowUp: '↑', ArrowDown: '↓', ArrowLeft: '←', ArrowRight: '→' }
    if (arrows[name]) return arrows[name]
    if (name === 'Space') return t('keys.space')
    if (name === 'Enter') return t('keys.enter')
    return name
  }

  function capture(e: KeyboardEvent) {
    if (!listening) return
    e.preventDefault()
    e.stopPropagation()
    if (e.key !== 'Escape') keys[listening] = keyName(e)
    listening = null
    saved = false
  }

  async function save() {
    error = ''
    try {
      await api.updateSettings({ keys })
      saved = true
    } catch (e) {
      error = e instanceof ApiError ? e.detail : String(e)
    }
  }
</script>

<svelte:window onkeydown={capture} />

<div class="backdrop">
  <div class="panel dialog" role="dialog" aria-modal="true" aria-labelledby="keys-title">
    <h2 id="keys-title">{t('keys.title')}</h2>
    <p class="muted small">{t('keys.intro')}</p>
    <table>
      <tbody>
        {#each buttons as b (b)}
          <tr>
            <th>{t(`keys.button.${b}`)}</th>
            <td>
              <button class="key" class:listening={listening === b} class:dup={duplicates.has(keys[b])} onclick={() => (listening = b)}>
                {listening === b ? t('keys.press') : label(keys[b] ?? '')}
              </button>
            </td>
          </tr>
        {/each}
      </tbody>
    </table>
    {#if duplicates.size}<p class="bad small">{t('keys.duplicate')}</p>{/if}
    {#if error}<p class="bad small">{error}</p>{/if}
    {#if saved}<p class="good small">{t('keys.saved')}</p>{/if}
    <div class="actions">
      <button onclick={onClose}>{t('build.close')}</button>
      <button class="primary" onclick={save} disabled={duplicates.size > 0 || !!listening}>{t('keys.save')}</button>
    </div>
  </div>
</div>

<style>
  .backdrop { position: fixed; inset: 0; background: rgb(0 0 0 / 0.45); display: grid; place-items: center; padding: 1rem; z-index: 50; }
  .dialog { width: min(420px, 100%); max-height: 90vh; overflow: auto; }
  table { width: 100%; border-collapse: collapse; }
  th { text-align: left; font-weight: 500; padding: 0.25rem 0; }
  td { text-align: right; padding: 0.25rem 0; }
  .key { min-width: 7em; font-weight: 600; }
  .key.listening { border-color: var(--accent); background: var(--accent-soft); }
  .key.dup { border-color: var(--bad); color: var(--bad); }
  .small { font-size: 0.85rem; }
  .actions { display: flex; justify-content: flex-end; gap: 0.5rem; margin-top: 1rem; }
  .good { color: var(--good); }
  .bad { color: var(--bad); }
</style>
