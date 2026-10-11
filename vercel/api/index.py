"""Vercel entry point: stateless FastAPI over the PolisDiff engine (see polisdiff/webapi.py)."""
import os

# Each serverless invocation is already isolated and time-limited; skip child processes.
os.environ.setdefault("POLISDIFF_ISOLATION", "inprocess")

from fastapi import FastAPI  # noqa: E402
from polisdiff.webapi import router, APP_VERSION  # noqa: E402

app = FastAPI(title="PolisDiff AI", version=APP_VERSION, docs_url=None, redoc_url=None)
app.include_router(router, prefix="/api")
app.include_router(router)  # in case the platform strips the /api prefix
