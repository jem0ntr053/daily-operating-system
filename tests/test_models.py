"""Tests for dayctl.models."""

from dayctl.models import (
    DayPlan, NON_NEGOTIABLE_KEYS, SCHEDULE_PROFILES,
    profile_for_date, score_plan, wake_time, week_dates,
    compute_streak, incomplete_tasks, carry_forward,
    HABIT_TEMPLATE, HABIT_KEYS, AREAS,
)


# ---------------------------------------------------------------------------
# Task 3: 5-area tasks
# ---------------------------------------------------------------------------

def test_areas_and_new_seeding():
    assert AREAS == ["music", "youtube", "marketing", "social", "code"]
    plan = DayPlan.new("2026-05-24")
    assert set(plan.tasks) == set(AREAS)
    assert all({"text", "done", "tag", "carried"} <= set(t) for t in plan.tasks["music"])


def test_from_dict_migrates_legacy_tasks():
    legacy = {
        "day": "2026-05-24", "profile": "weekday", "focus": "", "energy": "",
        "sleep_hours": "8", "fasting_window": "x", "schedule": [],
        "completed": {}, "notes": [],
        "app_tasks": [{"task": "ship it", "done": True}],
        "music_tasks": [{"task": "mix", "done": False}],
    }
    plan = DayPlan.from_dict(legacy)
    assert plan.tasks["code"] == [{"text": "ship it", "done": True, "tag": "", "carried": False}]
    assert plan.tasks["music"] == [{"text": "mix", "done": False, "tag": "", "carried": False}]


def test_carry_forward_marks_carried():
    prev = DayPlan.new("2026-05-23")
    prev.tasks["code"] = [{"text": "todo", "done": False, "tag": "", "carried": False}]
    today = DayPlan.new("2026-05-24")
    today.tasks["code"] = []
    carry_forward(today, prev)
    assert today.tasks["code"][0]["text"] == "todo"
    assert today.tasks["code"][0]["carried"] is True


def test_habit_template_has_six():
    assert [h["id"] for h in HABIT_TEMPLATE] == ["fast", "gym", "music", "ship", "post", "read"]
    assert HABIT_KEYS == ["fast", "gym", "music", "ship", "post", "read"]


def test_new_plan_seeds_six_habits():
    plan = DayPlan.new("2026-05-24")
    assert set(plan.completed) == set(HABIT_KEYS)
    assert all(v is False for v in plan.completed.values())


def test_score_counts_completed_out_of_six():
    plan = DayPlan.new("2026-05-24")
    for k in ("fast", "gym", "music"):
        plan.completed[k] = True
    assert score_plan(plan) == 3


def test_new_plan_defaults():
    # 2026-03-17 is a Tuesday → weekday profile
    plan = DayPlan.new("2026-03-17")
    assert plan.day == "2026-03-17"
    assert plan.fasting_window == "9:00 PM → 2:00 PM"
    assert plan.schedule[0] == "6:30 AM  Wake"
    assert all(v is False for v in plan.completed.values())
    assert len(plan.completed) == 6
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
    assert score_plan(plan) == 6


def test_to_dict_roundtrip():
    plan = DayPlan.new("2026-03-17")
    data = plan.to_dict()
    restored = DayPlan.from_dict(data)
    assert restored.day == plan.day
    assert restored.completed == plan.completed
    assert restored.tasks == plan.tasks


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
    # Simulate corrupted data: int text, string done
    data["tasks"]["code"] = [{"text": 42, "done": "yes", "tag": "", "carried": False}]
    restored = DayPlan.from_dict(data)
    assert restored.tasks["code"][0]["text"] == "42"
    assert restored.tasks["code"][0]["done"] is True


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
    plan.tasks["code"] = [
        {"text": "done task", "done": True, "tag": "", "carried": False},
        {"text": "pending task", "done": False, "tag": "", "carried": False},
    ]
    plan.tasks["music"] = [{"text": "all done", "done": True, "tag": "", "carried": False}]
    result = incomplete_tasks(plan)
    assert "code" in result
    assert len(result["code"]) == 1
    assert result["code"][0]["text"] == "pending task"
    assert "music" not in result


def test_carry_forward_adds_pending():
    today = DayPlan.new("2026-03-20")
    yesterday = DayPlan.new("2026-03-19")
    yesterday.tasks["code"] = [
        {"text": "finished", "done": True, "tag": "", "carried": False},
        {"text": "still pending", "done": False, "tag": "", "carried": False},
    ]
    yesterday.tasks["music"] = [{"text": "mix verse", "done": False, "tag": "", "carried": False}]

    carried = carry_forward(today, yesterday)
    assert len(carried) == 2
    assert any("still pending" in c for c in carried)
    assert any("mix verse" in c for c in carried)
    # Verify tasks were actually added
    code_texts = [t["text"] for t in today.tasks["code"]]
    assert "still pending" in code_texts


def test_carry_forward_deduplicates():
    today = DayPlan.new("2026-03-20")
    today.tasks["code"].append({"text": "already here", "done": False, "tag": "", "carried": False})
    yesterday = DayPlan.new("2026-03-19")
    yesterday.tasks["code"] = [{"text": "already here", "done": False, "tag": "", "carried": False}]

    carried = carry_forward(today, yesterday)
    assert len(carried) == 0
    # Should not have duplicated
    count = sum(1 for t in today.tasks["code"] if t["text"] == "already here")
    assert count == 1


# ---------------------------------------------------------------------------
# Scalar day fields: mood, bpm, flow_minutes
# ---------------------------------------------------------------------------

def test_new_plan_has_scalar_defaults():
    plan = DayPlan.new("2026-05-24")
    assert plan.mood == "" and plan.bpm == "" and plan.flow_minutes == 0


def test_from_dict_backfills_scalar_fields():
    legacy = DayPlan.new("2026-05-24").to_dict()
    legacy.pop("mood"); legacy.pop("bpm"); legacy.pop("flow_minutes")
    plan = DayPlan.from_dict(legacy)
    assert plan.mood == "" and plan.bpm == "" and plan.flow_minutes == 0


# ---------------------------------------------------------------------------
# Task 4: Timestamped notes
# ---------------------------------------------------------------------------

def test_from_dict_normalizes_string_notes():
    legacy = DayPlan.new("2026-05-24").to_dict()
    legacy["notes"] = ["belly felt weird", "note 2"]
    plan = DayPlan.from_dict(legacy)
    assert plan.notes == [{"text": "belly felt weird", "time": ""}, {"text": "note 2", "time": ""}]
