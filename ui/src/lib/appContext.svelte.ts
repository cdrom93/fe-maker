/**
 * Where the user is in the app (tab, selected record, detail such as a chapter unit).
 * Attached to feedback tickets so a report says what it is about without retyping it.
 */
export const appContext = $state({ tab: '', record: '', recordId: '', detail: '' })

export function resetAppContext() {
  appContext.tab = ''
  appContext.record = ''
  appContext.recordId = ''
  appContext.detail = ''
}
