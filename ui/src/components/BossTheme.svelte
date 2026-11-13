<script lang="ts">
  // A character's boss theme: the song the battle screen plays when they fight (server: gBanimBossBGMs, music.py).
  import { api, type BattleMusic, type MusicLibrary, type SongRef } from '../lib/api'
  import { t } from '../lib/i18n.svelte'
  import SongPicker from './SongPicker.svelte'

  const NO_SONG = 0xffff

  let { characterId }: { characterId: string } = $props()

  let library = $state<MusicLibrary | null>(null)
  let battle = $state<BattleMusic | null>(null)
  let error = $state('')

  async function load() {
    try {
      ;[library, battle] = await Promise.all([api.musicLibrary(), api.battleMusic()])
    } catch (e) {
      error = String(e)
    }
  }
  load()

  async function set(song: SongRef | null) {
    error = ''
    try {
      await api.setBattleMusic({ character: characterId, song })
      battle = await api.battleMusic()
    } catch (e) {
      error = String(e)
    }
  }
</script>

{#if library && battle}
  <SongPicker label={t('music.bossTheme')} value={battle.bosses[characterId] ?? null}
              gameValue={battle.gameBosses[characterId] ?? NO_SONG} {library} optional onchange={set} />
{/if}
{#if error}<p class="bad">{error}</p>{/if}

<style>
  .bad { color: var(--bad); margin: 0.3rem 0 0; font-size: 0.8rem; }
</style>
