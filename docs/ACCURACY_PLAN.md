# Accuracy, legal-checking and evidence-UX plan

Goal: when someone uploads an OSAGO offer in Uzbek (Latin or Cyrillic), Russian, English or a mix,
the product extracts the relevant terms correctly, checks them against the Uzbek OSAGO rules that
applied on the contract date, explains the result in plain words, and shows the proof on the
original page with the key words highlighted.

## 0. What "accuracy" means here (say this to the jury)

"Perfect" extraction is not achievable on arbitrary documents, and claiming it would be a
fabricated metric. The promise we can keep and prove is:

> **The system is never silently wrong.** It answers only when the quote, the number, the unit and the
> trigger event are all verified in the text; otherwise it says "cannot verify" and tells the user what is missing.

So we measure **precision on answered checks**, **abstention rate**, and **recall of true conflicts**,
per script and per document type, on a test set we built — and publish the failures.

## 1. Where we are (from the repo, not hopes)

- 3 rules (total sum, payment deadline, decision-notice deadline), date-versioned, verified on lex.uz.
- Extraction is deterministic regex/grammar; strong on our synthetic fixtures (100% on 81 regression labels),
  but on 3 real public PDFs 8 of 9 results abstained; 88.9% status accuracy on 3 fresh synthetic files.
- English documents unsupported; OCR absent; table/column layouts and appendix boundaries are heuristic.
- Semantic retrieval has not beaten keyword retrieval on our small set.

## 2. Law coverage: what "checking against OSAGO law" must include

Each rule becomes a structured record: *subject, quantity, unit, trigger event, comparator
(min/max/equal), effective dates, exact source quote + lex.uz link, reviewer status*. Nothing is added from memory:
every new rule is first read in the primary text, quoted, and marked `PENDING_LEGAL_REVIEW`.

| Tier | Checks | Why buyers care |
| --- | --- | --- |
| Have | total insurance sum; payment deadline; decision-notice deadline | money and time |
| Next (verify on lex.uz first) | premium/tariff consistency; separate limits per harm type; policyholder's own notification duties and deadlines; stated grounds for refusal vs the closed list in the rules; contract term/validity; claim documents the insurer may demand; dispute and complaint routes | what can be refused, what you pay, what you must do |
| Cross-checks | internal contradictions (two different sums/deadlines in one offer); offer vs the copied appendix; offer date vs version in force | catches sloppy or misleading offers |

Output per check is a **comparison**, not a flag: *offer value, law value, difference, direction (better/worse for the buyer), consequence.*

## 3. Multilingual extraction pipeline (Uzbek Latin, Uzbek Cyrillic, Russian, English, mixed)

1. **Ingest:** text-layer PDF → words with boxes (PyMuPDF/pypdfium2). No text layer → OCR (Tesseract `uzb`, `uzb_cyrl`, `rus`, `eng`)
   with per-word confidence and boxes; low-confidence words are marked and never used silently. Also DOCX, image, pasted text, URL.
2. **Normalise:** Unicode NFC; Uzbek apostrophe variants (`o'`, `o‘`, `oʻ`, `o’`); Cyrillic Uzbek letters (ў қ ғ ҳ); a
   deterministic Cyrillic↔Latin Uzbek transliteration so one lexicon serves both scripts; number words (`besh/беш/пять/five`),
   units (`ish kuni/иш куни/рабочих дней/working days`), money (`so'm/сўм/сум/UZS`, `mln/млн/million`), dates in all local formats.
   Letter-O-for-zero and similar OCR traps are detected and flagged, not "fixed".
3. **Segment:** layout-aware clauses (numbered items, tables, columns), per-passage script/language tag, offer vs regulatory-appendix classification with a visible confidence.
4. **Extract (two independent routes, must agree):**
   - Route A: the current deterministic grammar, extended with the English lexicon and the normaliser above.
   - Route B: a small local model proposes `{value, unit, trigger, quote}`; a validator accepts it only if the quote exists
     verbatim in the page text and the numbers/units parse. No free-text answers are ever trusted.
   - Agreement → *High confidence*. One route only → *Medium, shown with "please verify"*. Disagreement/none → *Cannot verify*.
5. **Compare:** exact arithmetic against the dated rule; trigger events must match (a deadline counted from "the accident" is not compared with one counted from "the insurer's decision").

## 4. Proving accuracy (the part juries ask about)

