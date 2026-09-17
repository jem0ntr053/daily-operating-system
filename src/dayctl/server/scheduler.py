"""Schedule-driven reminder logic. Pure functions here; APScheduler glue below."""
from __future__ import annotations

import logging
import os
from datetime import date, datetime, time, timedelta
from typing import Callable, Optional

from apscheduler.schedulers.background import BackgroundScheduler

from dayctl.models import DayPlan, incomplete_tasks, missed_twice, profile_for_date
from dayctl.schedule_parse import parse_block
from dayctl.server.ntfy import post_ntfy
from dayctl.storage import exists, load_plan

log = logging.getLogger(__name__)

Poster = Callable[..., None]


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
            lines.append(f"• {t['text']}")
    return "\n".join(lines)


def _stack_action(plan: Optional[DayPlan], day: str) -> Optional[str]:
    """ntfy http-action that advances the next incomplete stack step. LAN-only.
    Returns None unless DAYCTL_PUBLIC_URL is set and a pending stack item exists."""
    base = os.environ.get("DAYCTL_PUBLIC_URL", "").strip().rstrip("/")
    token = os.environ.get("DAYCTL_TOKEN", "").strip()
    if not base or not token or plan is None:
        return None
    if not any(not t["done"] for t in plan.tasks.get("stack", [])):
        return None
    if not os.environ.get("NTFY_AUTH", "").strip():
        log.warning(
            "DAYCTL_PUBLIC_URL is set but NTFY_AUTH is not — the advance action "
            "embeds DAYCTL_TOKEN in the ntfy push; set NTFY_AUTH so the topic "
            "itself is private, or anyone who can read it gets your token."
        )
    url = f"{base}/api/days/{day}/tasks/stack/advance"
    return f"http, Done ✓, {url}, method=POST, headers.Authorization=Bearer {token}, clear=true"


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
    if not fires:
        return
    action = _stack_action(plan, now.date().isoformat())
    for _, label in fires:
        try:
            poster(topic, label, _body_for(plan), "default", action)
        except Exception as e:
            log.warning("poster failed: %s", e)


class ReminderScheduler:
    def __init__(self) -> None:
        self._scheduler = BackgroundScheduler()
        self._last_tick: datetime = datetime.now() - timedelta(minutes=1)
        self._alarm_date: str | None = None

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
        self._maybe_miss_alarm(now)
        self._last_tick = now

    def _maybe_miss_alarm(self, now: datetime) -> None:
        """Fire one high-priority ntfy if the stack was missed 2 days running.

        Only judges days that were actually tracked — a day is never fabricated
        just to check it (load_plan auto-creates on miss; exists() guards that).
        """
        topic = os.environ.get("NTFY_TOPIC", "")
        today = now.date().isoformat()
        if not topic or self._alarm_date == today:
            return
        d1 = (now.date() - timedelta(days=1)).isoformat()
        d2 = (now.date() - timedelta(days=2)).isoformat()
        if exists(d1) and exists(d2):
            try:
                prev, prev2 = load_plan(d1), load_plan(d2)
            except Exception as e:
                log.warning("miss alarm: could not load prior days: %s", e)
                self._alarm_date = today
                return
            if missed_twice(prev, prev2):
                try:
                    post_ntfy(topic, "Don't miss twice", "Stack missed 2 days. Do one tiny step tonight.", "high")
                except Exception as e:
                    log.warning("miss alarm failed: %s", e)
        self._alarm_date = today
