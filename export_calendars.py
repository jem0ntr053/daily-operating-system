"""Export schedule profiles as .ics calendar files for Apple/Google Calendar."""

from __future__ import annotations

import re
import sys
from datetime import datetime, timedelta
from pathlib import Path
from uuid import uuid4

sys.path.insert(0, str(Path(__file__).parent / "src"))

from dayctl.models import SCHEDULE_PROFILES


# Map profile keys to RRULE BYDAY values
PROFILE_RRULE = {
    "weekday": "RRULE:FREQ=WEEKLY;BYDAY=MO,TU,WE,TH",
    "friday": "RRULE:FREQ=WEEKLY;BYDAY=FR",
    "friday_show": "RRULE:FREQ=WEEKLY;BYDAY=FR",
    "saturday_show": "RRULE:FREQ=WEEKLY;BYDAY=SA",
    "saturday_no_show": "RRULE:FREQ=WEEKLY;BYDAY=SA",
    "sunday": "RRULE:FREQ=WEEKLY;BYDAY=SU",
}

# Reference dates (a week starting Mon 2026-03-23) for anchoring events
PROFILE_REF_DATE = {
    "weekday": "20260323",       # Monday
    "friday": "20260327",        # Friday
    "friday_show": "20260327",   # Friday
    "saturday_show": "20260328", # Saturday
    "saturday_no_show": "20260328",
    "sunday": "20260329",        # Sunday
}


def parse_time(raw: str) -> tuple[int, int]:
    """Parse '6:30 AM' or '12:00 PM' or '3:00 AM' into (hour24, minute)."""
    raw = raw.strip().rstrip(".")
    m = re.match(r"(\d{1,2}):(\d{2})\s*(AM|PM)", raw, re.IGNORECASE)
    if not m:
        raise ValueError(f"Cannot parse time: {raw!r}")
    hour, minute, ampm = int(m.group(1)), int(m.group(2)), m.group(3).upper()
    if ampm == "AM" and hour == 12:
        hour = 0
    elif ampm == "PM" and hour != 12:
        hour += 12
    return hour, minute


def parse_schedule_entry(entry: str) -> dict | None:
    """Parse a schedule entry into start, end, and description.

    Handles formats:
      '6:30 AM  Wake'              -> point event (30 min default)
      '7:00–8:00 AM  App Work'     -> ranged event
      '8:00 AM–4:00 PM  Remote Work' -> ranged event crossing AM/PM
      '9:30 PM onward  ...'        -> point event
    """
    # Remove 'onward' for parsing
    cleaned = entry.replace(" onward", "")

    # Split on double-space to get time portion and activity
    parts = cleaned.split("  ", 1)
    if len(parts) != 2:
        return None
    time_part, activity = parts[0].strip(), parts[1].strip()

    # Range: "8:00 AM–4:00 PM" or "7:00–8:00 AM"
    # The dash can be – (en-dash) or - (hyphen)
    range_match = re.match(
        r"(\d{1,2}:\d{2})\s*(AM|PM)?\s*[–\-]\s*(\d{1,2}:\d{2})\s*(AM|PM)",
        time_part, re.IGNORECASE,
    )
    if range_match:
        start_raw = range_match.group(1)
        start_ampm = range_match.group(2)
        end_raw = range_match.group(3)
        end_ampm = range_match.group(4)
        # If start AM/PM missing, infer from end
        if not start_ampm:
            start_ampm = end_ampm
        start_h, start_m = parse_time(f"{start_raw} {start_ampm}")
        end_h, end_m = parse_time(f"{end_raw} {end_ampm}")
        return {"start": (start_h, start_m), "end": (end_h, end_m), "summary": activity}

    # Single time: "6:30 AM"
    single_match = re.match(r"(\d{1,2}:\d{2}\s*(?:AM|PM))", time_part, re.IGNORECASE)
    if single_match:
        start_h, start_m = parse_time(single_match.group(1))
        return {"start": (start_h, start_m), "end": None, "summary": activity}

    return None


def fmt_ics_time(ref_date: str, hour: int, minute: int) -> str:
    """Format as iCal local datetime string."""
    return f"{ref_date}T{hour:02d}{minute:02d}00"


def build_ics(profile_key: str, profile: dict) -> str:
    """Build an .ics file string for a single profile."""
    ref_date = PROFILE_REF_DATE[profile_key]
    rrule = PROFILE_RRULE[profile_key]
    cal_name = profile["label"]

    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//DayOS//Schedule Export//EN",
        "CALSCALE:GREGORIAN",
        f"X-WR-CALNAME:{cal_name}",
        "METHOD:PUBLISH",
    ]

    events = []
    for entry_str in profile["schedule"]:
        parsed = parse_schedule_entry(entry_str)
        if not parsed:
            continue
        events.append(parsed)

    # Assign end times: if an event has no end, use next event's start (or +30min)
    for i, ev in enumerate(events):
        if ev["end"] is None:
            if i + 1 < len(events):
                ev["end"] = events[i + 1]["start"]
            else:
                # Last event — default 30 min
                h, m = ev["start"]
                end_dt = datetime(2000, 1, 1, h, m) + timedelta(minutes=30)
                ev["end"] = (end_dt.hour, end_dt.minute)

    for ev in events:
        uid = str(uuid4())
        dtstart = fmt_ics_time(ref_date, *ev["start"])
        dtend = fmt_ics_time(ref_date, *ev["end"])

        lines += [
            "BEGIN:VEVENT",
            f"UID:{uid}",
            f"DTSTART;TZID=America/Chicago:{dtstart}",
            f"DTEND;TZID=America/Chicago:{dtend}",
            f"SUMMARY:{ev['summary']}",
            rrule,
            "END:VEVENT",
        ]

    lines.append("END:VCALENDAR")
    return "\r\n".join(lines) + "\r\n"


def main() -> None:
    out_dir = Path(__file__).parent / "calendars"
    out_dir.mkdir(exist_ok=True)

    for key, profile in SCHEDULE_PROFILES.items():
        ics_content = build_ics(key, profile)
        filename = f"{key}.ics"
        path = out_dir / filename
        path.write_text(ics_content)
        print(f"Exported: {path}")

    print(f"\nAll 6 calendars exported to {out_dir}/")
    print("Import each .ics file into Apple Calendar or Google Calendar as a separate calendar.")


if __name__ == "__main__":
    main()
