// What an imported battle animation can be given for: a weapon type of the class, or a group of linked weapons
// (tickets 49, 51: the three tomes, the three throwing axes, set at once; one of them can still get its own).
// Server: banim_import.GROUPS.
import { t } from './i18n.svelte'

export const GROUPS: Record<string, string[]> = { tomes: ['anima', 'light', 'dark'], throwing_axes: ['axe'] }

/** FEditor's numbered weapon folders ("1. Sword", "6. Magic") -> weapon type or group. */
const FOLDER_WTYPES: [RegExp, string][] = [
  [/staff|staves/i, 'staff'], [/light/i, 'light'], [/dark|flux/i, 'dark'], [/magic|anima|tome/i, 'tomes'],
  [/hand ?axe|throw|tomahawk|hatchet/i, 'throwing_axes'], [/axe/i, 'axe'], [/bow|arrow/i, 'bow'], [/lance|spear|javelin/i, 'lance'], [/sword|blade|knife/i, 'sword'],
  [/unarmed|item|refresh|dance|play/i, 'item'],
]

export function animationTargets(wtypes: string[]): string[] {
  return [...Object.keys(GROUPS).filter((g) => GROUPS[g].some((w) => wtypes.includes(w))), ...wtypes]
}

export function guessTarget(folderName: string, wtypes: string[]): string {
  const found = FOLDER_WTYPES.find(([re]) => re.test(folderName))?.[1]
  return found && animationTargets(wtypes).includes(found) ? found : wtypes[0] ?? 'sword'
}

export function targetLabel(target: string): string {
  return target in GROUPS ? t(`banim.group.${target}`) : t(`wtype.${target}`)
}
