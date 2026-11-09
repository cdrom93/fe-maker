<script lang="ts">
  import FolderPickButton from './FolderPickButton.svelte'
  import { inFolder } from '../lib/paths'
  import { untrack } from 'svelte'
  import { api, ApiError } from '../lib/api'
  import { t } from '../lib/i18n.svelte'
  import type { ProjectInfo } from '../lib/types'
  import Help from './Help.svelte'

  /** Project menu (ticket 174): rename the project, or save it as a copy in another folder (the copy opens). */
  let { project, mode, onClose, onSaved }: {
    project: ProjectInfo
    mode: 'rename' | 'saveAs'
    onClose: () => void
    onSaved: () => void
  } = $props()

  // the fields start from the project as it is when the dialog opens
  let name = $state(untrack(() => project.name))
  let author = $state(untrack(() => String(project.meta.author ?? '')))
  let folder = $state(untrack(() => `${project.path} (2)`))
  let error = $state('')
  let busy = $state(false)

  function message(e: unknown): string {
    if (!(e instanceof ApiError)) return String(e)
    const [code, ...rest] = e.detail.split(':')
    if (code === 'project.copyFailed') return t(code, { reason: rest.join(':') })
    const text = t(e.detail)
    return text === e.detail ? e.detail : text
  }

  async function save() {
    busy = true
    error = ''
    try {
      if (mode === 'rename') await api.renameProject({ name, author })
      else await api.saveProjectAs(folder.trim(), name)
      onSaved()
      onClose()
    } catch (e) {
      error = message(e)
    } finally {
      busy = false
    }
  }
</script>

<div class="backdrop">
  <div class="panel dialog" role="dialog" aria-modal="true" aria-labelledby="identity-title">
    <form onsubmit={(e) => { e.preventDefault(); save() }}>
      <h2 id="identity-title">
        {mode === 'rename' ? t('identity.renameTitle') : t('identity.saveAsTitle')}
        {#if mode === 'saveAs'}<Help text={t('identity.saveAsHint')} />{/if}
      </h2>
      <label>{mode === 'rename' ? t('identity.name') : t('identity.copyName')}<input bind:value={name} required maxlength="60" /></label>
      {#if mode === 'rename'}
        <label>{t('identity.author')}<input bind:value={author} maxlength="60" /></label>
      {:else}
        <label>{t('identity.folder')}
          <span class="pick"><input bind:value={folder} required />
            <FolderPickButton initial={project.path} onpick={(p) => (folder = inFolder(p, name))} /></span>
        </label>
      {/if}
      {#if error}<p class="bad small">{error}</p>{/if}
      <div class="actions">
        <button type="button" onclick={onClose}>{t('identity.cancel')}</button>
        <button class="primary" disabled={busy || !name.trim() || (mode === 'saveAs' && !folder.trim())}>{t('identity.save')}</button>
      </div>
    </form>
  </div>
</div>

<style>
  .pick { display: flex; gap: 0.4rem; }
  .pick input { flex: 1; }
  .backdrop { position: fixed; inset: 0; background: rgb(0 0 0 / 0.45); display: grid; place-items: center; padding: 1rem; z-index: 10; }
  .dialog { width: min(560px, 100%); max-height: 90vh; overflow: auto; }
  form { display: flex; flex-direction: column; gap: 0.75rem; }
  h2 { margin: 0; }
  .small { font-size: 0.85rem; }
  .bad { color: var(--bad); }
  .actions { display: flex; justify-content: flex-end; gap: 0.5rem; margin-top: 0.5rem; }
</style>
