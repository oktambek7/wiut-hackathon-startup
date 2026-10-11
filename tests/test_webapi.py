import json
from pathlib import Path

import pytest

pytest.importorskip("fastapi")
pytest.importorskip("multipart")
from fastapi import FastAPI
from fastapi.testclient import TestClient

from polisdiff.webapi import router

ROOT = Path(__file__).resolve().parents[1]
app = FastAPI()
app.include_router(router, prefix="/api")
client = TestClient(app)
FIXTURE = ROOT / "tests/fixtures/evaluation/uz-Latn_payment_conflict.pdf"


def analyze(**data):
    payload = {"mode": "lexical", "language": "en", **data}
    return client.post("/api/analyze", files={"file": ("offer.pdf", FIXTURE.read_bytes(), "application/pdf")}, data=payload)


def test_config_and_i18n():
    cfg = client.get("/api/config").json()
    assert cfg["catalogue_version"] == "1.0.0" and len(cfg["rules"]) == 3
    assert client.get("/api/i18n/uz-Cyrl").json()
    assert client.get("/api/i18n/xx").status_code == 400


def test_analyze_conflict_with_evidence_and_image():
    body = analyze(applicable_date="2026-01-05").json()
    statuses = {f["rule_id"]: f["status"] for f in body["view"]["findings"]}
    assert statuses["OSAGO_PAYMENT"] == "POTENTIAL_CONFLICT"
    first = body["view"]["findings"][0]
    assert first["evidence"][0]["image"] and first["evidence"][0]["quote"]
    assert body["report"]["retrieval_used"] == "lexical"


def test_unknown_date_is_unverifiable_not_guessed():
    body = analyze().json()
    assert {f["status"] for f in body["view"]["findings"]} == {"UNVERIFIABLE"}
    assert body["view"]["readiness"]


def test_invalid_inputs():
    assert analyze(applicable_date="not-a-date").status_code == 400
    assert analyze(mode="magic").status_code == 400
    bad = client.post("/api/analyze", files={"file": ("x.pdf", b"not a pdf", "application/pdf")}, data={"mode": "lexical"})
    assert bad.status_code == 422


def test_review_and_html_export_preserve_algorithm_result():
    report = analyze(applicable_date="2026-01-05").json()["report"]
    updated = client.post("/api/review", json={"report": report, "rule_id": "OSAGO_PAYMENT", "action": "confirm", "rationale": "Checked page 3"}).json()
    assert updated["reviews"][0]["action"] == "confirm"
    assert [f["status"] for f in updated["findings"]] == [f["status"] for f in report["findings"]]
    assert client.post("/api/review", json={"report": report, "rule_id": "OSAGO_PAYMENT", "action": "confirm", "rationale": "x"}).status_code == 400
    html = client.post("/api/export/html", json={"report": updated, "language": "ru"})
    assert html.status_code == 200 and "Checked page 3" in html.text


def test_page_preview():
    r = client.post("/api/page", files={"file": ("offer.pdf", FIXTURE.read_bytes(), "application/pdf")}, data={"number": 1})
    assert r.status_code == 200 and r.json()["image"]
