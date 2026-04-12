"""FastAPI application factory for dayctl server."""
from __future__ import annotations

import os
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from dayctl.server.api import router as api_router
from dayctl.server.web import router as web_router

STATIC_DIR = Path(__file__).parent / "static"


def create_app() -> FastAPI:
    if not os.environ.get("DAYCTL_TOKEN"):
        raise RuntimeError("DAYCTL_TOKEN env var is required to start the dayctl server")

    app = FastAPI(title="dayctl")

    @app.get("/health")
    def health() -> dict:
        return {"ok": True}

    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
    app.include_router(api_router)
    app.include_router(web_router)
    return app
