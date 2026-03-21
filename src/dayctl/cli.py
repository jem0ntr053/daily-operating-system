"""CLI entry point and command handlers for dayctl."""

from __future__ import annotations

import argparse
from datetime import date, timedelta

from dayctl.models import (
    DayPlan, NON_NEGOTIABLE_KEYS, SCHEDULE_PROFILES, SHOW_TOGGLE,
    score_plan, wake_time, compute_streak, carry_forward,
)
from dayctl.storage import load_plan, save_plan, plan_path, list_days, today_str, load_config, save_config
from dayctl.display import print_plan, print_score_table, resolve_theme
from dayctl.themes import list_themes


# ---------------------------------------------------------------------------
# Date resolution
# ---------------------------------------------------------------------------

_DAY_NAMES = {
    "monday": 0, "tuesday": 1, "wednesday": 2, "thursday": 3,
    "friday": 4, "saturday": 5, "sunday": 6,
    "mon": 0, "tue": 1, "wed": 2, "thu": 3,
    "fri": 4, "sat": 5, "sun": 6,
}


def resolve_date(raw: str | None) -> str | None:
    if raw is None:
        return None
    low = raw.lower()
    if low == "today":
        return date.today().isoformat()
    if low == "yesterday":
        return (date.today() - timedelta(days=1)).isoformat()
    # Relative offset: -1, -2, etc.
    if low.startswith("-") and low[1:].isdigit():
        return (date.today() - timedelta(days=int(low[1:]))).isoformat()
    # Day name: monday, tue, etc. — most recent occurrence
    if low in _DAY_NAMES:
        target_dow = _DAY_NAMES[low]
        today = date.today()
        diff = (today.weekday() - target_dow) % 7
        if diff == 0:
            diff = 0  # same day = today
        return (today - timedelta(days=diff)).isoformat()
    return raw  # assume YYYY-MM-DD


DATE_HELP = "Date: YYYY-MM-DD, 'today', 'yesterday', day name (mon-sunday), or -N (days ago)."


# ---------------------------------------------------------------------------
# Existing commands
# ---------------------------------------------------------------------------

def cmd_init(args: argparse.Namespace) -> None:
    ds = resolve_date(args.date) or today_str()
    path = plan_path(ds)
    if path.exists() and not args.force:
        print(f"Plan already exists: {path}")
        print("Use --force to overwrite.")
        return
    profile_key = getattr(args, "profile", None)
    plan = DayPlan.new(ds, profile_key=profile_key)

    # Carry forward incomplete tasks from yesterday
    yesterday = (date.fromisoformat(ds) - timedelta(days=1)).isoformat()
    if plan_path(yesterday).exists():
        prev = load_plan(yesterday)
        carried = carry_forward(plan, prev)
        if carried:
            print(f"Carried forward {len(carried)} task(s) from yesterday:")
            for desc in carried:
                print(f"  + {desc}")

    save_plan(plan)
    print(f"Created: {path} ({wake_time(plan)} wake)")


def cmd_show(args: argparse.Namespace) -> None:
    config = load_config()
    plan = load_plan(resolve_date(args.date))
    print_plan(plan, theme=resolve_theme(config.get("theme")))


def _set_completed(args: argparse.Namespace, value: bool) -> None:
    plan = load_plan(resolve_date(args.date))
    key = args.item.lower()
    if key not in NON_NEGOTIABLE_KEYS:
        raise SystemExit(f"Invalid item '{args.item}'. Use one of: {', '.join(NON_NEGOTIABLE_KEYS)}")
    plan.completed[key] = value
    save_plan(plan)
    print(f"{'Checked' if value else 'Unchecked'}: {key}")


def cmd_check(args: argparse.Namespace) -> None:
    _set_completed(args, True)


def cmd_uncheck(args: argparse.Namespace) -> None:
    _set_completed(args, False)


def cmd_note(args: argparse.Namespace) -> None:
    plan = load_plan(resolve_date(args.date))
    plan.notes.append(args.text)
    save_plan(plan)
    print("Note added.")


def cmd_score(args: argparse.Namespace) -> None:
    plan = load_plan(resolve_date(args.date))
    print(f"{plan.day} score: {score_plan(plan)} / 4")


