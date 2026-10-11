"use client";
import { useEffect, useRef, useState } from "react";
import * as api from "@/lib/api";
import * as audit from "@/lib/auditlog";
import { useLang } from "@/lib/lang";
import type { Key } from "@/lib/messages";
import type { Catalogue, CheckResponse, View } from "@/lib/types";
import { download, errorKey, isoToday } from "@/lib/util";
import Verdict from "@/components/Verdict";
import { Badge, Button, Card, ErrorNote, Field, inputClass } from "@/components/ui";

interface Row { file: File; data?: CheckResponse; view?: View; error?: string }
const MAX_FILES = 20;
const ACTIONS = ["confirm", "dismiss", "escalate"] as const;

export default function Insurer() {
  const { t, lang } = useLang();
  const input = useRef<HTMLInputElement>(null);
  const [cat, setCat] = useState<Catalogue | null>(null);
  const [date, setDate] = useState("");
  const [rows, setRows] = useState<Row[]>([]);
  const [busy, setBusy] = useState(false);
  const [open, setOpen] = useState<number | null>(null);
  const [log, setLog] = useState<audit.LogEntry[]>([]);
  const [verdict, setVerdict] = useState<string | null>(null);
  const [form, setForm] = useState({ rule: "", action: "confirm" as (typeof ACTIONS)[number], reason: "" });
  const [problem, setProblem] = useState<string | null>(null);

  useEffect(() => { api.catalogue().then(setCat).catch(() => undefined); setLog(audit.load()); }, []);
  // Re-localize every verdict when the language changes (the PDFs are not re-read).
  useEffect(() => {
    rows.forEach((r, i) => {
      if (r.data && r.view?.language !== lang) api.localize(r.data.report, lang).then((v) => setRows((cur) => cur.map((x, j) => (j === i ? { ...x, view: v } : x)))).catch(() => undefined);
    });
  }, [lang, rows]);

  async function runAll(files: File[]) {
    setBusy(true); setOpen(null);
    const list: Row[] = files.slice(0, MAX_FILES).map((file) => ({ file }));
    setRows(list);
    for (const [i, row] of list.entries()) {
      try {
        const data = await api.check(row.file, lang, date);
        list[i] = { file: row.file, data, view: data.view };
      } catch (e) { list[i] = { file: row.file, error: t(errorKey(e), { mb: 4 }) }; }
      setRows([...list]);
    }
    setBusy(false);
  }
  function pick(fl: FileList | null) {
    if (!fl) return;
    const files = [...fl].filter((f) => /\.pdf$/i.test(f.name) && (!cat || f.size <= cat.max_upload_bytes));
    if (files.length) runAll(files);
  }
  async function record(row: Row) {
    setProblem(null);
    if (form.reason.trim().length < 3 || !row.data) return setProblem(t("ins.reason"));
    setLog(await audit.append({ document: row.file.name, documentSha256: String((row.data.report as { document_sha256?: string }).document_sha256 ?? ""),
      ruleId: form.rule || row.view!.checks[0].rule_id, action: form.action, reason: form.reason.trim() }));
    setForm({ ...form, reason: "" });
  }
  async function check() {
    const bad = await audit.verify(log);
    setVerdict(bad === -1 ? t("ins.verify.ok", { n: log.length }) : t("ins.verify.bad", { n: bad }));
  }
  const ruleNames = rows.find((r) => r.view)?.view?.checks.map((c) => ({ id: c.rule_id, name: c.name })) ?? [];

  return (
    <div className="space-y-6">
      <div className="space-y-2">
        <h1 className="text-3xl font-bold tracking-tight sm:text-4xl">{t("ins.title")}</h1>
        <p className="text-lg text-muted">{t("ins.sub")}</p>
      </div>
      <Card className="flex flex-wrap items-end gap-4">
        <div className="w-full sm:w-64">
          <Field label={t("ins.date")}><input type="date" className={inputClass} value={date} max={isoToday()} onChange={(e) => setDate(e.target.value)} /></Field>
        </div>
        <input ref={input} type="file" accept="application/pdf,.pdf" multiple hidden onChange={(e) => pick(e.target.files)} />
        <Button variant="primary" disabled={busy} onClick={() => input.current?.click()}>{busy ? t("btn.checking") : t("ins.run")}</Button>
        <p className="text-sm text-muted">{t("ins.max")}</p>
      </Card>

      {rows.length > 0 && (
        <Card className="overflow-x-auto p-0">
          <table className="w-full min-w-[40rem] text-left text-sm">
            <thead className="border-b border-line bg-surface-2 text-muted">
              <tr>
                <th className="p-3">{t("ins.col.offer")}</th>
                {ruleNames.map((r) => <th key={r.id} className="p-3">{r.name}</th>)}
                <th className="p-3"><span className="sr-only">{t("ins.open")}</span></th>
              </tr>
            </thead>
            <tbody>
              {rows.map((row, i) => (
                <tr key={`${row.file.name}-${i}`} className="border-b border-line align-top last:border-0">
                  <td className="p-3 font-medium break-all">{row.file.name}</td>
                  {row.error ? <td colSpan={Math.max(ruleNames.length, 1)} className="p-3 text-attn">{row.error}</td>
                    : row.view ? row.view.checks.slice().sort((a, b) => a.rule_id.localeCompare(b.rule_id)).map((c) => (
                      <td key={c.rule_id} className="p-3"><Badge level={c.level}><span aria-hidden>{c.icon}</span>{c.status_label}</Badge></td>
                    )) : <td className="p-3 text-muted" colSpan={Math.max(ruleNames.length, 1)}>…</td>}
                  <td className="p-3">{row.view && <Button variant="ghost" onClick={() => setOpen(open === i ? null : i)} aria-expanded={open === i}>{t("ins.open")}</Button>}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </Card>
      )}

      {open !== null && rows[open]?.data && rows[open].view && (
        <div className="space-y-6">
          <Verdict data={rows[open].data!} view={rows[open].view!} file={rows[open].file} />
          <Card className="space-y-3">
            <h2 className="text-lg font-bold">{t("ins.col.review")}</h2>
            <div className="grid gap-3 sm:grid-cols-2">
              <Field label={t("check.offer")}>
                <select className={inputClass} value={form.rule} onChange={(e) => setForm({ ...form, rule: e.target.value })}>
                  {rows[open].view!.checks.map((c) => <option key={c.rule_id} value={c.rule_id}>{c.name}</option>)}
                </select>
              </Field>
              <Field label={t("ins.col.review")}>
                <select className={inputClass} value={form.action} onChange={(e) => setForm({ ...form, action: e.target.value as (typeof ACTIONS)[number] })}>
                  {ACTIONS.map((a) => <option key={a} value={a}>{t(`ins.review.${a}` as Key)}</option>)}
                </select>
              </Field>
            </div>
            <Field label={t("ins.reason")}><textarea className={`${inputClass} min-h-24`} value={form.reason} maxLength={2000} onChange={(e) => setForm({ ...form, reason: e.target.value })} /></Field>
            {problem && <ErrorNote>{problem}</ErrorNote>}
            <Button variant="primary" onClick={() => record(rows[open])}>{t("ins.col.review")}</Button>
          </Card>
        </div>
      )}

      <Card className="space-y-3">
        <h2 className="text-lg font-bold">{t("ins.log")}</h2>
        <p className="text-sm text-muted">{t("ins.log.note")}</p>
        {log.length === 0 ? <p className="text-muted">{t("ins.empty")}</p> : (
          <ul className="divide-y divide-line text-sm">
            {log.map((e) => (
              <li key={e.index} className="py-2"><strong>{e.document}</strong> · {e.ruleId} · {t(`ins.review.${e.action}` as Key)} · {e.at.slice(0, 19).replace("T", " ")}<br /><span className="text-muted">{e.reason}</span><br /><code className="text-xs text-muted">{e.hash.slice(0, 16)}…</code></li>
            ))}
          </ul>
        )}
        <div className="flex flex-wrap items-center gap-2">
          <Button onClick={check} disabled={!log.length}>{t("ins.verify")}</Button>
          <Button onClick={() => download("review-log.csv", "text/csv", audit.toCsv(log))} disabled={!log.length}>{t("ins.csv")}</Button>
          <Button variant="ghost" onClick={() => { audit.clear(); setLog([]); setVerdict(null); }} disabled={!log.length}>{t("ins.clear")}</Button>
          {verdict && <span role="status" className="text-sm font-semibold">{verdict}</span>}
        </div>
      </Card>
    </div>
  );
}
