"""Schedule-driven reminder logic. Pure functions here; APScheduler glue below."""
from __future__ import annotations

import logging
import os
from datetime import date, datetime, time, timedelta
from typing import Callable, Optional

from apscheduler.schedulers.background import BackgroundScheduler

from dayctl.models import DayPlan, incomplete_tasks, profile_for_date
from dayctl.schedule_parse import parse_block
from dayctl.server.ntfy import post_ntfy
from dayctl.storage import load_plan

log = logging.getLogger(__name__)

Poster = Callable[[str, str, str, str], None]


def _in_quiet_window(now: datetime) -> bool:
    quiet = os.environ.get("DAYCTL_QUIET_UNTIL", "").strip()
    if not quiet:
        return False
    try:
        until = date.fromisoformat(quiet)
    except ValueError:
        return False
    return now.date() <= until


def should_fire_now(
    profile: dict, now: datetime, last_tick: datetime
) -> list[tuple[time, str]]:
    """Return (time, label) for any schedule block whose start time
    falls strictly after last_tick and at or before now."""
    if _in_quiet_window(now):
        return []
    if last_tick >= now:
        return []
    fires: list[tuple[time, str]] = []
    for line in profile.get("schedule", []):
        parsed = parse_block(line)
        if parsed is None:
            continue
        t, label = parsed
        block_today = datetime.combine(now.date(), t)
        if last_tick < block_today <= now:
            fires.append((t, label))
    return fires


def _body_for(plan: Optional[DayPlan]) -> str:
    if plan is None:
        return ""
    pending = incomplete_tasks(plan)
    lines: list[str] = []
    for cat, tasks in pending.items():
        for t in tasks[:2]:
            lines.append(f"• {t['task']}")
    return "\n".join(lines)


def tick_once(
    profile: dict,
    now: datetime,
    last_tick: datetime,
    poster: Poster,
    plan: Optional[DayPlan],
) -> None:
    topic = os.environ.get("NTFY_TOPIC", "")
    if not topic:
        return
    fires = should_fire_now(profile, now, last_tick)
    for _, label in fires:
        try:
            poster(topic, label, _body_for(plan), "default")
        except Exception as e:
            log.warning("poster failed: %s", e)


class ReminderScheduler:
    def __init__(self) -> None:
        self._scheduler = BackgroundScheduler()
        self._last_tick: datetime = datetime.now() - timedelta(minutes=1)

    def start(self) -> None:
        self._scheduler.add_job(self._run, "interval", minutes=1, id="dayctl_tick")
        self._scheduler.start()

    def stop(self) -> None:
        self._scheduler.shutdown(wait=False)

    def _run(self) -> None:
        now = datetime.now()
        today = now.date().isoformat()
        profile = profile_for_date(today)
        try:
            plan = load_plan(today)
        except Exception:
            plan = None
        tick_once(profile, now, self._last_tick, post_ntfy, plan)
        self._last_tick = now
