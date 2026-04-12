"""FastAPI application factory for dayctl server."""
from __future__ import annotations

import os

from fastapi import FastAPI

from dayctl.server.api import router as api_router


def create_app() -> FastAPI:
    if not os.environ.get("DAYCTL_TOKEN"):
        raise RuntimeError("DAYCTL_TOKEN env var is required to start the dayctl server")

    app = FastAPI(title="dayctl")

    @app.get("/health")
    def health() -> dict:
        return {"ok": True}

    app.include_router(api_router)
    return app
