<script lang="ts">
  import { t } from '../lib/i18n.svelte'

  let { gender }: { gender: 'male' | 'female' | null | undefined } = $props()
</script>

{#if gender}
  <span class="sign {gender}" title={t(`gender.${gender}`)}>{gender === 'male' ? '♂' : '♀'}</span>
{/if}

<style>
  .sign { font-weight: 700; margin-left: 0.2em; }
  .male { color: var(--male); }
  .female { color: var(--female); }
</style>
