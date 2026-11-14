<script lang="ts">
  import { onDestroy } from 'svelte'
  import { api, patchUrl } from '../lib/api'
  import { t } from '../lib/i18n.svelte'
  import { useNavigator, type NavKind } from '../lib/navigation.svelte'
  import type { BuildStatus, BuildTime } from '../lib/types'

  let { launch, onClose }: { launch: boolean; onClose: () => void } = $props()
  const nav = useNavigator()
  // The tab holding the part of the project a failing file comes from (server: builderrors.AREAS).
  const AREA_TABS: Record<string, NavKind> = {
    characters: 'characters', portraits: 'characters', classes: 'classes', animations: 'classes', items: 'items',
    events: 'chapters', chapters: 'chapters', maps: 'maps', texts: 'dialogues', music: 'music', skills: 'options',
  }

  function openArea(area: string) {
    onClose()
    nav?.open(AREA_TABS[area])
  }

  let status = $state<BuildStatus | null>(null)
  let log = $state<string[]>([])
  let error = $state('')
  let showLog = $state(false)
  let cancelling = $state(false)   // ticket 40
  let history = $state<BuildTime[] | null>(null)   // the last builds' durations, once asked (ticket 30)
  let timer: ReturnType<typeof setTimeout> | undefined
  // Progress guessed from the lines printed against the last build's count; past it, the bar has no value (ticket 156).
  let progress = $derived(status?.expected && log.length < status.expected ? log.length / status.expected : null)
  // Another build of the same working copy (another FE Maker window, a test) goes first: this one waits (ticket 20).
  let waiting = $derived(!!log.at(-1)?.includes('Another build is running'))
  // ...the first build of the game, made in the background after installation (home page)
  let waitingFirst = $derived(!!log.at(-1)?.includes('(the first build)'))

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

  async function cancel() {
    cancelling = true
    try {
      await api.cancelBuild()
    } catch (e) {
      error = String(e)
    }
  }

  function duration(seconds: number): string {
    const s = Math.round(seconds)
    return s < 60 ? t('build.seconds', { s }) : t('build.minutes', { m: Math.floor(s / 60), s: s % 60 })
  }

  async function toggleHistory() {
    if (history) {
      history = null
      return
    }
    try {
      history = await api.buildTimes()
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
      <h2>{cancelling ? t('build.cancelling') : t('build.running')}</h2>
      {#if waiting}
        <progress></progress>
        <p>{t(waitingFirst ? 'build.waitingFirst' : 'build.waiting')}</p>
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
      {#if status.timing}
        <p class="muted">
          {t('build.took', { time: duration(status.timing.seconds) })}
          {#if status.previous}({t('build.previous', { time: duration(status.previous.seconds) })}){/if}
          · {t('build.compiled', { n: status.timing.compiled })}
        </p>
      {/if}
    {:else if status.state === 'cancelled'}
      <h2>{t('build.cancelled')}</h2>
    {:else if status.state === 'error'}
      <h2 class="bad">{t('build.error')}</h2>
      {#if status.why}
        {@const why = status.why}
        <div class="why">
          {#if why.kind === 'problems'}
            <p>{t('build.why.problems')}</p>
            <ul>{#each why.problems ?? [] as p, i (i)}<li>{p}</li>{/each}</ul>
          {:else if why.kind === 'text'}
            <p>{t('build.why.text', { text: why.text ?? '?', line: why.line ?? 0, message: why.message ?? '' })}</p>
          {:else if why.kind === 'code'}
            <p>{t('build.why.code', { file: why.file ?? '', line: why.line ?? 0, message: why.message ?? '' })}</p>
            {#if why.written}<p class="muted">{t('build.why.written')}</p>{/if}
          {:else if why.kind === 'missingFile'}
            <p>{t('build.why.missingFile', { file: why.file ?? '' })}</p>
          {:else if why.kind === 'undefined'}
            <p>{t('build.why.undefined', { symbol: why.symbol ?? '' })}</p>
          {:else if why.kind === 'romFull'}
            <p>{why.bytes ? t('build.why.romFullBy', { kb: Math.ceil(why.bytes / 1024) }) : t('build.why.romFull')}</p>
          {:else if why.kind === 'image'}
            <p>{t('build.why.image', { message: why.message ?? '' })}</p>
          {:else if why.kind === 'locked'}
            <p>{t('build.why.locked', { file: why.file ?? '' })}</p>
          {:else if why.kind === 'decompMismatch'}
            <p>{t('build.why.decompMismatch', { detail: why.detail ?? '' })}</p>
          {:else if why.kind === 'diskFull'}
            <p>{t('build.why.diskFull')}</p>
          {/if}
          {#if why.area && AREA_TABS[why.area]}
            <button class="link" onclick={() => openArea(why.area!)}>{t('build.why.open', { area: t(`build.area.${why.area}`) })}</button>
          {/if}
        </div>
      {:else}
        <pre class="mono">{status.error?.startsWith('build.') ? t(status.error) : status.error}</pre>
      {/if}
    {/if}

    {#if log.length || status?.why}
      <button class="link" onclick={() => (showLog = !showLog)}>{t('build.showLog')}</button>
      {#if showLog}
        {#if status?.why}<pre class="mono log">{status.error}</pre>{/if}
        <pre class="mono log">{log.slice(-200).join('\n')}</pre>
      {/if}
    {/if}
    {#if status && status.state !== 'running'}
      <button class="link" onclick={toggleHistory}>{t('build.history')}</button>
      {#if history}
        <table class="times">
          <tbody>
            {#each history as h (h.date + h.project)}
              <tr>
                <td>{new Date(h.date).toLocaleString()}</td>
                <td>{h.project}</td>
                <td class="num">{duration(h.seconds)}</td>
                <td>{h.native ? t('build.native') : t('build.docker')}</td>
                <td>{h.test ? t('build.kindTest') : t('build.kindPatch')}</td>
                <td class="num">{t('build.compiled', { n: h.compiled })}</td>
              </tr>
            {/each}
          </tbody>
        </table>
      {/if}
    {/if}

    <div class="actions">
      {#if status?.state === 'running'}
        <button onclick={cancel} disabled={cancelling}>{t('build.cancel')}</button>
      {/if}
      <button onclick={onClose} disabled={status?.state === 'running'}>{t('build.close')}</button>
    </div>
  </div>
</div>

<style>
  .why { display: flex; flex-direction: column; gap: 0.3rem; align-items: flex-start; }
  .why p, .why ul { margin: 0; }
  .backdrop { position: fixed; inset: 0; background: rgb(0 0 0 / 0.45); display: grid; place-items: center; padding: 1rem; z-index: 10; }
  .dialog { width: min(640px, 100%); max-height: 90vh; overflow: auto; }
  progress { width: 100%; }
  .bar { display: flex; align-items: center; gap: 0.6rem; }
  .bar span { min-width: 3.2rem; text-align: right; font-variant-numeric: tabular-nums; color: var(--muted); }
  .mono { font-family: ui-monospace, Consolas, monospace; font-size: 0.75rem; }
  .last { white-space: nowrap; overflow: hidden; text-overflow: ellipsis; color: var(--muted); }
  pre { white-space: pre-wrap; word-break: break-all; background: var(--panel-2); padding: 0.5rem; border-radius: 6px; }
  .log { max-height: 300px; overflow: auto; }
  .link { border: none; background: none; color: var(--accent); padding: 0; display: block; margin-top: 0.4rem; }
  .times { width: 100%; border-collapse: collapse; font-size: 0.8rem; margin-top: 0.3rem; }
  .times td { padding: 0.15rem 0.4rem; border-bottom: 1px solid var(--border); }
  .times .num { text-align: right; font-variant-numeric: tabular-nums; }
  .actions { display: flex; justify-content: flex-end; gap: 0.5rem; margin-top: 1rem; }
  .good { color: var(--good); }
  .bad { color: var(--bad); }
</style>
