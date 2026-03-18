"""Filesystem persistence for dayctl."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

from dayctl.models import DayPlan


DATA_DIR = Path.home() / ".dayctl"
DAYS_DIR = DATA_DIR / "days"


def ensure_dirs() -> None:
    DAYS_DIR.mkdir(parents=True, exist_ok=True)


def today_str() -> str:
    return date.today().isoformat()


def plan_path(day_str: str) -> Path:
    return DAYS_DIR / f"{day_str}.json"


def load_plan(day_str: str | None = None) -> DayPlan:
    ensure_dirs()
    ds = day_str or today_str()
    path = plan_path(ds)
    if not path.exists():
        plan = DayPlan.new(ds)
        save_plan(plan)
        return plan
    data = json.loads(path.read_text(encoding="utf-8"))
    return DayPlan.from_dict(data)


def save_plan(plan: DayPlan) -> None:
    ensure_dirs()
    path = plan_path(plan.day)
    path.write_text(json.dumps(plan.to_dict(), indent=2), encoding="utf-8")


def list_days() -> list[str]:
    """Return sorted list of YYYY-MM-DD strings for all saved day files."""
    ensure_dirs()
    return sorted(p.stem for p in DAYS_DIR.glob("*.json"))
