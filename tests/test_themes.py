"""Tests for dayctl.themes."""

from dayctl.themes import get_theme, list_themes, THEMES, DEFAULT_THEME


def test_list_themes():
    names = list_themes()
    assert "dracula" in names
    assert "catppuccin" in names
    assert "gruvbox" in names
    assert "nord" in names
    assert "mono" in names


def test_default_theme():
    t = get_theme(None)
    assert t == THEMES[DEFAULT_THEME]


def test_get_theme_by_name():
    t = get_theme("nord")
    assert t == THEMES["nord"]


def test_get_theme_fallback():
    t = get_theme("nonexistent")
    assert t == THEMES[DEFAULT_THEME]


def test_theme_has_all_roles():
    roles = {"green", "red", "yellow", "cyan", "purple", "orange", "pink", "accent", "heading", "muted"}
    for name, theme in THEMES.items():
        assert set(theme.keys()) == roles, f"Theme '{name}' missing roles"
