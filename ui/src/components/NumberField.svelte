<script lang="ts">
  import Help from './Help.svelte'

  let {
    label,
    value,
    min,
    max,
    onchange,
    problem = '',
    compact = false,
    hint = '',
  }: {
    label: string
    value: number
    min?: number
    max?: number
    onchange: (v: number) => void
    problem?: string
    compact?: boolean
    hint?: string
  } = $props()

  let text = $state('')
  let invalid = $state(false)

  // Follow outside changes (undo, switching record) unless the user is mid-edit on an invalid value.
  $effect(() => {
    text = String(value)
    invalid = false
  })

  function input(e: Event) {
    text = (e.target as HTMLInputElement).value
    if (!/^-?\d+$/.test(text.trim())) {
      invalid = true
      return
    }
    const v = parseInt(text, 10)
    invalid = (min !== undefined && v < min) || (max !== undefined && v > max)
    if (!invalid && v !== value) onchange(v)
  }
</script>

<label class:compact title={problem || undefined}>
  <span>{label}{#if hint} <Help text={hint} />{/if}</span>
  <input
    type="text"
    inputmode="numeric"
    value={text}
    class:invalid={invalid || !!problem}
    oninput={input}
    aria-invalid={invalid || !!problem}
  />
</label>

<style>
  input { width: 100%; text-align: right; font-variant-numeric: tabular-nums; }
  .compact input { width: 3.3em; padding-left: 0.3em; padding-right: 0.3em; }
</style>
