// Text layout of the game's talk boxes, the same as the build (server: decomp/dialogues.py layout).
import type { DialogueFont } from './types'

const PRINTABLE: Record<string, string> = { LQuote: '“', RQuote: '”', DashedLine: '\u007f' }

/** "text" and "code" pieces of a line ([ToggleSmile] is a code). */
export function pieces(line: string): { code: boolean; value: string }[] {
  const out: { code: boolean; value: string }[] = []
  const re = /\[([^\]]*)\]/g
  let pos = 0
  for (let m = re.exec(line); m; m = re.exec(line)) {
    if (m.index > pos) out.push({ code: false, value: line.slice(pos, m.index) })
    out.push({ code: true, value: m[1] })
    pos = m.index + m[0].length
  }
  if (pos < line.length) out.push({ code: false, value: line.slice(pos) })
  return out
}

/** Visible characters of a line (printable codes as their character). */
export function visibleText(line: string): string {
  return pieces(line).map((p) => (p.code ? (PRINTABLE[p.value] ?? '') : p.value)).join('')
}

export function lineWidth(line: string, font: DialogueFont): number {
  let total = 0
  for (const ch of visibleText(line)) total += font.chars[ch]?.[1] ?? 0
  return total
}

function splitWord(word: string, font: DialogueFont, max: number): string[] {
  const parts: string[] = []
  let current = ''
  for (const p of pieces(word)) {
    for (const piece of p.code ? [`[${p.value}]`] : [...p.value]) {
      if (current && lineWidth(current + piece, font) > max) {
        parts.push(current)
        current = ''
      }
      current += piece
    }
  }
  return current ? [...parts, current] : parts
}

export function wrapLine(line: string, font: DialogueFont, max: number): string[] {
  const out: string[] = []
  let current = ''
  for (const word of line.split(' ')) {
    const candidate = current ? `${current} ${word}` : word
    if (lineWidth(candidate, font) <= max) {
      current = candidate
      continue
    }
    if (current) out.push(current)
    const parts = lineWidth(word, font) > max ? splitWord(word, font, max) : [word]
    out.push(...parts.slice(0, -1))
    current = parts.length ? parts[parts.length - 1] : ''
  }
  if (current || !out.length) out.push(current)
  return out
}

/** Boxes of a line as the game shows them: too wide lines are cut between words, and a box that gets
 * more than two lines that way is split into boxes of two lines. */
export function layoutBoxes(text: string, font: DialogueFont, max: number): string[][] {
  const boxes: string[][] = []
  for (const box of text.split('\n\n')) {
    const lines: string[] = []
    let wrapped = false
    for (const line of box.split('\n')) {
      if (lineWidth(line, font) <= max) lines.push(line)
      else {
        wrapped = true
        lines.push(...wrapLine(line, font, max))
      }
    }
    if (wrapped && lines.length > font.boxLines) {
      for (let k = 0; k < lines.length; k += font.boxLines) boxes.push(lines.slice(k, k + font.boxLines))
    } else boxes.push(lines)
  }
  return boxes
}

export function layout(text: string, font: DialogueFont, max: number): string {
  return layoutBoxes(text, font, max).map((b) => b.join('\n')).join('\n\n')
}