# ---------------------------------------------------------------------------
# New: set
# ---------------------------------------------------------------------------

SETTABLE_FIELDS = {
    "focus": "focus",
    "energy": "energy",
    "sleep": "sleep_hours",
}


def cmd_set(args: argparse.Namespace) -> None:
    plan = load_plan(resolve_date(args.date))
    attr = SETTABLE_FIELDS[args.field]
    setattr(plan, attr, args.value)
    save_plan(plan)
    print(f"Set {args.field} = {args.value}")


# ---------------------------------------------------------------------------
# New: task
# ---------------------------------------------------------------------------

TASK_LIST_ATTR = {"app": "app_tasks", "music": "music_tasks"}


def _task_add(tasks: list, plan: DayPlan, category: str, value: str | None) -> None:
    if not value:
        raise SystemExit("Usage: dayctl task <category> add <description>")
    tasks.append({"task": value, "done": False})
    save_plan(plan)
    print(f"Added task #{len(tasks)} to {category}")


def _task_edit(tasks: list, plan: DayPlan, category: str, idx: int, num: str, value: str) -> None:
    tasks[idx]["task"] = value
    save_plan(plan)
    print(f"Updated: {category} task #{num}")


def _task_toggle(tasks: list, plan: DayPlan, category: str, idx: int, num: str, value: str) -> None:
    tasks[idx]["done"] = (value == "done")
    save_plan(plan)
    verb = "Completed" if value == "done" else "Unchecked"
    print(f"{verb}: {category} task #{num}")


def cmd_task(args: argparse.Namespace) -> None:
    plan = load_plan(resolve_date(args.date))
    tasks: list = getattr(plan, TASK_LIST_ATTR[args.category])

    action = args.action_or_index
    value = args.value

    if action == "add":
        _task_add(tasks, plan, args.category, value)
        return

    try:
        idx = int(action) - 1
    except ValueError:
        raise SystemExit(f"Unknown action '{action}'. Use 'add', or a task number with 'done'/'undo'.")

    if idx < 0 or idx >= len(tasks):
        raise SystemExit(f"Task #{action} out of range (1-{len(tasks)})")

    if not value:
        raise SystemExit(f"Usage: dayctl task {args.category} {action} done|undo|\"new text\"")

    if value not in ("done", "undo"):
        _task_edit(tasks, plan, args.category, idx, action, value)
    else:
        _task_toggle(tasks, plan, args.category, idx, action, value)


# ---------------------------------------------------------------------------
# New: week
# ---------------------------------------------------------------------------

def cmd_week(args: argparse.Namespace) -> None:
    t = resolve_theme(load_config().get("theme"))
    today = date.today()
    days = [(today - timedelta(days=i)).isoformat() for i in range(6, -1, -1)]
    rows: list[tuple[str, int | None]] = []
    for d in days:
        if plan_path(d).exists():
            plan = load_plan(d)
            rows.append((d, score_plan(plan)))
        else:
            rows.append((d, None))
    print_score_table(rows, highlight=today.isoformat(), theme=t)


# ---------------------------------------------------------------------------
# New: history
# ---------------------------------------------------------------------------

def cmd_history(args: argparse.Namespace) -> None:
    all_days = list_days()
    if not all_days:
        print("No history yet.")
        return
    t = resolve_theme(load_config().get("theme"))
    rows: list[tuple[str, int | None]] = []
    for d in all_days:
        plan = load_plan(d)
        rows.append((d, score_plan(plan)))
    print_score_table(rows, theme=t)


# ---------------------------------------------------------------------------
# New: summary (current ISO week Mon–Sun)
# ---------------------------------------------------------------------------

def cmd_summary(args: argparse.Namespace) -> None:
    t = resolve_theme(load_config().get("theme"))
    today = date.today()
    monday = today - timedelta(days=today.weekday())
    days = [(monday + timedelta(days=i)).isoformat() for i in range(7)]
    rows: list[tuple[str, int | None]] = []
    for d in days:
        if plan_path(d).exists():
            plan = load_plan(d)
            rows.append((d, score_plan(plan)))
        else:
            rows.append((d, None))
    print_score_table(rows, highlight=today.isoformat(), theme=t)


