<script lang="ts">
  // "Import…" of a character or class file made by "Export" in another project (server: packages.py): the sheets come
  // in as new ones, with their portrait, animations and map sprite; what could not follow is said under the button.
  import Help from './Help.svelte'
  import { ApiError } from '../lib/api'
  import { t } from '../lib/i18n.svelte'

  let { kind, onimport }: {
    kind: 'character' | 'class'
    /** the file chosen; returns the warnings (links left out) */
    onimport: (file: File) => Promise<string[]>
  } = $props()

  let input = $state<HTMLInputElement>()
  let busy = $state(false)
  let message = $state('')
  let bad = $state(false)

  async function chosen() {
    const file = input?.files?.[0]
    if (!file) return
    busy = true
    message = ''
    try {
      const warnings = await onimport(file)
      bad = false
      message = [t('package.imported'), ...warnings.map((w) => t(`package.warning.${w}`))].join(' ')
    } catch (e) {
      bad = true
      message = e instanceof ApiError ? t(`package.error.${e.detail}`) : String(e)
    } finally {
      busy = false
      if (input) input.value = ''
    }
  }
</script>

<button onclick={() => input?.click()} disabled={busy} title={t(`package.import.${kind}Hint`)}>{t(`package.import.${kind}`)}</button>
<Help text={t('package.importHint')} />
<input bind:this={input} type="file" accept=".femchar,.femclass" hidden onchange={chosen} />
{#if message}<p class="small" class:bad class:good={!bad}>{message}</p>{/if}

<style>
  .small { font-size: 0.8rem; margin: 0; }
  .bad { color: var(--bad); }
  .good { color: var(--good-text); }
</style>
