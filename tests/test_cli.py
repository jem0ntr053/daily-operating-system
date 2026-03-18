"""Tests for dayctl.cli."""

import sys
from datetime import date, timedelta
from io import StringIO

from dayctl.cli import resolve_date, main
from dayctl.storage import load_plan, plan_path
from dayctl.models import score_plan


def _run(day_env, args: list[str], monkeypatch) -> str:
    """Run CLI with args and capture stdout."""
    monkeypatch.setattr(sys, "argv", ["dayctl"] + args)
    buf = StringIO()
    monkeypatch.setattr(sys, "stdout", buf)
    main()
    return buf.getvalue()


# ---------------------------------------------------------------------------
# resolve_date
# ---------------------------------------------------------------------------

def test_resolve_date_none():
    assert resolve_date(None) is None


def test_resolve_date_today():
    assert resolve_date("today") == date.today().isoformat()


def test_resolve_date_yesterday():
    assert resolve_date("yesterday") == (date.today() - timedelta(days=1)).isoformat()


def test_resolve_date_passthrough():
    assert resolve_date("2026-03-17") == "2026-03-17"


# ---------------------------------------------------------------------------
# init / show / check / uncheck / note / score
# ---------------------------------------------------------------------------

def test_init_and_show(day_env, monkeypatch):
    out = _run(day_env, ["init", "--date", "2026-03-17"], monkeypatch)
    assert "Created" in out
    out = _run(day_env, ["show", "--date", "2026-03-17"], monkeypatch)
    assert "2026-03-17" in out


def test_check_and_uncheck(day_env, monkeypatch):
    _run(day_env, ["init", "--date", "2026-03-17"], monkeypatch)
    _run(day_env, ["check", "gym", "--date", "2026-03-17"], monkeypatch)
    plan = load_plan("2026-03-17")
    assert plan.completed["gym"] is True

    _run(day_env, ["uncheck", "gym", "--date", "2026-03-17"], monkeypatch)
    plan = load_plan("2026-03-17")
    assert plan.completed["gym"] is False


def test_note(day_env, monkeypatch):
    _run(day_env, ["init", "--date", "2026-03-17"], monkeypatch)
    _run(day_env, ["note", "Felt great", "--date", "2026-03-17"], monkeypatch)
    plan = load_plan("2026-03-17")
    assert "Felt great" in plan.notes


def test_score(day_env, monkeypatch):
    _run(day_env, ["init", "--date", "2026-03-17"], monkeypatch)
    out = _run(day_env, ["score", "--date", "2026-03-17"], monkeypatch)
    assert "0 / 4" in out


# ---------------------------------------------------------------------------
# set
# ---------------------------------------------------------------------------

def test_set_focus(day_env, monkeypatch):
    _run(day_env, ["init", "--date", "2026-03-17"], monkeypatch)
    out = _run(day_env, ["set", "focus", "Deep work", "--date", "2026-03-17"], monkeypatch)
    assert "Set focus" in out
    plan = load_plan("2026-03-17")
    assert plan.focus == "Deep work"


def test_set_energy(day_env, monkeypatch):
    _run(day_env, ["init", "--date", "2026-03-17"], monkeypatch)
    _run(day_env, ["set", "energy", "high", "--date", "2026-03-17"], monkeypatch)
    plan = load_plan("2026-03-17")
    assert plan.energy == "high"


def test_set_sleep(day_env, monkeypatch):
    _run(day_env, ["init", "--date", "2026-03-17"], monkeypatch)
    _run(day_env, ["set", "sleep", "7.5", "--date", "2026-03-17"], monkeypatch)
    plan = load_plan("2026-03-17")
    assert plan.sleep_hours == "7.5"


# ---------------------------------------------------------------------------
# task
# ---------------------------------------------------------------------------

