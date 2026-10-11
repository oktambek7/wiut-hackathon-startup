"""Stateless HTTP API over the unchanged engine; used by the Vercel web UI.

Nothing is stored server side: the browser keeps the PDF and report, and sends them
back for page previews, review annotations and HTML export. Findings, rules and
statuses come from the same engine as the Streamlit app.
"""
import base64
import os
from datetime import date

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

from .deployment import model_files_status
from .engine import load_catalogue
from .export import add_review, html_report
from .extraction import PDFError, render_evidence, render_page
from .i18n import LANGUAGES, TRANSLATIONS, tr, warning_text
from .localization import quote_html
from .models import Report, Status
from .presentation import (MODE_LABELS, REVIEW_LABELS, SECTION_LABELS, STANDARD_LIMITATIONS, STATUS_ICONS,
                           STATUS_LABELS, compact_finding, counts, finding_details, labels, readiness_message,
                           rule_name, summary)
from .runtime import web_retriever
from .service import BusyError, analyze_pdf

APP_VERSION = "0.3.0-web"
MODES = ("hybrid", "semantic", "lexical")
# Vercel functions reject request bodies above 4.5 MB; the Streamlit app keeps 10 MiB.
MAX_UPLOAD = int(os.getenv("POLISDIFF_MAX_UPLOAD_BYTES", str(4 * 1024 * 1024)))

router = APIRouter()


def _language(language: str) -> str:
    if language not in LANGUAGES:
        raise HTTPException(400, "Unsupported language")
    return language


def _parse_date(value: str | None, field: str) -> date | None:
    if not value:
        return None
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise HTTPException(400, f"{field} must be YYYY-MM-DD") from exc


def _read_pdf(upload: UploadFile) -> bytes:
    data = upload.file.read(MAX_UPLOAD + 1)
    if len(data) > MAX_UPLOAD:
        raise HTTPException(413, f"PDF exceeds the {MAX_UPLOAD // (1024 * 1024)} MiB limit of this deployment")
    return data


def _ai_backend() -> str | None:
    return os.getenv("POLISDIFF_AI_BACKEND_URL", "").rstrip("/") or None


@router.get("/health")
def health():
    return {"status": "ok", "version": APP_VERSION}


@router.get("/config")
def config():
    catalogue, rules, digest = load_catalogue()
    model = model_files_status()
    return {
        "version": APP_VERSION,
        "catalogue_version": catalogue["catalogue_version"],
        "catalogue_sha256": digest,
        "verified_access_date": catalogue["verified_access_date"],
        "supported_date_range": catalogue["supported_date_range"],
        "max_upload_bytes": MAX_UPLOAD,
        "languages": LANGUAGES,
        "modes": list(MODES),
        "ai_local": model["state"] == "files_present",
        "ai_backend": bool(_ai_backend()),
        "rules": [{"id": r.id, "name": rule_name(r), "reference": r.reference, "official_source": r.official_source,
                   "interpretation": r.interpretation, "reviewer_status": r.reviewer_status,
                   "versions": [v.model_dump(mode="json") for v in r.versions]} for r in rules],
        "today": date.today().isoformat(),
    }


@router.get("/i18n/{language}")
def i18n(language: str):
    """Russian source string -> reviewed translation; the UI uses Russian text as its keys."""
    return TRANSLATIONS[_language(language)]


def _evidence_view(report, finding, ev, language, data, doc, with_image):
    view = {"passage_id": ev.passage_id, "page": ev.page, "section": ev.section,
            "section_label": labels(SECTION_LABELS, language).get(ev.section, ev.section),
            "quote_html": quote_html(ev, finding), "quote": ev.quote,
            "extracted_value": ev.extracted_value, "unit": ev.unit, "image": None, "highlight": None}
    if with_image:
        try:
            rendered = render_evidence(data, doc, finding, ev)
            view["image"] = base64.b64encode(rendered["png"]).decode("ascii")
            view["highlight"] = rendered["location"]["state"]
        except PDFError:
            pass
    return view


