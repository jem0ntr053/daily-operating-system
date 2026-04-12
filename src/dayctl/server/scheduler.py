"""Schedule-driven reminder logic. Pure functions here; APScheduler glue in Task 10."""
from __future__ import annotations

import os
from datetime import date, datetime, time

from dayctl.schedule_parse import parse_block


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
