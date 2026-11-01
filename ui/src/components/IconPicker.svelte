<script lang="ts">
  import { itemIconUrl } from '../lib/api'

  let { count, current, onpick }: { count: number; current: number; onpick: (icon: number) => void } = $props()
</script>

<div class="icons">
  {#each { length: count } as _, icon (icon)}
    <button class:current={icon === current} onclick={() => onpick(icon)}>
      <img class="pixel" src={itemIconUrl(icon)} alt="" loading="lazy" />
    </button>
  {/each}
</div>

<style>
  .icons { display: grid; grid-template-columns: repeat(auto-fill, 2.25rem); gap: 0.25rem; max-height: 13rem; overflow-y: auto; padding: 0.25rem; }
  button { width: 2.25rem; height: 2.25rem; padding: 0.25rem; display: flex; align-items: center; justify-content: center; }
  button.current { outline: 2px solid var(--accent); }
  img { width: 100%; height: 100%; }
</style>
