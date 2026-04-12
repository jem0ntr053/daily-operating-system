"""Parse schedule block strings like '6:30 AM  Wake' or '8:00 AM-4:00 PM  Remote Work'."""
from __future__ import annotations

import re
from datetime import time

_TIME_RE = re.compile(r"^\s*(\d{1,2}):(\d{2})\s*(AM|PM)", re.IGNORECASE)


def parse_block(line: str) -> tuple[time, str] | None:
    """Return (start_time, label) or None if no leading time found.

    For ranges like '8:00 AM-4:00 PM  Remote Work', returns the start time.
    The label is everything after the first double-space separator, stripped.
    """
    m = _TIME_RE.match(line)
    if not m:
        return None
    hour = int(m.group(1)) % 12
    if m.group(3).upper() == "PM":
        hour += 12
    minute = int(m.group(2))
    parts = line.split("  ", 1)
    label = parts[1].strip() if len(parts) == 2 else ""
    return time(hour, minute), label
