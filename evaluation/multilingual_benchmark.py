"""Measure English and mixed-language fixtures in each retrieval mode; writes MULTILINGUAL_RESULTS.md.

Usage: python evaluation/multilingual_benchmark.py [--modes lexical hybrid]
Hybrid/semantic need the E5 model at POLISDIFF_MODEL_PATH; a fallback is reported, never hidden.
"""
import argparse
import json
import statistics
import sys
import time
from datetime import date, datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from polisdiff.retrieval import Retriever  # noqa: E402
from polisdiff.service import analyze_pdf  # noqa: E402

AUDIT_DATE = date(2026, 10, 11)


def run(mode, manifest):
    retriever = Retriever(mode)
    rows, times = [], []
    for item in manifest:
        applicable = date.fromisoformat(item["applicable_date"]) if item["applicable_date"] else None
        start = time.perf_counter()
        _, report = analyze_pdf((ROOT / item["path"]).read_bytes(), AUDIT_DATE, applicable, retriever)
        times.append(time.perf_counter() - start)
        got = {f.rule_id: f.status.value for f in report.findings}
        for rule, want in item["expected"].items():
            rows.append({"doc": item["id"], "group": "mixed" if item["id"].startswith("mixed") else "en", "rule": rule,
                         "expected": want, "got": got[rule], "used": report.retrieval_used})
    return rows, times, retriever.used


def metrics(rows):
    correct = sum(r["expected"] == r["got"] for r in rows)
    tp = sum(r["expected"] == r["got"] == "POTENTIAL_CONFLICT" for r in rows)
    flagged = sum(r["got"] == "POTENTIAL_CONFLICT" for r in rows)
    actual = sum(r["expected"] == "POTENTIAL_CONFLICT" for r in rows)
    answered = [r for r in rows if r["got"] in {"MATCH_FOUND", "POTENTIAL_CONFLICT"}]
    return {"labels": len(rows), "status_accuracy": correct / len(rows),
            "conflict_precision": tp / flagged if flagged else None, "conflict_recall": tp / actual if actual else None,
            "precision_on_answered": sum(r["expected"] == r["got"] for r in answered) / len(answered) if answered else None,
            "abstention": sum(r["got"] == "UNVERIFIABLE" for r in rows) / len(rows)}


def pct(v):
    return "—" if v is None else f"{v * 100:.1f}%"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--modes", nargs="+", default=["lexical", "hybrid"])
    args = parser.parse_args()
    manifest = json.loads((ROOT / "evaluation" / "multilingual_manifest.json").read_text(encoding="utf-8"))
    results, lines = {}, []
    for mode in args.modes:
        rows, times, used = run(mode, manifest)
        results[mode] = {"used": used, "median_seconds": statistics.median(times), "max_seconds": max(times),
                         "all": metrics(rows), "en": metrics([r for r in rows if r["group"] == "en"]),
                         "mixed": metrics([r for r in rows if r["group"] == "mixed"]),
                         "errors": [r for r in rows if r["expected"] != r["got"]]}
    out = {"measured_at": datetime.now(timezone.utc).isoformat(), "documents": len(manifest), "results": results}
    (ROOT / "evaluation" / "multilingual_results.json").write_text(json.dumps(out, indent=2), encoding="utf-8")
    lines += ["# English and mixed-language results", "",
              f"Measured {out['measured_at']} on {len(manifest)} original synthetic PDFs "
              "([manifest](multilingual_manifest.json), [generator](generate_multilingual.py), [raw](multilingual_results.json)).", "",
              "**These are development fixtures written together with the English extraction rules. They show the rules work as "
              "designed; they are not a blind or real-world accuracy estimate.**", "",
              "| Mode requested → used | Group | Labels | Status accuracy | Precision on answered | Conflict precision | Conflict recall | Abstention | Median / max s |",
              "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |"]
    for mode, r in results.items():
        for group in ("en", "mixed", "all"):
            m = r[group]
            lines.append(f"| {mode} → {r['used']} | {group} | {m['labels']} | {pct(m['status_accuracy'])} | {pct(m['precision_on_answered'])} | "
                         f"{pct(m['conflict_precision'])} | {pct(m['conflict_recall'])} | {pct(m['abstention'])} | "
                         f"{r['median_seconds']:.2f} / {r['max_seconds']:.2f} |")
    lines += ["", "## Disagreements with the designed label", ""]
    for mode, r in results.items():
        for e in r["errors"]:
            lines.append(f"- {mode}: `{e['doc']}` {e['rule']}: expected {e['expected']}, got {e['got']}")
    lines += ["", "`en-a_wrong_trigger` is labelled UNVERIFIABLE (a deadline exists but counts from the accident). The engine returns "
              "NOT_FOUND because its payment-clause topic requires the insurer's decision, the same design as for Russian and Uzbek. "
              "Either way no comparison is made; the wording shown to the user differs."]
    (ROOT / "evaluation" / "MULTILINGUAL_RESULTS.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
