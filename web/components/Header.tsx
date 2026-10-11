"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useLang } from "@/lib/lang";
import { LANG_NAMES } from "@/lib/messages";
import type { Lang } from "@/lib/types";

export default function Header() {
  const { t, lang, setLang } = useLang();
  const path = usePathname();
  const links = [["/", t("nav.check")], ["/deadlines", t("nav.deadlines")], ["/insurer", t("nav.insurer")]] as const;
  return (
    <header className="sticky top-0 z-10 border-b border-line bg-bg/90 backdrop-blur">
      <div className="mx-auto flex max-w-6xl flex-wrap items-center gap-x-6 gap-y-2 px-4 py-3">
        <Link href="/" className="flex items-center gap-2 font-bold tracking-tight">
          <span aria-hidden className="grid size-8 place-items-center rounded-lg bg-brand text-brand-ink">P</span>
          PolisDiff
        </Link>
        <nav aria-label="Main" className="order-3 flex w-full gap-1 overflow-x-auto sm:order-none sm:w-auto sm:flex-1">
          {links.map(([href, label]) => {
            const active = href === "/" ? path === "/" : path.startsWith(href);
            return (
              <Link key={href} href={href} aria-current={active ? "page" : undefined}
                className={`whitespace-nowrap rounded-lg px-3 py-2 text-sm font-medium ${active ? "bg-brand-soft text-brand" : "text-muted hover:bg-surface-2"}`}>
                {label}
              </Link>
            );
          })}
        </nav>
        <label className="ml-auto">
          <span className="sr-only">{t("lang")}</span>
          <select value={lang} onChange={(e) => setLang(e.target.value as Lang)}
            className="min-h-11 rounded-lg border border-line bg-surface px-3 text-sm">
            {(Object.keys(LANG_NAMES) as Lang[]).map((l) => <option key={l} value={l}>{LANG_NAMES[l]}</option>)}
          </select>
        </label>
      </div>
    </header>
  );
}
