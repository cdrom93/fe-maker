/**
 * Skills (game option skills; server/fe_maker/decomp/skills.py, ported from C-SkillSys): the catalogue offered on
 * the character and class sheets, and the game's class abilities shown as skills.
 */
import { api } from './api'
import { magicSplit } from './magic.svelte'

export interface SkillEntry { id: string; kind: string; magic: boolean }
export interface GameSkill { id: string; abilities: string[]; classes: string[]; characters: string[] }
export interface SkillCatalogue { skills: SkillEntry[]; game: GameSkill[]; maxPerSheet: number }

export const skillsOption = $state({ on: false })
export const skillCatalogue = $state<SkillCatalogue>({ skills: [], game: [], maxPerSheet: 3 })

let loading: Promise<void> | null = null

/** Loads the catalogue once. */
export function loadSkills(): Promise<void> {
  loading ??= api.skills().then((c) => { Object.assign(skillCatalogue, c) }).catch(() => { loading = null })
  return loading
}

/** The skills a sheet can offer (Magic ones only with the split). */
export const offeredSkills = () => skillCatalogue.skills.filter((s) => !s.magic || magicSplit.on)

/** The game skills a unit has from its abilities (its own and its class's), its class and itself. */
export const gameSkills = (abilities: string[], classId?: string, characterId?: string) =>
  skillCatalogue.game.filter((g) => g.abilities.some((a) => abilities.includes(a)) || (!!classId && g.classes.includes(classId))
    || (!!characterId && (g.characters ?? []).includes(characterId)))
    .map((g) => g.id)

/** The ability boxes a unit's skills tick (ticket 46): the first ability of each game skill (Dance gives Dance, not Play);
 *  Supply opens the convoy ('convoy', the sheet's "Opens the convoy" box). */
export const abilitiesFromSkills = (skills: string[]) =>
  [...new Set(skills.flatMap((id) => (id === 'Supply' ? ['convoy']
    : (skillCatalogue.game.find((g) => g.id === id)?.abilities ?? []).slice(0, 1))))]

export const skillIcon = (id: string) => `/api/skills/${encodeURIComponent(id)}/icon.png`
