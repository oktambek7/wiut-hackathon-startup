"""Original synthetic English and mixed-language OSAGO offers with expected statuses.

Labels are set by the document design, independently of the engine. These files were
written together with the English extraction rules, so they are DEVELOPMENT data,
not a blind test set; the results file says so.
"""
from pathlib import Path
import hashlib
import json
from generate_fixtures import create_pdf, RULE_IDS

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "tests" / "fixtures" / "multilingual"

EN = {
    "a": ["The total insurance sum under this contract is 80,000,000 UZS.",
          "Insurance compensation is paid within 5 working days from the date of the insurer's decision.",
          "The insurer notifies the policyholder of the decision on compensation within 15 days after the written or electronic claim."],
    "b": ["Sum insured (total): 80 million soums.",
          "The insurer shall transfer the compensation within five business days after the insurer's payment decision.",
          "The policyholder is informed of the insurer's decision on compensation no later than fifteen days after receipt of the written or electronic application."],
}
EN_DISTRACTORS = ["The insurance premium is 160,000 UZS; payment by card.", "Policy number 2026-141; personal data is not published.",
                  "The information desk works from 09:00 to 18:00.", "The vehicle owner states a contact address in the application form."]
HEADER = ["PUBLIC TEST OFFER · OSAGO · synthetic", "05.01.2026"]


def cases():
    """(id, terms per rule, distractors, expected statuses, applicable date)."""
    ok = dict.fromkeys(RULE_IDS, "MATCH_FOUND")
    out = []
    for v, (s, p, n) in EN.items():
        out.append((f"en-{v}_match", [s, p, n], ok))
        out.append((f"en-{v}_sum_conflict", [s.replace("80", "60"), p, n], {**ok, "OSAGO_SUM": "POTENTIAL_CONFLICT"}))
        out.append((f"en-{v}_payment_conflict", [s, p.replace(" 5 ", " 9 ").replace("five", "seven"), n], {**ok, "OSAGO_PAYMENT": "POTENTIAL_CONFLICT"}))
        out.append((f"en-{v}_notice_conflict", [s, p, n.replace("15 days", "22 days").replace("fifteen days", "22 days")], {**ok, "OSAGO_DECISION_NOTICE": "POTENTIAL_CONFLICT"}))
        out.append((f"en-{v}_omission", [s, "This offer does not describe the payment timetable.", n], {**ok, "OSAGO_PAYMENT": "NOT_FOUND"}))
    s, p, n = EN["a"]
    out.append(("en-a_calendar_days", [s, p.replace("working days", "calendar days"), n], {**ok, "OSAGO_PAYMENT": "UNVERIFIABLE"}))
    out.append(("en-a_wrong_trigger", [s, "Insurance compensation is paid within 5 working days after the road accident.", n], {**ok, "OSAGO_PAYMENT": "UNVERIFIABLE"}))
    out.append(("en-a_conditional", [s, "If all documents are complete, insurance compensation is paid within 5 working days from the date of the insurer's decision.", n],
                {**ok, "OSAGO_PAYMENT": "UNVERIFIABLE"}))
    out.append(("en-a_unknown_date", [s, p, n], dict.fromkeys(RULE_IDS, "UNVERIFIABLE")))
    return out


def mixed_cases(texts):
    ru, uz, uzc = texts["evaluation"]["ru-Cyrl"], texts["evaluation"]["uz-Latn"], texts["evaluation"]["uz-Cyrl"]
    ok = dict.fromkeys(RULE_IDS, "MATCH_FOUND")
    return [
        ("mixed_en-ru-uzLatn_match", [EN["a"][0], ru[1], uz[2]], ok),
        ("mixed_uzCyrl-en-ru_payment_conflict", [uzc[0], EN["a"][1].replace(" 5 ", " 9 "), ru[2]], {**ok, "OSAGO_PAYMENT": "POTENTIAL_CONFLICT"}),
        ("mixed_ru-uzCyrl-en_notice_conflict", [ru[0], uzc[1], EN["b"][2].replace("fifteen days", "22 days")], {**ok, "OSAGO_DECISION_NOTICE": "POTENTIAL_CONFLICT"}),
        ("mixed_uzLatn-en-uzCyrl_sum_conflict", [uz[0].replace("80", "60"), EN["b"][1], uzc[2]], {**ok, "OSAGO_SUM": "POTENTIAL_CONFLICT"}),
    ]


def generate():
    texts = json.loads((ROOT / "evaluation" / "fixture_texts.json").read_text(encoding="utf-8"))
    distract = texts["distractors"]
    manifest = []
    for case_id, terms, expected in cases() + mixed_cases(texts):
        unknown = case_id.endswith("unknown_date")
        langs = ["en", "ru-Cyrl", "uz-Latn"] if case_id.startswith("mixed") else ["en"]
        pages = [HEADER + EN_DISTRACTORS[:2] + (distract["uz-Latn"][:1] if case_id.startswith("mixed") else [])]
        for i, term in enumerate(terms):
            lang = langs[i % len(langs)]
            pages.append([term] + (EN_DISTRACTORS if lang == "en" else distract[lang]))
        path = OUT / f"{case_id}.pdf"
        create_pdf(path, pages, title="Original synthetic multilingual OSAGO test document")
        manifest.append({"id": case_id, "path": str(path.relative_to(ROOT)).replace("\\", "/"),
                         "sha256": hashlib.sha256(path.read_bytes()).hexdigest(), "applicable_date": None if unknown else "2026-01-05",
                         "expected": expected, "split": "development_multilingual", "terms": terms})
    (ROOT / "evaluation" / "multilingual_manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=1), encoding="utf-8")
    print("Generated", len(manifest), "English/mixed synthetic PDFs")


if __name__ == "__main__":
    generate()
