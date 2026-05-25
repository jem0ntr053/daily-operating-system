"""Filesystem persistence for dayctl — delegates to the selected backend."""
from __future__ import annotations

import json
from datetime import date, timedelta
from functools import lru_cache
from pathlib import Path

from dayctl.models import DayPlan, carry_forward
from dayctl.storage_backends import select_backend

DATA_DIR = Path.home() / ".dayctl"
DAYS_DIR = DATA_DIR / "days"
CONFIG_PATH = DATA_DIR / "config.json"
PERSISTENT_PATH = DATA_DIR / "persistent.json"


@lru_cache(maxsize=1)
def _backend():
    return select_backend()


def _reset_backend_cache() -> None:
    """Test hook: clear cached backend after env changes."""
    _backend.cache_clear()


def ensure_dirs() -> None:
    DAYS_DIR.mkdir(parents=True, exist_ok=True)


def today_str() -> str:
    return date.today().isoformat()


def plan_path(day_str: str) -> Path:
    return DAYS_DIR / f"{day_str}.json"


def load_plan(day_str: str | None = None) -> DayPlan:
    ds = day_str or today_str()
    return _backend().load_plan(ds)


def save_plan(plan: DayPlan) -> None:
    _backend().save_plan(plan)


def list_days() -> list[str]:
    return _backend().list_days()


def init_or_load_plan(day_str: str, profile_key: str | None = None) -> tuple[DayPlan, list[str]]:
    """Load existing plan or create a new one with carry-forward."""
    b = _backend()
    carried: list[str] = []
    if b.exists(day_str):
        plan = b.load_plan(day_str)
        if profile_key and plan.profile != profile_key:
            plan.switch_profile(profile_key)
            b.save_plan(plan)
    else:
        plan = DayPlan.new(day_str, profile_key=profile_key)
        b.save_plan(plan)
    # Carry incomplete tasks forward once per day, idempotently. Runs even when the
    # day was pre-created (by navigation/auto-create) before carry-forward had a
    # chance to run; the rolled_over flag guarantees it never duplicates.
    if not getattr(plan, "rolled_over", False):
        yesterday = (date.fromisoformat(day_str) - timedelta(days=1)).isoformat()
        if b.exists(yesterday):
            carried = carry_forward(plan, b.load_plan(yesterday))
        plan.rolled_over = True
        b.save_plan(plan)
    return plan, carried


def exists(day_str: str) -> bool:
    return _backend().exists(day_str)


def delete_plan(day_str: str) -> None:
    _backend().delete_plan(day_str)


def load_config() -> dict:
    ensure_dirs()
    if not CONFIG_PATH.exists():
        return {}
    return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))


def save_config(config: dict) -> None:
    ensure_dirs()
    CONFIG_PATH.write_text(json.dumps(config, indent=2), encoding="utf-8")
