"""Tests for dayctl.display."""

from dayctl.display import render_checkbox, render_check, _supports_color, _visible_len


def test_render_checkbox_plain(monkeypatch):
    monkeypatch.setenv("NO_COLOR", "1")
    assert render_checkbox(True) == "[x]"
    assert render_checkbox(False) == "[ ]"


def test_render_check_plain(monkeypatch):
    monkeypatch.setenv("NO_COLOR", "1")
    text, length = render_check(True)
    assert text == "✓"
    assert length == 1
    text, length = render_check(False)
    assert text == "✗"
    assert length == 1


def test_no_color_env(monkeypatch):
    monkeypatch.setenv("NO_COLOR", "1")
    assert not _supports_color()


def test_supports_color_non_tty(monkeypatch):
    monkeypatch.delenv("NO_COLOR", raising=False)
    # In tests, stdout is not a tty
    assert not _supports_color()


def test_visible_len_plain():
    assert _visible_len("hello") == 5


def test_visible_len_strips_ansi():
    assert _visible_len("\033[32mhello\033[0m") == 5
    assert _visible_len("\033[38;2;80;250;123mhi\033[0m") == 2
