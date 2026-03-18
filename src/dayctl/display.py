"""Terminal display and ANSI color support for dayctl."""

from __future__ import annotations

import os
import sys
from typing import List, Dict

from dayctl.models import DayPlan, NON_NEGOTIABLE_KEYS, SCHEDULE_PROFILES, profile_for_date, score_plan


# ---------------------------------------------------------------------------
# ANSI helpers
# ---------------------------------------------------------------------------

class Color:
    GREEN = "\033[32m"
    RED = "\033[31m"
    YELLOW = "\033[33m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    RESET = "\033[0m"
    CYAN = "\033[36m"
    BG_DIM = "\033[48;5;236m"


def _supports_color() -> bool:
    if os.environ.get("NO_COLOR"):
        return False
    if not hasattr(sys.stdout, "isatty"):
        return False
    return sys.stdout.isatty()


def _c(code: str, text: str) -> str:
    if _supports_color():
        return f"{code}{text}{Color.RESET}"
    return text


# ---------------------------------------------------------------------------
# Rendering helpers
# ---------------------------------------------------------------------------

def render_checkbox(value: bool) -> str:
    if value:
        return _c(Color.GREEN, "[x]")
    return _c(Color.RED, "[ ]")


def render_tasks(tasks: List[Dict[str, bool | str]]) -> str:
    lines = []
    for idx, item in enumerate(tasks, start=1):
        cb = render_checkbox(bool(item["done"]))
        lines.append(f"  {idx}. {cb} {item['task']}")
    return "\n".join(lines)


def _score_bar(score: int, max_score: int = 4) -> str:
    filled = "█" * score
    empty = "░" * (max_score - score)
    if score == max_score:
        return _c(Color.GREEN, filled + empty)
    elif score >= max_score // 2:
        return _c(Color.YELLOW, filled) + _c(Color.DIM, empty)
    else:
        return _c(Color.RED, filled) + _c(Color.DIM, empty)


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
    header = f"DAY: {plan.day}"
    print(f"\n{_c(Color.BOLD, header)}")
    print("=" * len(header))
    label = _detect_profile_label(plan)
    print(f"Profile: {_c(Color.CYAN, label)}")
    print(f"Focus: {plan.focus or _c(Color.DIM, '-')}")
    print(f"Energy: {plan.energy or _c(Color.DIM, '-')}")
    print(f"Sleep: {plan.sleep_hours or _c(Color.DIM, '-')}")
    print(f"Fasting Window: {plan.fasting_window}")

    print(f"\n{_c(Color.BOLD, 'NON-NEGOTIABLES')}")
    for key in NON_NEGOTIABLE_KEYS:
        print(f"  {render_checkbox(plan.completed[key])} {key.upper()}")

    print(f"\n{_c(Color.BOLD, 'SCHEDULE')}")
    for item in plan.schedule:
        print(f"  - {item}")

    print(f"\n{_c(Color.BOLD, 'APP TASKS')}")
    print(render_tasks(plan.app_tasks))

    print(f"\n{_c(Color.BOLD, 'MUSIC TASKS')}")
    print(render_tasks(plan.music_tasks))

    print(f"\n{_c(Color.BOLD, 'NOTES')}")
    if plan.notes:
        for n in plan.notes:
            print(f"  - {n}")
    else:
        print(f"  {_c(Color.DIM, '-')}")

    s = score_plan(plan)
    print(f"\n{_c(Color.BOLD, 'SCORE')}: {_score_bar(s)} {s} / 4\n")


# ---------------------------------------------------------------------------
# Score tables (week / history / summary)
# ---------------------------------------------------------------------------

def print_score_table(
    rows: list[tuple[str, int | None]],
    highlight: str | None = None,
) -> None:
    if not rows:
        print(_c(Color.DIM, "No data."))
        return

    print(f"\n{'DATE':<14} {'SCORE':<8} {'':>4}")
    print("-" * 28)

    total, count = 0, 0
    for day_str, score in rows:
        is_hl = highlight and day_str == highlight
        if score is None:
            row = f"{day_str:<14} {_c(Color.DIM, '  -')}"
        else:
            bar = _score_bar(score)
            row = f"{day_str:<14} {bar} {score}/4"
            total += score
            count += 1

        if is_hl:
            row = _c(Color.CYAN, "▸ ") + row
        else:
            row = "  " + row
        print(row)

    print("-" * 28)
    if count:
        avg = total / count
        print(f"  {'Average':<14} {avg:.1f}/4")
    print()
