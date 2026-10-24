/** Codes put in a line with one click (they change the face of the speaker). */
export const EXPRESSIONS = [
  { code: 'ToggleSmile', icon: '😊' },
  { code: 'ToggleMouthMove', icon: '🤐' },
  { code: 'HalfCloseEyes', icon: '😑' },
  { code: 'CloseEyes', icon: '😌' },
  { code: 'OpenEyes', icon: '👀' },
  { code: 'Wink', icon: '😉' },
]

/** A line as the conversation view shows it: expression codes as their icon (ticket 24). */
export function toDisplay(text: string): string {
  return EXPRESSIONS.reduce((s, ex) => s.replaceAll(`[${ex.code}]`, ex.icon), text)
}

/** Back to the game's text: each icon becomes its code again. */
export function fromDisplay(text: string): string {
  return EXPRESSIONS.reduce((s, ex) => s.replaceAll(ex.icon, `[${ex.code}]`), text)
}
