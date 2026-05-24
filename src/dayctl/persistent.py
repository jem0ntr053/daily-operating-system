"""Cross-day persistent store: ideas, settings, stats. Flat JSON on DATA_DIR."""
from __future__ import annotations

import json
import re
from datetime import datetime

from dayctl.storage import PERSISTENT_PATH, ensure_dirs

SPARK_CAP = 8


def _defaults() -> dict:
    return {
        "ideas": [],
        "settings": {"accent": "cyan", "show_glance": True},
        "stats": {
            "scPlays":     {"label": "SC Plays · 7d", "v": "", "d": "", "trend": "flat", "spark": [], "updated_at": ""},
            "scFollowers": {"label": "SC Followers",     "v": "", "d": "", "trend": "flat", "spark": [], "updated_at": ""},
            "ytSubs":      {"label": "YouTube Subs",     "v": "", "d": "", "trend": "flat", "spark": [], "updated_at": ""},
            "campaigns":   {"label": "Open campaigns",   "v": "", "d": "", "trend": "flat", "spark": [], "updated_at": ""},
        },
    }


def load_persistent() -> dict:
    if not PERSISTENT_PATH.exists():
        return _defaults()
    try:
        data = json.loads(PERSISTENT_PATH.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return _defaults()
    base = _defaults()
    base.update({k: data[k] for k in ("ideas", "settings", "stats") if k in data})
    return base


def save_persistent(data: dict) -> None:
    ensure_dirs()
    PERSISTENT_PATH.write_text(json.dumps(data, indent=2), encoding="utf-8")


def update_stat(data: dict, key: str, patch: dict) -> None:
    stat = data["stats"].setdefault(
        key, {"label": key, "v": "", "d": "", "trend": "flat", "spark": [], "updated_at": ""}
    )
    if "v" in patch and patch["v"] != stat.get("v"):
        num = float(re.sub(r"[^0-9.]", "", str(patch["v"])) or 0)
        stat["spark"] = ([*stat.get("spark", []), num])[-SPARK_CAP:]
    stat.update({k: v for k, v in patch.items() if k in ("v", "d", "trend", "label")})
    stat["updated_at"] = datetime.now().isoformat()
