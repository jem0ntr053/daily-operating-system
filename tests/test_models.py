"""Tests for dayctl.models."""

from dayctl.models import DayPlan, NON_NEGOTIABLE_KEYS, score_plan


def test_new_plan_defaults():
    plan = DayPlan.new("2026-03-17")
    assert plan.day == "2026-03-17"
    assert plan.fasting_window == "9:00 PM → 2:00 PM"
    assert all(v is False for v in plan.completed.values())
    assert len(plan.completed) == 4
    assert set(plan.completed.keys()) == set(NON_NEGOTIABLE_KEYS)


def test_score_empty():
    plan = DayPlan.new("2026-03-17")
    assert score_plan(plan) == 0


def test_score_partial():
    plan = DayPlan.new("2026-03-17")
    plan.completed["gym"] = True
    plan.completed["fast"] = True
    assert score_plan(plan) == 2


def test_score_full():
    plan = DayPlan.new("2026-03-17")
    for k in NON_NEGOTIABLE_KEYS:
        plan.completed[k] = True
    assert score_plan(plan) == 4


def test_to_dict_roundtrip():
    plan = DayPlan.new("2026-03-17")
    data = plan.to_dict()
    restored = DayPlan.from_dict(data)
    assert restored.day == plan.day
    assert restored.completed == plan.completed
    assert restored.app_tasks == plan.app_tasks
