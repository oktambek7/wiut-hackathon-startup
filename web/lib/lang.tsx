"use client";
import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import { MESSAGES, type Key } from "./messages";
import type { Lang } from "./types";

type Vars = Record<string, string | number>;
interface Ctx { lang: Lang; setLang: (l: Lang) => void; t: (key: Key, vars?: Vars) => string }
const LangContext = createContext<Ctx | null>(null);
const STORAGE = "polisdiff-lang";
const LANGS: Lang[] = ["ru", "uz-Latn", "uz-Cyrl", "en"];

export function LangProvider({ children }: { children: ReactNode }) {
  const [lang, setLangState] = useState<Lang>("ru");
  useEffect(() => {
    try {
      const saved = localStorage.getItem(STORAGE) as Lang | null;
      if (saved && LANGS.includes(saved)) setLangState(saved);
    } catch { /* storage may be blocked */ }
  }, []);
  useEffect(() => { document.documentElement.lang = lang; }, [lang]);
  const setLang = useCallback((l: Lang) => {
    setLangState(l);
    try { localStorage.setItem(STORAGE, l); } catch { /* ignore */ }
  }, []);
  const t = useCallback((key: Key, vars?: Vars) => {
    const text = MESSAGES[lang][key] ?? MESSAGES.en[key];
    return vars ? text.replace(/\{(\w+)\}/g, (_, k) => String(vars[k] ?? `{${k}}`)) : text;
  }, [lang]);
  const value = useMemo(() => ({ lang, setLang, t }), [lang, setLang, t]);
  return <LangContext.Provider value={value}>{children}</LangContext.Provider>;
}

export function useLang(): Ctx {
  const ctx = useContext(LangContext);
  if (!ctx) throw new Error("useLang outside LangProvider");
  return ctx;
}
