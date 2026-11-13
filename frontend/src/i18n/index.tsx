import { createContext, useContext, useState, useEffect, type ReactNode } from 'react'
import type { Lang, TranslationKey, Translations } from './types'
import vi from './vi'
import en from './en'

const dictionaries: Record<Lang, Translations> = { vi, en }

const STORAGE_KEY = 'gp_lang'

// Exported for non-React code (api.ts) that needs the current language.
export function getStoredLang(): Lang {
  try {
    const v = localStorage.getItem(STORAGE_KEY)
    if (v === 'en' || v === 'vi') return v
  } catch { /* ignore */ }
  return 'vi'
}

function interpolate(template: string, params?: Record<string, string | number>): string {
  if (!params) return template
  return Object.entries(params).reduce(
    (s, [k, v]) => s.split(`{{${k}}}`).join(String(v)),
    template,
  )
}

// Standalone translate for non-React code (api.ts)
export function translate(key: TranslationKey, params?: Record<string, string | number>): string {
  const lang = getStoredLang()
  return interpolate(dictionaries[lang][key] ?? key, params)
}

interface LanguageContextValue {
  lang: Lang
  setLang: (l: Lang) => void
  t: (key: TranslationKey, params?: Record<string, string | number>) => string
}

const LanguageContext = createContext<LanguageContextValue | null>(null)

export function LanguageProvider({ children }: { children: ReactNode }) {
  const [lang, setLangState] = useState<Lang>(getStoredLang)

  function setLang(l: Lang) {
    setLangState(l)
    try { localStorage.setItem(STORAGE_KEY, l) } catch { /* ignore */ }
  }

  useEffect(() => {
    document.documentElement.lang = lang
  }, [lang])

  function t(key: TranslationKey, params?: Record<string, string | number>): string {
    return interpolate(dictionaries[lang][key] ?? key, params)
  }

  return (
    <LanguageContext.Provider value={{ lang, setLang, t }}>
      {children}
    </LanguageContext.Provider>
  )
}

export function useT() {
  const ctx = useContext(LanguageContext)
  if (!ctx) throw new Error('useT must be used within LanguageProvider')
  return ctx.t
}

export function useLanguage() {
  const ctx = useContext(LanguageContext)
  if (!ctx) throw new Error('useLanguage must be used within LanguageProvider')
  return { lang: ctx.lang, setLang: ctx.setLang }
}
