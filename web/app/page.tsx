"use client";
import { useCallback, useEffect, useRef, useState } from "react";
import * as api from "@/lib/api";
import { MODEL_ID, rankPassages, type AIProgress } from "@/lib/browserAI";
import { useLang } from "@/lib/lang";
import type { Catalogue, CheckResponse, View } from "@/lib/types";
import { errorKey, mbOf } from "@/lib/util";
import UploadCard from "@/components/UploadCard";
import DateGate from "@/components/DateGate";
import Verdict from "@/components/Verdict";
import { Button, ErrorNote } from "@/components/ui";

const AI_PREF = "polisdiff-browser-ai";

export default function Home() {
  const { t, lang } = useLang();
  const [cat, setCat] = useState<Catalogue | null>(null);
  const [file, setFile] = useState<File | null>(null);
  const [data, setData] = useState<CheckResponse | null>(null);
  const [view, setView] = useState<View | null>(null);
  const [busy, setBusy] = useState(false);
  const [stage, setStage] = useState(0);
  const [detail, setDetail] = useState<string | undefined>();
  const [ai, setAi] = useState(true);
  const [notice, setNotice] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const progressRef = useRef<(p: AIProgress) => void>(() => undefined);

  useEffect(() => {
    api.catalogue().then(setCat).catch(() => undefined);
    // Default: on for desktops, off for touch devices (the model download is ~120 MB). The choice is remembered.
    try {
      const saved = localStorage.getItem(AI_PREF);
      setAi(saved === null ? !window.matchMedia("(pointer: coarse)").matches : saved === "1");
    } catch { /* storage may be blocked */ }
  }, []);
  const chooseAi = (on: boolean) => { setAi(on); try { localStorage.setItem(AI_PREF, on ? "1" : "0"); } catch { /* ignore */ } };

  progressRef.current = (p: AIProgress) => {
    if (p.phase === "download") setDetail(t("ai.download", { pct: p.total ? Math.min(100, Math.round((p.loaded / p.total) * 100)) : 0 }));
    else setDetail(t("ai.embed", { done: p.done, total: p.total }));
  };

  // Switching language re-renders the verdict text from the report; the PDF is not re-read.
  useEffect(() => {
    if (!data || view?.language === lang) return;
    api.localize(data.report, lang).then(setView).catch(() => undefined);
  }, [lang, data, view?.language]);

  const run = useCallback(async (f: File, date: string) => {
    setBusy(true); setError(null); setNotice(null); setFile(f); setStage(1); setDetail(undefined);
    try {
      let browser: { ranking: Record<string, string[]>; model: string } | undefined;
      if (ai) {
        try {
          const info = await api.passages(f);
          setStage(2);
          const ranked = await rankPassages(info.passages, info.queries, (p) => progressRef.current(p));
          browser = { ranking: ranked.ranking, model: MODEL_ID };
        } catch (e) {
          if (e instanceof api.ApiError) throw e;   // the PDF itself failed; report that
          setNotice(t("ai.failed"));               // model could not run here; continue with keywords
        }
      }
      setStage(3); setDetail(undefined);
      const res = await api.check(f, lang, date, browser ? "hybrid" : "lexical", browser);
      setData(res); setView(res.view);
    } catch (e) {
      setError(t(errorKey(e), { mb: cat ? mbOf(cat.max_upload_bytes) : 10 }));
    } finally {
      setBusy(false); setStage(0); setDetail(undefined);
    }
  }, [ai, lang, t, cat]);

  const needsDate = view?.checks.every((c) => c.pending_date) ?? false;
  const reset = () => { setData(null); setView(null); setFile(null); setError(null); setNotice(null); };

  if (data && view) {
    return (
      <div className="space-y-6">
        <div className="no-print flex flex-wrap gap-2">
          <Button onClick={reset}>← {t("btn.another")}</Button>
        </div>
        {notice && <p className="rounded-xl bg-miss-bg px-4 py-3 text-miss">{notice}</p>}
        {needsDate && (
          <div id="date-gate">
            <DateGate suggestions={data.suggested_dates} range={cat?.supported_date_range} busy={busy} onConfirm={(d) => file && run(file, d)} />
          </div>
        )}
        {busy && detail && <p className="text-sm font-medium text-brand" aria-live="polite">{detail}</p>}
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
      <UploadCard maxBytes={cat?.max_upload_bytes ?? 4 * 1024 * 1024} busy={busy} stage={stage} detail={detail}
        ai={ai} onAi={chooseAi} onRun={run} />
      {error && <ErrorNote>{error}</ErrorNote>}
    </div>
  );
}
