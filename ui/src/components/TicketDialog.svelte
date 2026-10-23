<script lang="ts">
  import { onMount, tick } from 'svelte'
  import { api, ApiError, ticketImageUrl } from '../lib/api'
  import { appContext } from '../lib/appContext.svelte'
  import { i18n, t } from '../lib/i18n.svelte'
  import type { Ticket, TicketKind, TicketPriority } from '../lib/types'

  let { onClose, onChanged }: { onClose: () => void; onChanged: (openCount: number) => void } = $props()

  const KINDS: TicketKind[] = ['bug', 'idea', 'question']
  const PRIORITIES: TicketPriority[] = ['high', 'normal', 'low']
  const MAX_IMAGE_BYTES = 8 * 1024 * 1024

  let view = $state<'new' | 'list'>('new')
  let kind = $state<TicketKind>('bug')
  let priority = $state<TicketPriority>('normal')
  let body = $state('')
  let images = $state<string[]>([])
  let error = $state('')
  let sent = $state<number | null>(null)
  let sending = $state(false)
  let tickets = $state<Ticket[]>([])
  let showClosed = $state(false)
  let editing = $state<{ id: string; body: string } | null>(null)
  let confirmDelete = $state<string | null>(null)
  let textarea = $state<HTMLTextAreaElement>()

  // Captured when the window opens: what the user was looking at.
  const context = Object.fromEntries(
    Object.entries({ tab: appContext.tab ? t(`ws.${appContext.tab}`) : '', record: appContext.record, detail: appContext.detail }).filter(([, v]) => v),
  ) as Record<string, string>
  const contextText = Object.values(context).join(' · ')

  const openCount = $derived(tickets.filter((x) => x.status === 'open').length)
  const shown = $derived(tickets.filter((x) => showClosed || x.status === 'open'))

  onMount(async () => {
    await load()
    textarea?.focus()
  })

  async function load() {
    tickets = await api.tickets()
    onChanged(tickets.filter((x) => x.status === 'open').length)
  }

  function readImage(file: File) {
    if (!file.type.startsWith('image/')) return
    if (file.size > MAX_IMAGE_BYTES) {
      error = t('ticket.error.imageTooBig')
      return
    }
    const reader = new FileReader()
    reader.onload = () => (images = [...images, String(reader.result)])
    reader.readAsDataURL(file)
  }

  /** Screenshots pasted with Ctrl+V anywhere in the window. */
  function paste(e: ClipboardEvent) {
    if (view !== 'new') return
    const files = [...(e.clipboardData?.files ?? [])].filter((f) => f.type.startsWith('image/'))
    if (!files.length) return
    e.preventDefault()
    files.forEach(readImage)
  }

  async function send() {
    error = ''
    sending = true
    try {
      const ticket = await api.createTicket({ body, kind, priority, context, images })
      sent = ticket.number
      body = ''
      images = []
      kind = 'bug'
      priority = 'normal'
      await load()
      await tick()
      textarea?.focus()
    } catch (e) {
      error = e instanceof ApiError ? t(`ticket.error.${e.detail}`) : String(e)
    } finally {
      sending = false
    }
  }

  async function update(id: string, changes: Parameters<typeof api.updateTicket>[1]) {
    await api.updateTicket(id, changes)
    editing = null
    await load()
  }

  async function remove(id: string) {
    await api.deleteTicket(id)
    confirmDelete = null
    await load()
  }

  function nextPriority(p: TicketPriority): TicketPriority {
    return PRIORITIES[(PRIORITIES.indexOf(p) + 1) % PRIORITIES.length]
  }

  function date(iso: string): string {
    return new Date(iso).toLocaleString(i18n.lang, { dateStyle: 'short', timeStyle: 'short' })
  }

  function keydown(e: KeyboardEvent) {
    if (e.key === 'Escape' && !editing && confirmDelete === null) onClose()
    if (e.key === 'Enter' && (e.ctrlKey || e.metaKey) && view === 'new' && body.trim()) send()
  }
</script>

<svelte:window onkeydown={keydown} onpaste={paste} />