# ---------------------------------------------------------------------------
# New: tonight (show/no-show profile toggle)
# ---------------------------------------------------------------------------

def cmd_tonight(args: argparse.Namespace) -> None:
    ds = resolve_date(args.date) or today_str()
    plan = load_plan(ds)

    if plan.profile not in SHOW_TOGGLE:
        raise SystemExit(
            f"Profile '{plan.profile}' has no show toggle. "
            f"Only available on Friday and Saturday."
        )

    mode = getattr(args, "mode", None)
    if mode == "show":
        target = "friday_show" if "friday" in plan.profile else "saturday_show"
    elif mode == "off":
        target = "friday" if "friday" in plan.profile else "saturday_no_show"
    else:
        # Toggle
        target = SHOW_TOGGLE[plan.profile]

    if target == plan.profile:
        print(f"Already on {SCHEDULE_PROFILES[plan.profile]['label']}.")
        return

    plan.switch_profile(target)
    save_plan(plan)
    print(f"Switched to {SCHEDULE_PROFILES[target]['label']}.")


# ---------------------------------------------------------------------------
# New: streak
# ---------------------------------------------------------------------------

def cmd_streak(args: argparse.Namespace) -> None:
    all_days = list_days()
    if not all_days:
        print("No history yet.")
        return

    day_scores = []
    for d in all_days:
        plan = load_plan(d)
        day_scores.append((d, score_plan(plan)))

    threshold = getattr(args, "threshold", 3)
    streak = compute_streak(day_scores, threshold=threshold)

    if streak == 0:
        print(f"No active streak (threshold: {threshold}/4).")
    else:
        print(f"Current streak: {streak} day{'s' if streak != 1 else ''} (>= {threshold}/4)")


# ---------------------------------------------------------------------------
# New: config
# ---------------------------------------------------------------------------

def cmd_config(args: argparse.Namespace) -> None:
    config = load_config()
    key = args.key
    value = args.value

    if key == "theme":
        available = list_themes()
        if value is None:
            current = config.get("theme", "dracula")
            print(f"Current theme: {current}")
            print(f"Available: {', '.join(available)}")
            return
        if value.lower() not in available:
            raise SystemExit(f"Unknown theme '{value}'. Available: {', '.join(available)}")
        config["theme"] = value.lower()
        save_config(config)
        print(f"Theme set to: {value.lower()}")
    else:
        raise SystemExit(f"Unknown config key '{key}'. Available: theme")


# ---------------------------------------------------------------------------
# Parser
# ---------------------------------------------------------------------------

