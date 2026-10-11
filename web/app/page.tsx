"use client";
import { useCallback, useEffect, useRef, useState } from "react";
import * as api from "@/lib/api";
import { useLang } from "@/lib/lang";
import type { Catalogue, CheckResponse, View } from "@/lib/types";
import { errorKey, mbOf } from "@/lib/util";
import UploadCard from "@/components/UploadCard";
import DateGate from "@/components/DateGate";
import Verdict from "@/components/Verdict";
import { Button, ErrorNote } from "@/components/ui";

export default function Home() {
  const { t, lang } = useLang();
  const [cat, setCat] = useState<Catalogue | null>(null);
  const [file, setFile] = useState<File | null>(null);
  const [data, setData] = useState<CheckResponse | null>(null);
  const [view, setView] = useState<View | null>(null);
  const [busy, setBusy] = useState(false);
  const [stage, setStage] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const timers = useRef<number[]>([]);

  useEffect(() => { api.catalogue().then(setCat).catch(() => undefined); }, []);

  // Switching language re-renders the verdict text from the report; the PDF is not re-read.
  useEffect(() => {
    if (!data || view?.language === lang) return;
    api.localize(data.report, lang).then(setView).catch(() => undefined);
  }, [lang, data, view?.language]);

  const run = useCallback(async (f: File, date: string) => {
    setBusy(true); setError(null); setFile(f); setStage(1);
    timers.current.forEach(clearTimeout);
    timers.current = [window.setTimeout(() => setStage(2), 1500), window.setTimeout(() => setStage(3), 3500)];
    try {
      const res = await api.check(f, lang, date);
      setData(res); setView(res.view);
    } catch (e) {
      setError(t(errorKey(e), { mb: cat ? mbOf(cat.max_upload_bytes) : 10 }));
    } finally {
      timers.current.forEach(clearTimeout);
      setBusy(false); setStage(0);
    }
  }, [lang, t, cat]);

  const needsDate = view?.checks.every((c) => c.pending_date) ?? false;
  const reset = () => { setData(null); setView(null); setFile(null); setError(null); };

  if (data && view) {
    return (
      <div className="space-y-6">
        <div className="no-print flex flex-wrap gap-2">
          <Button onClick={reset}>← {t("btn.another")}</Button>
        </div>
        {needsDate && (
          <DateGate suggestions={data.suggested_dates} range={cat?.supported_date_range} busy={busy}
            onConfirm={(d) => file && run(file, d)} />
        )}
        {error && <ErrorNote>{error}</ErrorNote>}
        <Verdict data={data} view={view} file={file} />
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-3xl space-y-8">
      <div className="space-y-3 pt-4">
        <h1 className="text-4xl font-bold tracking-tight sm:text-5xl">{t("home.title")}</h1>
        <p className="text-lg text-muted">{t("home.sub")}</p>
        <ol className="flex flex-wrap gap-x-6 gap-y-1 pt-2 text-sm font-semibold text-muted" aria-label={t("home.how.title")}>
          {([1, 2, 3] as const).map((n) => (
            <li key={n} className="flex items-center gap-2">
              <span className="grid size-6 place-items-center rounded-full bg-brand-soft text-brand">{n}</span>{t(`step.${n}`)}
            </li>
          ))}
        </ol>
      </div>
      <UploadCard maxBytes={cat?.max_upload_bytes ?? 4 * 1024 * 1024} busy={busy} stage={stage} onRun={run} />
      {error && <ErrorNote>{error}</ErrorNote>}
    </div>
  );
}
