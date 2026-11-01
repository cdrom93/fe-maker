<script lang="ts">
  import Help from './Help.svelte'
  import { untrack } from 'svelte'
  import { api, animationUrl } from '../lib/api'
  import { t } from '../lib/i18n.svelte'
  import AnimationLibrary from './AnimationLibrary.svelte'
  import LocalAnimationImport from './LocalAnimationImport.svelte'
  import type { ClassAnimation, FeRepoEntry, Item } from '../lib/types'

  /** The class's battle animations played as in the game (ticket 44), by weapon and mode. */
  let { classId, className, items, wtypes, onchanged, preview = false, colors, focus = null, selected = null, onpick, palette = $bindable(0) }: {
    classId: string; className: string; items: Item[]; wtypes: string[]
    /** the class's animations changed (imported, restored, removed): weapons animated and problems to refresh */
    onchanged?: () => void
    /** only the player: nothing to import or restore */
    preview?: boolean
    /** the lines of colours to draw with, one per side, instead of the animation's */
    colors?: string[][]
    /** with `colors`: the only colour numbers in colour, the others in grey */
    focus?: number[] | null
    /** with `colors`: the colour numbers outlined on the sprite */
    selected?: number[] | null
    /** with `colors`: a click on the sprite, with the colour number of the pixel, null outside it */
    onpick?: (index: number | null) => void
    /** the side shown */
    palette?: number
  } = $props()
  let showLibrary = $state(false)
  let showLocal = $state(false)
  /** the imported animation to show in the library again */
  let reopen = $state<FeRepoEntry | null>(null)

  const MODES = ['stand', 'attack_close', 'attack_close_critical', 'attack_range', 'attack_range_critical', 'dodge_close', 'attack_miss'] as const
  const PALETTES = ['player', 'enemy', 'ally'] as const

  let animations = $state<ClassAnimation[]>([])
  let chosen = $state(0)
  let mode = $state<string>(untrack(() => (preview ? 'stand' : 'attack_close')))
  let playing = $state(untrack(() => !preview))
  type Box = { x: number; y: number; w: number; h: number }
  /** `box`: the part of a frame shown */
  let strip = $state<{ img: CanvasImageSource; durations: number[]; width: number; height: number; box: Box; indexes?: Uint8Array } | null>(null)
  let zoom = $state(untrack(() => (preview ? 3 : 2)))
  let canvas = $state<HTMLCanvasElement | null>(null)
  let error = $state(false)

  function reload() {
    const id = classId
    api.classAnimations(id).then((list) => {
      if (id === classId) animations = list
    }).catch(() => {})
  }
  // Only when the class really changes: an edit of the class gives this prop's getter a new value to read, and
  // emptying the list then closed the library (ticket 61).
  const currentClass = $derived(classId)
  $effect(() => {
    void currentClass
    animations = []
    chosen = 0
    untrack(reload)
  })

  function changed() {
    reload()
    onchanged?.()
  }

  /** Back to the game's animation for this weapon type (an imported one stays in the project). */
  async function restore(a: ClassAnimation) {
    const target = a.wtype ?? a.item   // a throwing axe is set by its item id
    if (!target) return
    await api.setClassAnimation(classId, target, null)
    changed()
  }
  async function removeImported(a: ClassAnimation) {
    if (!a.ref.startsWith('new-')) return
    await api.removeAnimation(a.ref.slice(4))
    changed()
  }

  const anim = $derived(animations[chosen])
  const modes = $derived(anim ? MODES.filter((m) => anim.modes.includes(m)) : [])

  // Load the strip of the chosen mode (frames side by side) and its timings.
  $effect(() => {
    if (!anim) return
    const m = modes.includes(mode as (typeof MODES)[number]) ? mode : modes[0]
    if (!m) return
    const number = anim.ref
    const pal = palette
    const url = animationUrl(number, m, pal, preview ? NUMBERS : undefined)
    error = false
    Promise.all([api.animationMode(number, m, pal), loadImage(url)])
      .then(([info, img]) => {
        const box = { x: 0, y: 0, w: info.width, h: info.height }
        if (anim?.ref === number && palette === pal) strip = preview ? numbered(img, info) : { img, box, ...info }
      })
      .catch(() => (error = true))
  })

  /** Colours that give away a pixel's colour number, to read it back from the strip (255: transparent). */
  const NUMBERS = Array.from({ length: 16 }, (_, i) => `#${(i * 16).toString(16).padStart(2, '0')}0000`)
  function numbered(img: HTMLImageElement, info: { durations: number[]; width: number; height: number }) {
    const sheet = document.createElement('canvas')
    sheet.width = img.width
    sheet.height = img.height
    const ctx = sheet.getContext('2d', { willReadFrequently: true })!
    ctx.drawImage(img, 0, 0)
    const data = ctx.getImageData(0, 0, img.width, img.height).data
    const indexes = new Uint8Array(img.width * img.height)
    for (let i = 0; i < indexes.length; i++) indexes[i] = data[i * 4 + 3] ? data[i * 4] / 16 : 255
    return { img: sheet, indexes, box: drawn(indexes, img.width, info), ...info }
  }
  /** What the frames really draw, a zoom has nothing to show around it. */
  function drawn(indexes: Uint8Array, sheetWidth: number, { width, height }: { width: number; height: number }): Box {
    let [left, top, right, bottom] = [width, height, 0, 0]
    indexes.forEach((index, i) => {
      if (index === 255) return
      const [x, y] = [(i % sheetWidth) % width, Math.floor(i / sheetWidth)]
      left = Math.min(left, x)
      right = Math.max(right, x + 1)
      top = Math.min(top, y)
      bottom = Math.max(bottom, y + 1)
    })
    return right > left ? { x: left, y: top, w: right - left, h: bottom - top } : { x: 0, y: 0, w: width, h: height }
  }

  const rgb = (hex: string) => [1, 3, 5].map((i) => parseInt(hex.slice(i, i + 2), 16))
  /** Paint the strip again from its colour numbers: at once, without asking the server. */
  $effect(() => {
    const s = strip
    const line = colors?.[palette]
    const shown = focus
    if (!s?.indexes || !line) return
    const sheet = s.img as HTMLCanvasElement
    const ctx = sheet.getContext('2d')!
    const picture = ctx.createImageData(sheet.width, sheet.height)
    const paint = line.map((hex, i) => {
      const [r, g, b] = rgb(hex)
      const grey = Math.round(0.3 * r + 0.59 * g + 0.11 * b)
      return !shown || shown.includes(i) ? [r, g, b] : [grey, grey, grey]
    })
    s.indexes.forEach((index, i) => {
      if (index === 255) return
      picture.data.set([...paint[index], 255], i * 4)
    })
    ctx.putImageData(picture, 0, 0)
    redraw?.()
  })

  function pick(e: MouseEvent) {
    const s = strip
    if (!s?.indexes || !onpick) return
    const box = (e.currentTarget as HTMLElement).getBoundingClientRect()
    const x = s.box.x + Math.floor(((e.clientX - box.left) / box.width) * s.box.w)
    const y = s.box.y + Math.floor(((e.clientY - box.top) / box.height) * s.box.h)
    const index = s.indexes[y * s.width * s.durations.length + shownFrame * s.width + x]
    onpick(index === undefined || index === 255 ? null : index)
  }

  function loadImage(src: string): Promise<HTMLImageElement> {
    return new Promise((resolve, reject) => {
      const img = new Image()
      img.onload = () => resolve(img)
      img.onerror = reject
      img.src = src
    })
  }

  let redraw: (() => void) | null = null
  let shownFrame = 0
  /** The edges of the selected colours' zones, in two colours that show on any sprite. */
  const OUTLINE = ['#ffffff', '#ff2fd0']
  const BLINK = 24
  let blink = 0
  function outline(ctx: CanvasRenderingContext2D, s: NonNullable<typeof strip>, frame: number, scale: number) {
    if (!s.indexes || !selected?.length) return
    const { indexes, box, width, durations } = s
    const chosen = new Set<number>(selected)
    const inside = (x: number, y: number) => x >= box.x && y >= box.y && x < box.x + box.w && y < box.y + box.h
      && chosen.has(indexes[y * width * durations.length + frame * width + x])
    const thick = Math.max(1, Math.floor(scale / 3))
    ctx.fillStyle = OUTLINE[blink % 2]
    for (let y = box.y; y < box.y + box.h; y++) {
      for (let x = box.x; x < box.x + box.w; x++) {
        if (!inside(x, y)) continue
        const [left, top] = [(x - box.x) * scale, (y - box.y) * scale]
        if (!inside(x - 1, y)) ctx.fillRect(left, top, thick, scale)
        if (!inside(x + 1, y)) ctx.fillRect(left + scale - thick, top, thick, scale)
        if (!inside(x, y - 1)) ctx.fillRect(left, top, scale, thick)
        if (!inside(x, y + 1)) ctx.fillRect(left, top + scale - thick, scale, thick)
      }
    }
  }
  $effect(() => {
    void selected
    redraw?.()
  })
  // Play the frames with the game's timings (1/60 s each), then wait a little and start again.
  $effect(() => {
    const s = strip
    const c = canvas
    const scale = zoom
    if (!s || !c) return
    const ctx = c.getContext('2d')
    if (!ctx) return
    let frame = Math.min(shownFrame, s.durations.length - 1)    // a zoom leaves the picture where it is
    let left = s.durations[frame] ?? 1
    let pause = 0
    let raf = 0
    let last = performance.now()
    let acc = 0
    let beat = 0
    const draw = () => {
      shownFrame = frame
      ctx.imageSmoothingEnabled = false
      ctx.clearRect(0, 0, c.width, c.height)
      const { x, y, w, h } = s.box
      ctx.drawImage(s.img, frame * s.width + x, y, w, h, 0, 0, w * scale, h * scale)
      outline(ctx, s, frame, scale)
    }
    draw()
    redraw = draw
    const tick = (now: number) => {
      acc += now - last
      last = now
      while (acc >= 1000 / 60) {
        acc -= 1000 / 60
        if (selected?.length && ++beat >= BLINK) {
          beat = 0
          blink++
          draw()
        }
        if (!playing) continue
        if (pause > 0) {
          pause--
          if (pause === 0) { frame = 0; left = s.durations[0] ?? 1; draw() }
          continue
        }
        if (--left <= 0) {
          if (frame + 1 < s.durations.length) {
            frame++
            left = s.durations[frame]
            draw()
          } else {
            pause = 40
          }
        }
      }
      raf = requestAnimationFrame(tick)
    }
    raf = requestAnimationFrame(tick)
    return () => cancelAnimationFrame(raf)
  })

  function weaponLabel(a: ClassAnimation): string {
    if (a.wtype) return t(`wtype.${a.wtype}`)
    return items.find((i) => i.id === a.item)?.name ?? a.item ?? ''
  }
