"""Tests for dayctl.models."""

from dayctl.models import (
    DayPlan, NON_NEGOTIABLE_KEYS, SCHEDULE_PROFILES,
    profile_for_date, score_plan, wake_time, week_dates,
    compute_streak, incomplete_tasks, carry_forward,
)


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


# ---------------------------------------------------------------------------
# week_dates
# ---------------------------------------------------------------------------

def test_week_dates_returns_mon_to_sun():
    # 2026-03-18 is a Wednesday
    days = week_dates("2026-03-18")
    assert len(days) == 7
    assert days[0] == "2026-03-16"  # Monday
    assert days[6] == "2026-03-22"  # Sunday


def test_week_dates_monday_input():
    days = week_dates("2026-03-16")
    assert days[0] == "2026-03-16"
    assert days[6] == "2026-03-22"


# ---------------------------------------------------------------------------
# compute_streak
# ---------------------------------------------------------------------------

def test_streak_empty():
    assert compute_streak([]) == 0


def test_streak_single_day_above():
    assert compute_streak([("2026-03-20", 3)]) == 1


def test_streak_single_day_below():
    assert compute_streak([("2026-03-20", 2)]) == 0


def test_streak_consecutive():
    scores = [
        ("2026-03-18", 3),
        ("2026-03-19", 4),
        ("2026-03-20", 3),
    ]
    assert compute_streak(scores) == 3


def test_streak_broken_by_low_score():
    scores = [
        ("2026-03-18", 4),
        ("2026-03-19", 1),
        ("2026-03-20", 4),
    ]
    assert compute_streak(scores) == 1


def test_streak_broken_by_gap():
    scores = [
        ("2026-03-17", 4),
        # gap: 03-18 missing
        ("2026-03-19", 4),
        ("2026-03-20", 4),
    ]
    assert compute_streak(scores) == 2


def test_streak_custom_threshold():
    scores = [
        ("2026-03-19", 4),
        ("2026-03-20", 4),
    ]
    assert compute_streak(scores, threshold=4) == 2
    assert compute_streak(scores, threshold=5) == 0


# ---------------------------------------------------------------------------
# incomplete_tasks / carry_forward
# ---------------------------------------------------------------------------

def test_incomplete_tasks_filters_done():
    plan = DayPlan.new("2026-03-20")
    plan.app_tasks = [
        {"task": "done task", "done": True},
        {"task": "pending task", "done": False},
    ]
    plan.music_tasks = [{"task": "all done", "done": True}]
    result = incomplete_tasks(plan)
    assert "app_tasks" in result
    assert len(result["app_tasks"]) == 1
    assert result["app_tasks"][0]["task"] == "pending task"
    assert "music_tasks" not in result


def test_carry_forward_adds_pending():
    today = DayPlan.new("2026-03-20")
    yesterday = DayPlan.new("2026-03-19")
    yesterday.app_tasks = [
        {"task": "finished", "done": True},
        {"task": "still pending", "done": False},
    ]
    yesterday.music_tasks = [{"task": "mix verse", "done": False}]

    carried = carry_forward(today, yesterday)
    assert len(carried) == 2
    assert any("still pending" in c for c in carried)
    assert any("mix verse" in c for c in carried)
    # Verify tasks were actually added
    app_texts = [t["task"] for t in today.app_tasks]
    assert "still pending" in app_texts


def test_carry_forward_deduplicates():
    today = DayPlan.new("2026-03-20")
    today.app_tasks.append({"task": "already here", "done": False})
    yesterday = DayPlan.new("2026-03-19")
    yesterday.app_tasks = [{"task": "already here", "done": False}]

    carried = carry_forward(today, yesterday)
    assert len(carried) == 0
    # Should not have duplicated
    count = sum(1 for t in today.app_tasks if t["task"] == "already here")
    assert count == 1
