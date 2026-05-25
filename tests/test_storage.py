"""Tests for dayctl.storage."""

from dayctl.storage import load_plan, save_plan, plan_path, list_days, init_or_load_plan
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


def test_carry_forward_into_preexisting_day(day_env):
    # Day A has an incomplete task.
    a = DayPlan.new("2026-03-02")
    a.tasks["social"] = [{"text": "ship short", "done": False, "tag": "", "carried": False}]
    save_plan(a)
    # Day B was pre-created empty (rolled_over defaults False) — simulates a day
    # auto-created by navigation before carry-forward ran.
    b = DayPlan.new("2026-03-03")
    b.tasks["social"] = []
    save_plan(b)

    plan, carried = init_or_load_plan("2026-03-03")
    assert "ship short" in carried
    assert any(t["text"] == "ship short" and t["carried"] for t in plan.tasks["social"])
    assert plan.rolled_over is True

    # Idempotent: a second call must not duplicate or re-carry.
    plan2, carried2 = init_or_load_plan("2026-03-03")
    assert carried2 == []
    assert sum(1 for t in plan2.tasks["social"] if t["text"] == "ship short") == 1


def test_rolled_over_defaults_false_and_backfills():
    p = DayPlan.new("2026-03-02")
    assert p.rolled_over is False
    d = p.to_dict()
    d.pop("rolled_over")
    assert DayPlan.from_dict(d).rolled_over is False
