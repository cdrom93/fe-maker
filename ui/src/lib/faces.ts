import { t } from './i18n.svelte'
import type { Character, DialogueFace } from './types'

/** What a portrait is called: the character who wears it in the project, else its own name (ticket 94). */
export function faceName(fid: string, faces: DialogueFace[], characters: Character[]): string {
  const face = faces.find((f) => f.id === fid)
  if (face?.active) return t('dlg.activeFace')
  const wearer = face && characters.find((c) => c.id.startsWith('CHARACTER_') && c.portraitId === face.portrait)
  return wearer?.name || face?.name || fid.replace('FID_', '').replace(/([a-z])([A-Z])/g, '$1 $2')
}
