<script lang="ts">
  import { OBJECTIVE_ICONS, OBJECTIVE_SPRITES } from '../lib/objectiveIcons'
  import { itemIconUrl, mapSpriteUrl } from '../lib/api'
  import { hideBroken } from '../lib/hideBroken'

  /** An objective type as the game's visuals: enemy map sprites for the fights (ticket 140), an item icon otherwise. */
  let { type }: { type: keyof typeof OBJECTIVE_ICONS } = $props()
  const sprites = $derived((OBJECTIVE_SPRITES as Record<string, readonly string[]>)[type])
</script>

<span class="objective-icon">
  {#if sprites}
    {#each sprites as cls, i (i)}<img class="pixel sprite" src={mapSpriteUrl(cls, 'enemy', true)} alt="" use:hideBroken />{/each}
    {#if type === 'defeat_boss'}<img class="pixel badge" src={itemIconUrl(OBJECTIVE_ICONS[type])} alt="" />{/if}
  {:else}
    <img class="pixel item" src={itemIconUrl(OBJECTIVE_ICONS[type])} alt="" />
  {/if}
</span>

<style>
  .objective-icon { position: relative; display: inline-flex; align-items: flex-end; height: 20px; flex-shrink: 0; }
  .item { width: 20px; height: 20px; }
  .sprite { height: 20px; }
  .sprite + .sprite { margin-left: -8px; }
  .badge { position: absolute; right: -6px; bottom: -3px; width: 12px; height: 12px; }
</style>
