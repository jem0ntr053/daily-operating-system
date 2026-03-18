"""Data model and constants for dayctl."""

from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Dict, List


DEFAULT_SCHEDULE = [
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
    "9:00 PM  Fast Starts",
    "10:30 PM  Sleep",
]

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

NON_NEGOTIABLE_KEYS = ["fast", "gym", "app", "music"]


@dataclass
class DayPlan:
    day: str
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
    def new(day_str: str) -> DayPlan:
        return DayPlan(
            day=day_str,
            focus="",
            energy="",
            sleep_hours="",
            fasting_window="9:00 PM → 2:00 PM",
            schedule=DEFAULT_SCHEDULE.copy(),
            completed={k: False for k in NON_NEGOTIABLE_KEYS},
            app_tasks=[{"task": t, "done": False} for t in DEFAULT_TASKS["app"]],
            music_tasks=[{"task": t, "done": False} for t in DEFAULT_TASKS["music"]],
            notes=[],
        )

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> DayPlan:
        return cls(**data)


def score_plan(plan: DayPlan) -> int:
    return sum(1 for key in NON_NEGOTIABLE_KEYS if plan.completed.get(key, False))
