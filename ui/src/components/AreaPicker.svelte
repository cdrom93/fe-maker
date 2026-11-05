<script lang="ts">
  // A chapter's map where a rectangle of tiles is drawn by dragging (an area scene, ticket 151).
  import { chapterMapUrl } from '../lib/api'
  import { t } from '../lib/i18n.svelte'

  let { chapter, area, onchange }: {
    /** chapter index (its map is shown) */
    chapter: number
    /** x1, y1, x2, y2 */
    area: number[]
    onchange: (area: number[]) => void
  } = $props()

  const TILE = 16
  const MAX_WIDTH = 520
  let size = $state<{ w: number; h: number } | null>(null)
  let drag = $state<{ x: number; y: number; x2: number; y2: number } | null>(null)
  let el = $state<HTMLDivElement>()
  const scale = $derived(size ? Math.min(2, MAX_WIDTH / (size.w * TILE)) : 1)
  const cell = $derived(TILE * scale)
  const shown = $derived(drag
    ? [Math.min(drag.x, drag.x2), Math.min(drag.y, drag.y2), Math.max(drag.x, drag.x2), Math.max(drag.y, drag.y2)]
    : area)

  function tileAt(e: PointerEvent): [number, number] {
    const rect = el!.getBoundingClientRect()
    const x = Math.floor((e.clientX - rect.left) / cell)
    const y = Math.floor((e.clientY - rect.top) / cell)
    return [Math.max(0, Math.min((size?.w ?? 1) - 1, x)), Math.max(0, Math.min((size?.h ?? 1) - 1, y))]
  }

  function down(e: PointerEvent) {
    if (!size) return
    const [x, y] = tileAt(e)
    drag = { x, y, x2: x, y2: y }
    el?.setPointerCapture(e.pointerId)
  }

  function move(e: PointerEvent) {
    if (!drag) return
    const [x, y] = tileAt(e)
    drag = { ...drag, x2: x, y2: y }
  }

  function up() {
    if (!drag) return
    const next = shown
    drag = null
    onchange(next)
  }
</script>

<div class="picker">
  <p class="tiny muted">{t('dlg.areaDraw')}</p>
  <div
    class="map"
    role="application"
    aria-label={t('dlg.areaDraw')}
    bind:this={el}
    style:width={size ? `${size.w * cell}px` : 'auto'}
    style:height={size ? `${size.h * cell}px` : 'auto'}
    onpointerdown={down}
    onpointermove={move}
    onpointerup={up}
  >
    <img src={chapterMapUrl(chapter)} alt="" draggable="false"
         onload={(e) => { const img = e.currentTarget as HTMLImageElement; size = { w: img.naturalWidth / TILE, h: img.naturalHeight / TILE } }} />
    {#if size}
      <span class="area" style="left: {shown[0] * cell}px; top: {shown[1] * cell}px; width: {(shown[2] - shown[0] + 1) * cell}px; height: {(shown[3] - shown[1] + 1) * cell}px"></span>
    {/if}
  </div>
</div>

<style>
  .picker { display: flex; flex-direction: column; gap: 0.3rem; margin-top: 0.4rem; }
  .picker p { margin: 0; }
  .map { position: relative; cursor: crosshair; user-select: none; touch-action: none; max-width: 100%; }
  .map img { display: block; width: 100%; height: 100%; image-rendering: pixelated; pointer-events: none; }
  /* the same look as an area objective on the chapter map (ChapterEditor .area-marker) */
  .area { position: absolute; box-sizing: border-box; border: 3px dashed #e74c3c; background: rgb(231 76 60 / 0.15); pointer-events: none; }
</style>
