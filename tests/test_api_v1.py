from datetime import date
from pathlib import Path

import pytest

pytest.importorskip("fastapi")
pytest.importorskip("multipart")
from fastapi.testclient import TestClient

from polisdiff.deadlines import claim_clock, is_working_day, working_days_after
from polisdiff.server import app

ROOT = Path(__file__).resolve().parents[1]
client = TestClient(app)
PAYMENT_CONFLICT = (ROOT / "tests/fixtures/evaluation/uz-Latn_payment_conflict.pdf").read_bytes()


def check(data=PAYMENT_CONFLICT, **form):
    return client.post("/v1/checks", files={"file": ("offer.pdf", data, "application/pdf")}, data={"mode": "lexical", "language": "en", **form})


def test_working_days_skip_weekend_and_decreed_holidays():
    # 26 May 2026 decision: 27-29 May are Qurbon Hayit days off; five working days end Fri 5 June.
    due, skipped = working_days_after(date(2026, 5, 26), 5)
    assert due == date(2026, 6, 5) and [s["date"] for s in skipped] == ["2026-05-27", "2026-05-28", "2026-05-29"]
    assert not is_working_day(date(2026, 3, 9)) and not is_working_day(date(2026, 1, 1)) and is_working_day(date(2026, 1, 5))


def test_claim_clock_uses_catalogue_rules():
    steps = {s["key"]: s for s in claim_clock(date(2026, 1, 12), date(2026, 1, 12))["steps"]}
    assert steps["decision_notice"]["due"] == "2026-01-27" and steps["payment"]["due"] == "2026-01-19"
    assert steps["payment"]["rule_id"] == "OSAGO_PAYMENT" and steps["payment"]["source_quote"]


def test_check_returns_plain_verdict_with_evidence_images():
    body = check(applicable_date="2026-01-05").json()
    view = body["view"]
    assert view["level"] == "attention" and view["checks"][0]["status"] == "POTENTIAL_CONFLICT"
    first = view["checks"][0]
    assert first["can_complain"] and first["evidence"][0]["passage_id"] in body["images"]
    assert body["doc"]["pages"] >= 1 and body["engine"]["retrieval_used"] == "lexical"


def test_unknown_date_never_guessed():
    view = check().json()["view"]
    assert view["level"] == "unknown" and not any(c["can_complain"] for c in view["checks"])


def test_localize_changes_language_without_the_pdf():
    body = check(applicable_date="2026-01-05").json()
    ru = client.post("/v1/localize", json={"report": body["report"], "language": "ru"}).json()
    assert ru["language"] == "ru" and ru["headline"] != body["view"]["headline"]


def test_letters_only_for_real_conflicts():
    body = check(applicable_date="2026-01-05").json()
    letter = client.post("/v1/letters", json={"kind": "offer_conflict", "report": body["report"], "rule_id": "OSAGO_PAYMENT", "language": "en"}).json()
    assert "offer.pdf" in letter["text"] or "page" in letter["text"]
    assert client.post("/v1/letters", json={"kind": "offer_conflict", "report": body["report"], "rule_id": "OSAGO_SUM", "language": "en"}).status_code == 400
    late = client.post("/v1/letters", json={"kind": "late_payment", "decision_date": "2026-01-12", "language": "uz-Latn"}).json()
    assert "2026-01-19" in late["text"] and late["unreviewed"]


def test_deadlines_endpoint_validation():
    assert client.post("/v1/deadlines", json={}).status_code == 400
    assert client.post("/v1/deadlines", json={"claim_date": "2026-02-01", "decision_date": "2026-01-01"}).status_code == 400
    assert client.post("/v1/deadlines", json={"claim_date": "2026-02-01"}).json()["steps"][0]["due"] == "2026-02-16"


def test_bad_pdf_and_cors():
    assert check(b"nope").status_code == 422
    r = client.options("/v1/checks", headers={"Origin": "https://x.example", "Access-Control-Request-Method": "POST"})
    assert r.headers.get("access-control-allow-origin") == "*"


def test_comparison_focus_and_two_colour_quote():
    body = check(applicable_date="2026-01-05").json()
    pay = next(c for c in body["view"]["checks"] if c["rule_id"] == "OSAGO_PAYMENT")
    assert pay["comparison"] == {"kind": "deadline", "offer": 9.0, "law": 5.0, "unit": "working_days", "difference": 4.0, "direction": "worse"}
    ev = pay["evidence"][0]
    assert "<mark>" in ev["quote_html"] and '<mark class="ctx">' in ev["quote_html"]
    assert body["highlight"][ev["passage_id"]] == "precise" and ev["passage_id"] in body["focus"]
    total = next(c for c in body["view"]["checks"] if c["rule_id"] == "OSAGO_SUM")
    assert total["comparison"]["direction"] == "same"
