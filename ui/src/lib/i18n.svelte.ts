import fr from '../locales/fr.json'
import en from '../locales/en.json'
import es from '../locales/es.json'
import it from '../locales/it.json'

const dictionaries: Record<string, Record<string, string>> = { fr, en, es, it }

/** Interface languages, with their own name (shown in the language picker). */
export const LANGUAGES = [
  { code: 'fr', name: 'Français' },
  { code: 'en', name: 'English' },
  { code: 'es', name: 'Español' },
  { code: 'it', name: 'Italiano' },
] as const
export type Lang = (typeof LANGUAGES)[number]['code']

export const i18n = $state({ lang: 'fr' as Lang })

/** Translate a key, replacing {placeholders} with params. Falls back to French, then the key. */
export function t(key: string, params: Record<string, string | number> = {}): string {
  const text = dictionaries[i18n.lang][key] ?? dictionaries.fr[key] ?? key
  return text.replace(/\{(\w+)\}/g, (_, name) => String(params[name] ?? `{${name}}`))
}

/** Text of a validation problem. `terrain` (a terrain id), `object` and `wtype` parameters are shown by their name. */
export function problemText(p: { code: string; params: Record<string, string | number> }): string {
  const params = { ...p.params }
  if (typeof params.terrain === 'number') params.terrain = t(`terrain.${params.terrain}`)
  if (typeof params.object === 'string') params.object = t(`maps.kind.${params.object}`)
  if (typeof params.wtype === 'string') params.wtype = t(`wtype.${params.wtype}`)
  return t(`problem.${p.code}`, params)
}