</script>

{#if animations.length}
  <section class="panel">
    <h3>{t('banim.title')}</h3>
    <div class="weapons" role="radiogroup" aria-label={t('banim.weapon')}>
      {#each animations as a, i (i)}
        <button role="radio" aria-checked={chosen === i} class:active={chosen === i} onclick={() => (chosen = i)} title={a.name}>
          {weaponLabel(a)}{#if a.imported} ⭐{:else if a.changed} ✎{/if}
        </button>
      {/each}
    </div>
    <div class="player">
      <div class="stage" class:fixed={preview}>
        {#if strip}
          <canvas bind:this={canvas} class:pick={!!onpick} width={strip.box.w * zoom} height={strip.box.h * zoom} onclick={pick}></canvas>
        {:else if error}
          <span class="muted small">{t('banim.none')}</span>
        {:else}
          <span class="muted">…</span>
        {/if}
      </div>
      <div class="controls">
        <label>
          <span>{t('banim.mode')}</span>
          <select bind:value={mode}>
            {#each modes as m (m)}<option value={m}>{t(`banim.mode.${m}`)}</option>{/each}
          </select>
        </label>
        <label>
          <span>{t('banim.palette')}</span>
          <select bind:value={palette}>
            {#each PALETTES as p, i (p)}<option value={i}>{t(`banim.palette.${p}`)}</option>{/each}
          </select>
        </label>
        {#if preview}
          <label>
            <span>{t('banim.zoom')}</span>
            <input type="range" min="2" max="8" bind:value={zoom} />
          </label>
        {/if}
        <button onclick={() => (playing = !playing)}>{playing ? t('banim.pause') : t('banim.play')}</button>
      </div>
    </div>
    {#if anim?.changed && !preview}
      <p class="small">
        {#if anim.source}
          {t('banim.importedLabel')}
          <button class="link" title={t('banim.reopenHint')} onclick={() => { reopen = anim.source!; showLibrary = true; showLocal = false }}>{anim.name}</button>
        {:else}
          {anim.imported ? t('banim.importedFrom', { name: anim.name }) : t('banim.changedTo', { name: anim.name })}
        {/if}
        <button class="link" onclick={() => restore(anim)}>↺ {t('banim.restore')}</button>
        {#if anim.imported}<button class="link danger" onclick={() => removeImported(anim)}>✕ {t('banim.removeImported')}</button>{/if}
      </p>
    {/if}
    {#if !preview}
    <Help text={t('banim.hint')} />
    <div class="sources">
      <button class:active={showLibrary} onclick={() => { showLibrary = !showLibrary; showLocal = false }}>{t('banim.lib.title')}</button>
      <button class:active={showLocal} onclick={() => { showLocal = !showLocal; showLibrary = false }}>{t('banim.local.title')}</button>
    </div>
    {#if showLibrary}<AnimationLibrary initial={className} {classId} wtypes={wtypes} open={reopen} onimported={changed} />{/if}
    {#if showLocal}<LocalAnimationImport {classId} {wtypes} onimported={changed} />{/if}
    {/if}
  </section>
{/if}

<style>
  .weapons { display: flex; flex-wrap: wrap; gap: 0.3rem; margin-bottom: 0.6rem; }
  .weapons button.active { background: var(--header); color: var(--header-text); }
  .player { display: flex; gap: 1rem; align-items: flex-start; flex-wrap: wrap; }
  canvas.pick { cursor: crosshair; }
  .stage {
    min-width: 200px; min-height: 140px; max-width: 100%; overflow: auto; display: flex; align-items: center; justify-content: center;
    background: var(--accent-soft); border: 1px solid var(--border); border-radius: var(--radius);
  }
  .stage.fixed { width: 340px; height: 340px; }   /* a zoom leaves everything around it in place */
  .stage canvas { image-rendering: pixelated; display: block; margin: auto; flex: none; }
  .controls { display: flex; flex-direction: column; gap: 0.5rem; }
  .small { font-size: 0.8rem; margin: 0.5rem 0 0; }
  .sources { display: flex; flex-wrap: wrap; gap: 0.4rem; margin-top: 0.6rem; }
  .sources button.active { background: var(--accent-soft); border-color: var(--accent); }
</style>
