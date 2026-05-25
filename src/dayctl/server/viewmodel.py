"""Build the day-view context for templates."""
from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path

from dayctl.models import (
    HABIT_TEMPLATE, HABIT_KEYS, SCHEDULE_PROFILES,
    compute_streak, profile_for_date, score_plan, week_dates,
)
from dayctl.persistent import load_persistent
from dayctl.storage import exists, list_days, load_plan

_STYLE_PATH = Path(__file__).parent / "static" / "style.css"


def _css_version() -> int:
    """Mtime of style.css, used to cache-bust the stylesheet link."""
    try:
        return int(_STYLE_PATH.stat().st_mtime)
    except OSError:
        return 0


def _profile_label(plan) -> str:
    prof = SCHEDULE_PROFILES.get(plan.profile)
    return prof["label"] if prof else profile_for_date(plan.day)["label"]


def _parse_schedule(plan) -> list[dict]:
    rows = []
    for line in plan.schedule:
        parts = line.split("  ", 1)
        if len(parts) == 2:
            rows.append({"time": parts[0].strip(), "title": parts[1].strip()})
        else:
            rows.append({"time": "", "title": line.strip()})
    return rows


def _week(day: str) -> list[dict]:
    today = date.today().isoformat()
    out = []
    for iso in week_dates(day):
        wscore = score_plan(load_plan(iso)) if exists(iso) else 0
        out.append({
            "iso": iso,
            "label": date.fromisoformat(iso).strftime("%a %m/%d"),
            "score": wscore,
            "total": len(HABIT_KEYS),
            "is_today": iso == today,
            "is_view": iso == day,
            "is_future": iso > today,
        })
    return out


def _streak() -> int:
    days = sorted(list_days())
    scores = [(d, score_plan(load_plan(d))) for d in days]
    return compute_streak(scores, threshold=len(HABIT_KEYS))


def build_day_view(day: str) -> dict:
    plan = load_plan(day)
    today = date.today().isoformat()
    return {
        "plan": plan,
        "day": day,
        "score": score_plan(plan),
        "habits": HABIT_TEMPLATE,
        "total": len(HABIT_KEYS),
        "schedule": _parse_schedule(plan),
        "week": _week(day),
        "streak": _streak(),
        "profile_label": _profile_label(plan),
        "persistent": load_persistent(),
        "is_today": day == today,
        "prev_day": (date.fromisoformat(day) - timedelta(days=1)).isoformat(),
        "next_day": (date.fromisoformat(day) + timedelta(days=1)).isoformat(),
        "today": today,
        "date_long": date.fromisoformat(day).strftime("%A, %B %-d"),
        "css_v": _css_version(),
        "week_number": date.fromisoformat(day).isocalendar()[1],
        "logged": len(list_days()),
    }
