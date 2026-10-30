<script lang="ts">
  // A short explanation kept out of the way: a small "i" that shows it on hover or keyboard focus. The bubble is
  // placed on the screen, so a scrolling panel does not cut it.
  let { text }: { text: string } = $props()

  const WIDTH = 288
  let place = $state<{ left: number; top: number; above: boolean } | null>(null)

  function show(e: Event) {
    const box = (e.currentTarget as HTMLElement).getBoundingClientRect()
    const above = box.bottom > window.innerHeight - 140
    place = {
      left: Math.max(8, Math.min(box.left + box.width / 2 - WIDTH / 2, window.innerWidth - WIDTH - 8)),
      top: above ? box.top - 6 : box.bottom + 6,
      above,
    }
  }
</script>

<button type="button" class="help-mark" aria-label={text} onclick={(e) => e.preventDefault()} onmouseenter={show} onmouseleave={() => (place = null)}
        onfocus={show} onblur={() => (place = null)}>i{#if place}<span class="bubble" class:above={place.above} style="left: {place.left}px; top: {place.top}px; width: {WIDTH}px">{text}</span>{/if}</button>

<style>
  .help-mark {
    display: inline-flex; align-items: center; justify-content: center; flex: none; width: 1.1em; height: 1.1em; padding: 0; min-height: 0;
    margin: 0 0.25em; vertical-align: 0.1em; border: 1px solid var(--border); border-radius: 50%; cursor: help;
    font-family: Georgia, serif; font-size: 0.75rem; font-style: italic; font-weight: 700; text-transform: none; letter-spacing: 0;
    color: var(--muted); background: var(--panel-2);
  }
  .help-mark:hover, .help-mark:focus { color: var(--text); border-color: var(--accent); outline: none; }
  .bubble {
    position: fixed; z-index: 100; padding: 0.5rem 0.7rem; border: 1px solid var(--border); border-radius: var(--radius);
    background: var(--panel); color: var(--text); box-shadow: 0 4px 16px rgb(0 0 0 / 35%);
    font-family: inherit; font-size: 0.8rem; font-style: normal; font-weight: 400; line-height: 1.35; text-align: left; white-space: normal; pointer-events: none;
  }
  .bubble.above { transform: translateY(-100%); }
</style>
