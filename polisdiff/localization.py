"""Conservative original-text -> character geometry mapping; never use Passage.bbox.

Only whitespace and Uzbek apostrophe equivalence are admitted. No OCR, spelling
repair, transliteration, or search for an arbitrary occurrence of a number.
"""
from dataclasses import dataclass, field
from html import escape
import re
from .text import APOSTROPHES


@dataclass
class Localization:
    state: str
    quote: str = ""
    start: int | None = None  # quote-relative original offsets
    end: int | None = None
    rectangles: list[tuple] = field(default_factory=list)


def canonical_map(text):
    """Return comparison string and inclusive original-character ranges."""
    out, positions = [], []
    for i, char in enumerate(text):
        char = " " if char.isspace() else "'" if char in APOSTROPHES else char
        if char == " " and out and out[-1] == " ":
            positions[-1] = (positions[-1][0], i + 1)
        else:
            out.append(char)
            positions.append((i, i + 1))
    return "".join(out), positions


def trigger_range(finding, ev):
    """Revalidate the engine value and identify its original spelling, or abstain."""
    from .engine import load_catalogue, extract_value, SUM, MONEY, DAYS
    from .text import normalize
    rule = next((r for r in load_catalogue()[1] if r.id == finding.rule_id), None)
    if rule is None or ev.extracted_value is None:
        return None
    # Do not map lossy NFKC/casefold expansions. Apostrophes and whitespace have
    # an explicit reversible index map, unlike arbitrary normalization repairs.
    original, offsets = canonical_map(ev.quote)
    folded = original.casefold().strip()
    if len(original.casefold()) != len(original) or normalize(ev.quote) != folded:
        return None
    prefix = len(original.casefold()) - len(original.casefold().lstrip())
    value, unit, _ = extract_value(rule, folded)
    if (value, unit) != (ev.extracted_value, ev.unit):
        return None
    if rule.logic == "sum":
        concept = re.search(SUM, folded)
        if not concept:
            return None
        begin = concept.end()
        matches = list(MONEY.finditer(folded[begin:begin + 160]))
    else:
        begin = 0
        matches = list(DAYS.finditer(folded))
    if len(matches) != 1:
        return None
    match = matches[0]
    a, b = prefix + begin + match.start(), prefix + begin + match.end()
    return offsets[a][0], offsets[b - 1][1]


def context_range(finding, ev):
    """Original span of the words that give the value its meaning: the insurance-sum subject or the
    event a deadline counts from. Only shown when the value itself was revalidated."""
    from .engine import load_catalogue, context_pattern
    from .text import normalize
    if trigger_range(finding, ev) is None:
        return None
    rule = next((r for r in load_catalogue()[1] if r.id == finding.rule_id), None)
    original, offsets = canonical_map(ev.quote)
    folded = original.casefold()
    prefix = len(folded) - len(folded.lstrip())
    if rule is None or normalize(ev.quote) != folded.strip():
        return None
    match = context_pattern(rule).search(folded.strip())
    if match is None or match.end() <= match.start():
        return None
    a, b = prefix + match.start(), prefix + match.end()
    return offsets[a][0], offsets[b - 1][1]


def quote_html(ev, finding):
    """Always escape source text; mark only revalidated original substrings.
    <mark> = the checked value; <mark class="ctx"> = its subject or trigger event."""
    value = trigger_range(finding, ev)
    if value is None:
        return escape(ev.quote)
    spans = [(value[0], value[1], "<mark>")]
    context = context_range(finding, ev)
    if context and (context[1] <= value[0] or context[0] >= value[1]):
        spans.append((context[0], context[1], '<mark class="ctx">'))
    out, cursor = [], 0
    for a, b, tag in sorted(spans):
        out += [escape(ev.quote[cursor:a]), tag, escape(ev.quote[a:b]), "</mark>"]
        cursor = b
    return "".join(out) + escape(ev.quote[cursor:])


