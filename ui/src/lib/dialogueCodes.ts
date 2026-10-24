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

export type Eyes = 'open' | 'half' | 'closed'
export interface Expressions {
  /** [ToggleSmile] is on: whoever talks smiles (src/scene.c faceSmileEnabled; off at each message's start) */
  smile: boolean
  /** [ToggleMouthMove] is on: the mouths stop moving */
  mouthStill: boolean
  /** eyes of each slot's face: [HalfCloseEyes] and [CloseEyes] last until [OpenEyes] or a new face */
  eyes: Map<string, Eyes>
}

/** How the expression codes leave the faces once steps 0..i are played ([Wink] only lasts a moment). */
export function expressionsAt(steps: { kind: string; pos?: string | null; to?: string; text?: string; code?: string }[], i: number): Expressions {
  const out: Expressions = { smile: false, mouthStill: false, eyes: new Map() }
  let active: string | null = null
  for (const s of steps.slice(0, i + 1)) {
    if (s.kind === 'face' && s.pos) out.eyes.delete(s.pos)
    else if (s.kind === 'clear' && s.pos) out.eyes.delete(s.pos)
    else if (s.kind === 'move' && s.pos && s.to) {
      const eyes = out.eyes.get(s.pos)
      out.eyes.delete(s.pos)
      if (eyes) out.eyes.set(s.to, eyes)
    }
    const codes = s.kind === 'say' ? [...(s.text ?? '').matchAll(/\[(\w+)\]/g)].map((m) => m[1]) : s.kind === 'code' && s.code ? [s.code] : []
    if (s.kind === 'say') active = s.pos ?? null
    for (const code of codes) {
      if (code === 'ToggleSmile') out.smile = !out.smile
      else if (code === 'ToggleMouthMove') out.mouthStill = !out.mouthStill
      else if (active && code === 'OpenEyes') out.eyes.delete(active)
      else if (active && code === 'HalfCloseEyes') out.eyes.set(active, 'half')
      else if (active && code === 'CloseEyes') out.eyes.set(active, 'closed')
    }
  }
  return out
}
