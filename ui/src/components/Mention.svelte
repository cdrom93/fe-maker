<script lang="ts">
  import type { Snippet } from 'svelte'
  import { t } from '../lib/i18n.svelte'
  import { type NavKind, useNavigator } from '../lib/navigation.svelte'

  // Anything mentioned in an editor is a link to its own sheet (see CAHIER_DES_CHARGES.md, principle 8).
  let { kind, id = null, children }: { kind: NavKind; id?: string | null; children: Snippet } = $props()
  const nav = useNavigator()
</script>

<button type="button" class="mention" title={t('nav.open')} onclick={() => nav.open(kind, id)}>{@render children()}</button>

<style>
  .mention {
    border: none;
    background: none;
    padding: 0;
    font: inherit;
    color: inherit;
    cursor: pointer;
    text-decoration: underline dotted var(--muted);
    text-underline-offset: 3px;
    display: inline-flex;
    align-items: center;
    gap: 0.25rem;
  }
  .mention:hover { color: var(--accent); text-decoration-color: var(--accent); }
</style>
