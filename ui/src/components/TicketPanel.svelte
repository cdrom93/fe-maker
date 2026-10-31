<script lang="ts">
  import { onMount, tick } from 'svelte'
  import { api, ApiError, ticketImageUrl } from '../lib/api'
  import { appContext } from '../lib/appContext.svelte'
  import { i18n, t } from '../lib/i18n.svelte'
  import type { Ticket, TicketKind, TicketPriority } from '../lib/types'

  /** Side column to write feedback tickets while using the app: new ticket on top, open tickets below. */
  let { onClose, onChanged }: { onClose: () => void; onChanged: (openCount: number) => void } = $props()

  const KINDS: TicketKind[] = ['bug', 'idea', 'question']
  const PRIORITIES: TicketPriority[] = ['high', 'normal', 'low']
  const MAX_IMAGE_BYTES = 8 * 1024 * 1024

  let kind = $state<TicketKind>('bug')
  let priority = $state<TicketPriority>('normal')
  let body = $state('')
  let images = $state<string[]>([])
  let error = $state('')
  const ISSUES_REPO = 'cdrom93/fe-maker'
  let version = $state('')
  api.status().then((s) => (version = s.version)).catch(() => {})
  let sent = $state<number | null>(null)
  let sending = $state(false)
  let tickets = $state<Ticket[]>([])
  let showClosed = $state(false)
  let editing = $state<{ id: string; body: string } | null>(null)
  let confirmDelete = $state<string | null>(null)
  let reply = $state<{ id: string; body: string; images: string[]; error: string } | null>(null)
  let replying = $state(false)
  let textarea = $state<HTMLTextAreaElement>()
  let panel = $state<HTMLElement>()

  // What the user is looking at right now (the column stays open while they use the app).
  const context = $derived(
    Object.fromEntries(
      Object.entries({ tab: appContext.tab ? t(`ws.${appContext.tab}`) : '', record: appContext.record, detail: appContext.detail }).filter(([, v]) => v),
    ) as Record<string, string>,
  )
  const contextText = $derived(Object.values(context).join(' · '))
  const shown = $derived(tickets.filter((x) => showClosed || x.status === 'open'))

  onMount(async () => {
    await load()
    textarea?.focus()
  })

  /** A GitHub issue filled in from a ticket, in the user's browser: they read it and send it, or not (alpha, step 7). */
  function issueUrl(tk: Ticket): string {
    const lines = [tk.body, '', ...Object.entries(tk.context).map(([k, v]) => `- ${k}: ${v}`), `- FE Maker: ${version}`]
    for (const comment of tk.comments) lines.push('', '---', comment.body)
    const pictures = tk.images.length + tk.comments.reduce((n, comment) => n + comment.images.length, 0)
    if (pictures) lines.push('', t('ticket.issueImages', { n: pictures }))
    const query = new URLSearchParams({ title: `[${tk.kind}] ${tk.body.split('\n')[0].slice(0, 70)}`, body: lines.join('\n').slice(0, 6000) })
    return `https://github.com/${ISSUES_REPO}/issues/new?${query}`
  }

  async function load() {
    tickets = await api.tickets()
    onChanged(tickets.filter((x) => x.status === 'open').length)
  }

  function readImage(file: File, add = (src: string) => { images = [...images, src] }, fail = (message: string) => { error = message }) {
    if (!file.type.startsWith('image/')) return
    if (file.size > MAX_IMAGE_BYTES) {
      fail(t('ticket.error.imageTooBig'))
      return
    }
    const reader = new FileReader()
    reader.onload = () => add(String(reader.result))
    reader.readAsDataURL(file)
  }

  /** Screenshots pasted with Ctrl+V while typing a ticket. */
  function paste(e: ClipboardEvent, read = (file: File) => readImage(file)) {
    const files = [...(e.clipboardData?.files ?? [])].filter((f) => f.type.startsWith('image/'))
    if (!files.length) return
    e.preventDefault()
    files.forEach(read)
  }

  /** A screenshot for the reply being written. */
  function readReplyImage(file: File) {
    readImage(file, (src) => { if (reply) reply.images = [...reply.images, src] }, (message) => { if (reply) reply.error = message })
  }

  async function sendReply() {
    if (!reply || replying) return
    const { id, body: text, images: pictures } = $state.snapshot(reply)
    replying = true
    reply.error = ''
    try {
      await api.addTicketComment(id, { body: text, images: pictures })
      reply = null
      await load()
    } catch (e) {
      if (reply) reply.error = e instanceof ApiError ? t(`ticket.error.${e.detail}`) : String(e)
    } finally {
      replying = false
    }
  }

  async function removeComment(id: string, commentId: string) {
    await api.deleteTicketComment(id, commentId)
    confirmDelete = null
    await load()
  }

  const focus = (element: HTMLElement) => element.focus()

  async function send() {
    error = ''
    sending = true
    try {
      const ticket = await api.createTicket({ body, kind, priority, context: $state.snapshot(context), images })
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
    if (e.key === 'Enter' && (e.ctrlKey || e.metaKey) && body.trim()) send()
  }
</script>

<aside class="side" bind:this={panel} aria-labelledby="ticket-title">
  <div class="head">
    <h2 id="ticket-title">{t('ticket.title')}</h2>
    <button class="ghost" aria-label={t('build.close')} title={t('build.close')} onclick={onClose}>✕</button>
  </div>

  <section class="new" aria-label={t('ticket.new')}>
    <h3>{t('ticket.new')}</h3>
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
    <textarea bind:this={textarea} bind:value={body} rows="4" placeholder={t('ticket.placeholder')} oninput={() => (sent = null)} onpaste={paste} onkeydown={keydown}></textarea>
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
          ;[...(input.files ?? [])].forEach((file) => readImage(file))
          input.value = ''
        }} />
        {t('ticket.addImage')}
      </label>
    </div>
    <p class="muted small">{t('ticket.pasteHint')}</p>
    {#if contextText}<p class="muted small">{t('ticket.context')} : {contextText}</p>{/if}
    {#if error}<p class="bad small">{error}</p>{/if}
    {#if sent !== null}<p class="good small">{t('ticket.sent', { n: sent })}</p>{/if}
    <button class="primary" onclick={send} disabled={!body.trim() || sending}>{t('ticket.send')}</button>
  </section>

  <section class="list" aria-label={t('ticket.list')}>
    <div class="list-head">
      <h3>{t('ticket.list')}</h3>
      <label class="check"><input type="checkbox" bind:checked={showClosed} /> {t('ticket.showClosedShort')}</label>
    </div>
    {#if !shown.length}<p class="muted small">{t('ticket.none')}</p>{/if}
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
            <span class="muted tiny">{date(tk.createdAt)}</span>
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
            <p class="muted tiny">{[tk.context.tab, tk.context.record, tk.context.detail].filter(Boolean).join(' · ')}</p>
          {/if}
          {#if tk.images.length}
            <div class="images">
              {#each tk.images as name (name)}
                <a class="thumb" href={ticketImageUrl(name)} target="_blank" rel="noreferrer"><img src={ticketImageUrl(name)} alt={name} /></a>
              {/each}
            </div>
          {/if}
          {#each tk.comments as comment (comment.id)}
            <div class="comment">
              <div class="meta">
                <span class="muted tiny">{date(comment.createdAt)}</span>
                {#if confirmDelete === comment.id}
                  <button class="link danger" onclick={() => removeComment(tk.id, comment.id)}>{t('ticket.confirmDeleteShort')}</button>
                  <button class="link" onclick={() => (confirmDelete = null)}>{t('ticket.cancelEdit')}</button>
                {:else}
                  <button class="link" onclick={() => (confirmDelete = comment.id)}>{t('ticket.delete')}</button>
                {/if}
              </div>
              <p class="comment-body">{comment.body}</p>
              {#if comment.images.length}
                <div class="images">
                  {#each comment.images as name (name)}
                    <a class="thumb" href={ticketImageUrl(name)} target="_blank" rel="noreferrer"><img src={ticketImageUrl(name)} alt={name} /></a>
                  {/each}
                </div>
              {/if}
            </div>
          {/each}
          {#if reply?.id === tk.id}
            <div class="reply">
              <textarea use:focus bind:value={reply.body} rows="3" aria-label={t('ticket.reply')} placeholder={t('ticket.replyPlaceholder')}
                onpaste={(e) => paste(e, readReplyImage)}
                onkeydown={(e) => { if (e.key === 'Enter' && (e.ctrlKey || e.metaKey) && reply?.body.trim()) sendReply() }}></textarea>
              <div class="images">
                {#each reply.images as src, i (i)}
                  <span class="thumb">
                    <img {src} alt={t('ticket.image', { n: i + 1 })} />
                    <button class="x" aria-label={t('ticket.removeImage')} onclick={() => { if (reply) reply.images = reply.images.filter((_, j) => j !== i) }}>✕</button>
                  </span>
                {/each}
                <label class="add-image">
                  <input type="file" accept="image/*" multiple onchange={(e) => {
                    const input = e.target as HTMLInputElement
                    ;[...(input.files ?? [])].forEach(readReplyImage)
                    input.value = ''
                  }} />
                  {t('ticket.addImage')}
                </label>
              </div>
              {#if reply.error}<p class="bad small">{reply.error}</p>{/if}
              <div class="actions">
                <button onclick={() => (reply = null)}>{t('ticket.cancelEdit')}</button>
                <button class="primary" disabled={!reply.body.trim() || replying} onclick={sendReply}>{t('ticket.replySend')}</button>
              </div>
            </div>
          {/if}
          <div class="actions left">
            {#if tk.status === 'open'}
              {#if reply?.id !== tk.id}
                <button onclick={() => (reply = { id: tk.id, body: '', images: [], error: '' })}>{t('ticket.reply')}</button>
              {/if}
              <a class="issue" href={issueUrl(tk)} target="_blank" rel="noreferrer" title={t('ticket.issueHint')}>{t('ticket.issue')}</a>
              <button onclick={() => update(tk.id, { status: 'done' })}>{t('ticket.markDone')}</button>
              <button onclick={() => update(tk.id, { status: 'cancelled' })}>{t('ticket.markCancelled')}</button>
            {:else}
              <button onclick={() => update(tk.id, { status: 'open' })}>{t('ticket.reopen')}</button>
            {/if}
            {#if confirmDelete === tk.id}
              <button class="danger" onclick={() => remove(tk.id)}>{t('ticket.confirmDeleteShort')}</button>
              <button onclick={() => (confirmDelete = null)}>{t('ticket.cancelEdit')}</button>
            {:else}
              <button class="ghost" onclick={() => (confirmDelete = tk.id)}>{t('ticket.delete')}</button>
            {/if}
          </div>
        </li>
      {/each}
    </ul>
  </section>
</aside>

<style>
  .issue { font-size: 0.8rem; align-self: center; }
  .side {
    position: fixed; top: var(--header-height, 49px); right: 0; bottom: 0; width: var(--side-width, 380px); z-index: 15;
    display: flex; flex-direction: column; gap: 0.9rem; overflow-y: auto; box-sizing: border-box;
    padding: 0.9rem 1rem 1.5rem; background: var(--panel); border-left: 1px solid var(--border);
    box-shadow: -6px 0 18px rgb(0 0 0 / 0.18);
  }
  .head { display: flex; justify-content: space-between; align-items: center; }
  h2 { margin: 0; font-size: 1.05rem; }
  h3 { margin: 0; font-size: 0.8rem; text-transform: uppercase; letter-spacing: 0.04em; color: var(--muted); }
  section { display: flex; flex-direction: column; gap: 0.5rem; }
  .list { border-top: 1px solid var(--border); padding-top: 0.8rem; }
  .list-head { display: flex; justify-content: space-between; align-items: center; gap: 0.5rem; }
  .seg { display: inline-flex; }
  .seg button { border-radius: 0; margin-left: -1px; flex: 1; padding: 0.3em 0.5em; font-size: 0.85rem; }
  .seg button:first-child { border-radius: var(--radius) 0 0 var(--radius); margin-left: 0; }
  .seg button:last-child { border-radius: 0 var(--radius) var(--radius) 0; }
  .seg button.active { background: var(--accent-soft); border-color: var(--accent); position: relative; }
  .prio.high { color: var(--bad); }
  .prio.low { color: var(--muted); }
  textarea { width: 100%; resize: vertical; font: inherit; box-sizing: border-box; }
  .images { display: flex; flex-wrap: wrap; gap: 0.4rem; align-items: center; }
  .thumb { position: relative; display: inline-block; }
  .thumb img { height: 56px; max-width: 120px; object-fit: cover; border: 1px solid var(--border); border-radius: 6px; display: block; }
  .x { position: absolute; top: 2px; right: 2px; padding: 0 0.35rem; font-size: 0.75rem; line-height: 1.4; }
  .add-image { display: inline-flex; align-items: center; height: 56px; padding: 0 0.8rem; border: 1px dashed var(--border); border-radius: 6px; cursor: pointer; font-size: 0.82rem; color: var(--muted); }
  .add-image input { display: none; }
  p { margin: 0; }
  .small { font-size: 0.8rem; }
  .tiny { font-size: 0.72rem; }
  .good { color: var(--good); }
  .bad { color: var(--bad); }
  .actions { display: flex; justify-content: flex-end; gap: 0.4rem; flex-wrap: wrap; align-items: center; }
  .actions.left { justify-content: flex-start; }
  .actions button { padding: 0.2em 0.6em; font-size: 0.82rem; }
  .check { flex-direction: row; align-items: center; gap: 0.3rem; font-size: 0.78rem; color: var(--muted); }
  ul { list-style: none; margin: 0; padding: 0; display: flex; flex-direction: column; gap: 0.5rem; }
  li { border: 1px solid var(--border); border-radius: var(--radius); padding: 0.5rem 0.6rem; display: flex; flex-direction: column; gap: 0.35rem; background: var(--panel-2); }
  li.closed { opacity: 0.65; }
  .meta { display: flex; align-items: center; gap: 0.4rem; flex-wrap: wrap; }
  .tag { font-size: 0.72rem; padding: 0.05rem 0.4rem; border: 1px solid var(--border); border-radius: 999px; background: var(--panel); }
  button.tag { line-height: 1.4; }
  .body { text-align: left; white-space: pre-wrap; border: none; background: none; padding: 0; font: inherit; font-size: 0.88rem; color: var(--text); cursor: text; }
  .comment { display: flex; flex-direction: column; gap: 0.2rem; padding-left: 0.6rem; border-left: 2px solid var(--border); }
  .comment-body { white-space: pre-wrap; font-size: 0.88rem; }
  .reply { display: flex; flex-direction: column; gap: 0.4rem; }
  .link { border: none; background: none; padding: 0; font-size: 0.72rem; color: var(--muted); text-decoration: underline; }
  .danger { color: var(--bad); }
  .ghost { border-color: transparent; background: none; color: var(--muted); }
</style>
