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
```

## Architecture

Pure stdlib Python package (`src/dayctl/`) with four modules and a strict dependency flow:

```
cli.py → models.py    (DayPlan dataclass, schedule profiles, scoring)
       → storage.py   (JSON persistence to ~/.dayctl/days/)
       → display.py   (ANSI terminal rendering, respects NO_COLOR)
```

- **models.py** — `DayPlan` dataclass, `SCHEDULE_PROFILES` dict (5 profiles auto-detected by weekday), `score_plan()`, `profile_for_date()`. No I/O.
- **storage.py** — `load_plan()`/`save_plan()` read/write JSON files at `~/.dayctl/days/{YYYY-MM-DD}.json`. `load_plan()` auto-creates missing days.
- **display.py** — Color output via `_c(code, text)` helper that checks `NO_COLOR` env and `isatty()`. `print_plan()` for full view, `print_score_table()` for week/history/summary.
- **cli.py** — argparse with subcommands. Each `cmd_*` handler follows: resolve date → load plan → mutate → save → print. `app` and `music` are top-level aliases for `task app` and `task music`.

## Testing

Tests use a `day_env` fixture (in `conftest.py`) that patches `storage.DATA_DIR` and `storage.DAYS_DIR` to `tmp_path` — no real filesystem side effects. CLI integration tests capture stdout via `monkeypatch` on `sys.argv` and `sys.stdout`.

## Key Patterns

- All dates are ISO strings (`YYYY-MM-DD`). `resolve_date()` in cli.py handles `today`/`yesterday` aliases.
- Saturday defaults to `saturday_no_show`; use `--profile saturday_show` to override.
- `DayPlan.new(day_str, profile_key=None)` is the factory — auto-selects schedule profile from weekday if no override given.
- Tasks use `list[dict]` with `{"task": str, "done": bool}` — 1-based indexing at the CLI layer, 0-based internally.
