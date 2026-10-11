"""ASGI app: v1 API (+ the v1 Streamlit-era web router) with CORS for the Next.js front end."""
import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .api_v1 import API_VERSION, router as v1
from .webapi import router as legacy

app = FastAPI(title="PolisDiff AI API", version=API_VERSION, docs_url="/docs", redoc_url=None)
origins = [o.strip() for o in os.getenv("POLISDIFF_CORS_ORIGINS", "*").split(",") if o.strip()]
app.add_middleware(CORSMiddleware, allow_origins=origins, allow_methods=["GET", "POST"], allow_headers=["*"], allow_credentials=False)
app.include_router(v1)
app.include_router(v1, prefix="/api")  # Vercel serves the function under /api
app.include_router(legacy, prefix="/api")
