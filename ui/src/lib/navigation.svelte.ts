import { getContext, setContext, untrack } from 'svelte'

/** Editor tabs that can show a record. */
export type NavKind = 'characters' | 'classes' | 'items' | 'combat' | 'chapters'

/** A request to show a record; `n` changes on every request so the same target can be reopened. */
export interface Focus {
  kind: NavKind
  id: string | null
  n: number
}

export interface Navigator {
  /** Open the tab of `kind` and select the record `id` (if any). */
  open: (kind: NavKind, id?: string | null) => void
  readonly focus: Focus | null
}

const KEY = Symbol('navigator')

export function provideNavigator(nav: Navigator) {
  setContext(KEY, nav)
}

export function useNavigator(): Navigator {
  return getContext<Navigator>(KEY)
}

/**
 * In an editor: select the record the navigator asks for. Only reacts to new focus
 * requests, not to edits of the records.
 */
export function followFocus(kind: NavKind, nav: Navigator, ids: () => string[], select: (index: number) => void) {
  $effect(() => {
    const f = nav.focus
    if (!f || f.kind !== kind || !f.id) return
    untrack(() => {
      const index = ids().indexOf(f.id!)
      if (index >= 0) select(index)
    })
  })
}
