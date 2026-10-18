import fr from '../locales/fr.json'
import en from '../locales/en.json'

const dictionaries: Record<string, Record<string, string>> = { fr, en }

export const i18n = $state({ lang: 'fr' as 'fr' | 'en' })

/** Translate a key, replacing {placeholders} with params. Falls back to French, then the key. */
export function t(key: string, params: Record<string, string | number> = {}): string {
  const text = dictionaries[i18n.lang][key] ?? dictionaries.fr[key] ?? key
  return text.replace(/\{(\w+)\}/g, (_, name) => String(params[name] ?? `{${name}}`))
}
