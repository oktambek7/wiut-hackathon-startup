from datetime import date, datetime, timezone
import threading
import time
from .extraction import extract_pdf
from .engine import load_catalogue, evaluate, topic
from .models import Report, Document
from .retrieval import Retriever

_ANALYSIS_GATE = threading.BoundedSemaphore(1)
# English retrieval queries; the catalogue's own queries (ru, uz-Latn, uz-Cyrl) stay unchanged.
EXTRA_QUERIES = {
    "OSAGO_SUM": ["total insurance sum of compulsory motor liability insurance UZS"],
    "OSAGO_PAYMENT": ["insurance compensation paid within five working days from the date of the insurer's decision"],
    "OSAGO_DECISION_NOTICE": ["insurer notifies the policyholder of the decision on compensation within fifteen days after the written or electronic claim"],
}


class BusyError(RuntimeError):
    pass


def audit_document(doc: Document, audit_date: date, applicable_date: date | None,
                   retriever: Retriever, *, date_basis="user_confirmed", k=8, on_progress=None) -> Report:
    start = time.perf_counter()
    catalogue, rules, digest = load_catalogue()
    warnings = list(doc.warnings)
    if retriever.warning:
        warnings.append(retriever.warning)
    warnings.append("All engineering interpretations are PENDING_LEGAL_REVIEW.")
    warnings.append("Offer/appendix classification is heuristic and requires manual review.")
    # Separate offer and appendix searches, preventing copied statute from crowding out offers.
    offer = [p for p in doc.passages if p.section == "offer"]
    appendix = [p for p in doc.passages if p.section != "offer"]
    candidates = {r.id: [] for r in rules}
    if on_progress:
        on_progress("retrieval")
    retrieval_start = time.perf_counter()
    for section in (offer, appendix):
        retriever.prepare(section)
        for rule in rules:
            candidates[rule.id].extend(p for p, _ in retriever.search(rule.queries + EXTRA_QUERIES.get(rule.id, []), k=k))
    # Top-K ranking must not hide competing contractual terms elsewhere.
    # Expand evidence candidates; never assume their extracted values are valid.
    for rule in rules:
        ids = {p.id for p in candidates[rule.id]}
        candidates[rule.id].extend(p for p in offer if p.id not in ids and topic(rule, p.normalized))
    retrieval_seconds = time.perf_counter() - retrieval_start
    if on_progress:
        on_progress("evaluation")
    findings = [evaluate(r, doc, candidates[r.id], applicable_date, audit_date) for r in rules]
    if on_progress:
        on_progress("report")
    return Report(rules_catalogue_version=catalogue["catalogue_version"], rules_catalogue_sha256=digest,
        document_sha256=doc.sha256, audit_date=audit_date, applicable_date=applicable_date,
        date_basis=date_basis if applicable_date else "unknown", created_at=datetime.now(timezone.utc),
        detected_languages=doc.languages, page_count=len(doc.pages), warnings=warnings,
        retrieval_requested=retriever.requested, retrieval_used=retriever.used, model_revision=retriever.model_revision,
        candidate_selection="top_8_per_section_plus_offer_topic_guard",
        timings_seconds={"retrieval": retrieval_seconds, "evaluation": time.perf_counter()-start-retrieval_seconds,
                         "analysis": time.perf_counter()-start, "model_initialization": retriever.initialization_seconds},
        findings=findings)


def analyze_pdf(data: bytes, audit_date: date, applicable_date: date | None, retriever: Retriever,
                *, date_basis="user_confirmed", on_progress=None, on_document=None) -> tuple[Document, Report]:
    if not _ANALYSIS_GATE.acquire(blocking=False):
        raise BusyError("Analysis is already running. Please retry after it finishes.")
    try:
        start = time.perf_counter()
        if on_progress:
            on_progress("extraction")
        doc = extract_pdf(data)
        if on_document:
            on_document(doc)
        extract_time = time.perf_counter()-start
        report = audit_document(doc, audit_date, applicable_date, retriever, date_basis=date_basis, on_progress=on_progress)
        report.timings_seconds["extraction"] = extract_time
        report.timings_seconds["end_to_end"] = time.perf_counter()-start
        return doc, report
    finally:
        # Never keep uploaded passages in a process-global cached retriever.
        retriever._passages = []
        retriever._embeddings = None
        _ANALYSIS_GATE.release()
