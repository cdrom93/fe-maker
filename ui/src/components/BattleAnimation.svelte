<script lang="ts">
  import { untrack } from 'svelte'
  import { api, animationUrl } from '../lib/api'
  import { t } from '../lib/i18n.svelte'
  import AnimationLibrary from './AnimationLibrary.svelte'
  import type { ClassAnimation, Item } from '../lib/types'

  /** The class's battle animations played as in the game (ticket 44), by weapon and mode. */
  let { classId, className, items, wtypes }: { classId: string; className: string; items: Item[]; wtypes: string[] } = $props()
  let showLibrary = $state(false)

  const MODES = ['stand', 'attack_close', 'attack_close_critical', 'attack_range', 'attack_range_critical', 'dodge_close', 'attack_miss'] as const
  const PALETTES = ['player', 'enemy', 'ally'] as const

  let animations = $state<ClassAnimation[]>([])
  let chosen = $state(0)
  let mode = $state<string>('attack_close')
  let palette = $state(0)
  let playing = $state(true)
  let strip = $state<{ img: HTMLImageElement; durations: number[]; width: number; height: number } | null>(null)
  let canvas = $state<HTMLCanvasElement | null>(null)
  let error = $state(false)

  function reload() {
    const id = classId
    api.classAnimations(id).then((list) => {
      if (id === classId) animations = list
    }).catch(() => {})
  }
  $effect(() => {
    void classId
    animations = []
    chosen = 0
    untrack(reload)
  })

  /** Back to the game's animation for this weapon type (an imported one stays in the project). */
  async function restore(a: ClassAnimation) {
    if (!a.wtype) return
    await api.setClassAnimation(classId, a.wtype, null)
    reload()
  }
  async function removeImported(a: ClassAnimation) {
    if (!a.ref.startsWith('new-')) return
    await api.removeAnimation(a.ref.slice(4))
    reload()
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
    error = false
    Promise.all([api.animationMode(number, m, pal), loadImage(animationUrl(number, m, pal))])
      .then(([info, img]) => {
        if (anim?.ref === number && palette === pal) strip = { img, ...info }
      })
      .catch(() => (error = true))
  })

  function loadImage(src: string): Promise<HTMLImageElement> {
    return new Promise((resolve, reject) => {
      const img = new Image()
      img.onload = () => resolve(img)
      img.onerror = reject
      img.src = src
    })
  }

  const SCALE = 2
  // Play the frames with the game's timings (1/60 s each), then wait a little and start again.
  $effect(() => {
    const s = strip
    const c = canvas
    if (!s || !c) return
    const ctx = c.getContext('2d')
    if (!ctx) return
    let frame = 0
    let left = s.durations[0] ?? 1
    let pause = 0
    let raf = 0
    let last = performance.now()
    let acc = 0
    const draw = () => {
      ctx.imageSmoothingEnabled = false
      ctx.clearRect(0, 0, c.width, c.height)
      ctx.drawImage(s.img, frame * s.width, 0, s.width, s.height, 0, 0, s.width * SCALE, s.height * SCALE)
    }
    draw()
    const tick = (now: number) => {
      acc += now - last
      last = now
      while (acc >= 1000 / 60) {
        acc -= 1000 / 60
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
      <div class="stage">
        {#if strip}
          <canvas bind:this={canvas} width={strip.width * SCALE} height={strip.height * SCALE}></canvas>
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
        <button onclick={() => (playing = !playing)}>{playing ? `⏸ ${t('banim.pause')}` : `▶ ${t('banim.play')}`}</button>
      </div>
    </div>
    {#if anim?.changed}
      <p class="small">
        {anim.imported ? t('banim.importedFrom', { name: anim.name }) : t('banim.changedTo', { name: anim.name })}
        <button class="link" onclick={() => restore(anim)}>↺ {t('banim.restore')}</button>
        {#if anim.imported}<button class="link danger" onclick={() => removeImported(anim)}>✕ {t('banim.removeImported')}</button>{/if}
      </p>
    {/if}
    <p class="muted small">{t('banim.hint')}</p>
    <button class="library-toggle" onclick={() => (showLibrary = !showLibrary)}>📚 {t('banim.lib.title')}</button>
    {#if showLibrary}<AnimationLibrary initial={className} {classId} wtypes={wtypes} onimported={reload} />{/if}
  </section>
{/if}

<style>
  .weapons { display: flex; flex-wrap: wrap; gap: 0.3rem; margin-bottom: 0.6rem; }
  .weapons button.active { background: var(--header); color: var(--header-text); }
  .player { display: flex; gap: 1rem; align-items: center; flex-wrap: wrap; }
  .stage {
    min-width: 200px; min-height: 140px; display: flex; align-items: center; justify-content: center;
    background: var(--accent-soft); border: 1px solid var(--border); border-radius: var(--radius);
  }
  .stage canvas { image-rendering: pixelated; display: block; }
  .controls { display: flex; flex-direction: column; gap: 0.5rem; }
  .small { font-size: 0.8rem; margin: 0.5rem 0 0; }
  .library-toggle { margin-top: 0.6rem; }
</style>
