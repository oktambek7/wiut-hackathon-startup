"""Public v1 API for the buyer/insurer web app. Stateless: nothing is stored server side.

POST /v1/checks       PDF -> verdict (+ highlighted evidence page images)
POST /v1/localize     report + language -> the same verdict text in another language
POST /v1/pages        PDF + page number -> page image
POST /v1/deadlines    claim/decision dates -> legal deadlines with rule, source and holiday notes
POST /v1/letters      confirmed conflict or missed deadline -> deterministic letter draft
GET  /v1/catalogue    rules, versions and sources;  GET /v1/health
"""
import base64
import os
import time
from datetime import date

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from pydantic import BaseModel

from .deadlines import claim_clock
from .deployment import model_files_status
from .engine import load_catalogue
from .extraction import MAX_BYTES, PDFError, render_evidence, render_page
from .i18n import LANGUAGES, TRANSLATIONS, tr, warning_text
from .letters import deadline_letter, offer_conflict_letter
from .localization import quote_html
from .models import Report, Status
from .presentation import (SECTION_LABELS, STATUS_ICONS, STATUS_LABELS, counts, expected, finding_details, labels,
                           next_step, observation, rule_name, summary)
from .runtime import web_retriever
from .service import BusyError, analyze_pdf

API_VERSION = "1.0.0"
LEVELS = {Status.MATCH_FOUND: "ok", Status.POTENTIAL_CONFLICT: "attention", Status.NOT_FOUND: "missing", Status.UNVERIFIABLE: "unknown"}
# Vercel rejects request bodies above 4.5 MB; a container host keeps the full 10 MiB.
MAX_UPLOAD = int(os.getenv("POLISDIFF_MAX_UPLOAD_BYTES", str(4 * 1024 * 1024 if os.getenv("POLISDIFF_ISOLATION") == "inprocess" else MAX_BYTES)))
IMAGES_PER_CHECK = 3

router = APIRouter(prefix="/v1")


def _lang(language: str) -> str:
    if language not in LANGUAGES:
        raise HTTPException(400, "Unsupported language")
    return language


def _date(value: str | None, field: str) -> date | None:
    if not value:
        return None
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise HTTPException(400, f"{field} must be YYYY-MM-DD") from exc


def _read(upload: UploadFile) -> bytes:
    data = upload.file.read(MAX_UPLOAD + 1)
    if len(data) > MAX_UPLOAD:
        raise HTTPException(413, "FILE_TOO_LARGE")
    return data


def build_view(report: Report, language: str) -> dict:
    """Localized, plain verdict derived only from the engine's report."""
    status_labels = labels(STATUS_LABELS, language)
    section_labels = labels(SECTION_LABELS, language)
    c = counts(report)
    unknown = c[Status.UNVERIFIABLE] == len(report.findings)
    level = "unknown" if unknown else "attention" if c[Status.POTENTIAL_CONFLICT] else "ok"
    checks = []
    for f in sorted(report.findings, key=lambda f: f.status != Status.POTENTIAL_CONFLICT):
        d = finding_details(report, f, language)
        checks.append({
            "rule_id": f.rule_id, "name": rule_name(f, language), "status": f.status.value, "level": LEVELS[f.status],
            "status_label": status_labels[f.status], "icon": STATUS_ICONS[f.status],
            "pending_date": report.applicable_date is None and f.status == Status.UNVERIFIABLE and f.expected_value is None,
            "offer_says": observation(f, language), "law_says": expected(f, language), "meaning": d["reason"],
            "next_step": next_step(f, language), "verification": d["verification"], "remediation": d["remediation"],
            "can_complain": f.status == Status.POTENTIAL_CONFLICT and d["comparable"],
            "evidence": [{"passage_id": ev.passage_id, "page": ev.page, "section": ev.section,
                          "section_label": section_labels.get(ev.section, ev.section), "quote": ev.quote,
                          "quote_html": quote_html(ev, f)} for ev in f.evidence],
            "law": {"reference": d["reference"], "provision": d["provision_reference"], "period": d["period"],
                    "source_url": d["source_url"], "source_quote": d["source_quote"], "date_note": d["date_note"]},
        })
    return {"language": language, "level": level, "headline": summary(report, language),
            "counts": {s.value: c[s] for s in Status}, "checks": checks,
            "warnings": [warning_text(w, language) for w in report.warnings]}


def _doc_info(doc, name: str) -> dict:
    return {"name": name, "pages": len(doc.pages), "languages": doc.languages,
            "unreadable_pages": [p.number for p in doc.pages if not p.readable],
            "detected_dates": [d.isoformat() for d in doc.detected_dates],
            "page_sections": {p.number: p.section for p in doc.pages}}


@router.get("/health")
def health():
    model = model_files_status()
    return {"status": "ok", "api": API_VERSION, "ai_model_present": model["state"] == "files_present",
            "ai_backend": bool(os.getenv("POLISDIFF_AI_BACKEND_URL"))}


