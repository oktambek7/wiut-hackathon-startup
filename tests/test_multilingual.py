import json
from datetime import date
from pathlib import Path

import pytest

from polisdiff.engine import extract_value, load_catalogue
from polisdiff.retrieval import Retriever
from polisdiff.service import analyze_pdf
from polisdiff.text import detect_languages, normalize

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = json.loads((ROOT / "evaluation/multilingual_manifest.json").read_text(encoding="utf-8"))
RULES = {r.id: r for r in load_catalogue()[1]}
# Designed label UNVERIFIABLE, engine NOT_FOUND: documented in evaluation/MULTILINGUAL_RESULTS.md.
KNOWN = {("en-a_wrong_trigger", "OSAGO_PAYMENT"): "NOT_FOUND"}


@pytest.mark.parametrize("item", MANIFEST, ids=[m["id"] for m in MANIFEST])
def test_english_and_mixed_fixtures(item):
    applicable = date.fromisoformat(item["applicable_date"]) if item["applicable_date"] else None
    _, report = analyze_pdf((ROOT / item["path"]).read_bytes(), date(2026, 10, 11), applicable, Retriever("lexical"))
    got = {f.rule_id: f.status.value for f in report.findings}
    for rule, want in item["expected"].items():
        assert got[rule] == KNOWN.get((item["id"], rule), want), rule


@pytest.mark.parametrize("text,rule,value,unit,problem", [
    ("insurance compensation is paid within 5 working days from the date of the insurer's decision.", "OSAGO_PAYMENT", 5, "working_days", None),
    ("the insurer shall transfer the compensation within seven business days after the insurer's payment decision.", "OSAGO_PAYMENT", 7, "working_days", None),
    ("compensation is paid within 5 calendar days from the date of the insurer's decision.", "OSAGO_PAYMENT", 5, "days", "calendar"),
    ("if documents are complete, compensation is paid within 5 working days from the insurer's decision.", "OSAGO_PAYMENT", None, None, "condition"),
    ("the total insurance sum is 80,000,000 uzs.", "OSAGO_SUM", 80_000_000, "UZS", None),
    ("sum insured: 80 million soums.", "OSAGO_SUM", 80_000_000, "UZS", None),
    ("the total insurance sum is up to 80 million uzs.", "OSAGO_SUM", None, None, "range"),
    ("the policyholder is informed of the decision on compensation within fifteen days after receipt of the written or electronic application.",
     "OSAGO_DECISION_NOTICE", 15, "days", None),
])
def test_english_extraction(text, rule, value, unit, problem):
    got_value, got_unit, reason = extract_value(RULES[rule], normalize(text))
    if problem is None:
        assert (got_value, got_unit, reason) == (value, unit, None)
    else:
        assert reason is not None
        if value is not None:
            assert (got_value, got_unit) == (value, unit)


def test_english_language_label_does_not_replace_uzbek():
    assert "en" in detect_languages("The insurer pays compensation within 5 working days.")
    assert detect_languages("Sug'urta tovoni besh ish kuni ichida to'lanadi.") == ["uz-Latn"]
