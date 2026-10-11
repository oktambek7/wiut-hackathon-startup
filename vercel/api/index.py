"""Vercel entry point; the ASGI app lives in polisdiff/server.py."""
import os

# Each serverless invocation is already isolated and time-limited; skip child processes.
os.environ.setdefault("POLISDIFF_ISOLATION", "inprocess")

from polisdiff.server import app  # noqa: E402,F401
