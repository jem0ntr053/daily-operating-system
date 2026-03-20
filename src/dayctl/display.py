"""Terminal display and ANSI color support for dayctl."""

from __future__ import annotations

import os
import re
import sys
import unicodedata
from datetime import date

from dayctl.models import DayPlan, NON_NEGOTIABLE_KEYS, SCHEDULE_PROFILES, profile_for_date, score_plan
from dayctl.themes import BOLD, RESET, get_theme


# ---------------------------------------------------------------------------
# ANSI helpers
# ---------------------------------------------------------------------------

def _supports_color() -> bool:
    if os.environ.get("NO_COLOR"):
        return False
    if not hasattr(sys.stdout, "isatty"):
        return False
    return sys.stdout.isatty()


def resolve_theme(theme_name: str | None = None) -> dict[str, str]:
    """Resolve a theme by name. Used by callers to pass theme into display functions."""
    return get_theme(theme_name)


def _c(code: str, text: str) -> str:
    if _supports_color():
        return f"{code}{text}{RESET}"
    return text


# ---------------------------------------------------------------------------
# Box-drawing helpers (all accept theme dict to avoid repeated I/O)
# ---------------------------------------------------------------------------

BOX_W = 55  # inner width (between │ walls)


def _visible_len(s: str) -> int:
    """Length of string without ANSI escape codes, accounting for wide Unicode."""
    stripped = re.sub(r"\033\[[0-9;]*m", "", s)
    width = 0
    for ch in stripped:
        eaw = unicodedata.east_asian_width(ch)
        width += 2 if eaw in ("W", "F") else 1
    return width


def _box_top(t: dict[str, str]) -> str:
    return _c(t["muted"], "┌" + "─" * BOX_W + "┐")


def _box_bot(t: dict[str, str]) -> str:
    return _c(t["muted"], "└" + "─" * BOX_W + "┘")


def _box_div(t: dict[str, str]) -> str:
    return _c(t["muted"], "├" + "─" * BOX_W + "┤")


def _box_row(t: dict[str, str], content: str) -> str:
    """Wrap content in box walls, padding to BOX_W."""
    raw_len = _visible_len(content)
    pad = BOX_W - 2 - raw_len  # -2 for leading/trailing space
    if pad < 0:
        pad = 0
    wall = _c(t["muted"], "│")
    return f"{wall} {content}{' ' * pad} {wall}"


# ---------------------------------------------------------------------------
# Rendering helpers
# ---------------------------------------------------------------------------

def _render_check(t: dict[str, str], value: bool) -> str:
    """Return themed ✓ or ✗."""
    if value:
        return _c(t["green"], "✓")
    return _c(t["red"], "✗")


def render_check(value: bool, theme: dict[str, str] | None = None) -> tuple[str, int]:
    """Public API: return (rendered string, raw length) for a check mark."""
    t = theme or resolve_theme()
    return _render_check(t, value), 1


def render_checkbox(value: bool, theme: dict[str, str] | None = None) -> str:
    """Legacy checkbox for non-box contexts."""
    t = theme or resolve_theme()
    if value:
        return _c(t["green"], "[x]")
    return _c(t["red"], "[ ]")


def _score_bar(t: dict[str, str], score: int, max_score: int = 4) -> str:
    filled = "●" * score
    empty = "·" * (max_score - score)
    if score == max_score:
        return _c(t["green"], filled + empty)
    elif score >= max_score // 2:
        return _c(t["yellow"], filled) + _c(t["muted"], empty)
    else:
        return _c(t["red"], filled) + _c(t["muted"], empty)


def _abbreviate_time(s: str) -> str:
    """Shorten time strings: '9:00 PM' → '9PM', '11:00 AM' → '11AM'."""
    return re.sub(r"(\d+):00\s*(AM|PM)", r"\1\2", s)


def _format_date_header(day_str: str) -> str:
    """Format as 'Tuesday, Mar 17'."""
    d = date.fromisoformat(day_str)
    return d.strftime("%A, %b %d").replace(" 0", " ")


# ---------------------------------------------------------------------------
# Plan display
# ---------------------------------------------------------------------------

def _get_profile_label(plan: DayPlan) -> str:
    """Return the label for the plan's stored profile key."""
    key = getattr(plan, "profile", None)
    if key and key in SCHEDULE_PROFILES:
        return SCHEDULE_PROFILES[key]["label"]
    return profile_for_date(plan.day)["label"]


def _two_col(t: dict[str, str], left: str, right: str) -> str:
    """Format two strings into a fixed-width row for the box."""
    inner = BOX_W - 2
    gap = inner - _visible_len(left) - _visible_len(right)
    if gap < 1:
        gap = 1
    content = left + " " * gap + right
    return _box_row(t, content)


