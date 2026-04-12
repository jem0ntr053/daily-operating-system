"""JSON API routes mirroring CLI commands."""
from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from dayctl.models import DayPlan
from dayctl.server.auth import require_token
from dayctl.storage import list_days, load_plan, save_plan

router = APIRouter(prefix="/api", dependencies=[Depends(require_token)])

Category = Literal["app", "music"]


class TaskBody(BaseModel):
    task: str


def _tasks_attr(cat: Category) -> str:
    return f"{cat}_tasks"


@router.get("/days")
def list_all_days() -> dict:
    return {"days": list_days()}


@router.get("/days/{day}")
def get_day(day: str) -> dict:
    return load_plan(day).to_dict()


@router.put("/days/{day}")
def put_day(day: str, payload: dict) -> dict:
    if payload.get("day") != day:
        raise HTTPException(400, "payload day mismatch")
    plan = DayPlan.from_dict(payload)
    save_plan(plan)
    return plan.to_dict()


@router.post("/days/{day}/tasks/{cat}")
def add_task(day: str, cat: Category, body: TaskBody) -> dict:
    plan = load_plan(day)
    getattr(plan, _tasks_attr(cat)).append({"task": body.task, "done": False})
    save_plan(plan)
    return plan.to_dict()


@router.post("/days/{day}/tasks/{cat}/{idx}/toggle")
def toggle_task(day: str, cat: Category, idx: int) -> dict:
    plan = load_plan(day)
    tasks = getattr(plan, _tasks_attr(cat))
    if idx < 0 or idx >= len(tasks):
        raise HTTPException(404, "task index out of range")
    tasks[idx]["done"] = not tasks[idx]["done"]
    save_plan(plan)
    return plan.to_dict()


@router.delete("/days/{day}/tasks/{cat}/{idx}")
def delete_task(day: str, cat: Category, idx: int) -> dict:
    plan = load_plan(day)
    tasks = getattr(plan, _tasks_attr(cat))
    if idx < 0 or idx >= len(tasks):
        raise HTTPException(404, "task index out of range")
    tasks.pop(idx)
    save_plan(plan)
    return plan.to_dict()
