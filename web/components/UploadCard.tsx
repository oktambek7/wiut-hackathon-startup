"use client";
import { useEffect, useRef, useState } from "react";
import { useLang } from "@/lib/lang";
import type { Key } from "@/lib/messages";
import type { Sample } from "@/lib/types";
import { Button, Card, Field, inputClass } from "./ui";
import { mbOf } from "@/lib/util";

interface Props {
  maxBytes: number; busy: boolean; stage: number; detail?: string;
  ai: boolean; onAi: (on: boolean) => void;
  onRun: (file: File, date: string) => void;
}
const CASES = ["match", "sum_conflict", "payment_conflict", "notice_conflict", "omission"];

export default function UploadCard({ maxBytes, busy, stage, detail, ai, onAi, onRun }: Props) {
  const { t } = useLang();
  const input = useRef<HTMLInputElement>(null);
  const [file, setFile] = useState<File | null>(null);
  const [date, setDate] = useState("");
  const [over, setOver] = useState(false);
  const [problem, setProblem] = useState<Key | null>(null);
  const [samples, setSamples] = useState<Sample[]>([]);

  useEffect(() => { fetch("/samples/index.json").then((r) => r.json()).then(setSamples).catch(() => setSamples([])); }, []);

  function pick(f: File | undefined | null) {
    setProblem(null);
    if (!f) return;
    if (!/\.pdf$/i.test(f.name) && f.type !== "application/pdf") return setProblem("err.pdf");
    if (f.size > maxBytes) return setProblem("err.big");
    setFile(f);
  }
  async function useSample(s: Sample) {
    const blob = await (await fetch(s.file)).blob();
    const f = new File([blob], s.file.split("/").pop() ?? "sample.pdf", { type: "application/pdf" });
    setFile(f); setDate(s.applicable_date); setProblem(null);
    onRun(f, s.applicable_date);
  }
  const shown = samples.filter((s) => CASES.includes(s.case));
  const prefix: Record<string, Key> = { "uz-Latn": "sample.uz", en: "sample.en", mixed: "sample.mixed" };

  return (
    <Card className="space-y-5">
      <div
        role="button" tabIndex={0} aria-label={t("drop.title")}
        onClick={() => input.current?.click()}
        onKeyDown={(e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); input.current?.click(); } }}
        onDragOver={(e) => { e.preventDefault(); setOver(true); }} onDragLeave={() => setOver(false)}
        onDrop={(e) => { e.preventDefault(); setOver(false); pick(e.dataTransfer.files[0]); }}
        className={`flex cursor-pointer flex-col items-center gap-2 rounded-2xl border-2 border-dashed px-4 py-10 text-center transition-colors ${over ? "border-brand bg-brand-soft" : "border-line bg-surface-2 hover:border-brand"}`}>
        <span aria-hidden className="text-3xl text-brand">⇪</span>
        <strong className="text-lg">{file ? file.name : t("drop.title")}</strong>
        <span className="text-sm text-muted">{t("drop.hint", { mb: mbOf(maxBytes) })}</span>
        <input ref={input} type="file" accept="application/pdf,.pdf" hidden onChange={(e) => pick(e.target.files?.[0])} />
      </div>
      {problem && <p role="alert" className="text-attn">{t(problem, { mb: mbOf(maxBytes) })}</p>}

      <Field label={t("date.label")} hint={t("date.help")}>
        <input type="date" value={date} onChange={(e) => setDate(e.target.value)} className={inputClass} />
      </Field>

      <label className="flex cursor-pointer items-start gap-3 rounded-xl border border-line bg-surface-2 p-3">
        <input type="checkbox" checked={ai} onChange={(e) => onAi(e.target.checked)} disabled={busy}
          className="mt-1 size-5 accent-[var(--color-brand)]" />
        <span>
          <span className="font-semibold">{t("ai.toggle")}</span>
          <span className="block text-sm text-muted">{t("ai.hint")}</span>
        </span>
      </label>

      <div className="flex flex-wrap items-center gap-3">
        <Button variant="primary" disabled={!file || busy} onClick={() => file && onRun(file, date)} className="flex-1 sm:min-w-56 sm:flex-none">
          {busy ? t("btn.checking") : t("btn.check")}
        </Button>
        {busy && (
          <ol className="flex flex-wrap gap-x-4 text-sm text-muted" aria-live="polite">
            {([1, 2, 3] as const).map((n) => (
              <li key={n} className={stage >= n ? "font-semibold text-ink" : ""}>{stage >= n ? "● " : "○ "}{t(`progress.${n}` as Key)}</li>
            ))}
          </ol>
        )}
      </div>
      {busy && detail && <p className="text-sm font-medium text-brand" aria-live="polite">{detail}</p>}

      {shown.length > 0 && (
        <div>
          <p className="text-sm"><strong>{t("samples.title")}</strong> <span className="text-muted">{t("samples.note")}</span></p>
          <div className="mt-2 flex flex-wrap gap-2">
            {shown.map((s) => (
              <button key={s.id} type="button" disabled={busy} onClick={() => useSample(s)}
                className="min-h-10 rounded-full border border-line bg-surface px-3 text-sm hover:border-brand disabled:opacity-50">
                {prefix[s.language] ? `${t(prefix[s.language])} · ` : ""}{t(`sample.${s.case}` as Key)}
              </button>
            ))}
          </div>
        </div>
      )}
    </Card>
  );
}
