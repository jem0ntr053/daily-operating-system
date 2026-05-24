"""HTML routes with HTMX fragment responses."""
from __future__ import annotations

import hmac
import os
from datetime import date
from pathlib import Path
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi import Path as PathParam
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from dayctl.server.auth import require_token
from dayctl.server.viewmodel import build_day_view
from dayctl.storage import load_plan, save_plan

TEMPLATES_DIR = Path(__file__).parent / "templates"
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

router = APIRouter()
Category = Literal["app", "music"]

_DAY_PATTERN = r"^\d{4}-\d{2}-\d{2}$"


@router.get("/login")
def login(token: str) -> RedirectResponse:
    expected = os.environ.get("DAYCTL_TOKEN", "")
    if not expected or not hmac.compare_digest(token, expected):
        raise HTTPException(401, "bad token")
    resp = RedirectResponse(url="/", status_code=302)
    resp.set_cookie("dayctl_token", token, httponly=True, secure=True, samesite="strict")
    return resp


@router.get("/", dependencies=[Depends(require_token)])
def root() -> RedirectResponse:
    return RedirectResponse(url=f"/day/{date.today().isoformat()}", status_code=302)


@router.get("/day/{day}", response_class=HTMLResponse, dependencies=[Depends(require_token)])
def view_day(request: Request, day: str = PathParam(..., pattern=_DAY_PATTERN)) -> HTMLResponse:
    ctx = build_day_view(day)
    ctx["request"] = request
    return templates.TemplateResponse(request, "day.html", ctx)


@router.post(
    "/web/day/{day}/tasks/{cat}/{idx}/toggle",
    response_class=HTMLResponse,
    dependencies=[Depends(require_token)],
)
def toggle_task(
    request: Request,
    cat: Category,
    idx: int,
    day: str = PathParam(..., pattern=_DAY_PATTERN),
) -> HTMLResponse:
    if request.headers.get("HX-Request") != "true":
        raise HTTPException(403, "HTMX request required")
    plan = load_plan(day)
    _area_alias = {"app": "code"}
    area = _area_alias.get(cat, cat)
    tasks = plan.tasks.get(area, [])
    if idx < 0 or idx >= len(tasks):
        raise HTTPException(404, "task index out of range")
    tasks[idx]["done"] = not tasks[idx]["done"]
    save_plan(plan)
    return templates.TemplateResponse(
        request,
        "_task_row.html",
        {
            "t": tasks[idx],
            "plan": plan,
            "cat": cat,
            "idx": idx,
        },
    )
