"""Filesystem persistence for dayctl."""

from __future__ import annotations

import json
from datetime import date, timedelta
from pathlib import Path

from dayctl.models import DayPlan, carry_forward


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


def init_or_load_plan(day_str: str, profile_key: str | None = None) -> tuple[DayPlan, list[str]]:
    """Load existing plan or create a new one with carry-forward.

    Returns (plan, carried) where carried is a list of task descriptions
    that were carried forward from the previous day (empty if plan existed).
    """
    path = plan_path(day_str)
    carried: list[str] = []

    if path.exists():
        plan = load_plan(day_str)
        if profile_key and plan.profile != profile_key:
            plan.switch_profile(profile_key)
            save_plan(plan)
    else:
        plan = DayPlan.new(day_str, profile_key=profile_key)
        yesterday = (date.fromisoformat(day_str) - timedelta(days=1)).isoformat()
        if plan_path(yesterday).exists():
            prev = load_plan(yesterday)
            carried = carry_forward(plan, prev)
        save_plan(plan)

    return plan, carried


def list_days() -> list[str]:
    """Return sorted list of YYYY-MM-DD strings for all saved day files."""
    ensure_dirs()
    return sorted(p.stem for p in DAYS_DIR.glob("*.json"))


# ---------------------------------------------------------------------------
# Config (theme, etc.)
# ---------------------------------------------------------------------------

CONFIG_PATH = DATA_DIR / "config.json"


def load_config() -> dict:
    """Load user config from ~/.dayctl/config.json."""
    ensure_dirs()
    if not CONFIG_PATH.exists():
        return {}
    return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))


def save_config(config: dict) -> None:
    """Save user config to ~/.dayctl/config.json."""
    ensure_dirs()
    CONFIG_PATH.write_text(json.dumps(config, indent=2), encoding="utf-8")
