"""FastAPI application factory for dayctl server."""
from __future__ import annotations

from fastapi import Depends, FastAPI

from dayctl.server.auth import require_token


def create_app() -> FastAPI:
    app = FastAPI(title="dayctl")

    @app.get("/health")
    def health() -> dict:
        return {"ok": True}

    # Placeholder protected route — replaced by full router in Task 5
    @app.get("/api/days/{day}", dependencies=[Depends(require_token)])
    def get_day(day: str) -> dict:
        from dayctl.storage import load_plan
        return load_plan(day).to_dict()

    return app
