"use client";
import { useState } from "react";
import { useLang } from "@/lib/lang";
import { formatDate } from "@/lib/util";
import { Button, Card, Field, inputClass } from "./ui";

interface Props { suggestions: string[]; range?: [string, string]; busy: boolean; onConfirm: (date: string) => void }

/** Shown when the contract date is unknown: the engine never guesses it, the user confirms it. */
export default function DateGate({ suggestions, range, busy, onConfirm }: Props) {
  const { t, lang } = useLang();
  const [date, setDate] = useState("");
  return (
    <Card className="border-brand bg-brand-soft/40">
      <h2 className="text-lg font-bold">{t("gate.title")}</h2>
      <p className="mt-1 text-muted">{t("gate.body")}</p>
      <p className="mt-3 text-sm font-semibold">{suggestions.length ? t("gate.found") : t("gate.none")}</p>
      {suggestions.length > 0 && (
        <div className="mt-2 flex flex-wrap gap-2">
          {suggestions.map((d) => (
            <button key={d} type="button" onClick={() => setDate(d)} aria-pressed={date === d}
              className={`min-h-10 rounded-full border px-3 text-sm ${date === d ? "border-brand bg-brand text-brand-ink" : "border-line bg-surface"}`}>
              {formatDate(d, lang)}
            </button>
          ))}
        </div>
      )}
      <div className="mt-4 flex flex-wrap items-end gap-3">
        <div className="w-full sm:w-64">
          <Field label={t("gate.label")} hint={range ? t("gate.range", { from: range[0], to: range[1] }) : undefined}>
            <input type="date" value={date} onChange={(e) => setDate(e.target.value)} className={inputClass} />
          </Field>
        </div>
        <Button variant="primary" disabled={!date || busy} onClick={() => onConfirm(date)}>{t("gate.confirm")}</Button>
      </div>
    </Card>
  );
}
