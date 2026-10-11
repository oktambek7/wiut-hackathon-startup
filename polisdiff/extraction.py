"""Bounded PDF parsing. JavaScript, attachments and links are never executed."""
import hashlib
import json
import os
import re
import subprocess
import sys
from pathlib import Path
from .models import Document, Page, Passage
from .text import normalize, detect_languages, extract_dates

MAX_BYTES = 10 * 1024 * 1024
MAX_PAGES = 80
MAX_CHARS = 500_000
MAX_PASSAGES = 1800


class PDFError(ValueError):
    pass


def validate_pdf(data: bytes):
    if not data or len(data) > MAX_BYTES:
        raise PDFError("PDF must contain between 1 byte and 10 MiB.")
    if not data.startswith(b"%PDF-"):
        raise PDFError("Invalid PDF header; changing a file extension is insufficient.")


def _extract(data: bytes) -> Document:
    import pymupdf
    validate_pdf(data)
    pymupdf.TOOLS.mupdf_display_errors(False)
    pymupdf.TOOLS.mupdf_display_warnings(False)
    try:
        pdf = pymupdf.open(stream=data, filetype="pdf")
    except Exception as exc:
        raise PDFError("PDF could not be parsed.") from exc
    with pdf:
        if pdf.needs_pass:
            raise PDFError("Encrypted PDFs are unsupported.")
        if not 1 <= len(pdf) <= MAX_PAGES:
            raise PDFError("Supported PDF length is 1–80 pages.")
        pages, passages, warnings = [], [], []
        total_chars = 0
        appendix = False
        for i, page in enumerate(pdf):
            # MuPDF text extraction does not execute PDF JavaScript.
            blocks = [b for b in page.get_text("blocks", sort=True) if b[6] == 0]
            text = "".join(b[4] for b in blocks)
            norm = normalize(text)
            # Require both a rules heading and legal attribution, not a passing reference.
            is_rules = bool(re.search(r"(?im)^\s*(?:правила\s+обязательного\s+страхования|қоидалар|qoidalar)(?:\s|$)", text))
            heading_search = re.sub(r"прилож\s+ение", "приложение", norm)
            attribution = bool(re.search(r"(?:приложение|илова|ilova).{0,250}(?:141|2008)|(?:141|2008).{0,250}(?:приложение|илова|ilova)", heading_search))
            if is_rules and attribution:
                appendix = True
            section = "regulatory_appendix" if appendix else "offer"
            readable = len(re.sub(r"\s", "", text)) >= 30 and text.count("\ufffd") < max(3, len(text) * .02)
            if not readable:
                warnings.append(f"Page {i + 1}: insufficient or damaged text; OCR is not enabled. Manual review required.")
            total_chars += len(text)
            if total_chars > MAX_CHARS:
                raise PDFError("Extracted text exceeds the resource limit.")
            pages.append(Page(number=i + 1, text=text, chars=len(text), readable=readable, section=section))
            # Sentence/numbered-clause boundaries preserve context across PDF layout blocks.
            block_positions, offset = [], 0
            for block in blocks:
                block_positions.append((offset, offset + len(block[4]), block[:4]))
                offset += len(block[4])
            boundaries = [0] + [m.end() for m in re.finditer(
                r"(?<=[;!?])\s+|(?<=\.)\s+(?=[A-ZА-ЯЎҚҒҲЁ])|\n(?=\s*\d+[.)]\s)", text)] + [len(text)]
            for begin, finish in zip(boundaries, boundaries[1:]):
                start = begin
                while start < finish:
                    end = min(start + 1200, finish)
                    if end < finish:
                        boundary = text.rfind(" ", start + 650, end)
                        if boundary > start:
                            end = boundary + 1
                    fragment = text[start:end]
                    boxes = [box for a,b,box in block_positions if a < end and b > start]
                    if len(fragment.strip()) >= 12 and boxes:
                        bbox = (min(b[0] for b in boxes), min(b[1] for b in boxes),
                                max(b[2] for b in boxes), max(b[3] for b in boxes))
                        passages.append(Passage(id=f"p{i+1}-{len(passages)}", page=i+1,
                            text=fragment, normalized=normalize(fragment), start=start,
                            end=end, bbox=bbox, languages=detect_languages(fragment), section=section))
                    start = end
            if len(passages) > MAX_PASSAGES:
                raise PDFError("Too many passages; document exceeds resource limits.")
        languages = sorted({lang for p in passages for lang in p.languages})
        refs = [p for p in passages if p.section == "offer" and
                re.search(r"\b141\b", p.normalized) and
                re.search(r"правил|qoid|қоид|qaror|қарор|постановлен", p.normalized)]
        return Document(sha256=hashlib.sha256(data).hexdigest(), pages=pages, passages=passages,
                        languages=languages, warnings=warnings,
                        detected_dates=extract_dates(pages[0].text), governing_reference=refs)