@router.get("/catalogue")
def catalogue():
    cat, rules, digest = load_catalogue()
    return {"version": cat["catalogue_version"], "sha256": digest, "verified_access_date": cat["verified_access_date"],
            "supported_date_range": cat["supported_date_range"], "languages": LANGUAGES, "max_upload_bytes": MAX_UPLOAD,
            "rules": [{"id": r.id, "reference": r.reference, "source_url": r.official_source, "reviewer_status": r.reviewer_status,
                       "versions": [v.model_dump(mode="json") for v in r.versions]} for r in rules]}


@router.get("/i18n/{language}")
def i18n(language: str):
    return TRANSLATIONS[_lang(language)]


@router.post("/checks")
def checks(file: UploadFile = File(...), applicable_date: str = Form(""), language: str = Form("ru"), mode: str = Form("hybrid")):
    language = _lang(language)
    if mode not in {"hybrid", "semantic", "lexical"}:
        raise HTTPException(400, "Unsupported mode")
    applicable = _date(applicable_date, "applicable_date")
    data = _read(file)
    backend = os.getenv("POLISDIFF_AI_BACKEND_URL", "").rstrip("/")
    if backend and mode != "lexical":
        import requests
        try:
            reply = requests.post(f"{backend}/v1/checks", timeout=100, files={"file": (file.filename or "offer.pdf", data, "application/pdf")},
                                  data={"applicable_date": applicable_date, "language": language, "mode": mode})
            if reply.ok:
                return reply.json()
        except (requests.RequestException, ValueError):
            pass  # fall through to the local engine; the report records the mode actually used
    started = time.perf_counter()
    try:
        doc, report = analyze_pdf(data, date.today(), applicable, web_retriever(mode))
    except PDFError as exc:
        raise HTTPException(422, "PDF_UNREADABLE") from exc
    except BusyError as exc:
        raise HTTPException(429, "BUSY") from exc
    view = build_view(report, language)
    images, rendered = {}, time.perf_counter()
    for f in report.findings:
        for ev in f.evidence[:IMAGES_PER_CHECK]:
            try:
                images[ev.passage_id] = base64.b64encode(render_evidence(data, doc, f, ev)["png"]).decode("ascii")
            except PDFError:
                pass
    return {"view": view, "report": report.model_dump(mode="json"), "doc": _doc_info(doc, file.filename or "offer.pdf"),
            "images": images, "engine": {"retrieval_used": report.retrieval_used, "ai_fallback": report.retrieval_requested != report.retrieval_used,
            "analysis_seconds": round(report.timings_seconds.get("analysis", 0), 2), "render_seconds": round(time.perf_counter() - rendered, 2),
            "total_seconds": round(time.perf_counter() - started, 2)}, "suggested_dates": [d.isoformat() for d in doc.detected_dates]}


class LocalizeRequest(BaseModel):
    report: Report
    language: str = "ru"


@router.post("/localize")
def localize(body: LocalizeRequest):
    return build_view(body.report, _lang(body.language))


@router.post("/pages")
def pages(file: UploadFile = File(...), number: int = Form(...)):
    try:
        return {"image": base64.b64encode(render_page(_read(file), number)).decode("ascii")}
    except PDFError as exc:
        raise HTTPException(422, "PDF_UNREADABLE") from exc


class DeadlineRequest(BaseModel):
    claim_date: date | None = None
    decision_date: date | None = None


@router.post("/deadlines")
def deadlines(body: DeadlineRequest):
    if not (body.claim_date or body.decision_date):
        raise HTTPException(400, "Provide claim_date or decision_date")
    if body.claim_date and body.decision_date and body.decision_date < body.claim_date:
        raise HTTPException(400, "decision_date cannot precede claim_date")
    return claim_clock(body.claim_date, body.decision_date)


class LetterRequest(BaseModel):
    kind: str
    language: str = "ru"
    report: Report | None = None
    rule_id: str | None = None
    document_name: str = "offer.pdf"
    claim_date: date | None = None
    decision_date: date | None = None
    insurer: str = "[insurer]"
    name: str = "[your name]"
    policy: str = "[number]"


@router.post("/letters")
def letters(body: LetterRequest):
    language, today = _lang(body.language), date.today().isoformat()
    try:
        if body.kind == "offer_conflict":
            if body.report is None or not body.rule_id:
                raise HTTPException(400, "report and rule_id are required")
            finding = next((f for f in body.report.findings if f.rule_id == body.rule_id), None)
            if finding is None:
                raise HTTPException(400, "Unknown rule")
            return offer_conflict_letter(body.report, finding, finding_details(body.report, finding, language), language,
                                         body.document_name, body.insurer, body.name, body.policy, today)
        clock = claim_clock(body.claim_date, body.decision_date)
        key = "decision_notice" if body.kind == "late_decision" else "payment"
        step = next((s for s in clock["steps"] if s["key"] == key), None)
        if step is None:
            raise HTTPException(400, "The matching date is required")
        return deadline_letter(body.kind, step, language, body.claim_date.isoformat() if body.claim_date else "",
                               body.decision_date.isoformat() if body.decision_date else "", body.insurer, body.name, body.policy, today)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
