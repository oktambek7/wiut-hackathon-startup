"use client";
import Link from "next/link";
import { useEffect, useMemo, useRef, useState } from "react";
import * as api from "@/lib/api";
import { useLang } from "@/lib/lang";
import type { Key } from "@/lib/messages";
import type { Check, CheckResponse, View } from "@/lib/types";
import { download } from "@/lib/util";
import { Badge, Button, Card, LEVEL_BORDER } from "./ui";
import LetterDialog from "./LetterDialog";

interface Props { data: CheckResponse; view: View; file: File | null }

export default function Verdict({ data, view, file }: Props) {
  const { t, lang } = useLang();
  const [selected, setSelected] = useState(() => view.checks.find((c) => c.level === "attention")?.rule_id ?? view.checks[0]?.rule_id);
  const [letterFor, setLetterFor] = useState<string | null>(null);
  const panel = useRef<HTMLDivElement>(null);
  const current = view.checks.find((c) => c.rule_id === selected) ?? view.checks[0];
  const request = useMemo(() => ({ kind: "offer_conflict", report: data.report, rule_id: letterFor, document_name: data.doc.name }), [data, letterFor]);
  const levelBadge = view.level === "ok" ? "ok" : view.level === "attention" ? "attention" : "unknown";

  async function html() {
    download("polisdiff-report.html", "text/html", await api.reportHtml(data.report, lang));
  }

  return (
    <div className="space-y-6">
      <Card className="space-y-3">
        <div className="flex flex-wrap items-center gap-3">
          <Badge level={levelBadge}>{t(`level.${view.level}` as Key)}</Badge>
          <span className="text-sm text-muted">{data.doc.name} · {data.doc.pages} p.</span>
        </div>
        <p className="text-lg">{view.headline}</p>
        {data.doc.unreadable_pages.length > 0 && <p className="rounded-xl bg-miss-bg px-3 py-2 text-miss">{view.warnings.find((w) => data.doc.unreadable_pages.some((n) => w.includes(String(n)))) ?? ""}</p>}
        <div className="no-print flex flex-wrap gap-2">
          <Link href="/deadlines" className="inline-flex min-h-11 items-center rounded-xl bg-brand px-4 text-sm font-semibold text-brand-ink">{t("act.deadlines")}</Link>
          <Button onClick={html}>{t("act.html")}</Button>
          <Button variant="ghost" onClick={() => download("polisdiff-report.json", "application/json", JSON.stringify(data.report, null, 2))}>{t("act.json")}</Button>
        </div>
      </Card>

      <div className="grid gap-6 lg:grid-cols-[1.05fr_1fr]">
        <ol className="space-y-4">
          {view.checks.map((c) => (
            <li key={c.rule_id}>
              <CheckCard check={c} active={c.rule_id === current?.rule_id}
                onShow={() => { setSelected(c.rule_id); panel.current?.scrollIntoView({ behavior: "smooth", block: "nearest" }); }}
                onComplain={() => setLetterFor(c.rule_id)} />
            </li>
          ))}
        </ol>
        <div ref={panel} className="lg:sticky lg:top-24 lg:self-start">
          {current && <EvidencePanel key={current.rule_id} check={current} images={data.images} file={file} engine={data.engine} />}
        </div>
      </div>
      <LetterDialog open={letterFor !== null} onClose={() => setLetterFor(null)} request={request} />
    </div>
  );
}

