# PolisDiff — full build prompt (v2 rebuild)

Use this as the single brief for rebuilding the product. It replaces the scattered
v1 web UI. The v1 engine in `polisdiff/` and `rules/` is kept and reused.

## 1. Product in one sentence

**PolisDiff tells an OSAGO buyer, in plain words, whether an insurer's offer matches
Uzbek law, what deadlines the insurer must meet if a claim happens, and what to do if
it doesn't — with every statement tied to a quote from the document and a dated legal
source.** Insurers use the same engine to check their own offers before publishing.

Not a legal opinion. Every legal interpretation stays `PENDING_LEGAL_REVIEW` until a
lawyer signs it off; the UI says so once, clearly, never hidden.

## 2. Users and the one job each one has

| User | Job to be done | Success |
| --- | --- | --- |
| **Buyer** (vehicle owner) | "Is this offer fair and what are my rights if I claim?" | Gets a verdict in under 60 s, knows the deadlines, can send a complaint if breached |
| **Insurer compliance officer** (owner of the product) | "Does our offer comply before we publish it?" | Checks one or many offers, gets a defensible, auditable report |

One app, one primary flow. A switch at the top ("I am buying" / "I am an insurer")
only changes wording and adds the batch table; the engine and screens are the same.

## 3. Insurance logic (what the product must know)

Use only what the verified catalogue (`rules/catalogue.v1.json`) states. Never invent law.

1. **Total insurance sum:** 40,000,000 UZS for contracts applying before 2026-01-01;
   80,000,000 UZS from 2026-01-01. Compare only an explicit *total* sum; not the premium,
   not a sub-limit, not an example.
2. **Payment deadline:** compensation is paid within **5 working days after the insurer
   decides to pay**. A shorter unambiguous deadline is consistent; a longer one is a
   potential conflict; "days after the accident" is a *different trigger* and is not compared.
3. **Decision notice:** the insurer informs the policyholder of its decision within
   **15 days after a written or electronic claim**. Working-day wording needs manual review.
4. **Date drives everything.** The contract's applicability date picks the legal version.
   Never assume it from upload date or filename. Detected dates are suggestions the user
   confirms. Unknown/unsupported date => `UNVERIFIABLE`, never a guess.
5. **Four statuses only:** Match found · Potential conflict · Not found (never = violation) ·
   Cannot verify. Offer text and copied regulatory appendix are separated; appendix text
   never proves what the insurer promised.
6. **Claim clock (new, buyer-critical):** given the date the buyer files a claim, show
   - latest date the insurer must tell them its decision (claim date + 15 days),
   - latest payment date once a decision to pay exists (decision date + 5 working days,
     counting Uzbek public holidays and transferred days from the official calendar,
     source and year declared in the UI; moving holidays loaded per year, not guessed).
   Show the rule and source next to each date.
7. **Complaint draft (new, buyer-critical):** only for a *confirmed* conflict or a missed
   claim deadline. Deterministic template (no free-form LLM text): who, what the offer says
   (quote + page), what the cited provision says (quote + link), what is requested, in the
   user's language. Clearly marked "draft, not legal advice"; user edits and sends it themselves.

New rules are added only after checking primary text on lex.uz and recording quote, link
and effective dates; each new rule ships `PENDING_LEGAL_REVIEW`. Do not add rules from memory.

## 4. Screens (exactly four, mobile-first)

1. **Check an offer** (home). One card: drop PDF / paste text / "try a sample" → date box
   (suggested date shown with its source quote; one confirm tap) → **Check**. Nothing else on
   the page except a one-line trust note ("PDF is processed in memory, not stored").
2. **Verdict.** Top: one sentence ("2 of 3 checks match, 1 needs attention") and three
   check cards. Each card: status icon + word, the offer's quote, the law's value, what it
   means for you, next step. Click a card => PDF page with the quote highlighted beside it.
   Primary actions: *Claim deadlines*, *Draft complaint* (only if applicable), *Download report*.
3. **Claim deadlines.** Date picker for claim/decision date; the two deadlines with rule,
   source and holiday notes. Printable.
4. **Insurer workspace** (insurer mode): upload up to 20 offers, table of offer × check with
   status chips, open any row into the Verdict screen, review decisions (confirm / dismiss /
   escalate + reason), export CSV/JSON/HTML. Review log is persistent and tamper-evident
   (hash-chained).

Language switcher always visible: Russian (default), Uzbek Latin, Uzbek Cyrillic, English.
Reuse reviewed copy from `polisdiff/i18n.py`; mark any new string `unreviewed` in the repo
and in a translations review list. Quotes from documents and law are never translated.

## 5. UX rules

