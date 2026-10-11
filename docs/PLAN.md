# PolisDiff AI — audit and enhancement plan (WIUT hackathon, FinTech track)

Status: plan only. Written 2026-10-11 after auditing `docs/BUSINESS_CASE.md`,
`LIMITATIONS.md`, `DEFENCE.md`, `CLOUD_READINESS.md`, `evaluation/RESULTS.md` and
`rules/catalogue.v1.json`. No code was changed by this plan.

## 1. Core idea

Reposition from "a PDF reader with three checks" to:

> A regulation-to-checks engine for Uzbek insurance offers. It turns primary legal
> texts into dated, machine-checkable rules, runs them on offers in Uzbek and
> Russian with quoted evidence, and keeps a human-approved audit trail.

- Moat (replication test): a date-versioned rule catalogue verified against lex.uz;
  a multilingual evidence pipeline (Uzbek Latin, Uzbek Cyrillic, Russian); a
  reviewer workflow with a tamper-evident audit trail.
- Users: insurer compliance teams (payer, self-check before publishing) and
  regulator analysts (market-wide monitoring).
- Mode: **Startup** (in-perimeter licences to insurers; regulator as pilot channel).
  No partner claim is made.

## 2. Problems found

| # | Problem | Why it matters |
|---|---|---|
| 1 | 8 of 9 rule results on real PDFs abstain | The jury supplies a live input; mostly "unverifiable" fails the demo |
| 2 | Semantic retrieval is not better than keyword search in our own evaluation | Weak on both technology criteria |
| 3 | Business case values the saving at ~1.4M UZS/month (~$110) | Cannot support pricing or payback; value must come from regulator-scale monitoring and avoided complaints/fines |
| 4 | No measured saving (25 -> 18 min is an invented assumption) | Invented metrics are disqualifiable; run a small timed study |
| 5 | Text-based PDFs only; OCR never measured | Jury input may be a scan or phone photo |
| 6 | Supported date range hard-coded to end 2026-10-10 | Already stale on 2026-10-11 |
| 7 | Only three checks | Too narrow to be a monitor |
| 8 | Not deployed; Streamlit Cloud ~1 GB RAM vs >1.3 GiB model peak | Deployment is mandatory |
| 9 | PyMuPDF is AGPL | Conflicts with a commercial startup story |
| 10 | Review annotations are session-only | Audit trail is a required engineering-constraint item |
| 11 | No mode named; pre-final work not declared | Both are rule requirements |

## 3. Features to add

P0 (needed for the demo to hold)
1. Robust intake: OCR (Uzbek + Russian, error rate measured), DOCX, images, pasted text, URL fetch.
2. Real AI role: model proposes structured extractions with a verbatim quote; the
   deterministic engine accepts a quote only if it exists in the source text and
   then compares. Prototype may use an external API; production uses a local model.
3. Expand catalogue from 3 to ~10-12 OSAGO checks, each verified against lex.uz
   primary text and marked `PENDING_LEGAL_REVIEW` until reviewed.
4. Auto-suggest applicability date and product with evidence quotes; user still confirms.
5. Public deployment from the repo via GitHub Actions.
6. Larger honest test set (~60-100 docs; real public offers with sources/licences,
   synthetic with declared method): precision, recall, abstention, latency,
   cost/request, known failure cases.

P1 (differentiation)
7. Market monitor: batch upload, insurer-by-check heatmap, ranked risk.
8. Regulation-change impact: diff catalogue versions, re-run only affected offers.
9. Tamper-evident audit log: persistent store, hash chain, signed export, roles.
10. Live cost and latency panel in the app.
11. Rule explorer: per-rule version timeline with source links.

P2: second product (KASKO), REST API, complaint triage.

## 4. Architecture

- Keep the Python engine, catalogue and tests; expose via FastAPI.
- Backend on a container host with enough RAM for the E5 model (e.g. Hugging Face
  Spaces Docker); frontend on Vercel (React/Next.js).
- SQLite for demo, Postgres for production. Production design is fully offline
  (OCR, local LLM, embeddings inside the perimeter, no outbound calls).
- Replace PyMuPDF with `pypdfium2` + `pdfminer.six`.
- Fallback if time is short: keep Streamlit with a custom theme.

## 5. UI/UX

Mobile-first; Russian default with always-visible language switcher; status shown
by icon and text, never colour alone; light/dark; WCAG AA; one set of design tokens.
Screens: Analyze (drop zone, sample documents, date chip with evidence) -> Result
(split view: check cards + PDF page with highlighted quote) -> Reviewer drawer ->
Market monitor -> Rule explorer -> Audit log -> Trust panel (deployment diagram,
live cost/latency).

## 6. Order of work

1. Foundation: API wrapper, deployment pipeline, early public URL, rolling date range.
2. Intake + AI extraction; re-measure abstention.
3. Rules + test set + honest metrics.
4. UI screens 1-3, then 4-7.
5. Audit log and market monitor.
6. Business and defence: timed 3-5 person study, reworked ROI, 7-minute deck, recorded backup.
7. Freeze: redeploy the same commit only; README sources/licences; declare pre-final code.

## 7. Open decisions

Deadline and team size; stack (FastAPI + React vs restyled Streamlit); mode (Startup
recommended); external LLM API for the prototype; access to a legal reviewer.
