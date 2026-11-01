<script lang="ts">
  // The help text the game shows with R: two short lines.
  import { t } from '../lib/i18n.svelte'

  let { value, label, onchange }: { value: string; label?: string; onchange: (text: string) => void } = $props()
  const LINE = 32
  const tooLong = $derived(value.split('\n').length > 2 || value.split('\n').some((l) => l.length > LINE))
</script>

<label class="description">
  {label ?? t('field.description')}
  <textarea rows="2" {value} class:invalid={tooLong} oninput={(e) => onchange((e.target as HTMLTextAreaElement).value)}></textarea>
  {#if tooLong}<span class="warn">{t('field.descriptionLong', { n: LINE })}</span>{/if}
</label>

<style>
  .description { width: 100%; max-width: 26rem; }
  textarea { resize: vertical; }
  textarea.invalid { border-color: var(--warn); }
  .warn { color: var(--warn); font-size: 0.75rem; font-weight: 400; }
</style>
