"""Hex color themes for the web UI.

Keys must match dayctl.themes.THEMES — validated at import time.
"""

from __future__ import annotations

WEB_THEMES: dict[str, dict[str, str]] = {
    "dracula": {
        "bg": "#282a36",
        "surface": "#44475a",
        "fg": "#f8f8f2",
        "green": "#50fa7b",
        "red": "#ff5555",
        "yellow": "#f1fa8c",
        "cyan": "#8be9fd",
        "purple": "#bd93f9",
        "orange": "#ffb86c",
        "pink": "#ff79c6",
        "accent": "#bd93f9",
        "heading": "#8be9fd",
        "muted": "#6272a4",
    },
    "catppuccin": {
        "bg": "#24273a",
        "surface": "#363a4f",
        "fg": "#cad3f5",
        "green": "#a6da95",
        "red": "#ed8796",
        "yellow": "#eed49f",
        "cyan": "#8bd5ca",
        "purple": "#c6a0f6",
        "orange": "#f5a97f",
        "pink": "#f5bde6",
        "accent": "#c6a0f6",
        "heading": "#8bd5ca",
        "muted": "#6e7391",
    },
    "gruvbox": {
        "bg": "#282828",
        "surface": "#3c3836",
        "fg": "#ebdbb2",
        "green": "#b8bb26",
        "red": "#fb4934",
        "yellow": "#fabd2f",
        "cyan": "#83a598",
        "purple": "#d3869b",
        "orange": "#fe8019",
        "pink": "#d3869b",
        "accent": "#fabd2f",
        "heading": "#83a598",
        "muted": "#928374",
    },
    "nord": {
        "bg": "#2e3440",
        "surface": "#3b4252",
        "fg": "#eceff4",
        "green": "#a3be8c",
        "red": "#bf616a",
        "yellow": "#ebcb8b",
        "cyan": "#88c0d0",
        "purple": "#b48ead",
        "orange": "#d08770",
        "pink": "#b48ead",
        "accent": "#88c0d0",
        "heading": "#81a1c1",
        "muted": "#4c566a",
    },
    "mono": {
        "bg": "#1a1a1a",
        "surface": "#2a2a2a",
        "fg": "#d4d4d4",
        "green": "#6a9955",
        "red": "#d16969",
        "yellow": "#dcdcaa",
        "cyan": "#9cdcfe",
        "purple": "#c586c0",
        "orange": "#ce9178",
        "pink": "#c586c0",
        "accent": "#9cdcfe",
        "heading": "#d4d4d4",
        "muted": "#808080",
    },
}

DEFAULT_WEB_THEME = "dracula"


def _validate_theme_keys() -> None:
    from dayctl.themes import THEMES
    cli_keys = set(THEMES.keys())
    web_keys = set(WEB_THEMES.keys())
    if cli_keys != web_keys:
        missing_web = cli_keys - web_keys
        missing_cli = web_keys - cli_keys
        parts = []
        if missing_web:
            parts.append(f"missing from web: {missing_web}")
        if missing_cli:
            parts.append(f"missing from CLI: {missing_cli}")
        raise AssertionError(f"Theme registries out of sync: {'; '.join(parts)}")


_validate_theme_keys()
