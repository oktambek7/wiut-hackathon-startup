"use client";
import { useEffect, useRef, useState } from "react";
import * as api from "@/lib/api";
import { useLang } from "@/lib/lang";
import { download, errorKey } from "@/lib/util";
import type { Letter } from "@/lib/types";
import { Button, ErrorNote, Field, inputClass } from "./ui";

interface Props { open: boolean; onClose: () => void; request: Record<string, unknown> }

export default function LetterDialog({ open, onClose, request }: Props) {
  const { t, lang } = useLang();
  const ref = useRef<HTMLDialogElement>(null);
  const [fields, setFields] = useState({ insurer: "", name: "", policy: "" });
  const [letter, setLetter] = useState<Letter | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    const d = ref.current;
    if (!d) return;
    if (open && !d.open) d.showModal();
    if (!open && d.open) d.close();
  }, [open]);
  useEffect(() => {
    if (!open) return;
    let cancelled = false;
    const body = { ...request, language: lang, insurer: fields.insurer || "[insurer]", name: fields.name || "[your name]", policy: fields.policy || "[number]" };
    api.letter(body).then((l) => { if (!cancelled) { setLetter(l); setError(null); } })
      .catch((e) => { if (!cancelled) setError(t(errorKey(e))); });
    return () => { cancelled = true; };
  }, [open, request, lang, fields, t]);

  return (
    <dialog ref={ref} onClose={onClose} className="m-auto w-[min(42rem,calc(100vw-2rem))] rounded-2xl border border-line bg-surface p-0 text-ink backdrop:bg-black/50">
      <div className="space-y-4 p-5">
        <h2 className="text-lg font-bold">{t("letter.title")}</h2>
        <div className="grid gap-3 sm:grid-cols-3">
          {(["insurer", "name", "policy"] as const).map((k) => (
            <Field key={k} label={t(`letter.${k}`)}>
              <input className={inputClass} value={fields[k]} onChange={(e) => setFields({ ...fields, [k]: e.target.value })} />
            </Field>
          ))}
        </div>
        {error && <ErrorNote>{error}</ErrorNote>}
        {letter && (
          <>
            <textarea readOnly value={letter.text} aria-label={t("letter.title")} rows={12} className="w-full rounded-xl border border-line bg-surface-2 p-3 font-mono text-sm" />
            <p className="text-sm text-muted">{letter.note}{letter.unreviewed ? ` ${t("letter.unreviewed")}` : ""}</p>
          </>
        )}
        <div className="flex flex-wrap gap-2">
          <Button variant="primary" disabled={!letter} onClick={async () => { await navigator.clipboard.writeText(letter!.text); setCopied(true); setTimeout(() => setCopied(false), 1500); }}>
            {copied ? t("letter.copied") : t("letter.copy")}
          </Button>
          <Button disabled={!letter} onClick={() => download("letter.txt", "text/plain", letter!.text)}>{t("letter.download")}</Button>
          <Button variant="ghost" onClick={onClose} className="ml-auto">{t("letter.close")}</Button>
        </div>
      </div>
    </dialog>
  );
}
