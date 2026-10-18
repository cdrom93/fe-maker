<script lang="ts">
  import { api } from '../lib/api'
  import { t } from '../lib/i18n.svelte'

  let { onDone }: { onDone: () => void } = $props()
  let state = $state<'idle' | 'checking' | 'invalid'>('idle')

  async function choose(event: Event) {
    const file = (event.target as HTMLInputElement).files?.[0]
    if (!file) return
    state = 'checking'
    try {
      await api.uploadRom(file)
      onDone()
    } catch {
      state = 'invalid'
    }
  }
</script>

<section class="panel setup">
  <h1>{t('setup.title')}</h1>
  <p>{t('setup.intro')}</p>
  <label class="file">
    <span class="primary-like">{t('setup.choose')}</span>
    <input type="file" accept=".gba" onchange={choose} disabled={state === 'checking'} />
  </label>
  {#if state === 'checking'}<p class="muted">{t('setup.checking')}</p>{/if}
  {#if state === 'invalid'}<p class="error">{t('setup.invalid')}</p>{/if}
</section>

<style>
  .setup { max-width: 560px; margin: 3rem auto; }
  .file input { position: absolute; opacity: 0; width: 1px; height: 1px; }
  .primary-like {
    display: inline-block;
    background: var(--accent);
    color: var(--accent-text);
    padding: 0.6em 1.1em;
    border-radius: var(--radius);
    font-weight: 600;
    font-size: 1rem;
    cursor: pointer;
  }
  .file:focus-within .primary-like { outline: 2px solid var(--accent); outline-offset: 2px; }
  .error { color: var(--bad); }
</style>
