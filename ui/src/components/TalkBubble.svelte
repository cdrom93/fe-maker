<script lang="ts">
  // A talk box drawn with the game's font (glyph sheet /api/dialogues/font.png: 16 x 16 cells, cell = byte).
  import type { DialogueFont } from '../lib/types'
  import { visibleText, lineWidth } from '../lib/textLayout'

  let { lines, font, scale = 2 }: { lines: string[]; font: DialogueFont; scale?: number } = $props()

  let canvas = $state<HTMLCanvasElement>()
  let sheet = $state<HTMLImageElement | null>(null)

  const sheetImage = new Image()
  sheetImage.onload = () => (sheet = sheetImage)
  sheetImage.src = '/api/dialogues/font.png'

  // The box is as wide as its longest line, 24 pixels at least, plus a tile of border on each side (src/scene.c).
  const textWidth = $derived(Math.max(24, ...lines.map((l) => lineWidth(l, font))))
  const width = $derived((Math.ceil(textWidth / 8) + 2) * 8)
  const height = $derived(Math.max(1, lines.length) * 16 + 16)

  $effect(() => {
    const ctx = canvas?.getContext('2d')
    if (!ctx || !canvas) return
    canvas.width = width
    canvas.height = height
    ctx.clearRect(0, 0, width, height)
    ctx.fillStyle = '#f8f0d8'
    ctx.strokeStyle = '#6b5a3a'
    ctx.beginPath()
    ctx.roundRect(0.5, 0.5, width - 1, height - 1, 6)
    ctx.fill()
    ctx.stroke()
    if (!sheet) return
    lines.forEach((line, row) => {
      let x = 8
      for (const ch of visibleText(line)) {
        const glyph = font.chars[ch]
        if (!glyph) continue
        const [byte, w] = glyph
        ctx.drawImage(sheet!, (byte % 16) * 16, Math.floor(byte / 16) * 16, 16, 16, x, 8 + row * 16, 16, 16)
        x += w
      }
    })
  })
</script>

<canvas bind:this={canvas} style="width: {width * scale}px; height: {height * scale}px"></canvas>

<style>
  canvas { image-rendering: pixelated; display: block; filter: drop-shadow(0 2px 3px rgb(0 0 0 / 0.4)); }
</style>
