# PROJECT.md — project-authored archive (transported verbatim from pre-migration CLAUDE.md, 2026-07-09)

> NOTE (2026-07-09): facts below were corrected post-migration after review; where this file and .claude/skills/dayctl-architecture-contract disagree, the skill is canonical.

## Architecture

The CLI core is pure stdlib (`src/dayctl/`); an optional FastAPI web layer lives under `src/dayctl/server/` (installed via the `[server]` extra, not imported by the CLI). Core dependency flow:

```
cli.py → models.py    (DayPlan dataclass, schedule profiles, scoring)
       → storage.py   (JSON persistence to ~/.dayctl/days/)
       → display.py   (ANSI terminal rendering, respects NO_COLOR)
```

- **models.py** — `DayPlan` dataclass, `SCHEDULE_PROFILES` dict (6 profiles: weekday, friday, friday_show, saturday_show, saturday_no_show, sunday — auto-detected by weekday), `score_plan()`, `profile_for_date()`. No I/O.
- **storage.py** — thin facade delegating to `storage_backends/` (JSON default at `~/.dayctl/days/{YYYY-MM-DD}.json`, SQLite via `DAYCTL_STORAGE`, remote via `DAYCTL_REMOTE`). `load_plan()` auto-creates missing days.
- **display.py** — Color output via `_c(code, text)` helper that checks `NO_COLOR` env and `isatty()`. `print_plan()` for full view, `print_score_table()` for week/history/summary.
- **cli.py** — argparse with subcommands. Each `cmd_*` handler follows: resolve date → load plan → mutate → save → print. `music`, `code`, and `app` (legacy alias for code) are top-level shortcuts for `task <category>`.
- **server/** (optional, `[server]` extra) — FastAPI "Daily OS" dashboard, server-rendered with Jinja + HTMX: `app.py` (app factory), `web.py` (HTML/HTMX routes), `api.py` (JSON API), `auth.py` (bearer/cookie token), `scheduler.py` (ntfy reminders), `viewmodel.py` (template context), plus `templates/` + `static/`. Cross-day ideas/settings/stats persist to `~/.dayctl/persistent.json` via `persistent.py`. Deploy: `Dockerfile` + `fly.toml` (Fly.io) or `scripts/com.dayos.web.plist` (local launchd).

## Testing

Tests use a `day_env` fixture (in `conftest.py`) that patches `storage.DATA_DIR` and `storage.DAYS_DIR` to `tmp_path` (plus `CONFIG_PATH` and `select_backend`, resetting the backend cache before and after each test) — no real filesystem side effects. CLI integration tests capture stdout via `monkeypatch` on `sys.argv` and `sys.stdout`.