def _build_response(data, doc, report, language, mode_note=None):
    status_labels = labels(STATUS_LABELS, language)
    findings = []
    for f in sorted(report.findings, key=lambda f: f.status != Status.POTENTIAL_CONFLICT):
        details = finding_details(report, f, language)
        compact = compact_finding(report, f, language)
        findings.append({
            "rule_id": f.rule_id, "name": rule_name(f, language), "status": f.status.value,
            "status_label": status_labels[f.status], "icon": STATUS_ICONS[f.status],
            "pending_date": compact["pending"], "observation": compact["observation"],
            "details": {k: details[k] for k in ("checked", "found", "reference", "reason", "verification",
                        "remediation", "remediation_kind", "verification_state", "blockers", "provision_reference",
                        "period", "date_note", "source_url", "source_quote", "comparable")},
            "source_version_note": f.source_version_note,
            "evidence": [_evidence_view(report, f, ev, language, data, doc, i == 0)
                         for i, ev in enumerate(f.evidence)],
        })
    c = counts(report)
    return {
        "report": report.model_dump(mode="json"),
        "view": {
            "language": language,
            "summary": summary(report, language),
            "counts": {s.value: c[s] for s in Status},
            "findings": findings,
            "readiness": readiness_message(language) if report.applicable_date is None else None,
            "warnings": [warning_text(w, language) for w in report.warnings],
            "unreadable_pages": [p.number for p in doc.pages if not p.readable],
            "detected_dates": [d.isoformat() for d in doc.detected_dates],
            "pages": [{"number": p.number, "readable": p.readable, "section": p.section,
                       "section_label": labels(SECTION_LABELS, language).get(p.section, p.section)} for p in doc.pages],
            "retrieval_label": labels(MODE_LABELS, language)[report.retrieval_used],
            "ai_fallback": report.retrieval_requested != report.retrieval_used,
            "limitations": [tr(t, language) for t in STANDARD_LIMITATIONS],
            "review_labels": labels(REVIEW_LABELS, language),
            "mode_note": mode_note,
        },
    }


@router.post("/analyze")
def analyze(file: UploadFile = File(...), applicable_date: str = Form(""), audit_date: str = Form(""),
            mode: str = Form("hybrid"), language: str = Form("ru")):
    language = _language(language)
    if mode not in MODES:
        raise HTTPException(400, "Unsupported retrieval mode")
    audit = _parse_date(audit_date, "audit_date") or date.today()
    applicable = _parse_date(applicable_date, "applicable_date")
    if audit > date.today():
        raise HTTPException(400, "audit_date cannot be in the future")
    data = _read_pdf(file)
    backend = _ai_backend()
    if backend and mode != "lexical":
        import requests
        try:
            reply = requests.post(f"{backend}/api/analyze", timeout=100,
                files={"file": (file.filename or "offer.pdf", data, "application/pdf")},
                data={"applicable_date": applicable_date, "audit_date": audit.isoformat(), "mode": mode, "language": language})
            if reply.ok:
                body = reply.json()
                body["view"]["mode_note"] = "ai_backend"
                return body
        except (requests.RequestException, ValueError):
            pass  # visible lexical fallback below; the report records the mode actually used
    try:
        retriever = web_retriever(mode)
        doc, report = analyze_pdf(data, audit, applicable, retriever)
    except PDFError as exc:
        raise HTTPException(422, "PDF_UNREADABLE") from exc
    except BusyError as exc:
        raise HTTPException(429, "BUSY") from exc
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    return _build_response(data, doc, report, language,
                           "ai_backend_unreachable" if backend and mode != "lexical" else None)


@router.post("/page")
def page(file: UploadFile = File(...), number: int = Form(...)):
    data = _read_pdf(file)
    try:
        png = render_page(data, number)
    except PDFError as exc:
        raise HTTPException(422, "PDF_UNREADABLE") from exc
    return {"image": base64.b64encode(png).decode("ascii")}


class ReviewRequest(BaseModel):
    report: Report
    rule_id: str
    action: str
    rationale: str


@router.post("/review")
def review(body: ReviewRequest):
    """Append an analyst annotation to a client-held report; the algorithm result is preserved."""
    if body.action not in REVIEW_LABELS:
        raise HTTPException(400, "Unsupported action")
    if not 3 <= len(body.rationale.strip()) <= 2000:
        raise HTTPException(400, "RATIONALE_LENGTH")
    try:
        add_review(body.report, body.rule_id, body.action, body.rationale)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    return body.report.model_dump(mode="json")


class ExportRequest(BaseModel):
    report: Report
    language: str = "ru"


@router.post("/export/html", response_class=HTMLResponse)
def export_html(body: ExportRequest):
    return HTMLResponse(html_report(body.report, _language(body.language)))


@router.get("/diagnostics")
def diagnostics():
    """Non-sensitive runtime facts for the in-app trust panel."""
    import sys
    return {"version": APP_VERSION, "python": sys.version.split()[0], "ai_local": model_files_status()["state"] == "files_present",
            "ai_backend": bool(_ai_backend()), "isolation": os.getenv("POLISDIFF_ISOLATION") or "subprocess",
            "external_ai_api": False}
