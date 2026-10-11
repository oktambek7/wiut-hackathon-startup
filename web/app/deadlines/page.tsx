"use client";
import { useState } from "react";
import * as api from "@/lib/api";
import { useLang } from "@/lib/lang";
import type { Clock, Step } from "@/lib/types";
import { errorKey, formatDate } from "@/lib/util";
import LetterDialog from "@/components/LetterDialog";
import { Button, Card, ErrorNote, Field, inputClass } from "@/components/ui";

export default function Deadlines() {
  const { t, lang } = useLang();
  const [claim, setClaim] = useState("");
  const [decision, setDecision] = useState("");
  const [clock, setClock] = useState<Clock | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [letter, setLetter] = useState<{ kind: string } | null>(null);

  async function go() {
    setError(null);
    if (!claim && !decision) return setError(t("dl.need"));
    try { setClock(await api.deadlines(claim, decision)); } catch (e) { setClock(null); setError(t(errorKey(e))); }
  }
  const step = (key: Step["key"]) => clock?.steps.find((s) => s.key === key);
  const notice = step("decision_notice"), pay = step("payment");

  return (
    <div className="mx-auto max-w-3xl space-y-6">
      <div className="space-y-2">
        <h1 className="text-3xl font-bold tracking-tight sm:text-4xl">{t("dl.title")}</h1>
        <p className="text-lg text-muted">{t("dl.sub")}</p>
      </div>
      <Card className="space-y-4">
        <div className="grid gap-4 sm:grid-cols-2">
          <Field label={t("dl.claim")}><input type="date" className={inputClass} value={claim} onChange={(e) => setClaim(e.target.value)} /></Field>
          <Field label={t("dl.decision")}><input type="date" className={inputClass} value={decision} onChange={(e) => setDecision(e.target.value)} /></Field>
        </div>
        <Button variant="primary" onClick={go}>{t("dl.go")}</Button>
        {error && <ErrorNote>{error}</ErrorNote>}
      </Card>

      {clock && (
        <div className="space-y-4">
          {notice && <Result step={notice} title={t("dl.notice")} lang={lang} action={<Button onClick={() => setLetter({ kind: "late_decision" })}>{t("dl.late.notice")}</Button>} />}
          {pay && <Result step={pay} title={t("dl.pay")} lang={lang} action={<Button onClick={() => setLetter({ kind: "late_payment" })}>{t("dl.late.pay")}</Button>} />}
          <p className="text-sm text-muted">{t("dl.week")}</p>
          {clock.caveats.length > 0 && (
            <Card className="border-miss bg-miss-bg">
              <h2 className="font-bold text-miss">{t("dl.caveats")}</h2>
              <ul className="mt-1 list-disc pl-5 text-miss">{clock.caveats.map((c) => <li key={c}>{c}</li>)}</ul>
            </Card>
          )}
        </div>
      )}
      <LetterDialog open={letter !== null} onClose={() => setLetter(null)}
        request={{ kind: letter?.kind, claim_date: claim || null, decision_date: decision || null }} />
    </div>
  );
}

function Result({ step, title, lang, action }: { step: Step; title: string; lang: string; action: React.ReactNode }) {
  const { t } = useLang();
  return (
    <Card className="space-y-2">
      <p className="text-sm font-semibold text-muted">{title}</p>
      <p className="text-3xl font-bold tracking-tight">{formatDate(step.due, lang)}</p>
      <p className="text-sm text-muted">{t("dl.rule")}: {step.reference} · {step.days} {step.unit === "working_days" ? t("unit.working_days") : t("unit.days")} · {formatDate(step.label_from, lang)} → {formatDate(step.due, lang)}</p>
      {step.source_quote && <p className="font-mono text-sm">{step.source_quote}</p>}
      {step.note && <p className="text-sm text-muted">{step.note}</p>}
      {step.skipped_holidays && step.skipped_holidays.length > 0 && (
        <p className="text-sm">{t("dl.skipped")}: {step.skipped_holidays.map((h) => `${formatDate(h.date, lang)} (${h.name})`).join("; ")}</p>
      )}
      <div className="flex flex-wrap items-center gap-3 pt-1">
        {action}
        <a href={step.source_url} target="_blank" rel="noreferrer" className="text-sm font-semibold text-brand underline">lex.uz</a>
      </div>
    </Card>
  );
}
