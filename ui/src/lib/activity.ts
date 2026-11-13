// The interface's last actions and errors (tabs opened, failed requests, script errors), joined to a ticket with the
// server's own (server: activity.py) when the user leaves it ticked. Memory only.

const MAX = 40
const entries: string[] = []

export function note(text: string) {
  entries.push(`${new Date().toTimeString().slice(0, 8)} ${text.slice(0, 300)}`)
  if (entries.length > MAX) entries.splice(0, entries.length - MAX)
}

export function recentActivity(): string[] {
  return [...entries]
}

/** Script errors anywhere in the page. */
export function watchErrors() {
  window.addEventListener('error', (e) => note(`ERROR ${e.message} (${(e.filename ?? '').split('/').pop()}:${e.lineno})`))
  window.addEventListener('unhandledrejection', (e) => note(`ERROR ${String(e.reason).slice(0, 250)}`))
}
