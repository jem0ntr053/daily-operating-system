#!/usr/bin/env python3
"""Send macOS notifications for upcoming schedule blocks.

Designed to run every minute via launchd. Checks today's plan and fires
a notification 5 minutes before each schedule entry.
"""

from __future__ import annotations

import re
import subprocess
import sys
from datetime import datetime, date
from pathlib import Path

# Ensure the package is importable
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from dayctl.storage import load_plan, plan_path

LEAD_MINUTES = 5  # notify this many minutes before


def parse_start_time(entry: str) -> datetime | None:
    """Extract the start time from a schedule entry as a datetime for today."""
    cleaned = entry.replace(" onward", "")
    parts = cleaned.split("  ", 1)
    if len(parts) != 2:
        return None
    time_part = parts[0].strip()

    # Match first time in the entry (e.g. "7:00" from "7:00–8:00 AM")
    m = re.match(r"(\d{1,2}):(\d{2})\s*(AM|PM)?", time_part, re.IGNORECASE)
    if not m:
        return None

    hour, minute = int(m.group(1)), int(m.group(2))
    ampm = m.group(3)

    # If no AM/PM on start time, look for it later in the string
    if not ampm:
        ampm_match = re.search(r"(AM|PM)", time_part, re.IGNORECASE)
        if ampm_match:
            ampm = ampm_match.group(1)
        else:
            return None

    ampm = ampm.upper()
    if ampm == "AM" and hour == 12:
        hour = 0
    elif ampm == "PM" and hour != 12:
        hour += 12

    today = date.today()
    return datetime(today.year, today.month, today.day, hour, minute)


def get_activity(entry: str) -> str:
    """Extract the activity name from a schedule entry."""
    parts = entry.split("  ", 1)
    return parts[1].strip() if len(parts) == 2 else entry.strip()


def send_notification(title: str, message: str) -> None:
    """Send a macOS notification via osascript."""
    script = (
        f'display notification "{message}" '
        f'with title "{title}" '
        f'sound name "Glass"'
    )
    subprocess.run(["osascript", "-e", script], check=False)


def main() -> None:
    today = date.today().isoformat()

    if not plan_path(today).exists():
        return

    plan = load_plan(today)
    now = datetime.now()

    for entry in plan.schedule:
        start = parse_start_time(entry)
        if start is None:
            continue

        diff = (start - now).total_seconds() / 60  # minutes until event

        # Fire if we're within the lead window (0 to LEAD_MINUTES minutes before)
        if 0 <= diff <= LEAD_MINUTES:
            activity = get_activity(entry)
            if diff < 1:
                send_notification("Daily OS", f"Now: {activity}")
            else:
                send_notification("Daily OS", f"In {int(diff)} min: {activity}")


if __name__ == "__main__":
    main()