EPILOG = """\
automation:
  Auto-init runs daily at 6:00 AM via launchd (com.dayos.autoinit).
  Schedule notifications fire 5 min before each block (com.dayos.notify).

  Install agents:
    cp scripts/com.dayos.*.plist ~/Library/LaunchAgents/
    launchctl load ~/Library/LaunchAgents/com.dayos.autoinit.plist
    launchctl load ~/Library/LaunchAgents/com.dayos.notify.plist

  Pause/resume notifications:
    launchctl unload ~/Library/LaunchAgents/com.dayos.notify.plist
    launchctl load  ~/Library/LaunchAgents/com.dayos.notify.plist

  Logs: /tmp/dayos-autoinit.log, /tmp/dayos-notify.log

calendar export:
  python export_calendars.py    # generates .ics files in calendars/
"""


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Minimal daily operating system CLI.",
        epilog=EPILOG,
        formatter_class=argparse.RawDescriptionHelpFormatter,
        usage="day <command> [options]",
    )
    sub = parser.add_subparsers(dest="command", title="commands", metavar="")

    # init
    p_init = sub.add_parser("init", help="Create today's plan file.")
    p_init.add_argument("--date", help=DATE_HELP)
    p_init.add_argument("--force", action="store_true", help="Overwrite existing file.")
    p_init.add_argument(
        "--profile",
        choices=list(SCHEDULE_PROFILES),
        help="Schedule profile override (e.g. saturday_show). Auto-detected from day of week if omitted.",
    )
    p_init.set_defaults(func=cmd_init)

    # show
    p_show = sub.add_parser("show", help="Show today's plan.")
    p_show.add_argument("--date", help=DATE_HELP)
    p_show.set_defaults(func=cmd_show)

    # check
    p_check = sub.add_parser("check", help="Mark a non-negotiable complete.")
    p_check.add_argument("item", help="One of: fast, gym, app, music")
    p_check.add_argument("--date", help=DATE_HELP)
    p_check.set_defaults(func=cmd_check)

    # uncheck
    p_uncheck = sub.add_parser("uncheck", help="Mark a non-negotiable incomplete.")
    p_uncheck.add_argument("item", help="One of: fast, gym, app, music")
    p_uncheck.add_argument("--date", help=DATE_HELP)
    p_uncheck.set_defaults(func=cmd_uncheck)

    # note
    p_note = sub.add_parser("note", help="Add a note to today's plan.")
    p_note.add_argument("text", help="Note text")
    p_note.add_argument("--date", help=DATE_HELP)
    p_note.set_defaults(func=cmd_note)

    # score
    p_score = sub.add_parser("score", help="Show today's score.")
    p_score.add_argument("--date", help=DATE_HELP)
    p_score.set_defaults(func=cmd_score)

    # set
    p_set = sub.add_parser("set", help="Set a plan field (focus, energy, sleep).")
    p_set.add_argument("field", choices=list(SETTABLE_FIELDS), help="Field to set")
    p_set.add_argument("value", help="Value to set")
    p_set.add_argument("--date", help=DATE_HELP)
    p_set.set_defaults(func=cmd_set)

    # task (legacy: dayctl task app 2 done)
    p_task = sub.add_parser("task", help="Manage app/music tasks.")
    p_task.add_argument("category", choices=["app", "music"], help="Task category")
    p_task.add_argument("action_or_index", help="'add' or task number (1-based)")
    p_task.add_argument("value", nargs="?", default=None, help="Task text (for add) or done/undo")
    p_task.add_argument("--date", help=DATE_HELP)
    p_task.set_defaults(func=cmd_task)

    # app / music shortcuts (dayctl app 2 done, dayctl music add "Mix verse")
    for category in ("app", "music"):
        p = sub.add_parser(category, help=f"Manage {category} tasks.")
        p.add_argument("action_or_index", help="'add' or task number (1-based)")
        p.add_argument("value", nargs="?", default=None, help="Task text (for add) or done/undo")
        p.add_argument("--date", help=DATE_HELP)
        p.set_defaults(func=cmd_task, category=category)

    # tonight
    p_tonight = sub.add_parser("tonight", help="Toggle show/no-show profile (Fri & Sat).")
    p_tonight.add_argument(
        "mode", nargs="?", choices=["show", "off"], default=None,
        help="Force 'show' or 'off'. Omit to toggle.",
    )
    p_tonight.add_argument("--date", help=DATE_HELP)
    p_tonight.set_defaults(func=cmd_tonight)

    # week
    p_week = sub.add_parser("week", help="Show scores for the past 7 days.")
    p_week.set_defaults(func=cmd_week)

    # streak
    p_streak = sub.add_parser("streak", help="Show current streak (consecutive days >= threshold).")
    p_streak.add_argument("--threshold", type=int, default=3, help="Minimum score to count (default: 3).")
    p_streak.set_defaults(func=cmd_streak)

    # history
    p_history = sub.add_parser("history", help="Show scores across all tracked days.")
    p_history.set_defaults(func=cmd_history)

    # summary
    p_summary = sub.add_parser("summary", help="Current week at a glance (Mon–Sun).")
    p_summary.set_defaults(func=cmd_summary)

    # config
    p_config = sub.add_parser("config", help="View or change settings (e.g. theme).")
    p_config.add_argument("key", help="Config key (e.g. theme)")
    p_config.add_argument("value", nargs="?", default=None, help="Value to set (omit to view current)")
    p_config.set_defaults(func=cmd_config)

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    if args.command is None:
        # Default to 'show' when no subcommand given
        args = parser.parse_args(["show"])
    args.func(args)


if __name__ == "__main__":
    main()
