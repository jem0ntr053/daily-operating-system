"""HTML routes with HTMX fragment responses."""
from __future__ import annotations

import hmac
import os
from datetime import date, datetime
from pathlib import Path

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi import Path as PathParam
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from dayctl.models import AREAS, HABIT_KEYS, _norm_task
from dayctl.persistent import load_persistent, save_persistent, update_stat
from dayctl.server.auth import require_token
from dayctl.server.viewmodel import build_day_view
from dayctl.storage import init_or_load_plan, load_plan, save_plan

TEMPLATES_DIR = Path(__file__).parent / "templates"
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

router = APIRouter()

_DAY_PATTERN = r"^\d{4}-\d{2}-\d{2}$"

_AREA_ALIAS = {"app": "code"}


def _resolve_area(cat: str) -> str:
    area = _AREA_ALIAS.get(cat, cat)
    if area not in AREAS:
        raise HTTPException(404, "unknown area")
    return area


def _render_task_list(request: Request, day: str, area: str) -> HTMLResponse:
    ctx = build_day_view(day)
    ctx["request"] = request
    ctx["area"] = area
    return templates.TemplateResponse(request, "_task_list.html", ctx)


@router.get("/login")
def login(request: Request, token: str) -> RedirectResponse:
    expected = os.environ.get("DAYCTL_TOKEN", "")
    if not expected or not hmac.compare_digest(token, expected):
        raise HTTPException(401, "bad token")
    resp = RedirectResponse(url="/", status_code=302)
    # Secure only over HTTPS so the cookie is actually stored on http://localhost
    # during local dev; SameSite=lax so link-based login works on first navigation.
    resp.set_cookie(
        "dayctl_token",
        token,
        httponly=True,
        secure=request.url.scheme == "https",
        samesite="lax",
    )
    return resp


@router.get("/", dependencies=[Depends(require_token)])
def root() -> RedirectResponse:
    return RedirectResponse(url=f"/day/{date.today().isoformat()}", status_code=302)


@router.get("/day/{day}", response_class=HTMLResponse, dependencies=[Depends(require_token)])
def view_day(request: Request, day: str = PathParam(..., pattern=_DAY_PATTERN)) -> HTMLResponse:
    init_or_load_plan(day)
    ctx = build_day_view(day); ctx["request"] = request
    return templates.TemplateResponse(request, "day.html", ctx)


@router.post("/web/day/{day}/tasks/{cat}/add", response_class=HTMLResponse, dependencies=[Depends(require_token)])
def add_task(
    request: Request,
    cat: str,
    text: str = Form(""),
    tag: str = Form(""),
    day: str = PathParam(..., pattern=_DAY_PATTERN),
) -> HTMLResponse:
    area = _resolve_area(cat)
    plan = load_plan(day)
    if text.strip():
        plan.tasks.setdefault(area, []).append(_norm_task({"text": text.strip(), "tag": tag.strip().upper()}))
        save_plan(plan)
    return _render_task_list(request, day, area)


@router.post("/web/day/{day}/tasks/{cat}/{idx}/toggle", response_class=HTMLResponse, dependencies=[Depends(require_token)])
def toggle_task(
    request: Request,
    cat: str,
    idx: int,
    day: str = PathParam(..., pattern=_DAY_PATTERN),
) -> HTMLResponse:
    area = _resolve_area(cat)
    plan = load_plan(day)
    tasks = plan.tasks.get(area, [])
    if not (0 <= idx < len(tasks)):
        raise HTTPException(404, "task index out of range")
    tasks[idx]["done"] = not tasks[idx]["done"]
    save_plan(plan)
    ctx = build_day_view(day)
    ctx["request"] = request
    ctx.update({"t": load_plan(day).tasks[area][idx], "area": area, "idx": idx})
    return templates.TemplateResponse(request, "_task_row.html", ctx)


@router.post("/web/day/{day}/tasks/{cat}/{idx}/delete", response_class=HTMLResponse, dependencies=[Depends(require_token)])
def delete_task(
    request: Request,
    cat: str,
    idx: int,
    day: str = PathParam(..., pattern=_DAY_PATTERN),
) -> HTMLResponse:
    area = _resolve_area(cat)
    plan = load_plan(day)
    tasks = plan.tasks.get(area, [])
    if 0 <= idx < len(tasks):
        tasks.pop(idx)
        save_plan(plan)
    return _render_task_list(request, day, area)


_FIELD_ATTR = {"focus": "focus", "energy": "energy", "sleep": "sleep_hours", "mood": "mood", "bpm": "bpm"}


@router.post("/web/day/{day}/field/{name}", response_class=HTMLResponse, dependencies=[Depends(require_token)])
def edit_field(name: str, value: str = Form(""), day: str = PathParam(..., pattern=_DAY_PATTERN)) -> HTMLResponse:
    attr = _FIELD_ATTR.get(name)
    if attr is None:
        raise HTTPException(404, "unknown field")
    plan = load_plan(day)
    setattr(plan, attr, value)
    save_plan(plan)
    return HTMLResponse('<span class="saved"><span class="dot"></span>Saved</span>')