- One primary button per screen; plain words, no jargon (no "retrieval", "passage", "hybrid").
- Show progress in three human steps while analysing: *Reading → Finding clauses → Checking law*.
- Every status has icon + text + colour (colour is never the only signal); WCAG AA, 44 px touch
  targets, keyboard-complete, light/dark, reduced-motion respected.
- Errors say what to do next ("This PDF has no text layer. Upload a text PDF or paste the clause").
- Empty/NOT_FOUND/UNVERIFIABLE states explain *why* and what would resolve them.
- No dashboards, charts, or settings pages. Advanced options (search mode, JSON) live in one
  "Details" drawer.

## 6. Architecture

```
Browser (Next.js App Router, TypeScript, Tailwind + shadcn/ui, next-intl)  -- Vercel
   |  upload PDF directly (CORS, signed short-lived token) -> bypasses Vercel's 4.5 MB cap
   v
API (FastAPI, Docker)  -- Hugging Face Space (CPU, 16 GB) or any container host
   |-- extraction: PyMuPDF text layer; Tesseract OCR (uzb, rus) when a page has no text layer
   |-- retrieval: BM25 + multilingual-e5-small (hybrid), model baked into the image
   |-- engine: existing deterministic rules (polisdiff/engine.py), dated catalogue
   |-- deadlines: working-day calculator + official holiday calendar
   |-- letters: deterministic templates per language
   '-- Postgres (Neon): insurer review log (hash chain), batch jobs; no PDF bytes stored
```

- Next.js server routes only render pages and proxy light calls; heavy work stays in the API.
- API is stateless for buyers (nothing persisted). Insurer mode stores only findings, hashes and
  review actions, never document bytes, behind simple email-link login.
- Production design runs fully offline inside a bank perimeter: same container, no external calls.
  The public demo may call no external AI API either; the LLM is *not* required.
- Performance budget: first verdict < 10 s p50 for a 10-page text PDF (model warm); show cost
  per request and latency in the report footer; fix the 30 s outlier before launch (render
  evidence images lazily, one model load per process, keep the Space awake).
- Upload limit 10 MiB / 80 pages again (direct-to-API upload).

## 7. API contract (REST, JSON, versioned `/v1`)

`POST /v1/checks` (multipart: file or text, applicable_date?, language) => check id + verdict
`GET /v1/checks/{id}` | `GET /v1/checks/{id}/pages/{n}` (page PNG with highlight)
`POST /v1/deadlines` (claim_date | decision_date) => dates with rule + source
`POST /v1/letters` (check id, rule id, language) => draft text
`POST /v1/batches` | `GET /v1/batches/{id}` (insurer)
`POST /v1/reviews` (insurer) | `GET /v1/audit` (hash-chained)
`GET /v1/catalogue` | `GET /v1/health`
Typed with Pydantic; OpenAPI published; the frontend uses a generated TypeScript client.

## 8. Data, legal and honesty constraints

- No real personal data; sample offers are synthetic and labelled so. Public offers used for
  evaluation are listed with source and licence in `SOURCES.md` / `DATA_LICENSES.md`.
- Replace PyMuPDF (AGPL) with `pypdfium2` + `pdfminer.six`, or document the AGPL decision.
- Every metric shown or claimed comes from `evaluation/` runs on the labelled test set; no
  invented numbers. Report precision/recall/abstention, latency, cost/request, known failures.
- Pre-final work (the v1 engine) is declared in the README.

## 9. Acceptance tests (must pass before "done")

1. A synthetic offer promising payment in 9 working days => potential conflict, quote + page
   highlighted, complaint draft available, claim-clock dates correct incl. a holiday span.
2. Same offer with no confirmed date => all three `UNVERIFIABLE`, one clear prompt to confirm.
3. Scanned (image-only) PDF => OCR text used, flagged "recognised from image", error rate known.
4. 10 MiB PDF uploads on phone over mobile data; verdict < 15 s warm.
5. Four languages end to end, including the PDF page highlight and the exported HTML/PDF report.
6. Insurer uploads 10 offers => table; a review action appears in the audit log; tampering
   with a stored row breaks the hash chain check.
7. Axe/Lighthouse accessibility >= 95; keyboard-only run-through; no console errors.
8. Existing test suite (476 tests) still passes; new tests for deadlines, letters, OCR, API.

## 10. Explicit non-goals

No chatbot, no free-form LLM legal advice, no scoring of insurers, no payments, no accounts for
buyers, no other insurance products, no admin console. Add nothing not listed above.

## 11. Delivery order

1. Backend container on the Space (API + hybrid model + OCR) with `/v1/checks`, health, catalogue.
2. Next.js app: screens 1–2, wired to the Space; deploy to Vercel; kill the v1 UI.
3. Deadlines + holiday calendar; screen 3. 4. Complaint letters.
5. Insurer workspace + audit log. 6. OCR measurement, evaluation refresh, docs, deck numbers.
