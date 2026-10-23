<script lang="ts">
  import { itemIconUrl } from '../lib/api'
  import { t } from '../lib/i18n.svelte'

  /** One weapon triangle: each type beats the next one (types[0] beats types[1]...). */
  let {
    title,
    types,
    advantage,
    onchange,
  }: {
    title: string
    types: { id: string; color: string; iconId: number | undefined }[]
    /** bonus of `attacker` against `defender` (the engine gives the defender the opposite) */
    advantage: (attacker: string, defender: string) => { hit: number; damage: number }
    onchange: (attacker: string, defender: string, hit: number, damage: number) => void
  } = $props()

  const W = 440
  const H = 352
  const CX = W / 2
  const CY = 160
  const R = 100 // circle the three badges sit on
  const LABEL_R = R + 62 // values sit outside the circle, next to their arrow
  const ANGLES = [-90, 30, 150] // top, bottom right, bottom left
  const GAP = 24 // degrees left free around each badge
  const uid = Math.random().toString(36).slice(2, 8)

  const rad = (deg: number) => (deg * Math.PI) / 180
  const point = (deg: number, r = R) => ({ x: CX + r * Math.cos(rad(deg)), y: CY + r * Math.sin(rad(deg)) })

  function arc(i: number): string {
    const from = point(ANGLES[i] + GAP)
    const to = point(ANGLES[i] + 120 - GAP)
    return `M ${from.x} ${from.y} A ${R} ${R} 0 0 1 ${to.x} ${to.y}`
  }

  function clamp(v: number) {
    return Math.max(-128, Math.min(127, Math.round(v) || 0))
  }
</script>

<figure>
  <figcaption>{title}</figcaption>
  <div class="diagram" style="width: {W}px; height: {H}px">
    <svg viewBox="0 0 {W} {H}" width={W} height={H} aria-hidden="true">
      <defs>
        {#each types as a, i (a.id)}
          {@const b = types[(i + 1) % 3]}
          {@const p = point(ANGLES[i])}
          {@const q = point(ANGLES[i] + 120)}
          <linearGradient id="g-{uid}-{i}" gradientUnits="userSpaceOnUse" x1={p.x} y1={p.y} x2={q.x} y2={q.y}>
            <stop offset="0.15" stop-color={a.color} />
            <stop offset="0.85" stop-color={b.color} />
          </linearGradient>
          <marker id="m-{uid}-{i}" viewBox="0 0 10 10" refX="6" refY="5" markerWidth="4.2" markerHeight="4.2" orient="auto-start-reverse">
            <path d="M 0 0 L 10 5 L 0 10 z" fill={b.color} />
          </marker>
        {/each}
      </defs>
      {#each types as _, i (i)}
        <path d={arc(i)} fill="none" stroke="url(#g-{uid}-{i})" stroke-width="9" stroke-linecap="round" marker-end="url(#m-{uid}-{i})" />
      {/each}
      {#each types as a, i (a.id)}
        {@const p = point(ANGLES[i])}
        <g transform="translate({p.x} {p.y})">
          <rect x="-25" y="-25" width="50" height="50" rx="7" transform="rotate(45)" fill={a.color} stroke="white" stroke-width="2.5" />
        </g>
      {/each}
    </svg>

    {#each types as a, i (a.id)}
      {@const p = point(ANGLES[i])}
      <span class="badge" style="left: {p.x}px; top: {p.y}px">
        {#if a.iconId !== undefined}<img src={itemIconUrl(a.iconId)} alt="" />{/if}
      </span>
      <span class="type" style="left: {p.x}px; top: {p.y + (i === 0 ? -46 : 44)}px">{t(`wtype.${a.id}`)}</span>
    {/each}

    {#each types as a, i (a.id)}
      {@const b = types[(i + 1) % 3]}
      {@const v = advantage(a.id, b.id)}
      {@const m = point(ANGLES[i] + 60, LABEL_R)}
      <div class="bonus" style="left: {m.x}px; top: {m.y}px" title={t('combat.arrowHint', { a: t(`wtype.${a.id}`), b: t(`wtype.${b.id}`) })}>
        <label>
          <span>{t('field.hit')}</span>
          <input type="number" min="-128" max="127" value={v.hit} onchange={(e) => onchange(a.id, b.id, clamp(+(e.target as HTMLInputElement).value), v.damage)} />
        </label>
        <label>
          <span>{t('combat.damage')}</span>
          <input type="number" min="-128" max="127" value={v.damage} onchange={(e) => onchange(a.id, b.id, v.hit, clamp(+(e.target as HTMLInputElement).value))} />
        </label>
      </div>
    {/each}
  </div>
</figure>

<style>
  figure { margin: 0; display: flex; flex-direction: column; align-items: center; gap: 0.25rem; }
  figcaption { font-weight: 600; font-size: 0.9rem; }
  .diagram { position: relative; }
  svg { position: absolute; inset: 0; }
  .badge, .type, .bonus { position: absolute; transform: translate(-50%, -50%); }
  .badge { width: 32px; height: 32px; display: grid; place-items: center; pointer-events: none; }
  .badge img { width: 32px; height: 32px; image-rendering: pixelated; filter: drop-shadow(0 1px 1px rgb(0 0 0 / 0.5)); }
  .type { font-size: 0.8rem; font-weight: 600; white-space: nowrap; }
  .bonus {
    display: flex; flex-direction: column; gap: 0.15rem; padding: 0.3rem 0.45rem;
    background: var(--panel); border: 1px solid var(--border); border-radius: 8px; font-size: 0.72rem;
    box-shadow: 0 1px 3px rgb(0 0 0 / 0.15);
  }
  .bonus label { display: flex; flex-direction: row; align-items: center; justify-content: space-between; gap: 0.35rem; color: var(--muted); }
  .bonus input { width: 3.4em; padding: 0.1em 0.25em; font-size: 0.8rem; text-align: right; }
</style>