@router.post("/web/day/{day}/habit/{habit_id}/toggle", response_class=HTMLResponse, dependencies=[Depends(require_token)])
def toggle_habit(request: Request, habit_id: str, day: str = PathParam(..., pattern=_DAY_PATTERN)) -> HTMLResponse:
    if habit_id not in HABIT_KEYS:
        raise HTTPException(404, "unknown habit")
    plan = load_plan(day)
    plan.completed[habit_id] = not plan.completed.get(habit_id, False)
    save_plan(plan)
    ctx = build_day_view(day)
    ctx["request"] = request
    return templates.TemplateResponse(request, "_pulse.html", ctx)


@router.post("/web/day/{day}/notes/add", response_class=HTMLResponse, dependencies=[Depends(require_token)])
def add_note(request: Request, text: str = Form(""), day: str = PathParam(..., pattern=_DAY_PATTERN)) -> HTMLResponse:
    plan = load_plan(day)
    if text.strip():
        now = datetime.now()
        plan.notes.append({"text": text.strip(), "time": f"{now.hour:02d}:{now.minute:02d}"})
        save_plan(plan)
    ctx = build_day_view(day); ctx["request"] = request
    return templates.TemplateResponse(request, "_notes.html", ctx)


@router.post("/web/day/{day}/notes/{idx}/delete", response_class=HTMLResponse, dependencies=[Depends(require_token)])
def delete_note(request: Request, idx: int, day: str = PathParam(..., pattern=_DAY_PATTERN)) -> HTMLResponse:
    plan = load_plan(day)
    if 0 <= idx < len(plan.notes):
        plan.notes.pop(idx)
        save_plan(plan)
    ctx = build_day_view(day); ctx["request"] = request
    return templates.TemplateResponse(request, "_notes.html", ctx)


def _render_ideas(request: Request, editing_idx: int | None = None) -> HTMLResponse:
    return templates.TemplateResponse(
        request, "_area_ideas.html",
        {"request": request, "persistent": load_persistent(), "editing_idx": editing_idx},
    )


@router.post("/web/ideas/add", response_class=HTMLResponse, dependencies=[Depends(require_token)])
def add_idea(request: Request, text: str = Form(""), bucket: str = Form("Capture")) -> HTMLResponse:
    if text.strip():
        p = load_persistent()
        p["ideas"].insert(0, {"from": bucket, "text": text.strip()})
        save_persistent(p)
    return _render_ideas(request)


@router.post("/web/ideas/{idx}/delete", response_class=HTMLResponse, dependencies=[Depends(require_token)])
def delete_idea(request: Request, idx: int) -> HTMLResponse:
    p = load_persistent()
    if 0 <= idx < len(p["ideas"]):
        p["ideas"].pop(idx)
        save_persistent(p)
    return _render_ideas(request)


@router.get("/web/ideas", response_class=HTMLResponse, dependencies=[Depends(require_token)])
def ideas_display(request: Request) -> HTMLResponse:
    return _render_ideas(request)


@router.get("/web/ideas/{idx}/edit", response_class=HTMLResponse, dependencies=[Depends(require_token)])
def ideas_edit(request: Request, idx: int) -> HTMLResponse:
    return _render_ideas(request, editing_idx=idx)


@router.post("/web/ideas/{idx}/save", response_class=HTMLResponse, dependencies=[Depends(require_token)])
def ideas_save(request: Request, idx: int, text: str = Form(""), bucket: str = Form("")) -> HTMLResponse:
    p = load_persistent()
    if 0 <= idx < len(p["ideas"]):
        if text.strip():
            p["ideas"][idx]["text"] = text.strip()
        if bucket.strip():
            p["ideas"][idx]["from"] = bucket.strip()
        save_persistent(p)
    return _render_ideas(request)


def _glance_card(request: Request, key: str, editing: bool) -> HTMLResponse:
    p = load_persistent()
    stat = p["stats"].get(key)
    if stat is None:
        raise HTTPException(404, "unknown stat")
    from dayctl.server.viewmodel import _spark_points
    ctx = {"request": request, "key": key, "stat": stat, "points": _spark_points(stat.get("spark", [])), "editing": editing}
    return templates.TemplateResponse(request, "_glance_card.html", ctx)


@router.get("/web/stats/{key}", response_class=HTMLResponse, dependencies=[Depends(require_token)])
def stat_display(request: Request, key: str) -> HTMLResponse:
    return _glance_card(request, key, editing=False)


@router.get("/web/stats/{key}/edit", response_class=HTMLResponse, dependencies=[Depends(require_token)])
def stat_edit(request: Request, key: str) -> HTMLResponse:
    return _glance_card(request, key, editing=True)


@router.post("/web/stats/{key}", response_class=HTMLResponse, dependencies=[Depends(require_token)])
def edit_stat(request: Request, key: str, v: str = Form(""), d: str = Form(""), trend: str = Form("flat")) -> HTMLResponse:
    p = load_persistent()
    update_stat(p, key, {"v": v, "d": d, "trend": trend})
    save_persistent(p)
    return _glance_card(request, key, editing=False)


@router.post("/web/settings", dependencies=[Depends(require_token)])
def update_settings(accent: str = Form("cyan"), show_glance: str = Form("")) -> RedirectResponse:
    p = load_persistent()
    p["settings"]["accent"] = accent
    p["settings"]["show_glance"] = show_glance == "on"
    save_persistent(p)
    return RedirectResponse(url=f"/day/{date.today().isoformat()}", status_code=303)
