"""Data model and constants for dayctl."""

from __future__ import annotations

from dataclasses import dataclass, asdict, fields
from datetime import date, timedelta
from typing import Dict, List


SCHEDULE_PROFILES = {
    "weekday": {
        "label": "Mon-Thu Standard",
        "fasting_window": "9:00 PM → 2:00 PM",
        "schedule": [
            "6:30 AM  Wake",
            "7:00–8:00 AM  App Work",
            "8:00 AM–4:00 PM  Remote Work",
            "2:00 PM  Break Fast / Meal 1",
            "3:45 PM  Pre-Gym Snack",
            "4:20 PM  Leave for Gym",
            "4:30–6:00 PM  Gym",
            "6:00–6:10 PM  Drive Home",
            "6:10 PM  Dinner / Post-Workout Meal",
            "6:50–7:50 PM  Music Production",
            "7:50–9:30 PM  Free Time / Reset",
            "9:00 PM  Fast Starts",
            "10:30 PM  Sleep",
        ],
    },
    "friday": {
        "label": "Friday Flexible",
        "fasting_window": "11:00 PM → 4:00 PM",
        "schedule": [
            "7:00 AM  Wake",
            "8:00 AM–4:00 PM  Remote Work",
            "4:00 PM  Break Fast / Meal 1",
            "5:15 PM  Pre-Gym Snack",
            "5:50 PM  Leave for Gym",
            "6:00–7:30 PM  Gym",
            "7:30–7:40 PM  Drive Home",
            "7:45 PM  Dinner / Post-Workout Meal",
            "8:30–9:30 PM  Light Music / Prep / Overflow",
            "9:30 PM onward  Social / Show Prep / Flexible Night",
            "11:00 PM  Fast Starts",
            "1:00 AM  Target Sleep (flexible)",
        ],
    },
    "friday_show": {
        "label": "Friday Show Night",
        "fasting_window": "11:00 PM → 4:00 PM",
        "schedule": [
            "7:00 AM  Wake",
            "8:00 AM–4:00 PM  Remote Work",
            "4:00 PM  Break Fast / Meal 1",
            "5:15 PM  Pre-Gym Snack",
            "5:50 PM  Leave for Gym",
            "6:00–7:30 PM  Gym",
            "7:30–7:40 PM  Drive Home",
            "7:45 PM  Dinner / Post-Workout Meal",
            "8:30–10:00 PM  Set Prep / Travel / Showtime Prep",
            "10:00 PM–3:00 AM  Show / Gig / Late Night",
            "11:00 PM  Fast Starts (or after final meal)",
            "3:30 AM  Sleep",
        ],
    },
    "saturday_show": {
        "label": "Saturday Show Night",
        "fasting_window": "11:00 PM → 4:00 PM",
        "schedule": [
            "9:30 AM  Wake / Recovery",
            "10:00 AM–12:00 PM  Free Time / Recovery / Admin",
            "12:30 PM  Optional Light App Work or Planning",
            "4:00 PM  Break Fast / Meal 1",
            "5:15 PM  Pre-Gym Snack",
            "5:50 PM  Leave for Gym",
            "6:00–7:30 PM  Gym",
            "7:30–7:40 PM  Drive Home",
            "7:45 PM  Dinner / Post-Workout Meal",
            "8:30–10:00 PM  Set Prep / Travel / Showtime Prep",
            "10:00 PM–3:00 AM  Show / Gig / Late Night",
            "11:00 PM  Fast Starts (or after final meal)",
            "3:30 AM  Sleep",
        ],
    },
    "saturday_no_show": {
        "label": "Saturday No-Show",
        "fasting_window": "10:00 PM → 3:00 PM",
        "schedule": [
            "8:30 AM  Wake",
            "9:00–10:00 AM  App Work",
            "10:00 AM–1:00 PM  Free Time / Errands / Recovery",
            "3:00 PM  Break Fast / Meal 1",
            "4:15 PM  Pre-Gym Snack",
            "4:50 PM  Leave for Gym",
            "5:00–6:30 PM  Gym",
            "6:30–6:40 PM  Drive Home",
            "6:45 PM  Dinner / Post-Workout Meal",
            "7:30–8:30 PM  Music Production",
            "8:30–10:30 PM  Flexible Night",
            "10:00 PM  Fast Starts",
            "12:00 AM  Sleep",
        ],
    },
    "sunday": {
        "label": "Sunday Reset",
        "fasting_window": "9:00 PM → 2:00 PM",
        "schedule": [
            "8:30 AM  Wake",
            "9:00–9:30 AM  Weekly Reset / Planning",
            "10:20 AM  Leave for Gym",
            "10:30 AM–12:00 PM  Gym",
            "12:00–12:10 PM  Drive Home",
            "2:00 PM  Break Fast / Meal 1",
            "3:30 PM  App Planning / Weekly Review",
            "5:00 PM  Dinner",
            "6:00–7:00 PM  Music Production / Organization",
            "7:00–8:30 PM  Prepare for Monday",
            "9:00 PM  Fast Starts",
            "10:30 PM  Sleep",
        ],
    },
}

# Day-of-week (0=Mon) to profile key. Saturday defaults to no_show.
_DOW_TO_PROFILE = {
    0: "weekday",
    1: "weekday",
    2: "weekday",
    3: "weekday",
    4: "friday",
    5: "saturday_no_show",
    6: "sunday",
}


def profile_for_date(day_str: str) -> dict:
    """Return the schedule profile dict for a given YYYY-MM-DD date."""
    d = date.fromisoformat(day_str)
    key = _DOW_TO_PROFILE[d.weekday()]
    return SCHEDULE_PROFILES[key]


