<script lang="ts">
  // A button opening the system's folder picker (the local server shows it: /api/pick-folder), so that no path is typed.
  import { api, ApiError } from '../lib/api'
  import { t } from '../lib/i18n.svelte'

  let { label = t('file.browse'), title = t('file.pickFolder'), initial, disabled = false, primary = false, onpick }: {
    label?: string
    /** the picker window's title */
    title?: string
    initial?: string
    disabled?: boolean
    primary?: boolean
    onpick: (path: string) => void
  } = $props()

  let busy = $state(false)
  let error = $state('')

  async function pick() {
    busy = true
    error = ''
    try {
      const { path } = await api.pickFolder(title, initial)
      if (path) onpick(path)
    } catch (e) {
      error = e instanceof ApiError && e.detail === 'pickerUnavailable' ? t('file.pickerUnavailable') : String(e)
    } finally {
      busy = false
    }
  }
</script>

<button type="button" class:primary disabled={disabled || busy} onclick={pick}>{label}</button>
{#if error}<span class="error">{error}</span>{/if}

<style>
  .error { color: var(--bad); font-size: 0.85rem; }
</style>
