/** What the File menu (FileMenu.svelte, in the app's top bar) can do to the open project: Workspace.svelte fills it
 * while a project is open, and empties it when the project closes. */
export interface ProjectCommands {
  flush: () => Promise<unknown>
  saveAs: () => void
  rename: () => void
  openFolder: () => void
  exportPatch: () => void
  /** false while the project has errors: the patch cannot be built */
  canExport: () => boolean
  close: () => Promise<void>
}

/** keysOpen: the emulator keys dialog is up (the project's shortcuts then wait) */
export const fileMenu = $state<{ project: ProjectCommands | null; keysOpen: boolean }>({ project: null, keysOpen: false })