def test_task_add(day_env, monkeypatch):
    _run(day_env, ["init", "--date", "2026-03-17"], monkeypatch)
    out = _run(day_env, ["task", "app", "add", "Ship login", "--date", "2026-03-17"], monkeypatch)
    assert "Added task #3" in out
    plan = load_plan("2026-03-17")
    assert plan.app_tasks[-1]["task"] == "Ship login"
    assert plan.app_tasks[-1]["done"] is False


def test_task_done_and_undo(day_env, monkeypatch):
    _run(day_env, ["init", "--date", "2026-03-17"], monkeypatch)
    _run(day_env, ["task", "app", "1", "done", "--date", "2026-03-17"], monkeypatch)
    plan = load_plan("2026-03-17")
    assert plan.app_tasks[0]["done"] is True

    _run(day_env, ["task", "app", "1", "undo", "--date", "2026-03-17"], monkeypatch)
    plan = load_plan("2026-03-17")
    assert plan.app_tasks[0]["done"] is False


# ---------------------------------------------------------------------------
# app / music shortcuts
# ---------------------------------------------------------------------------

def test_app_shortcut_add(day_env, monkeypatch):
    _run(day_env, ["init", "--date", "2026-03-17"], monkeypatch)
    out = _run(day_env, ["app", "add", "Ship login", "--date", "2026-03-17"], monkeypatch)
    assert "Added task #3" in out
    plan = load_plan("2026-03-17")
    assert plan.app_tasks[-1]["task"] == "Ship login"


def test_app_shortcut_done_and_undo(day_env, monkeypatch):
    _run(day_env, ["init", "--date", "2026-03-17"], monkeypatch)
    _run(day_env, ["app", "1", "done", "--date", "2026-03-17"], monkeypatch)
    plan = load_plan("2026-03-17")
    assert plan.app_tasks[0]["done"] is True

    _run(day_env, ["app", "1", "undo", "--date", "2026-03-17"], monkeypatch)
    plan = load_plan("2026-03-17")
    assert plan.app_tasks[0]["done"] is False


def test_music_shortcut(day_env, monkeypatch):
    _run(day_env, ["init", "--date", "2026-03-17"], monkeypatch)
    _run(day_env, ["music", "add", "Mix verse 2", "--date", "2026-03-17"], monkeypatch)
    plan = load_plan("2026-03-17")
    assert plan.music_tasks[-1]["task"] == "Mix verse 2"

    _run(day_env, ["music", "1", "done", "--date", "2026-03-17"], monkeypatch)
    plan = load_plan("2026-03-17")
    assert plan.music_tasks[0]["done"] is True


# ---------------------------------------------------------------------------
# week / history / summary
# ---------------------------------------------------------------------------

def test_week(day_env, monkeypatch):
    today = date.today().isoformat()
    _run(day_env, ["init", "--date", today], monkeypatch)
    out = _run(day_env, ["week"], monkeypatch)
    assert today in out
    assert "DATE" in out


def test_history_empty(day_env, monkeypatch):
    out = _run(day_env, ["history"], monkeypatch)
    assert "No history" in out


def test_history_with_data(day_env, monkeypatch):
    _run(day_env, ["init", "--date", "2026-01-01"], monkeypatch)
    _run(day_env, ["init", "--date", "2026-01-02"], monkeypatch)
    out = _run(day_env, ["history"], monkeypatch)
    assert "2026-01-01" in out
    assert "2026-01-02" in out


def test_summary(day_env, monkeypatch):
    today = date.today().isoformat()
    _run(day_env, ["init", "--date", today], monkeypatch)
    out = _run(day_env, ["summary"], monkeypatch)
    assert today in out


# ---------------------------------------------------------------------------
# yesterday alias
# ---------------------------------------------------------------------------

def test_yesterday_alias(day_env, monkeypatch):
    yesterday = (date.today() - timedelta(days=1)).isoformat()
    _run(day_env, ["init", "--date", "yesterday"], monkeypatch)
    plan = load_plan(yesterday)
    assert plan.day == yesterday
