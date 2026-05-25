# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# Install (editable mode, no external deps)
pip install -e .

# Run tests
pytest tests/              # all tests
pytest tests/test_cli.py   # single file
pytest -k test_week -v     # single test by name

# Run the CLI
day init                   # primary command
dayctl init                # alias (both installed via pyproject.toml)
python -m dayctl init      # module invocation

# Run the web dashboard (optional server extras)
pip install -e '.[server]'
DAYCTL_TOKEN=dev uvicorn dayctl.server.app:create_app --factory --port 8000
# then open http://127.0.0.1:8000/login?token=dev
# (persistent local service via launchd: see README "Run the web dashboard locally")
```

## Architecture

The CLI core is pure stdlib (`src/dayctl/`); an optional FastAPI web layer lives under `src/dayctl/server/` (installed via the `[server]` extra, not imported by the CLI). Core dependency flow:

```
cli.py → models.py    (DayPlan dataclass, schedule profiles, scoring)
       → storage.py   (JSON persistence to ~/.dayctl/days/)
       → display.py   (ANSI terminal rendering, respects NO_COLOR)
```

- **models.py** — `DayPlan` dataclass, `SCHEDULE_PROFILES` dict (5 profiles auto-detected by weekday), `score_plan()`, `profile_for_date()`. No I/O.
- **storage.py** — `load_plan()`/`save_plan()` read/write JSON files at `~/.dayctl/days/{YYYY-MM-DD}.json`. `load_plan()` auto-creates missing days.
- **display.py** — Color output via `_c(code, text)` helper that checks `NO_COLOR` env and `isatty()`. `print_plan()` for full view, `print_score_table()` for week/history/summary.
- **cli.py** — argparse with subcommands. Each `cmd_*` handler follows: resolve date → load plan → mutate → save → print. `app` and `music` are top-level aliases for `task app` and `task music`.
- **server/** (optional, `[server]` extra) — FastAPI "Daily OS" dashboard, server-rendered with Jinja + HTMX: `app.py` (app factory), `web.py` (HTML/HTMX routes), `api.py` (JSON API), `auth.py` (bearer/cookie token), `scheduler.py` (ntfy reminders), `viewmodel.py` (template context), plus `templates/` + `static/`. Cross-day ideas/settings/stats persist to `~/.dayctl/persistent.json` via `persistent.py`. Deploy: `Dockerfile` + `fly.toml` (Fly.io) or `scripts/com.dayos.web.plist` (local launchd).

## Testing

Tests use a `day_env` fixture (in `conftest.py`) that patches `storage.DATA_DIR` and `storage.DAYS_DIR` to `tmp_path` — no real filesystem side effects. CLI integration tests capture stdout via `monkeypatch` on `sys.argv` and `sys.stdout`.

## Key Patterns

- All dates are ISO strings (`YYYY-MM-DD`). `resolve_date()` in cli.py handles `today`/`yesterday` aliases.
- Saturday defaults to `saturday_no_show`; use `--profile saturday_show` to override.
- `DayPlan.new(day_str, profile_key=None)` is the factory — auto-selects schedule profile from weekday if no override given.
- Tasks use `list[dict]` with `{"task": str, "done": bool}` — 1-based indexing at the CLI layer, 0-based internally.