def locate_context(page, finding, ev):
    """Rectangles for the subject/trigger words, using the same strict mapping as the value; [] if not precise."""
    target = context_range(finding, ev)
    if target is None:
        return []
    located = locate_on_page(page, finding, ev, target=target)
    return located.rectangles if located.state == "precise" else []


def locate_on_page(page, finding, ev, target=None):
    """Called inside the bounded PDF worker, on the selected page only."""
    target = target if target is not None else trigger_range(finding, ev)
    result = Localization("precise_unavailable", ev.quote)
    # Reconstruct precisely the extraction protocol, not PyMuPDF's sorted words
    # reading order (which can differ in columns/tables).
    blocks = [b for b in page.get_text("blocks", sort=True) if b[6] == 0]
    page_text = "".join(b[4] for b in blocks)
    if not ev.quote or ev.start < 0 or ev.end != ev.start + len(ev.quote) or page_text[ev.start:ev.end] != ev.quote:
        result.state = "evidence_mismatch"
        return result
    if target is None:
        return result
    result.start, result.end = target
    absolute_a, absolute_b = ev.start + target[0], ev.start + target[1]
    raw = page.get_text("rawdict")
    raw_blocks = [b for b in raw["blocks"] if b["type"] == 0]
    rectangles, offset = [], 0
    for block in blocks:
        a, b = max(absolute_a, offset), min(absolute_b, offset + len(block[4]))
        if a < b:
            # Image-preservation defaults differ between APIs: block numbers
            # are not stable identifiers. Require a unique matching boundary
            # AND the complete reconstructed text below before mapping chars.
            candidates = [rb for rb in raw_blocks if all(abs(x-y) < .001 for x,y in zip(rb['bbox'],block[:4]))]
            if len(candidates) != 1:
                return result
            rb = candidates[0]
            chars, text = [], []
            for line_id, line in enumerate(rb["lines"]):
                # Non-horizontal text needs quads; do not approximate with boxes.
                if tuple(line["dir"]) != (1.0, 0.0):
                    return result
                for span in line["spans"]:
                    for char in span["chars"]:
                        text.append(char["c"])
                        chars.append((line_id, char["bbox"], char["c"]))
                text.append("\n")
                chars.append(None)
            original_key, original_map = canonical_map(block[4])
            geometry_key, geometry_map = canonical_map("".join(text))
            if original_key != geometry_key:
                return result
            indices = [i for i, (x, y) in enumerate(original_map) if x < b - offset and y > a - offset]
            if not indices:
                return result
            selected = chars[geometry_map[indices[0]][0]:geometry_map[indices[-1]][1]]
            # Consecutive characters only; separate lines and large layout gaps.
            current, last_line = None, None
            for char in selected:
                if char is None or char[2].isspace():
                    continue
                line_id, box, _ = char
                x0, y0, x1, y1 = box
                import math
                if not all(math.isfinite(v) for v in box) or x1 <= x0 or y1 <= y0:
                    return result
                if current is not None and line_id == last_line and x0 >= current[0] and x0 - current[2] < 8:
                    current = (current[0], min(current[1], y0), max(current[2], x1), max(current[3], y1))
                    rectangles[-1] = current
                else:
                    current = tuple(box)
                    rectangles.append(current)
                last_line = line_id
        offset += len(block[4])
    if not rectangles or len(rectangles) > 40:
        return result
    # Duplicate/overlapping visible text cannot prove an unambiguous location.
    import pymupdf
    all_words = page.get_text("words")
    seen = set()
    for word in all_words:
        key = (tuple(round(v, 3) for v in word[:4]), word[4])
        if key in seen and any(pymupdf.Rect(word[:4]).intersects(pymupdf.Rect(r)) for r in rectangles):
            return result
        seen.add(key)
    for rect in rectangles:
        r = pymupdf.Rect(rect)
        if not page.cropbox.contains(r):
            return result
        words = page.get_text("words", clip=r)
        if not words:  # Independent word-level validation of visible geometry.
            return result
    result.rectangles = rectangles
    result.state = "precise"
    return result
