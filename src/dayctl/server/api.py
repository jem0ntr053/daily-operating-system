"""JSON API routes mirroring CLI commands."""
from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Path, Response
from pydantic import BaseModel

from dayctl.models import DayPlan, AREAS, _norm_task
from dayctl.server.auth import require_token
from dayctl.storage import delete_plan, list_days, load_plan, save_plan

router = APIRouter(prefix="/api", dependencies=[Depends(require_token)])

Category = Literal["app", "music", "code", "youtube", "marketing", "social"]

_AREA_ALIAS = {"app": "code"}


def _resolve_area(cat: str) -> str:
    return _AREA_ALIAS.get(cat, cat)


class TaskBody(BaseModel):
    task: str


@router.get("/days")
def list_all_days() -> dict:
    return {"days": list_days()}


@router.head("/days/{day}")
def head_day(
    day: str = Path(..., pattern=r"^\d{4}-\d{2}-\d{2}$"),
) -> Response:
    from dayctl.storage import _backend
    if _backend().exists(day):
        return Response(status_code=204)
    return Response(status_code=404)


@router.get("/days/{day}")
def get_day(day: str = Path(..., pattern=r"^\d{4}-\d{2}-\d{2}$")) -> dict:
    return load_plan(day).to_dict()


@router.put("/days/{day}")
def put_day(day: str = Path(..., pattern=r"^\d{4}-\d{2}-\d{2}$"), payload: dict = ...) -> dict:
    if payload.get("day") != day:
        raise HTTPException(400, "payload day mismatch")
    plan = DayPlan.from_dict(payload)
    save_plan(plan)
    return plan.to_dict()


@router.post("/days/{day}/tasks/{cat}")
def add_task(day: str = Path(..., pattern=r"^\d{4}-\d{2}-\d{2}$"), cat: Category = ..., body: TaskBody = ...) -> dict:
    plan = load_plan(day)
    area = _resolve_area(cat)
    plan.tasks.setdefault(area, []).append(_norm_task({"text": body.task}))
    save_plan(plan)
    return plan.to_dict()


@router.post("/days/{day}/tasks/{cat}/{idx}/toggle")
def toggle_task(day: str = Path(..., pattern=r"^\d{4}-\d{2}-\d{2}$"), cat: Category = ..., idx: int = ...) -> dict:
    plan = load_plan(day)
    area = _resolve_area(cat)
    tasks = plan.tasks.get(area, [])
    if idx < 0 or idx >= len(tasks):
        raise HTTPException(404, "task index out of range")
    tasks[idx]["done"] = not tasks[idx]["done"]
    save_plan(plan)
    return plan.to_dict()


@router.delete("/days/{day}")
def delete_day(
    day: str = Path(..., pattern=r"^\d{4}-\d{2}-\d{2}$"),
) -> dict:
    delete_plan(day)
    return {"deleted": day}


@router.delete("/days/{day}/tasks/{cat}/{idx}")
def delete_task(day: str = Path(..., pattern=r"^\d{4}-\d{2}-\d{2}$"), cat: Category = ..., idx: int = ...) -> dict:
    plan = load_plan(day)
    area = _resolve_area(cat)
    tasks = plan.tasks.get(area, [])
    if idx < 0 or idx >= len(tasks):
        raise HTTPException(404, "task index out of range")
    tasks.pop(idx)
    save_plan(plan)
    return plan.to_dict()
