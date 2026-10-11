# Vercel deployment (public demo)

The Streamlit app (`app.py`) needs a long-running websocket server and PyTorch plus a
~470 MB E5 model; Vercel serverless functions cannot host that. The Vercel build is
therefore a second front end over the **same engine**:

| Part | Location | Notes |
| --- | --- | --- |
| Engine, rules, i18n, exports | `polisdiff/`, `rules/` | Unchanged; copied into the build |
| HTTP API (FastAPI, stateless) | `polisdiff/webapi.py`, `vercel/api/index.py` | `/api/config`, `/api/i18n/{lang}`, `/api/analyze`, `/api/page`, `/api/review`, `/api/export/html` |
| Web UI (static) | `vercel/public/` | Four interface languages, evidence page images, reviewer annotations, HTML/JSON export |
| Sample offers | `tests/fixtures/` via `evaluation/dataset_manifest.json` | Synthetic, team-made test offers |
| Streamlit app, tests, evaluation, docs | repo root | Kept intact; not uploaded to the function |

`python scripts/build_vercel.py` assembles `dist_vercel/` (ignored by Git); deploy that folder.

## What differs from the Streamlit app

- **Retrieval:** the function runs keyword (BM25-style) retrieval; torch/E5 are not installed.
  The UI reports the mode actually used. Set `POLISDIFF_AI_BACKEND_URL` to a server running the
  full app's `polisdiff.webapi` (for example a Docker host with the model provisioned) and
  hybrid/semantic requests are forwarded there; if it is unreachable the request falls back to
  keyword search visibly.
- **Upload limit:** 4 MiB (Vercel rejects larger request bodies). Streamlit keeps 10 MiB.
- **Isolation:** `POLISDIFF_ISOLATION=inprocess` parses the PDF inside the invocation instead of a
  child process; each invocation is already isolated and time limited by the platform.
- **State:** nothing is stored. The browser keeps the PDF and report; review annotations live in the
  browser until exported.

## Deploy

```powershell
python scripts/build_vercel.py
cd dist_vercel
npx vercel deploy --prod
```

Live demo: https://polisdiff-ai.vercel.app (project `polisdiff-ai`, deployed from `dist_vercel/` with the Vercel CLI; Vercel Authentication disabled so judges can open it).
