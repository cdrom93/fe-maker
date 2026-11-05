// Palette colours by shades: shared by a character's battle colours and a map's colours (ticket 147).

/** Hue, saturation and lightness, from 0 to 1. */
export function hsl(hex: string): [number, number, number] {
  const [r, g, b] = [1, 3, 5].map((i) => parseInt(hex.slice(i, i + 2), 16) / 255)
  const high = Math.max(r, g, b)
  const low = Math.min(r, g, b)
  const l = (high + low) / 2
  const d = high - low
  if (!d) return [0, 0, l]
  const h = high === r ? (g - b) / d + (g < b ? 6 : 0) : high === g ? (b - r) / d + 2 : (r - g) / d + 4
  return [h / 6, d / (1 - Math.abs(2 * l - 1)), l]
}

export function hex(h: number, s: number, l: number): string {
  const part = (n: number) => {
    const k = (n + h * 12) % 12
    const v = l - s * Math.min(l, 1 - l) * Math.max(-1, Math.min(k - 3, 9 - k, 1))
    return Math.round(v * 255).toString(16).padStart(2, '0')
  }
  return `#${part(0)}${part(8)}${part(4)}`
}

const neutral = ([, s, l]: [number, number, number]) => s < 0.15 || l > 0.9 || l < 0.12

function close(a: string, b: string): boolean {
  const [x, y] = [hsl(a), hsl(b)]
  if (neutral(x) || neutral(y)) return neutral(x) && neutral(y)
  const turn = Math.abs(x[0] - y[0])
  return Math.min(turn, 1 - turn) < 0.11
}

/** Colours follow each other by shades: neighbours of close hues make a family (colour 0 is transparent). */
export function families(colours: string[] | undefined): number[][] {
  const out: number[][] = []
  for (let i = 1; colours && i < colours.length; i++) {
    const last = out.at(-1)
    if (last && close(colours[last.at(-1)!], colours[i])) last.push(i)
    else out.push([i])
  }
  return out
}

/** `picked` becomes `colour`, the other colours of `family` follow and keep their relief. */
export function recolorFamily(current: string[], picked: number, family: number[], colour: string): string[] {
  const [h, s, l] = hsl(colour)
  const from = hsl(current[picked])[2]
  return current.map((c, k) => {
    if (k === picked) return colour
    if (!family.includes(k)) return c
    const own = hsl(c)[2]    // darker shades scale down to black, lighter ones up to white: their order stays
    return hex(h, s, own < from ? (l * own) / from : l + ((own - from) * (1 - l)) / (1 - from || 1))
  })
}

/** Two colours, or two families whatever their sizes, swapped: dark goes to dark. */
export function swapColours(current: string[], a: number[], b: number[]): string[] {
  const dark = (slots: number[]) => [...slots].sort((x, y) => hsl(current[x])[2] - hsl(current[y])[2])
  const next = [...current]
  const fill = (to: number[], from: number[]) => to.forEach((slot, rank) => {
    next[slot] = current[from[Math.round((rank * (from.length - 1)) / (to.length - 1 || 1))]]
  })
  fill(dark(a), dark(b))
  fill(dark(b), dark(a))
  return next
}
