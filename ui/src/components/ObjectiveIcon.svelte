<script lang="ts">
  import { OBJECTIVE_ICONS, OBJECTIVE_SPRITES, SEIZE_TERRAIN } from '../lib/objectiveIcons'
  import { itemIconUrl, mapSpriteUrl } from '../lib/api'
  import { hideBroken } from '../lib/hideBroken'

  /** An objective type as the game's visuals (ticket 140): enemy map sprites for the fights, a fort for seizing, an item icon otherwise. */
  let { type }: { type: keyof typeof OBJECTIVE_ICONS } = $props()
  const sprites = $derived((OBJECTIVE_SPRITES as Record<string, readonly string[]>)[type])
</script>

<span class="objective-icon">
  {#if sprites}
    {#each sprites as cls, i (i)}<img class="pixel sprite" src={mapSpriteUrl(cls, 'enemy', true)} alt="" use:hideBroken />{/each}
    {#if type === 'defeat_boss'}<img class="pixel badge" src="/api/assets/boss-icon" alt="" use:hideBroken />{/if}
  {:else if type === 'seize'}
    <img class="pixel item" src={`/api/assets/terrain-icon/${SEIZE_TERRAIN}`} alt="" use:hideBroken />
  {:else}
    <img class="pixel item" src={itemIconUrl(OBJECTIVE_ICONS[type])} alt="" />
  {/if}
</span>

<style>
  .objective-icon { position: relative; display: inline-flex; align-items: flex-end; height: 20px; flex-shrink: 0; }
  .item { width: 20px; height: 20px; }
  .sprite { height: 20px; }
  .sprite + .sprite { margin-left: -8px; }
  .badge { position: absolute; right: -3px; bottom: 0; width: 9px; height: 9px; }
</style>
