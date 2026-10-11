"use client";
import { useLang } from "@/lib/lang";

export default function Footer() {
  const { t, lang } = useLang();
  return (
    <footer className="border-t border-line py-6 text-sm text-muted">
      <div className="mx-auto max-w-6xl space-y-1 px-4">
        <p>{t("trust")}</p>
        <p>{t("foot.legal")}</p>
        {lang.startsWith("uz") && <p>{t("foot.uz")}</p>}
      </div>
    </footer>
  );
}
