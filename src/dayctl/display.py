"""Terminal display and ANSI color support for dayctl."""

from __future__ import annotations

import os
import sys
from typing import List, Dict

from dayctl.models import DayPlan, NON_NEGOTIABLE_KEYS, SCHEDULE_PROFILES, profile_for_date, score_plan
from dayctl.themes import BOLD, DIM, RESET, get_theme
from dayctl.storage import load_config


# ---------------------------------------------------------------------------
# ANSI helpers
# ---------------------------------------------------------------------------

def _supports_color() -> bool:
    if os.environ.get("NO_COLOR"):
        return False
    if not hasattr(sys.stdout, "isatty"):
        return False
    return sys.stdout.isatty()


def _active_theme() -> dict[str, str]:
    """Load the user's configured theme."""
    config = load_config()
    return get_theme(config.get("theme"))


def _c(code: str, text: str) -> str:
    if _supports_color():
        return f"{code}{text}{RESET}"
    return text


# ---------------------------------------------------------------------------
# Rendering helpers
# ---------------------------------------------------------------------------

def render_checkbox(value: bool) -> str:
    t = _active_theme()
    if value:
        return _c(t["green"], "[x]")
    return _c(t["red"], "[ ]")


def render_tasks(tasks: List[Dict[str, bool | str]]) -> str:
    lines = []
    for idx, item in enumerate(tasks, start=1):
        cb = render_checkbox(bool(item["done"]))
        lines.append(f"  {idx}. {cb} {item['task']}")
    return "\n".join(lines)


def _score_bar(score: int, max_score: int = 4) -> str:
    t = _active_theme()
    filled = "█" * score
    empty = "░" * (max_score - score)
    if score == max_score:
        return _c(t["green"], filled + empty)
    elif score >= max_score // 2:
        return _c(t["yellow"], filled) + _c(t["muted"], empty)
    else:
        return _c(t["red"], filled) + _c(t["muted"], empty)


# ---------------------------------------------------------------------------
# Plan display
# ---------------------------------------------------------------------------

def _detect_profile_label(plan: DayPlan) -> str:
    """Match the plan's schedule to a profile and return its label."""
    for profile in SCHEDULE_PROFILES.values():
        if plan.schedule == profile["schedule"]:
            return profile["label"]
    return profile_for_date(plan.day)["label"]


def print_plan(plan: DayPlan) -> None:
    t = _active_theme()
    header = f"DAY: {plan.day}"
    print(f"\n{_c(BOLD, header)}")
    print(_c(t["muted"], "=" * len(header)))
    label = _detect_profile_label(plan)
    print(f"Profile: {_c(t['accent'], label)}")
    print(f"Focus: {plan.focus or _c(t['muted'], '-')}")
    print(f"Energy: {plan.energy or _c(t['muted'], '-')}")
    print(f"Sleep: {plan.sleep_hours or _c(t['muted'], '-')}")
    print(f"Fasting Window: {_c(t['orange'], plan.fasting_window)}")

    print(f"\n{_c(t['heading'], 'NON-NEGOTIABLES')}")
    for key in NON_NEGOTIABLE_KEYS:
        print(f"  {render_checkbox(plan.completed[key])} {key.upper()}")

    print(f"\n{_c(t['heading'], 'SCHEDULE')}")
    for item in plan.schedule:
        print(f"  {_c(t['muted'], '-')} {item}")

    print(f"\n{_c(t['heading'], 'APP TASKS')}")
    print(render_tasks(plan.app_tasks))

    print(f"\n{_c(t['heading'], 'MUSIC TASKS')}")
    print(render_tasks(plan.music_tasks))

    print(f"\n{_c(t['heading'], 'NOTES')}")
    if plan.notes:
        for n in plan.notes:
            print(f"  {_c(t['muted'], '-')} {n}")
    else:
        print(f"  {_c(t['muted'], '-')}")

    s = score_plan(plan)
    print(f"\n{_c(BOLD, 'SCORE')}: {_score_bar(s)} {s} / 4\n")


# ---------------------------------------------------------------------------
# Score tables (week / history / summary)
# ---------------------------------------------------------------------------

def print_score_table(
    rows: list[tuple[str, int | None]],
    highlight: str | None = None,
) -> None:
    t = _active_theme()

    if not rows:
        print(_c(t["muted"], "No data."))
        return

    print(f"\n{_c(t['heading'], 'DATE'):<28} {_c(t['heading'], 'SCORE'):<8}")
    print(_c(t["muted"], "-" * 28))

    total, count = 0, 0
    for day_str, score in rows:
        is_hl = highlight and day_str == highlight
        if score is None:
            row = f"{day_str:<14} {_c(t['muted'], '  -')}"
        else:
            bar = _score_bar(score)
            row = f"{day_str:<14} {bar} {score}/4"
            total += score
            count += 1

        if is_hl:
            row = _c(t["cyan"], "▸ ") + row
        else:
            row = "  " + row
        print(row)

    print(_c(t["muted"], "-" * 28))
    if count:
        avg = total / count
        print(f"  {_c(t['accent'], 'Average'):<28} {avg:.1f}/4")
    print()
