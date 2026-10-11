import json
from datetime import date
from pathlib import Path

import pytest

pytest.importorskip("fastapi")
pytest.importorskip("multipart")
from fastapi.testclient import TestClient

from polisdiff.advice import grounded, rules_plan
from polisdiff.deployment import model_files_status
from polisdiff.engine import load_catalogue
from polisdiff.models import Report
from polisdiff.server import app

ROOT = Path(__file__).resolve().parents[1]
client = TestClient(app)
PAYMENT = (ROOT / "tests/fixtures/evaluation/ru-Cyrl_payment_conflict.pdf").read_bytes()


def post_check(data, **form):
    return client.post("/v1/checks", files={"file": ("offer.pdf", data, "application/pdf")}, data={"language": "en", **form})


def test_passages_endpoint_gives_stable_ids_and_all_rule_queries():
    a = client.post("/v1/passages", files={"file": ("a.pdf", PAYMENT, "application/pdf")}).json()
    b = client.post("/v1/passages", files={"file": ("a.pdf", PAYMENT, "application/pdf")}).json()
    assert [p["id"] for p in a["passages"]] == [p["id"] for p in b["passages"]]
    assert set(a["queries"]) == {r.id for r in load_catalogue()[1]}
    assert any("working days" in q for q in a["queries"]["OSAGO_PAYMENT"])  # English query included


def test_browser_ranking_is_used_and_reported(monkeypatch):
    monkeypatch.setattr("polisdiff.api_v1.model_files_status", lambda: {"state": "not_provisioned"})
    passages = client.post("/v1/passages", files={"file": ("a.pdf", PAYMENT, "application/pdf")}).json()["passages"]
    ranking = {rule: [p["id"] for p in passages] for rule in ("OSAGO_SUM", "OSAGO_PAYMENT", "OSAGO_DECISION_NOTICE")}
    body = post_check(PAYMENT, applicable_date="2026-01-05", mode="hybrid", browser_ranking=json.dumps(ranking),
                      browser_model="Xenova/multilingual-e5-small").json()
    assert body["engine"]["retrieval_used"] == "hybrid" and not body["engine"]["ai_fallback"]
    assert body["report"]["model_revision"] == "browser:Xenova/multilingual-e5-small"
    assert {c["rule_id"]: c["status"] for c in body["view"]["checks"]}["OSAGO_PAYMENT"] == "POTENTIAL_CONFLICT"


def test_ranking_for_another_document_falls_back_visibly(monkeypatch):
    monkeypatch.setattr("polisdiff.api_v1.model_files_status", lambda: {"state": "not_provisioned"})
    body = post_check(PAYMENT, applicable_date="2026-01-05", mode="hybrid", browser_ranking=json.dumps({"OSAGO_SUM": ["p99-999"]})).json()
    assert body["engine"]["retrieval_used"] == "lexical" and body["engine"]["ai_fallback"]
    assert post_check(PAYMENT, mode="hybrid", browser_ranking="[1,2]").status_code == 400


@pytest.mark.skipif(model_files_status()["state"] != "files_present", reason="needs the offline E5 model")
@pytest.mark.parametrize("name", ["ru-Cyrl_payment_conflict", "uz-Latn_sum_conflict", "uz-Cyrl_notice_conflict", "ru-Cyrl_omission", "uz-Latn_ambiguous"])
def test_browser_style_ranking_matches_server_hybrid(name, monkeypatch):
    """Rank with the same E5 model outside the engine (as the browser does) and compare verdicts with server hybrid."""
    import numpy as np
    from polisdiff.runtime import web_retriever
    data = (ROOT / f"tests/fixtures/evaluation/{name}.pdf").read_bytes()
    server = post_check(data, applicable_date="2026-01-05", mode="hybrid").json()
    info = client.post("/v1/passages", files={"file": ("a.pdf", data, "application/pdf")}).json()
    model = web_retriever("hybrid").model
    vectors = model.encode(["passage: " + p["text"] for p in info["passages"]], normalize_embeddings=True)
    ranking = {}
    for rule, queries in info["queries"].items():
        q = model.encode(["query: " + x for x in queries], normalize_embeddings=True)
        scores = np.max(vectors @ q.T, axis=1)
        ranking[rule] = [info["passages"][i]["id"] for i in np.argsort(-scores)[:40]]
    monkeypatch.setattr("polisdiff.api_v1.model_files_status", lambda: {"state": "not_provisioned"})
    browser = post_check(data, applicable_date="2026-01-05", mode="hybrid", browser_ranking=json.dumps(ranking)).json()
    assert browser["engine"]["retrieval_used"] == "hybrid"
    assert [(c["rule_id"], c["status"]) for c in browser["view"]["checks"]] == [(c["rule_id"], c["status"]) for c in server["view"]["checks"]]


def test_action_plan_follows_findings():
    report = post_check(PAYMENT, applicable_date="2026-01-05", mode="lexical").json()["report"]
    plan = client.post("/v1/advice", json={"report": report, "language": "en"}).json()
    assert plan["source"] in {"rules", "ai"}
    first = plan["actions"][0]
    assert first["priority"] == "high" and first["kind"] == "letter" and first["rule_id"] == "OSAGO_PAYMENT"
    assert "9" in first["detail"] and "5" in first["detail"]
    assert any(a["kind"] == "deadlines" for a in plan["actions"])
    pending = client.post("/v1/advice", json={"report": post_check(PAYMENT, mode="lexical").json()["report"], "language": "ru"}).json()
    assert pending["actions"][0]["kind"] == "date"


def test_ai_wording_rejected_when_it_invents_numbers():
    report = Report.model_validate(post_check(PAYMENT, applicable_date="2026-01-05", mode="lexical").json()["report"])
    plan = rules_plan(report, "en")
    same = {"summary": plan["summary"], "actions": [dict(a) for a in plan["actions"]]}
    assert grounded(same, plan, report)
    invented = {"summary": "Call 1180 within 3 days.", "actions": [dict(a) for a in plan["actions"]]}
    assert not grounded(invented, plan, report)
    reordered = {"summary": plan["summary"], "actions": list(reversed([dict(a) for a in plan["actions"]]))}
    assert not grounded(reordered, plan, report)
