"""FastAPI application factory for dayctl server."""
from __future__ import annotations

import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from dayctl.server.api import router as api_router
from dayctl.server.scheduler import ReminderScheduler
from dayctl.server.web import router as web_router

STATIC_DIR = Path(__file__).parent / "static"


@asynccontextmanager
async def _lifespan(app: FastAPI):
    if os.environ.get("DAYCTL_ENABLE_SCHEDULER") == "1":
        sched = ReminderScheduler()
        sched.start()
        try:
            yield
        finally:
            sched.stop()
    else:
        yield


def create_app() -> FastAPI:
    if not os.environ.get("DAYCTL_TOKEN"):
        raise RuntimeError("DAYCTL_TOKEN env var is required to start the dayctl server")

    app = FastAPI(title="dayctl", lifespan=_lifespan)

    @app.get("/health")
    def health() -> dict:
        return {"ok": True}

    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
    app.include_router(api_router)
    app.include_router(web_router)
    return app
