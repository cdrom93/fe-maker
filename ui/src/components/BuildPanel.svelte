<script lang="ts">
  import { onDestroy } from 'svelte'
  import { api, patchUrl } from '../lib/api'
  import { t } from '../lib/i18n.svelte'
  import type { BuildStatus } from '../lib/types'

  let { launch, onClose }: { launch: boolean; onClose: () => void } = $props()

  let status = $state<BuildStatus | null>(null)
  let log = $state<string[]>([])
  let error = $state('')
  let showLog = $state(false)
  let timer: ReturnType<typeof setTimeout> | undefined
  // Progress guessed from the lines printed against the last build's count; past it, the bar has no value (ticket 156).
  let progress = $derived(status?.expected && log.length < status.expected ? log.length / status.expected : null)
  // Another build of the same working copy (another FE Maker window, a test) goes first: this one waits (ticket 20).
  let waiting = $derived(!!log.at(-1)?.includes('Another build is running'))

  async function poll() {
    try {
      const s = await api.buildStatus(log.length)
      log = [...log, ...s.log]
      status = s
      if (s.state === 'running') timer = setTimeout(poll, 800)
      else if (s.state === 'done' && !s.launch) window.location.href = patchUrl
    } catch (e) {
      error = String(e)
    }
  }

  async function start() {
    try {
      status = await api.startBuild(launch)
      poll()
    } catch (e) {
      error = String(e)
    }
  }

  start()
  onDestroy(() => clearTimeout(timer))
</script>

<div class="backdrop">
  <div class="panel dialog" role="dialog" aria-modal="true">
    {#if error}
      <h2 class="bad">{t('build.error')}</h2>
      <p>{error}</p>
    {:else if !status || status.state === 'running'}
      <h2>{t('build.running')}</h2>
      {#if waiting}
        <progress></progress>
        <p>{t('build.waiting')}</p>
      {:else if progress !== null}
        <div class="bar"><progress value={progress}></progress><span>{Math.round(progress * 100)} %</span></div>
      {:else}
        <progress></progress>
      {/if}
      {#if !waiting}<p class="muted">{t('build.firstTime')}</p>{/if}
      <p class="last mono">{log.at(-1) ?? ''}</p>
    {:else if status.state === 'done'}
      <h2 class="good">{t('build.done')}</h2>
      {#if status.launch}<p>{t('build.launched')}</p>{/if}
    {:else if status.state === 'error'}
      <h2 class="bad">{t('build.error')}</h2>
      <pre class="mono">{status.error}</pre>
    {/if}

    {#if log.length}
      <button class="link" onclick={() => (showLog = !showLog)}>{t('build.showLog')}</button>
      {#if showLog}<pre class="mono log">{log.slice(-200).join('\n')}</pre>{/if}
    {/if}

    <div class="actions">
      <button onclick={onClose} disabled={status?.state === 'running'}>{t('build.close')}</button>
    </div>
  </div>
</div>

<style>
  .backdrop { position: fixed; inset: 0; background: rgb(0 0 0 / 0.45); display: grid; place-items: center; padding: 1rem; z-index: 10; }
  .dialog { width: min(640px, 100%); max-height: 90vh; overflow: auto; }
  progress { width: 100%; }
  .bar { display: flex; align-items: center; gap: 0.6rem; }
  .bar span { min-width: 3.2rem; text-align: right; font-variant-numeric: tabular-nums; color: var(--muted); }
  .mono { font-family: ui-monospace, Consolas, monospace; font-size: 0.75rem; }
  .last { white-space: nowrap; overflow: hidden; text-overflow: ellipsis; color: var(--muted); }
  pre { white-space: pre-wrap; word-break: break-all; background: var(--panel-2); padding: 0.5rem; border-radius: 6px; }
  .log { max-height: 300px; overflow: auto; }
  .link { border: none; background: none; color: var(--accent); padding: 0; }
  .actions { display: flex; justify-content: flex-end; margin-top: 1rem; }
  .good { color: var(--good); }
  .bad { color: var(--bad); }
</style>
