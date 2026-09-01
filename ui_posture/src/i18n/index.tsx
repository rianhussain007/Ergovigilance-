import { createContext, useContext, useState, useCallback, type ReactNode } from 'react';
import en from './en.json';
import hi from './hi.json';
import zh from './zh.json';

export type Locale = 'en' | 'hi' | 'zh';

const translations: Record<Locale, typeof en> = { en, hi, zh };

interface I18nContextValue {
  locale: Locale;
  setLocale: (locale: Locale) => void;
  t: (key: string) => string;
}

const I18nContext = createContext<I18nContextValue | null>(null);

/**
 * Simple dot-path translator: t("dashboard.title") → translations[locale].dashboard.title
 */
function getByPath(obj: Record<string, unknown>, path: string): string | undefined {
  return path.split('.').reduce<unknown>((acc, key) => {
    if (acc && typeof acc === 'object' && key in (acc as Record<string, unknown>)) {
      return (acc as Record<string, unknown>)[key];
    }
    return undefined;
  }, obj) as string | undefined;
}

export function I18nProvider({ children }: { children: ReactNode }) {
  const [locale, setLocale] = useState<Locale>(() => {
    try {
      return (localStorage.getItem('ergovigilance_locale') as Locale) || 'en';
    } catch {
      return 'en';
    }
  });

  const handleSetLocale = useCallback((l: Locale) => {
    setLocale(l);
    try { localStorage.setItem('ergovigilance_locale', l); } catch { /* ignore */ }
  }, []);

  const t = useCallback(
    (key: string): string => {
      return getByPath(translations[locale], key) ?? getByPath(translations.en, key) ?? key;
    },
    [locale],
  );

  return (
    <I18nContext.Provider value={{ locale, setLocale: handleSetLocale, t }}>
      {children}
    </I18nContext.Provider>
  );
}

export function useI18n(): I18nContextValue {
  const ctx = useContext(I18nContext);
  if (!ctx) throw new Error('useI18n must be used within an I18nProvider');
  return ctx;
}
