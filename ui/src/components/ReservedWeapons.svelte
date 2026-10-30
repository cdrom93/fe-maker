<script lang="ts">
  import { itemIconUrl } from '../lib/api'
  import { t } from '../lib/i18n.svelte'
  import type { Item } from '../lib/types'
  import Mention from './Mention.svelte'

  // Reminder of the reserved weapons a character or a class may wield.
  let {
    items,
    characterId = null,
    classId = null,
    className = '',
  }: { items: Item[]; characterId?: string | null; classId?: string | null; className?: string } = $props()

  const direct = $derived(characterId ? items.filter((i) => i.reservedFor?.characters.includes(characterId)) : [])
  const viaClass = $derived(
    classId ? items.filter((i) => i.reservedFor?.classes.includes(classId) && !direct.includes(i)) : [],
  )
</script>

{#if direct.length || viaClass.length}
  <div class="reserved">
    <span class="muted">{t('reserve.reminder')}</span>
    {#each direct as i (i.id)}
      <Mention kind="items" id={i.id}><img class="pixel" src={itemIconUrl(i.iconId)} alt="" />{i.name}</Mention>
    {/each}
    {#each viaClass as i (i.id)}
      <span title={t('reserve.viaClass', { name: className })}><Mention kind="items" id={i.id}><img class="pixel" src={itemIconUrl(i.iconId)} alt="" />{i.name}</Mention>{#if characterId}<span class="muted"> ({t('reserve.viaClassShort')})</span>{/if}</span>
    {/each}
  </div>
{/if}

<style>
  .reserved { display: flex; flex-wrap: wrap; align-items: center; gap: 0.4rem 0.75rem; font-size: 0.85rem; }
  img { width: 16px; height: 16px; }
</style>