- **Test set we build:** ≥150 documents: 50 per script group (uz-Latn, uz-Cyrl, ru) plus 25 English and 25 mixed; each as clean text PDF,
  scan/photo, table layout and "noisy" (typos, OCR noise). Two people label independently; disagreements resolved and logged.
- **Splits:** development, blind (never inspected until final run), plus a growing set of real public offers with source and licence in `SOURCES.md`.
- **Metrics reported per script:** field extraction precision/recall, status accuracy, conflict precision/recall, abstention rate, OCR character error rate, latency, cost/request.
- **Targets (goals to be measured, not claims):** precision on answered checks ≥ 98%; conflict recall ≥ 90% on text PDFs; abstention explained for 100% of unanswered checks.
- **Failure gallery** published in the repo and the deck (what we get wrong and why).

## 5. Feedback people can act on (result card)

1. **Verdict sentence:** "This offer promises payment in 9 working days; the law says 5. That is 4 days longer."
2. **Side-by-side:** *Offer* (quote, page) vs *Law* (quote, provision, effective date, lex.uz link), with the difference computed.
3. **Why it matters:** one plain sentence on the consequence for the buyer.
4. **What you can do:** ask the insurer to correct/clarify (letter draft), keep the claim-deadline clock, where to escalate (only routes verified in the rules).
5. **How sure we are:** confidence tier + "how we know" (route A/B agreed, OCR confidence of the cited words).
6. **Severity colours with icons and words** (match / attention / cannot verify / not found); `not found` never reads as a violation.
7. All copy reviewed by a native speaker per language; glossary tooltips for terms such as "insurance sum" and "working day".

## 6. Evidence viewer (professional, jury-friendly)

- Split screen: left = the checks; right = the **page image with highlights**. Highlight colours: *value* (amber), *unit/trigger words* (blue), *subject* (green), with a legend.
  Boxes come from word coordinates (text PDFs) or OCR boxes (scans), not from coarse block unions.
- Controls: next/previous evidence, page thumbnails with markers, zoom, "show extracted text", "show in context".
- **Download annotated PDF** (highlights and numbered notes burned in) and the printable HTML report.
- Mobile: bottom sheet with swipe between evidence items.
- Conflicting values in one document are shown together so the user sees the contradiction.

## 7. Explaining it to a jury in 7 minutes

- **One-click guided demo:** a sample with a conflict → verdict → highlighted proof → claim-clock → letter draft (≈ 90 s).
- **"How we checked" strip** on every verdict: *Read → Find clauses → Compare with law*, each step expandable.
- **Trust panel:** live numbers from our own evaluation (precision, abstention, latency, cost) with a link to the failure gallery; the "never silently wrong" principle stated once.
- **Live input from the jury:** upload any text or scanned OSAGO offer; the app either answers with proof or says exactly why it cannot.
- Backup: recorded demo and screenshots; offline container path shown as a diagram (nothing leaves the bank perimeter).

## 8. Work plan

| Phase | Deliverable | Depends on |
| --- | --- | --- |
| P0 | English lexicon + normaliser + transliteration; word-level highlight boxes; comparison-style result cards; new test set skeleton + labelling protocol | none |
| P0 | Model host (hybrid retrieval, 10 MiB) | Hugging Face token or other container host |
| P1 | OCR (Tesseract in the container) with confidence; scanned-document tests | container host |
| P1 | Route B (local model proposals + validator) and confidence tiers; blind-set evaluation run | model host |
| P1 | 3–5 additional rules, each read in primary text and quoted | lawyer/compliance reviewer for sign-off |
| P2 | Annotated-PDF export, guided demo mode, trust panel with live metrics | evaluation results |
| P2 | Shared audit log (Postgres) | database account |

## 9. Risks

- Scans and photos are the hardest input; OCR error rates in Uzbek Cyrillic and Latin must be measured, not assumed.
- New rules need legal reading; wrong readings are worse than missing rules.
- Native-speaker review of Uzbek copy is a person-time dependency.
- A two-route extractor increases abstention before it increases coverage; that trade-off is intended and will be reported.

## 10. Acceptance criteria

1. Blind-set report published with per-script numbers; no unexplained abstention.
2. A phone photo of an offer in each of the four languages is read, checked and highlighted, or refused with a reason.
3. Every verdict shows offer quote, law quote, difference, confidence, and a highlighted page image.
4. Two judges unfamiliar with the project can explain the verdict of a sample after one minute on the screen.