function CheckCard({ check: c, active, onShow, onComplain }: { check: Check; active: boolean; onShow: () => void; onComplain: () => void }) {
  const { t } = useLang();
  return (
    <article className={`rounded-2xl border border-l-8 bg-surface p-5 shadow-sm ${LEVEL_BORDER[c.level]} ${active ? "border-brand" : "border-line"}`}>
      <div className="flex flex-wrap items-start justify-between gap-2">
        <h2 className="text-lg font-bold">{c.name}</h2>
        <Badge level={c.level}><span aria-hidden>{c.icon}</span>{c.status_label}</Badge>
      </div>
      <dl className="mt-3 space-y-3">
        <Row term={t("check.offer")} text={c.offer_says} />
        <Row term={t("check.law")} text={c.law_says} />
        <Row term={t("check.meaning")} text={c.meaning} />
        <Row term={t("check.next")} text={c.next_step} />
      </dl>
      <div className="no-print mt-4 flex flex-wrap gap-2">
        {c.evidence.length > 0 && <Button variant={active ? "secondary" : "primary"} onClick={onShow} aria-pressed={active}>{t("check.show", { page: c.evidence[0].page })}</Button>}
        {c.can_complain && <Button variant="primary" onClick={onComplain}>{t("check.complaint")}</Button>}
        {c.evidence.length === 0 && <Button variant="ghost" onClick={onShow}>{t("check.source")}</Button>}
      </div>
    </article>
  );
}

function Row({ term, text }: { term: string; text: string }) {
  return (
    <div>
      <dt className="text-xs font-semibold uppercase tracking-wide text-muted">{term}</dt>
      <dd>{text}</dd>
    </div>
  );
}

function EvidencePanel({ check, images, file, engine }: { check: Check; images: Record<string, string>; file: File | null; engine: CheckResponse["engine"] }) {
  const { t } = useLang();
  const [index, setIndex] = useState(0);
  const [lazy, setLazy] = useState<Record<number, string>>({});
  const ev = check.evidence[index];
  const image = ev ? images[ev.passage_id] ?? lazy[ev.page] : undefined;

  useEffect(() => {
    if (!ev || image || !file) return;
    let cancelled = false;
    api.page(file, ev.page).then((r) => { if (!cancelled) setLazy((m) => ({ ...m, [ev.page]: r.image })); }).catch(() => undefined);
    return () => { cancelled = true; };
  }, [ev, image, file]);

  return (
    <Card className="space-y-4">
      <h2 className="text-lg font-bold">{check.name}</h2>
      {check.evidence.length > 1 && (
        <div role="tablist" className="flex flex-wrap gap-2">
          {check.evidence.map((e, i) => (
            <button key={e.passage_id} role="tab" aria-selected={i === index} onClick={() => setIndex(i)}
              className={`min-h-10 rounded-full border px-3 text-sm ${i === index ? "border-brand bg-brand text-brand-ink" : "border-line"}`}>
              {t("check.show", { page: e.page })}
            </button>
          ))}
        </div>
      )}
      {ev ? (
        <>
          <p className="text-sm text-muted">{ev.section_label} · p. {ev.page}</p>
          <blockquote className="whitespace-pre-wrap break-words rounded-r-xl border-l-4 border-brand bg-surface-2 p-3" dangerouslySetInnerHTML={{ __html: ev.quote_html }} />
          {/* eslint-disable-next-line @next/next/no-img-element */}
          {image && <img alt={`p. ${ev.page}`} src={`data:image/png;base64,${image}`} className="w-full rounded-xl border border-line bg-white" />}
        </>
      ) : <p className="text-muted">{t("check.none")}</p>}
      <div className="rounded-xl bg-surface-2 p-3">
        <p className="text-xs font-semibold uppercase tracking-wide text-muted">{t("check.source")}</p>
        {check.law.source_quote && <p className="mt-1 font-mono text-sm">{check.law.source_quote}</p>}
        <p className="mt-1 text-sm text-muted">{check.law.provision} · {check.law.period}</p>
        <a href={check.law.source_url} target="_blank" rel="noreferrer" className="text-sm font-semibold text-brand underline">lex.uz</a>
      </div>
      <details className="text-sm">
        <summary className="min-h-8 cursor-pointer font-semibold">{t("check.details")}</summary>
        <ul className="mt-2 list-disc space-y-1 pl-5">{check.verification.map((v) => <li key={v}>{v}</li>)}</ul>
        <p className="mt-2 text-muted">{t("check.ai")}: {engine.retrieval_used} · {engine.total_seconds}s</p>
      </details>
    </Card>
  );
}