def week_dates(reference: str) -> list[str]:
    """Return Mon-Sun ISO date strings for the week containing reference date."""
    d = date.fromisoformat(reference)
    monday = d - timedelta(days=d.weekday())
    return [(monday + timedelta(days=i)).isoformat() for i in range(7)]

DEFAULT_TASKS = {
    "app": [
        "Define today's highest-value application task",
        "Complete one meaningful step",
    ],
    "music": [
        "Define today's highest-value music task",
        "Complete one meaningful step",
    ],
}

# Profiles that have a show/no-show counterpart (bidirectional)
SHOW_TOGGLE = {
    "friday": "friday_show",
    "friday_show": "friday",
    "saturday_no_show": "saturday_show",
    "saturday_show": "saturday_no_show",
}

NON_NEGOTIABLE_KEYS = ["fast", "gym", "app", "music"]


@dataclass
class DayPlan:
    day: str
    profile: str
    focus: str
    energy: str
    sleep_hours: str
    fasting_window: str
    schedule: List[str]
    completed: Dict[str, bool]
    app_tasks: List[Dict[str, bool | str]]
    music_tasks: List[Dict[str, bool | str]]
    notes: List[str]

    @staticmethod
    def new(day_str: str, profile_key: str | None = None) -> DayPlan:
        if profile_key is not None:
            if profile_key not in SCHEDULE_PROFILES:
                raise ValueError(f"Unknown profile '{profile_key}'. Valid: {', '.join(SCHEDULE_PROFILES)}")
            resolved_key = profile_key
        else:
            d = date.fromisoformat(day_str)
            resolved_key = _DOW_TO_PROFILE[d.weekday()]
        prof = SCHEDULE_PROFILES[resolved_key]
        return DayPlan(
            day=day_str,
            profile=resolved_key,
            focus="",
            energy="",
            sleep_hours="8",
            fasting_window=prof["fasting_window"],
            schedule=list(prof["schedule"]),
            completed={k: False for k in NON_NEGOTIABLE_KEYS},
            app_tasks=[{"task": t, "done": False} for t in DEFAULT_TASKS["app"]],
            music_tasks=[{"task": t, "done": False} for t in DEFAULT_TASKS["music"]],
            notes=[],
        )

    def switch_profile(self, new_key: str) -> None:
        """Switch schedule profile in-place, preserving user data."""
        if new_key not in SCHEDULE_PROFILES:
            raise ValueError(f"Unknown profile '{new_key}'. Valid: {', '.join(SCHEDULE_PROFILES)}")
        prof = SCHEDULE_PROFILES[new_key]
        self.profile = new_key
        self.fasting_window = prof["fasting_window"]
        self.schedule = list(prof["schedule"])

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> DayPlan:
        known = {f.name for f in fields(cls)}
        filtered = {k: v for k, v in data.items() if k in known}
        # Backfill profile for plans saved before this field existed
        if "profile" not in filtered and "day" in filtered:
            d = date.fromisoformat(filtered["day"])
            filtered["profile"] = _DOW_TO_PROFILE[d.weekday()]
        # Normalize task dicts to ensure correct types
        for key in ("app_tasks", "music_tasks"):
            if key in filtered:
                filtered[key] = [
                    {"task": str(t.get("task", "")), "done": bool(t.get("done", False))}
                    for t in filtered[key]
                ]
        try:
            return cls(**filtered)
        except TypeError as e:
            raise ValueError(f"Malformed plan data: {e}") from e


def score_plan(plan: DayPlan) -> int:
    return sum(1 for key in NON_NEGOTIABLE_KEYS if plan.completed.get(key, False))


def wake_time(plan: DayPlan) -> str:
    """Extract the wake time from the first schedule entry."""
    if plan.schedule:
        return plan.schedule[0].split("  ", 1)[0]
    return ""


def compute_streak(day_scores: list[tuple[str, int]], threshold: int = 3) -> int:
    """Count consecutive days (ending today/most recent) with score >= threshold.

    day_scores must be sorted chronologically [(oldest, score), ..., (newest, score)].
    Gaps in dates break the streak.
    """
    if not day_scores:
        return 0

    streak = 0
    prev_date: date | None = None

    for day_str, score in reversed(day_scores):
        d = date.fromisoformat(day_str)
        if prev_date is not None and (prev_date - d).days != 1:
            break  # gap in dates
        if score < threshold:
            break
        streak += 1
        prev_date = d

    return streak


def incomplete_tasks(plan: DayPlan) -> dict[str, list[dict]]:
    """Return incomplete tasks from a plan, keyed by category."""
    result: dict[str, list[dict]] = {}
    for attr in ("app_tasks", "music_tasks"):
        pending = [t for t in getattr(plan, attr) if not t.get("done", False)]
        if pending:
            result[attr] = [{"task": t["task"], "done": False} for t in pending]
    return result


def carry_forward(plan: DayPlan, previous: DayPlan) -> list[str]:
    """Carry incomplete tasks from previous day into plan. Returns list of carried descriptions."""
    carried: list[str] = []
    existing: dict[str, set[str]] = {}
    for attr in ("app_tasks", "music_tasks"):
        existing[attr] = {str(t["task"]) for t in getattr(plan, attr)}

    pending = incomplete_tasks(previous)
    for attr, tasks in pending.items():
        current = getattr(plan, attr)
        for t in tasks:
            if str(t["task"]) not in existing[attr]:
                current.append({"task": t["task"], "done": False})
                carried.append(f"{attr.replace('_tasks', '')}: {t['task']}")
    return carried
