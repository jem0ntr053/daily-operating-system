"""Color themes for dayctl terminal output."""

from __future__ import annotations


def _rgb(r: int, g: int, b: int) -> str:
    """ANSI 24-bit foreground color."""
    return f"\033[38;2;{r};{g};{b}m"


RESET = "\033[0m"
BOLD = "\033[1m"
DIM = "\033[2m"

# Each theme maps semantic roles to ANSI escape codes.
# Roles: green, red, yellow, cyan, purple, orange, pink, accent, heading, muted
THEMES: dict[str, dict[str, str]] = {
    "dracula": {
        "green": _rgb(80, 250, 123),
        "red": _rgb(255, 85, 85),
        "yellow": _rgb(241, 250, 140),
        "cyan": _rgb(139, 233, 253),
        "purple": _rgb(189, 147, 249),
        "orange": _rgb(255, 184, 108),
        "pink": _rgb(255, 121, 198),
        "accent": _rgb(189, 147, 249),     # purple
        "heading": _rgb(139, 233, 253),     # cyan
        "muted": _rgb(98, 114, 164),        # comment gray
    },
    "catppuccin": {
        "green": _rgb(166, 218, 149),
        "red": _rgb(237, 135, 150),
        "yellow": _rgb(238, 212, 159),
        "cyan": _rgb(139, 213, 202),
        "purple": _rgb(198, 160, 246),
        "orange": _rgb(245, 169, 127),
        "pink": _rgb(245, 189, 230),
        "accent": _rgb(198, 160, 246),
        "heading": _rgb(139, 213, 202),
        "muted": _rgb(110, 115, 141),
    },
    "gruvbox": {
        "green": _rgb(184, 187, 38),
        "red": _rgb(251, 73, 52),
        "yellow": _rgb(250, 189, 47),
        "cyan": _rgb(131, 165, 152),
        "purple": _rgb(211, 134, 155),
        "orange": _rgb(254, 128, 25),
        "pink": _rgb(211, 134, 155),
        "accent": _rgb(250, 189, 47),
        "heading": _rgb(131, 165, 152),
        "muted": _rgb(146, 131, 116),
    },
    "nord": {
        "green": _rgb(163, 190, 140),
        "red": _rgb(191, 97, 106),
        "yellow": _rgb(235, 203, 139),
        "cyan": _rgb(136, 192, 208),
        "purple": _rgb(180, 142, 173),
        "orange": _rgb(208, 135, 112),
        "pink": _rgb(180, 142, 173),
        "accent": _rgb(136, 192, 208),
        "heading": _rgb(129, 161, 193),
        "muted": _rgb(76, 86, 106),
    },
    "mono": {
        "green": "\033[32m",
        "red": "\033[31m",
        "yellow": "\033[33m",
        "cyan": "\033[36m",
        "purple": "\033[35m",
        "orange": "\033[33m",
        "pink": "\033[35m",
        "accent": "\033[36m",
        "heading": "\033[1m",
        "muted": "\033[2m",
    },
}

DEFAULT_THEME = "dracula"


def get_theme(name: str | None = None) -> dict[str, str]:
    """Return the color dict for the given theme name, falling back to default."""
    key = (name or DEFAULT_THEME).lower()
    return THEMES.get(key, THEMES[DEFAULT_THEME])


def list_themes() -> list[str]:
    """Return sorted list of available theme names."""
    return sorted(THEMES.keys())
