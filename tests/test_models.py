"""Tests for dayctl.models."""

from dayctl.models import DayPlan, NON_NEGOTIABLE_KEYS, SCHEDULE_PROFILES, profile_for_date, score_plan, wake_time


def test_new_plan_defaults():
    # 2026-03-17 is a Tuesday → weekday profile
    plan = DayPlan.new("2026-03-17")
    assert plan.day == "2026-03-17"
    assert plan.fasting_window == "9:00 PM → 2:00 PM"
    assert plan.schedule[0] == "6:30 AM  Wake"
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


def test_from_dict_ignores_unknown_keys():
    plan = DayPlan.new("2026-03-17")
    data = plan.to_dict()
    data["some_future_field"] = "value"
    restored = DayPlan.from_dict(data)
    assert restored.day == "2026-03-17"


def test_from_dict_raises_on_missing_required():
    import pytest
    with pytest.raises(ValueError, match="Malformed plan data"):
        DayPlan.from_dict({"day": "2026-03-17"})


# ---------------------------------------------------------------------------
# Schedule profiles
# ---------------------------------------------------------------------------

def test_profile_for_weekday():
    # Tuesday
    profile = profile_for_date("2026-03-17")
    assert profile["label"] == "Mon-Thu Standard"


def test_profile_for_friday():
    profile = profile_for_date("2026-03-20")
    assert profile["label"] == "Friday Flexible"


def test_profile_for_saturday():
    # Saturday defaults to no-show
    profile = profile_for_date("2026-03-21")
    assert profile["label"] == "Saturday No-Show"


def test_profile_for_sunday():
    profile = profile_for_date("2026-03-22")
    assert profile["label"] == "Sunday Reset"


def test_new_plan_friday_schedule():
    plan = DayPlan.new("2026-03-20")
    assert plan.fasting_window == "11:00 PM → 4:00 PM"
    assert plan.schedule[0] == "7:00 AM  Wake"


def test_new_plan_profile_override():
    # Saturday, but force show profile
    plan = DayPlan.new("2026-03-21", profile_key="saturday_show")
    assert plan.fasting_window == "11:00 PM → 4:00 PM"
    assert plan.schedule[0] == "9:30 AM  Wake / Recovery"


def test_new_plan_sunday_schedule():
    plan = DayPlan.new("2026-03-22")
    assert plan.fasting_window == "9:00 PM → 2:00 PM"
    assert plan.schedule[0] == "8:30 AM  Wake"


def test_new_plan_invalid_profile_raises():
    import pytest
    with pytest.raises(ValueError, match="Unknown profile 'typo_profile'"):
        DayPlan.new("2026-03-17", profile_key="typo_profile")


def test_wake_time():
    plan = DayPlan.new("2026-03-17")
    assert wake_time(plan) == "6:30 AM"


def test_from_dict_normalizes_task_types():
    plan = DayPlan.new("2026-03-17")
    data = plan.to_dict()
    # Simulate corrupted data: int task, string done
    data["app_tasks"] = [{"task": 42, "done": "yes"}]
    restored = DayPlan.from_dict(data)
    assert restored.app_tasks[0]["task"] == "42"
    assert restored.app_tasks[0]["done"] is True
