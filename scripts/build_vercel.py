"""Assemble the self-contained Vercel project in dist_vercel/ from the repository.

Nothing is moved or deleted in the repo: the engine (polisdiff/), rules, evaluation
manifests and the web UI (vercel/) stay where they are. Large or irrelevant parts
(model weights, tests, Streamlit app) are not uploaded to the serverless function.
"""
import json
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "dist_vercel"
SAMPLE_CASES = ("match", "sum_conflict", "payment_conflict", "notice_conflict", "omission")


def main():
    if OUT.exists():
        shutil.rmtree(OUT)
    shutil.copytree(ROOT / "vercel", OUT)
    shutil.copytree(ROOT / "polisdiff", OUT / "polisdiff", ignore=shutil.ignore_patterns("__pycache__"))
    (OUT / "rules").mkdir()
    for name in ("catalogue.v1.json", "holidays.json"):
        shutil.copy(ROOT / "rules" / name, OUT / "rules")
    (OUT / "evaluation").mkdir()
    shutil.copy(ROOT / "evaluation" / "model_manifest.json", OUT / "evaluation")
    manifest = json.loads((ROOT / "evaluation" / "dataset_manifest.json").read_text(encoding="utf-8"))
    samples = []
    for item in manifest:
        if item["case"] not in SAMPLE_CASES or item["split"] == "development" and item["case"] != "match":
            continue
        name = Path(item["path"]).name
        shutil.copy(ROOT / item["path"], OUT / "public" / "samples" / name)
        samples.append({"id": item["id"], "file": f"/samples/{name}", "language": item["language"],
                        "case": item["case"], "applicable_date": item["applicable_date"]})
    (OUT / "public" / "samples" / "index.json").write_text(json.dumps(samples, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"built {OUT} with {len(samples)} sample PDFs")


if __name__ == "__main__":
    main()
