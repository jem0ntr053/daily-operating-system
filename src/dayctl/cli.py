"""CLI entry point and command handlers for dayctl."""

from __future__ import annotations

import argparse
from datetime import date, timedelta

from dayctl.models import DayPlan, NON_NEGOTIABLE_KEYS, SCHEDULE_PROFILES, score_plan, wake_time
from dayctl.storage import load_plan, save_plan, plan_path, list_days, today_str, load_config, save_config
from dayctl.display import print_plan, print_score_table, resolve_theme
from dayctl.themes import list_themes


# ---------------------------------------------------------------------------
# Date resolution
# ---------------------------------------------------------------------------

def resolve_date(raw: str | None) -> str | None:
    if raw is None:
        return None
    low = raw.lower()
    if low == "today":
        return date.today().isoformat()
    if low == "yesterday":
        return (date.today() - timedelta(days=1)).isoformat()
    return raw  # assume YYYY-MM-DD


DATE_HELP = "Date: YYYY-MM-DD, 'today', or 'yesterday'."


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
    sub = parser.add_subparsers(dest="command", required=True, title="commands", metavar="")

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

    # week
    p_week = sub.add_parser("week", help="Show scores for the past 7 days.")
    p_week.set_defaults(func=cmd_week)

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
    args.func(args)


if __name__ == "__main__":
    main()
