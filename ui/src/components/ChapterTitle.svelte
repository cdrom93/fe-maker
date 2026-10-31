<script lang="ts">
  // A chapter's title: a click writes over it (Enter or leaving the field keeps it, Escape does not).
  import { tick } from 'svelte'
  import { t } from '../lib/i18n.svelte'

  let { title, value, onrename }: {
    /** what is shown */
    title: string
    /** what is edited: the title without what `title` adds to it */
    value: string
    onrename: (name: string) => void
  } = $props()

  let editing = $state(false)
  let field = $state<HTMLInputElement>()

  async function start() {
    editing = true
    await tick()
    field?.select()
  }

  function finish(keep: boolean) {
    if (!editing) return
    editing = false
    const name = field?.value.trim() ?? ''
    if (keep && name !== value) onrename(name)
  }
</script>

{#if editing}
  <input bind:this={field} class="title-input" {value} maxlength="40" aria-label={t('flow.add.title')} title={t('flow.renameHint')}
    onblur={() => finish(true)}
    onkeydown={(e) => { if (e.key === 'Enter') finish(true); if (e.key === 'Escape') finish(false) }} />
{:else}
  <button class="title-button" title={t('flow.rename')} onclick={start}>{title} <span class="pen" aria-hidden="true">✎</span></button>
{/if}

<style>
  .title-button { all: unset; cursor: text; border-radius: var(--radius); }
  .title-button:focus-visible { outline: 2px solid var(--accent); }
  .pen { font-size: 0.7em; opacity: 0; }
  .title-button:hover .pen, .title-button:focus-visible .pen { opacity: 0.6; }
  .title-input { font: inherit; width: min(100%, 22rem); }
</style>
