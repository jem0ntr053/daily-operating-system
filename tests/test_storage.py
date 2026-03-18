"""Tests for dayctl.storage."""

from dayctl.storage import load_plan, save_plan, plan_path, list_days
from dayctl.models import DayPlan


def test_save_and_load(day_env):
    plan = DayPlan.new("2026-01-01")
    save_plan(plan)
    loaded = load_plan("2026-01-01")
    assert loaded.day == "2026-01-01"
    assert loaded.completed == plan.completed


def test_load_auto_creates(day_env):
    path = plan_path("2026-06-15")
    assert not path.exists()
    plan = load_plan("2026-06-15")
    assert plan.day == "2026-06-15"
    assert path.exists()


def test_list_days(day_env):
    save_plan(DayPlan.new("2026-01-03"))
    save_plan(DayPlan.new("2026-01-01"))
    save_plan(DayPlan.new("2026-01-02"))
    days = list_days()
    assert days == ["2026-01-01", "2026-01-02", "2026-01-03"]


def test_list_days_empty(day_env):
    assert list_days() == []
