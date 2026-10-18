/**
 * Undo / redo for a list of records, with debounced autosave.
 * Each change replaces the whole list (lists are small: a few hundred records).
 */
export class EditableList<T> {
  records = $state<T[]>([])
  saving = $state(false)
  private past: string[] = []
  private future: string[] = []
  private timer: ReturnType<typeof setTimeout> | undefined
  canUndo = $state(false)
  canRedo = $state(false)

  constructor(private save: (records: T[]) => Promise<void>, private delayMs = 600) {}

  load(records: T[]) {
    this.records = records
    this.past = []
    this.future = []
    this.sync()
  }

  private lastEdit = { index: -1, time: 0 }

  /** Apply a change to one record (by index), recording it for undo.
   *  Quick successive edits of the same record (typing) form a single undo step. */
  update(index: number, change: (record: T) => void) {
    const now = Date.now()
    if (index !== this.lastEdit.index || now - this.lastEdit.time > 1000) {
      this.past.push(JSON.stringify(this.records))
      if (this.past.length > 200) this.past.shift()
    }
    this.lastEdit = { index, time: now }
    this.future = []
    const copy = structuredClone($state.snapshot(this.records)) as T[]
    change(copy[index])
    this.records = copy
    this.sync()
    this.scheduleSave()
  }

  undo() {
    const previous = this.past.pop()
    if (previous === undefined) return
    this.future.push(JSON.stringify(this.records))
    this.records = JSON.parse(previous)
    this.sync()
    this.scheduleSave()
  }

  redo() {
    const next = this.future.pop()
    if (next === undefined) return
    this.past.push(JSON.stringify(this.records))
    this.records = JSON.parse(next)
    this.sync()
    this.scheduleSave()
  }

  async flush() {
    if (this.timer) {
      clearTimeout(this.timer)
      this.timer = undefined
      await this.doSave()
    }
  }

  private sync() {
    this.canUndo = this.past.length > 0
    this.canRedo = this.future.length > 0
  }

  private scheduleSave() {
    this.saving = true
    clearTimeout(this.timer)
    this.timer = setTimeout(() => {
      this.timer = undefined
      this.doSave()
    }, this.delayMs)
  }

  private async doSave() {
    this.saving = true
    try {
      await this.save($state.snapshot(this.records) as T[])
    } finally {
      this.saving = false
    }
  }
}