def print_plan(plan: DayPlan, theme: dict[str, str] | None = None) -> None:
    t = theme or resolve_theme()
    s = score_plan(plan)
    label = _get_profile_label(plan)
    date_hdr = _format_date_header(plan.day)

    lines: list[str] = []

    # === Top border ===
    lines.append(_box_top(t))

    # === Header: date + profile ===
    lines.append(_two_col(t, _c(BOLD, date_hdr), _c(t["accent"], label)))

    # === Meta row 1: Focus + Sleep ===
    focus_val = plan.focus or _c(t["muted"], "–")
    sleep_val = f"Sleep: {plan.sleep_hours} hrs" if plan.sleep_hours else f"Sleep: {_c(t['muted'], '–')}"
    lines.append(_two_col(t, f"Focus: {focus_val}", sleep_val))

    # === Meta row 2: Energy + Fasting ===
    energy_val = plan.energy or _c(t["muted"], "–")
    fast_short = _abbreviate_time(plan.fasting_window)
    lines.append(_two_col(t, f"Energy: {energy_val}", f"Fasting: {_c(t['orange'], fast_short)}"))

    # === Divider ===
    lines.append(_box_div(t))

    # === Non-negotiables (inline row) ===
    nn_parts = []
    for key in NON_NEGOTIABLE_KEYS:
        mark = _render_check(t, plan.completed[key])
        nn_parts.append(f"{mark} {key.upper()}")
    bar = _score_bar(t, s)
    nn_parts.append(f"{bar} {s}/4")
    lines.append(_box_row(t, "   ".join(nn_parts)))

    # === Divider ===
    lines.append(_box_div(t))

    # === Schedule ===
    lines.append(_box_row(t, _c(t["heading"], "SCHEDULE")))
    for item in plan.schedule:
        parts = item.split("  ", 1)
        if len(parts) == 2:
            time_part, activity = parts
            entry = f"  {_c(t['muted'], time_part)}  {activity}"
        else:
            entry = f"  {item}"
        lines.append(_box_row(t, entry))

    # === Divider ===
    lines.append(_box_div(t))

    # === App Tasks ===
    lines.append(_box_row(t, _c(t["heading"], "APP TASKS")))
    for idx, item in enumerate(plan.app_tasks, start=1):
        mark = _render_check(t, bool(item["done"]))
        lines.append(_box_row(t, f"  {idx}. {mark} {item['task']}"))

    # === Divider ===
    lines.append(_box_div(t))

    # === Music Tasks ===
    lines.append(_box_row(t, _c(t["heading"], "MUSIC TASKS")))
    for idx, item in enumerate(plan.music_tasks, start=1):
        mark = _render_check(t, bool(item["done"]))
        lines.append(_box_row(t, f"  {idx}. {mark} {item['task']}"))

    # === Divider ===
    lines.append(_box_div(t))

    # === Notes ===
    lines.append(_box_row(t, _c(t["heading"], "NOTES")))
    if plan.notes:
        for n in plan.notes:
            lines.append(_box_row(t, f"  • {n}"))
    else:
        lines.append(_box_row(t, f"  {_c(t['muted'], '–')}"))

    # === Bottom border ===
    lines.append(_box_bot(t))

    print()
    print("\n".join(lines))
    print()


# ---------------------------------------------------------------------------
# Score tables (week / history / summary)
# ---------------------------------------------------------------------------

def _format_day_short(day_str: str) -> str:
    """Format as 'Mon 03/17'."""
    d = date.fromisoformat(day_str)
    return d.strftime("%a %m/%d")


def print_score_table(
    rows: list[tuple[str, int | None]],
    highlight: str | None = None,
    theme: dict[str, str] | None = None,
) -> None:
    t = theme or resolve_theme()

    if not rows:
        print(_c(t["muted"], "No data."))
        return

    lines: list[str] = []
    lines.append(_box_top(t))

    # Header
    lines.append(_two_col(t, _c(t["heading"], "DATE"), _c(t["heading"], "SCORE")))
    lines.append(_box_div(t))

    total, count = 0, 0
    for day_str, score in rows:
        is_hl = highlight and day_str == highlight
        day_label = _format_day_short(day_str)

        if score is None:
            right = _c(t["muted"], "  –")
        else:
            right = f"{_score_bar(t, score)} {score}/4"
            total += score
            count += 1

        if is_hl:
            left = f"{_c(t['cyan'], '▸')} {day_label}"
        else:
            left = f"  {day_label}"

        lines.append(_two_col(t, left, right))

    lines.append(_box_div(t))

    # Average
    if count:
        avg = total / count
        lines.append(_two_col(t, f"  {_c(t['accent'], 'Average')}", f"{avg:.1f}/4"))

    lines.append(_box_bot(t))

    print()
    print("\n".join(lines))
    print()
