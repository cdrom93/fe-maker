<script lang="ts">
  // A battle animation from the user's PC (ticket 53): a weapon's folder (FEditor script and frames) or its .zip,
  // converted and given to the class like a FE-Repo one (server: /api/animations/import/local).
  import { api, ApiError } from '../lib/api'
  import { t } from '../lib/i18n.svelte'
  import { animationTargets, guessTarget, targetLabel } from '../lib/animationTargets'

  let { classId, wtypes, onimported }: { classId: string; wtypes: string[]; onimported: () => void } = $props()

  const targets = $derived(animationTargets(wtypes))
  let files = $state<File[]>([])
  let name = $state('')
  let target = $state('')
  let busy = $state(false)
  let error = $state('')
  let done = $state('')

  function chosen(e: Event) {
    const input = e.target as HTMLInputElement
    files = [...(input.files ?? [])]
    input.value = ''
    error = ''
    done = ''
    // the folder's name (from the first file's path) or the zip's
    const first = files[0]
    const path = (first as File & { webkitRelativePath?: string })?.webkitRelativePath || first?.name || ''
    const folder = path.includes('/') ? path.split('/').slice(-2, -1)[0] : path.replace(/\.zip$/i, '')
    name = folder
    target = guessTarget(path, wtypes)
  }

  async function run() {
    if (!files.length) return
    busy = true
    error = ''
    try {
      await api.importLocalAnimation(classId, target || targets[0], name, files)
      done = name
      files = []
      onimported()
    } catch (e) {
      error = e instanceof ApiError ? t(`banim.import.error.${e.detail.split(':')[0]}`) : String(e)
    } finally {
      busy = false
    }
  }
</script>

<div class="local">
  <p class="muted small">{t('banim.local.hint')}</p>
  <div class="row">
    <label class="pick">
      <input type="file" webkitdirectory multiple onchange={chosen} />
      <span>{t('banim.local.folder')}</span>
    </label>
    <label class="pick">
      <input type="file" accept=".zip" onchange={chosen} />
      <span>{t('banim.local.zip')}</span>
    </label>
    {#if files.length}<span class="small">{t('banim.local.files', { n: files.length })}</span>{/if}
  </div>
  {#if files.length}
    <div class="row">
      <input bind:value={name} placeholder={t('banim.local.name')} aria-label={t('banim.local.name')} />
      <select bind:value={target} aria-label={t('banim.weapon')}>
        {#each targets as wt (wt)}<option value={wt}>{targetLabel(wt)}</option>{/each}
      </select>
      <button class="play" disabled={busy} onclick={run}>{busy ? t('banim.import.busy') : t('banim.import.use')}</button>
    </div>
  {/if}
  {#if error}<p class="bad small">{error}</p>{/if}
  {#if done}<p class="good small">✓ {t('banim.import.done', { weapon: done })}</p>{/if}
</div>

<style>
  .local { display: flex; flex-direction: column; gap: 0.5rem; margin-top: 0.75rem; }
  .row { display: flex; flex-wrap: wrap; gap: 0.5rem; align-items: center; }
  .row > input { flex: 1; min-width: 140px; }
  .pick { display: inline-flex; flex-direction: row; width: auto; cursor: pointer; }
  .pick input { display: none; }
  .pick span { padding: 0.35rem 0.8rem; border: 1px solid var(--border); border-radius: var(--radius); background: var(--panel); }
  .pick:hover span { border-color: var(--accent); }
  .small { font-size: 0.8rem; margin: 0; }
</style>
