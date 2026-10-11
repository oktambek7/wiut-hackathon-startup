import sys
from .extraction import _extract, validate_pdf, MAX_BYTES, MAX_PAGES


def render_png(data: bytes, page_number: int) -> bytes:
    """Rasterize one page; shared by the isolated worker and in-process hosts."""
    import pymupdf
    validate_pdf(data)
    with pymupdf.open(stream=data, filetype="pdf") as pdf:
        if pdf.needs_pass or not 1 <= len(pdf) <= MAX_PAGES or not 1 <= page_number <= len(pdf):
            raise ValueError("Unsupported document")
        page = pdf[page_number - 1]
        scale = min(1.4, 1400/max(page.rect.width, page.rect.height))
        return page.get_pixmap(matrix=pymupdf.Matrix(scale, scale), alpha=False).tobytes("png")


def evidence_png(request: dict) -> dict:
    """Highlight one verified evidence span; shared by worker and in-process hosts."""
    import base64
    import hashlib
    from dataclasses import asdict
    import pymupdf
    from .models import Finding, Evidence
    from .localization import locate_context, locate_on_page
    data = base64.b64decode(request["pdf"], validate=True)
    validate_pdf(data)
    if hashlib.sha256(data).hexdigest() != request["sha256"]:
        raise ValueError("Document mismatch")
    ev = Evidence.model_validate(request["evidence"])
    finding = Finding.model_validate(request["finding"])
    if ev not in finding.evidence:
        raise ValueError("Unknown evidence")
    with pymupdf.open(stream=data, filetype="pdf") as pdf:
        if pdf.needs_pass or not 1 <= len(pdf) <= MAX_PAGES or not 1 <= ev.page <= len(pdf):
            raise ValueError("Unsupported document")
        page = pdf[ev.page - 1]
        location = locate_on_page(page, finding, ev)
        if location.state == "evidence_mismatch":
            raise ValueError("Evidence mismatch")
        # Blue: the subject or the event a deadline counts from. Amber: the checked value.
        context = locate_context(page, finding, ev) if location.state == "precise" else []
        for box in context:
            page.draw_rect(pymupdf.Rect(box), color=(.15, .45, .9), fill=(.35, .6, 1), fill_opacity=.22, width=.6, overlay=True)
        for box in location.rectangles:
            page.draw_rect(pymupdf.Rect(box), color=(.85, .55, 0), fill=(1, .75, .15), fill_opacity=.35, width=.8, overlay=True)
        scale = min(1.4, 1400/max(page.rect.width, page.rect.height))
        png = page.get_pixmap(matrix=pymupdf.Matrix(scale, scale), alpha=False).tobytes("png")
        focus = None
        if location.rectangles:
            # Close-up of the highlighted lines across the full page width, for reading on a phone.
            boxes = [pymupdf.Rect(b) for b in location.rectangles + context]
            top, bottom = min(b.y0 for b in boxes), max(b.y1 for b in boxes)
            clip = pymupdf.Rect(page.rect.x0, max(page.rect.y0, top - 36), page.rect.x1, min(page.rect.y1, bottom + 36))
            focus = base64.b64encode(page.get_pixmap(matrix=pymupdf.Matrix(2.2, 2.2), clip=clip, alpha=False).tobytes("png")).decode("ascii")
        return {"location": asdict(location), "png": base64.b64encode(png).decode("ascii"), "focus": focus}


def main():
    # Linux container adds address-space/CPU limits; Windows uses parent timeout.
    if sys.platform != "win32":
        import resource
        resource.setrlimit(resource.RLIMIT_AS, (768 * 1024**2, 768 * 1024**2))
        resource.setrlimit(resource.RLIMIT_CPU, (20, 20))
    try:
        if "--evidence" in sys.argv:
            import json
            request = json.loads(sys.stdin.buffer.read(MAX_BYTES * 2 + 1))
            sys.stdout.buffer.write(json.dumps(evidence_png(request)).encode())
            return
        data = sys.stdin.buffer.read(MAX_BYTES + 1)
        validate_pdf(data)
        if "--render" in sys.argv:
            sys.stdout.buffer.write(render_png(data, int(sys.argv[-1])))
        else:
            sys.stdout.buffer.write(_extract(data).model_dump_json().encode("utf-8"))
    except Exception:
        # No document content, filenames or parser tracebacks in logs.
        sys.exit(2)

if __name__ == "__main__":
    main()