<div class="backdrop">
  <div class="panel dialog" role="dialog" aria-modal="true" aria-labelledby="ticket-title">
    <div class="head">
      <h2 id="ticket-title">{t('ticket.title')}</h2>
      <div class="views" role="tablist">
        <button role="tab" aria-selected={view === 'new'} class:active={view === 'new'} onclick={() => (view = 'new')}>{t('ticket.new')}</button>
        <button role="tab" aria-selected={view === 'list'} class:active={view === 'list'} onclick={() => (view = 'list')}>
          {t('ticket.list')}{#if openCount} <span class="count">{openCount}</span>{/if}
        </button>
      </div>
    </div>

    {#if view === 'new'}
      <div class="row">
        <div class="seg" role="radiogroup" aria-label={t('ticket.kind')}>
          {#each KINDS as k (k)}
            <button role="radio" aria-checked={kind === k} class:active={kind === k} onclick={() => (kind = k)}>{t(`ticket.kind.${k}`)}</button>
          {/each}
        </div>
        <div class="seg" role="radiogroup" aria-label={t('ticket.priority')}>
          {#each PRIORITIES as p (p)}
            <button role="radio" aria-checked={priority === p} class="prio {p}" class:active={priority === p} onclick={() => (priority = p)}>{t(`ticket.priority.${p}`)}</button>
          {/each}
        </div>
      </div>
      <textarea bind:this={textarea} bind:value={body} rows="6" placeholder={t('ticket.placeholder')} oninput={() => (sent = null)}></textarea>
      <div class="images">
        {#each images as src, i (i)}
          <span class="thumb">
            <img {src} alt={t('ticket.image', { n: i + 1 })} />
            <button class="x" aria-label={t('ticket.removeImage')} onclick={() => (images = images.filter((_, j) => j !== i))}>✕</button>
          </span>
        {/each}
        <label class="add-image">
          <input type="file" accept="image/*" multiple onchange={(e) => {
            const input = e.target as HTMLInputElement
            ;[...(input.files ?? [])].forEach(readImage)
            input.value = ''
          }} />
          {t('ticket.addImage')}
        </label>
      </div>
      <p class="muted small">{t('ticket.pasteHint')}</p>
      {#if contextText}<p class="muted small">{t('ticket.context')} : {contextText}</p>{/if}
      {#if error}<p class="bad small">{error}</p>{/if}
      {#if sent !== null}<p class="good small">{t('ticket.sent', { n: sent })}</p>{/if}
      <div class="actions">
        <button onclick={onClose}>{t('build.close')}</button>
        <button class="primary" onclick={send} disabled={!body.trim() || sending}>{t('ticket.send')}</button>
      </div>
    {:else}
      <label class="check"><input type="checkbox" bind:checked={showClosed} /> {t('ticket.showClosed')}</label>
      {#if !shown.length}<p class="muted">{t('ticket.none')}</p>{/if}
      <ul>
        {#each shown as tk (tk.id)}
          <li class:closed={tk.status !== 'open'}>
            <div class="meta">
              <strong>#{tk.number}</strong>
              <span class="tag">{t(`ticket.kind.${tk.kind}`)}</span>
              <button class="tag prio {tk.priority}" title={t('ticket.changePriority')} onclick={() => update(tk.id, { priority: nextPriority(tk.priority) })}>
                {t(`ticket.priority.${tk.priority}`)}
              </button>
              {#if tk.status !== 'open'}<span class="tag">{t(`ticket.status.${tk.status}`)}</span>{/if}
              <span class="muted small">{date(tk.createdAt)}</span>
            </div>
            {#if editing?.id === tk.id}
              <textarea bind:value={editing.body} rows="4"></textarea>
              <div class="actions">
                <button onclick={() => (editing = null)}>{t('ticket.cancelEdit')}</button>
                <button class="primary" disabled={!editing.body.trim()} onclick={() => update(tk.id, { body: editing!.body })}>✓ {t('ticket.save')}</button>
              </div>
            {:else}
              <button class="body" title={t('ticket.edit')} onclick={() => (editing = { id: tk.id, body: tk.body })}>{tk.body}</button>
            {/if}
            {#if Object.keys(tk.context).length}
              <p class="muted small">{[tk.context.project, tk.context.tab, tk.context.record, tk.context.detail].filter(Boolean).join(' · ')} · {tk.context.version}</p>
            {/if}
            {#if tk.images.length}
              <div class="images">
                {#each tk.images as name (name)}
                  <a class="thumb" href={ticketImageUrl(name)} target="_blank" rel="noreferrer"><img src={ticketImageUrl(name)} alt={name} /></a>
                {/each}
              </div>
            {/if}
            <div class="actions left">
              {#if tk.status === 'open'}
                <button onclick={() => update(tk.id, { status: 'done' })}>{t('ticket.markDone')}</button>
                <button onclick={() => update(tk.id, { status: 'cancelled' })}>{t('ticket.markCancelled')}</button>
              {:else}
                <button onclick={() => update(tk.id, { status: 'open' })}>{t('ticket.reopen')}</button>
              {/if}
              {#if confirmDelete === tk.id}
                <span class="bad small">{t('ticket.confirmDelete')}</span>
                <button class="danger" onclick={() => remove(tk.id)}>{t('ticket.delete')}</button>
                <button onclick={() => (confirmDelete = null)}>{t('ticket.cancelEdit')}</button>
              {:else}
                <button class="ghost" onclick={() => (confirmDelete = tk.id)}>{t('ticket.delete')}</button>
              {/if}
            </div>
          </li>
        {/each}
      </ul>
      <div class="actions">
        <button onclick={onClose}>{t('build.close')}</button>
      </div>
    {/if}
  </div>
</div>

<style>
  .backdrop { position: fixed; inset: 0; background: rgb(0 0 0 / 0.45); display: grid; place-items: center; padding: 1rem; z-index: 20; }
  .dialog { width: min(640px, 100%); max-height: 90vh; overflow: auto; display: flex; flex-direction: column; gap: 0.75rem; }
  .head { display: flex; justify-content: space-between; align-items: center; gap: 1rem; flex-wrap: wrap; }
  h2 { margin: 0; }
  .views, .seg { display: inline-flex; }
  .views button, .seg button { border-radius: 0; margin-left: -1px; }
  .views button:first-child, .seg button:first-child { border-radius: var(--radius) 0 0 var(--radius); margin-left: 0; }
  .views button:last-child, .seg button:last-child { border-radius: 0 var(--radius) var(--radius) 0; }
  .views button.active, .seg button.active { background: var(--accent-soft); border-color: var(--accent); position: relative; }
  .count { display: inline-block; min-width: 1.4em; padding: 0 0.3em; border-radius: 999px; background: var(--accent); color: var(--accent-text); font-size: 0.75rem; }
  .row { display: flex; gap: 0.75rem; flex-wrap: wrap; justify-content: space-between; }
  .prio.high { color: var(--bad); }
  .prio.low { color: var(--muted); }
  textarea { width: 100%; resize: vertical; font: inherit; box-sizing: border-box; }
  .images { display: flex; flex-wrap: wrap; gap: 0.5rem; align-items: center; }
  .thumb { position: relative; display: inline-block; }
  .thumb img { height: 72px; max-width: 160px; object-fit: cover; border: 1px solid var(--border); border-radius: 6px; display: block; }
  .x { position: absolute; top: 2px; right: 2px; padding: 0 0.35rem; font-size: 0.75rem; line-height: 1.4; }
  .add-image { display: inline-flex; align-items: center; height: 72px; padding: 0 0.9rem; border: 1px dashed var(--border); border-radius: 6px; cursor: pointer; font-size: 0.85rem; color: var(--muted); }
  .add-image input { display: none; }
  .small { font-size: 0.82rem; margin: 0; }
  .good { color: var(--good); }
  .bad { color: var(--bad); }
  .actions { display: flex; justify-content: flex-end; gap: 0.5rem; flex-wrap: wrap; align-items: center; }
  .actions.left { justify-content: flex-start; }
  .check { flex-direction: row; align-items: center; gap: 0.35rem; font-size: 0.85rem; color: var(--text); }
  ul { list-style: none; margin: 0; padding: 0; display: flex; flex-direction: column; gap: 0.6rem; }
  li { border: 1px solid var(--border); border-radius: var(--radius); padding: 0.6rem 0.75rem; display: flex; flex-direction: column; gap: 0.45rem; background: var(--panel-2); }
  li.closed { opacity: 0.65; }
  .meta { display: flex; align-items: center; gap: 0.5rem; flex-wrap: wrap; }
  .tag { font-size: 0.75rem; padding: 0.05rem 0.45rem; border: 1px solid var(--border); border-radius: 999px; background: var(--panel); }
  button.tag { line-height: 1.4; }
  .body { text-align: left; white-space: pre-wrap; border: none; background: none; padding: 0; font: inherit; color: var(--text); cursor: text; }
  .danger { color: var(--bad); }
  .ghost { border-color: transparent; background: none; color: var(--muted); }
</style>
