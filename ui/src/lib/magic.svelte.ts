/**
 * Strength and Magic split (game option strMagSplit, ticket 27): Magic is a stat of its own, "mag" in the bases,
 * growths, maximums and promotion gains. A missing value has a default, as the server's (decomp/strmag.py):
 * a class with a staff or magic rank takes its Strength figures, the others start at 0.
 */
import { t } from './i18n.svelte'

export const magicSplit = $state({ on: false })

const MAGIC_RANKS = ['staff', 'anima', 'light', 'dark']
const NON_MAGIC_GROWTH = 5 // a generic's Magic growth in a class without magic

type Stats = Record<string, number>
interface ClassLike { weaponRanks: Record<string, unknown>; bases: Stats; growths: Stats; maxes: Stats; promotionGains: Stats }
interface CharacterLike { bases: Stats; growths: Stats }

export const isMagicClass = (cls?: { weaponRanks: Record<string, unknown> }) =>
  !!cls && Object.keys(cls.weaponRanks ?? {}).some((rank) => MAGIC_RANKS.includes(rank))

/** A class's Magic: base, growth, maximum, promotion gain. */
export function classMagic(cls?: ClassLike): { bases: number; growths: number; maxes: number; promotionGains: number } {
  if (!cls) return { bases: 0, growths: 0, maxes: 20, promotionGains: 0 }
  const magic = isMagicClass(cls)
  return {
    bases: cls.bases.mag ?? (magic ? cls.bases.pow : 0),
    growths: cls.growths.mag ?? (magic ? cls.growths.pow : NON_MAGIC_GROWTH),
    maxes: cls.maxes.mag ?? cls.maxes.pow ?? 20,
    promotionGains: cls.promotionGains.mag ?? (magic ? cls.promotionGains.pow : 0),
  }
}

/** A character's Magic (added to its class's base, as the other stats). */
export function characterMagic(ch: CharacterLike, cls?: ClassLike): { bases: number; growths: number } {
  const magic = isMagicClass(cls)
  return {
    bases: ch.bases.mag ?? (magic ? ch.bases.pow : 0),
    growths: ch.growths.mag ?? (magic ? ch.growths.pow : Math.floor(ch.growths.pow / 4)),
  }
}

/** The stats shown, with Magic after Strength when the option is on. */
export const withMagic = <S extends string>(stats: readonly S[]): (S | 'mag')[] =>
  magicSplit.on ? stats.flatMap((s) => (s === 'pow' ? [s, 'mag' as const] : [s])) : [...stats]

/** A stat's short name: Strength alone when Magic is apart. */
export const statLabel = (stat: string) => t(magicSplit.on && stat === 'pow' ? 'stat.str' : `stat.${stat}`)
