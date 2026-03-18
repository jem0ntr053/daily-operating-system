"""Tests for dayctl.display."""

from dayctl.display import render_checkbox, render_tasks, _supports_color


def test_render_checkbox_plain(monkeypatch):
    monkeypatch.setenv("NO_COLOR", "1")
    assert render_checkbox(True) == "[x]"
    assert render_checkbox(False) == "[ ]"


def test_render_tasks_plain(monkeypatch):
    monkeypatch.setenv("NO_COLOR", "1")
    tasks = [
        {"task": "First", "done": True},
        {"task": "Second", "done": False},
    ]
    output = render_tasks(tasks)
    assert "1. [x] First" in output
    assert "2. [ ] Second" in output


def test_no_color_env(monkeypatch):
    monkeypatch.setenv("NO_COLOR", "1")
    assert not _supports_color()


def test_supports_color_non_tty(monkeypatch):
    monkeypatch.delenv("NO_COLOR", raising=False)
    # In tests, stdout is not a tty
    assert not _supports_color()