def in_process() -> bool:
    """Serverless hosts (Vercel) bound each invocation themselves; set to skip child processes."""
    return os.getenv("POLISDIFF_ISOLATION", "").lower() == "inprocess"


def extract_pdf(data: bytes, *, isolated: bool = True) -> Document:
    validate_pdf(data)
    if not isolated or in_process():
        return _extract(data)
    # Parsing runs in a killable process. Raw bytes are sent on stdin, never disk/logs.
    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"
    try:
        process = subprocess.run([sys.executable, "-m", "polisdiff.extract_worker"],
            input=data, capture_output=True, timeout=25, env=env,
            cwd=Path(__file__).resolve().parents[1])
    except subprocess.TimeoutExpired as exc:
        raise PDFError("PDF extraction exceeded 25 seconds.") from exc
    if process.returncode:
        raise PDFError("PDF rejected: malformed, encrypted, empty, or over resource limits.")
    try:
        return Document.model_validate_json(process.stdout)
    except (ValueError, json.JSONDecodeError) as exc:
        raise PDFError("Extraction worker returned an invalid result.") from exc


def render_page(data: bytes, page_number: int) -> bytes:
    """Raster evidence preview; excludes active PDF content."""
    validate_pdf(data)
    if type(page_number) is not int or not 1 <= page_number <= MAX_PAGES:
        raise PDFError("Invalid page number.")
    if in_process():
        from .extract_worker import render_png
        try:
            return render_png(data, page_number)
        except Exception as exc:
            raise PDFError("Page could not be rendered safely.") from exc
    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"
    try:
        proc = subprocess.run([sys.executable, "-m", "polisdiff.extract_worker", "--render", str(page_number)],
            input=data, capture_output=True, timeout=15, env=env, cwd=Path(__file__).resolve().parents[1])
    except subprocess.TimeoutExpired as exc:
        raise PDFError("Page rendering timed out.") from exc
    if proc.returncode:
        raise PDFError("Page could not be rendered safely.")
    return proc.stdout


def render_evidence(data, doc, finding, ev):
    """One selected page, one bounded worker, one session-local preview.

    Geometry is ephemeral and is never trusted from an imported JSON report.
    """
    import base64
    validate_pdf(data)
    if hashlib.sha256(data).hexdigest() != doc.sha256 or not 1 <= ev.page <= len(doc.pages):
        raise PDFError("Stale evidence selection.")
    passage = next((p for p in doc.passages if p.id == ev.passage_id), None)
    if passage is None or (passage.page, passage.start, passage.end, passage.text) != (ev.page, ev.start, ev.end, ev.quote):
        raise PDFError("Evidence does not match the original document.")
    payload = {"pdf": base64.b64encode(data).decode("ascii"), "sha256": doc.sha256,
               "finding": finding.model_dump(mode="json"), "evidence": ev.model_dump(mode="json")}
    if in_process():
        from .extract_worker import evidence_png
        try:
            result = evidence_png(payload)
            result["png"] = base64.b64decode(result["png"], validate=True)
            return result
        except Exception as exc:
            raise PDFError("Evidence could not be rendered safely.") from exc
    request = json.dumps(payload).encode()
    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"
    try:
        proc = subprocess.run([sys.executable, "-m", "polisdiff.extract_worker", "--evidence"],
            input=request, capture_output=True, timeout=15, env=env, cwd=Path(__file__).resolve().parents[1])
    except subprocess.TimeoutExpired as exc:
        raise PDFError("Evidence rendering timed out.") from exc
    if proc.returncode:
        raise PDFError("Evidence could not be rendered safely.")
    try:
        result = json.loads(proc.stdout)
        result["png"] = base64.b64decode(result["png"], validate=True)
        if result["location"]["state"] not in {"precise", "precise_unavailable"}:
            raise ValueError("Mismatched evidence")
        return result
    except (KeyError, ValueError, TypeError) as exc:
        raise PDFError("Invalid evidence preview.") from exc
