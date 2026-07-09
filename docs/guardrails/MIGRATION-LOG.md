# MIGRATION-LOG — guardrails-kit v1.0 install into daily-operating-system

Run date: 2026-07-09. Mode: full migration (existing CLAUDE.md, no sentinel).

## Surfaces

| surface | what it is | decision |
|---|---|---|
| `./CLAUDE.md` | root project instructions (60 lines, hash 714f071) | MIGRATE |
| `./.claude/worktrees/feature+web-ui-polish/CLAUDE.md` | worktree checkout of the same tracked file at an older commit (hash 12726e8); worktree has uncommitted style.css/base.html/day.html changes | LEAVE (worktree copy of the tracked file — updates itself when the worktree updates; never edited directly). FLAG-to-user: stale worktree `feature+web-ui-polish` holds uncommitted UI-polish changes |
| `.claude/settings.json` | absent | n/a |
| `.claude/settings.local.json` | machine-local permission allowlist only; contains no hooks and no instruction text | LEAVE (permissions, not instructions) |
| `@` imports in CLAUDE.md | none found | n/a |
| `.claude/commands`, `.claude/agents`, `.claude/skills` | absent | n/a |
| `docs/guardrails/` | did not exist before this log | n/a — no kit-doc name collisions |
| `~/.claude/CLAUDE.md` (user-global) | read-only context per kit rule | LEAVE, never copied |

Hooks in settings files: none (settings.local.json has only `permissions.allow`).

## Backup (M2)

Snapshot: `CLAUDE.md.pre-migration-20260709-1054` — 53 file lines, 39 non-blank, hash `714f071803121891af4fc82d43d002461c07a545` (equal to live CLAUDE.md at snapshot time). SNAPSHOT-UNCOMMITTED (tree dirty with this log; user commits per onboarding ground rules).

## Disposition table (M3)

Numbered non-blank lines of the snapshot: 39. Rows below: 39.

| # | original text (verbatim) | disposition | destination | note |
|---|---|---|---|---|
| 001 | `# CLAUDE.md` | DROPPED | — | label-only title heading; new CLAUDE.md is kit-structured |
| 002 | This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository. | DROPPED | — | boilerplate preamble, not a rule or fact |
| 003 | `## Commands` | DROPPED | — | label-only heading; commands land in `## Project` |
| 004 | ```` ```bash ```` | DROPPED | — | code-fence decoration; commands re-fenced in destination |
| 005 | `# Install (editable mode, no external deps)` | MOVED | CLAUDE.md ## Project | fact (no external deps) |
| 006 | `pip install -e .` | MOVED | CLAUDE.md ## Project | command |
| 007 | `# Run tests` | MOVED | CLAUDE.md ## Project | block label comment, travels with commands |
| 008 | `pytest tests/              # all tests` | MOVED | CLAUDE.md ## Project | command; resolved: user-approved rewording to `.venv/bin/python -m pytest tests/` 2026-07-09 (bare pytest not verified in repo env) |
| 009 | `pytest tests/test_cli.py   # single file` | MOVED | CLAUDE.md ## Project | command; resolved: user-approved rewording to `.venv/bin/python -m pytest tests/test_cli.py` 2026-07-09 |
| 010 | `pytest -k test_week -v     # single test by name` | MOVED | CLAUDE.md ## Project | command; resolved: user-approved rewording to `.venv/bin/python -m pytest -k test_week -v` 2026-07-09 |
| 011 | `# Run the CLI` | MOVED | CLAUDE.md ## Project | block label comment |
| 012 | `day init                   # primary command` | MOVED | CLAUDE.md ## Project | command |
| 013 | `dayctl init                # alias (both installed via pyproject.toml)` | MOVED | CLAUDE.md ## Project | command + fact |
| 014 | `python -m dayctl init      # module invocation` | MOVED | CLAUDE.md ## Project | command |
| 015 | `# Run the web dashboard (optional server extras)` | MOVED | CLAUDE.md ## Project | block label comment |
| 016 | `pip install -e '.[server]'` | MOVED | CLAUDE.md ## Project | command |
| 017 | `DAYCTL_TOKEN=dev uvicorn dayctl.server.app:create_app --factory --port 8000` | MOVED | CLAUDE.md ## Project | command |
| 018 | `# then open http://127.0.0.1:8000/login?token=dev` | MOVED | CLAUDE.md ## Project | command note |
| 019 | `# (persistent local service via launchd: see README "Run the web dashboard locally")` | MOVED | CLAUDE.md ## Project | pointer fact |
| 020 | ```` ``` ```` | DROPPED | — | code-fence decoration |
| 021 | `## Architecture` | MOVED | docs/guardrails/PROJECT.md ## Architecture | becomes PROJECT.md anchor |
| 022 | The CLI core is pure stdlib (`src/dayctl/`); an optional FastAPI web layer lives under `src/dayctl/server/` (installed via the `[server]` extra, not imported by the CLI). Core dependency flow: | MOVED | docs/guardrails/PROJECT.md ## Architecture | architecture note |
| 023 | ```` ``` ```` | DROPPED | — | code-fence decoration; diagram re-fenced in destination |
| 024 | `cli.py → models.py    (DayPlan dataclass, schedule profiles, scoring)` | MOVED | docs/guardrails/PROJECT.md ## Architecture | diagram line |
| 025 | `       → storage.py   (JSON persistence to ~/.dayctl/days/)` | MOVED | docs/guardrails/PROJECT.md ## Architecture | diagram line |
| 026 | `       → display.py   (ANSI terminal rendering, respects NO_COLOR)` | MOVED | docs/guardrails/PROJECT.md ## Architecture | diagram line |
| 027 | ```` ``` ```` | DROPPED | — | code-fence decoration |
| 028 | - **models.py** — `DayPlan` dataclass, `SCHEDULE_PROFILES` dict (5 profiles auto-detected by weekday), `score_plan()`, `profile_for_date()`. No I/O. | MOVED | docs/guardrails/PROJECT.md ## Architecture | module fact |
| 029 | - **storage.py** — `load_plan()`/`save_plan()` read/write JSON files at `~/.dayctl/days/{YYYY-MM-DD}.json`. `load_plan()` auto-creates missing days. | MOVED | docs/guardrails/PROJECT.md ## Architecture | module fact |
| 030 | - **display.py** — Color output via `_c(code, text)` helper that checks `NO_COLOR` env and `isatty()`. `print_plan()` for full view, `print_score_table()` for week/history/summary. | MOVED | docs/guardrails/PROJECT.md ## Architecture | module fact |
| 031 | - **cli.py** — argparse with subcommands. Each `cmd_*` handler follows: resolve date → load plan → mutate → save → print. `app` and `music` are top-level aliases for `task app` and `task music`. | MOVED | docs/guardrails/PROJECT.md ## Architecture | module fact |
| 032 | - **server/** (optional, `[server]` extra) — FastAPI "Daily OS" dashboard, server-rendered with Jinja + HTMX: `app.py` (app factory), `web.py` (HTML/HTMX routes), `api.py` (JSON API), `auth.py` (bearer/cookie token), `scheduler.py` (ntfy reminders), `viewmodel.py` (template context), plus `templates/` + `static/`. Cross-day ideas/settings/stats persist to `~/.dayctl/persistent.json` via `persistent.py`. Deploy: `Dockerfile` + `fly.toml` (Fly.io) or `scripts/com.dayos.web.plist` (local launchd). | MOVED | docs/guardrails/PROJECT.md ## Architecture | module fact |
| 033 | `## Testing` | MOVED | docs/guardrails/PROJECT.md ## Testing | becomes PROJECT.md anchor |
| 034 | Tests use a `day_env` fixture (in `conftest.py`) that patches `storage.DATA_DIR` and `storage.DAYS_DIR` to `tmp_path` — no real filesystem side effects. CLI integration tests capture stdout via `monkeypatch` on `sys.argv` and `sys.stdout`. | MOVED | docs/guardrails/PROJECT.md ## Testing | test-environment fact |
| 035 | `## Key Patterns` | DROPPED | — | label-only heading; bullets land in `## Project` |
| 036 | - All dates are ISO strings (`YYYY-MM-DD`). `resolve_date()` in cli.py handles `today`/`yesterday` aliases. | MOVED | CLAUDE.md ## Project | iron constraint |
| 037 | - Saturday defaults to `saturday_no_show`; use `--profile saturday_show` to override. | MOVED | CLAUDE.md ## Project | iron constraint |
| 038 | - `DayPlan.new(day_str, profile_key=None)` is the factory — auto-selects schedule profile from weekday if no override given. | MOVED | CLAUDE.md ## Project | iron constraint |
| 039 | - Tasks use `list[dict]` with `{"task": str, "done": bool}` — 1-based indexing at the CLI layer, 0-based internally. | MOVED | CLAUDE.md ## Project | iron constraint |

Counts: KEPT-VERBATIM 0 · MOVED 31 · MERGED 0 · SUPERSEDED-BY 0 · UNSORTED 0 · DROPPED 8 · CONFLICT-PENDING 0. 31+8 = 39 = numbered lines. EQUAL ✓

## CONFLICTS (M4)

none found.

Scan detail: modal-token grep over the snapshot returned one hit (line 022, "…not imported by the CLI") — a project FACT about packaging, not a process rule; no kit doc owns it. The original CLAUDE.md contains zero process rules (no test/build/debug/verify/commit behavior mandates) — it is purely factual, so nothing overlaps kit PLAN/CODE/DEBUG/VERIFY/EFFICIENCY/SESSION/TRAPS ownership. Nested worktree CLAUDE.md: zero modal hits; diff shows it is a strict older revision of the root file (pre-server-extras) with no independent rules.

## Kit-doc collisions (M6a)

Precheck 2026-07-09: none of the 8 kit doc names existed in docs/guardrails/.

- _FORMAT.md: installed
- PLAN.md: installed
- CODE.md: installed
- DEBUG.md: installed
- VERIFY.md: installed
- EFFICIENCY.md: installed
- SESSION.md: installed
- TRAPS.md: installed

All 8 hash-verified equal to `<KIT>` source at install time (pairs printed in transcript).

## Post-migration corrections (Phase-4 review, 2026-07-09)

Transported facts found stale by the FACTUAL review pass and corrected at their destinations (originals preserved in the snapshot; skill `dayctl-architecture-contract` holds the evidence):

- rows 005/016/017: `pip` / `uvicorn` → `.venv/bin/` forms (extends the M5 pytest decision to the remaining PATH-dependent commands)
- row 028: "5 profiles" → 6 profiles (models.py has weekday, friday, friday_show, saturday_show, saturday_no_show, sunday)
- row 029: storage.py described as direct JSON writer → thin facade over `storage_backends/` (JSON/SQLite/Remote)
- row 031: "`app` and `music` top-level aliases" → `music`, `code`, `app` (legacy) shortcuts
- row 034: day_env fixture also patches CONFIG_PATH + select_backend and resets the backend cache
- row 036: resolve_date also handles day names and `-N` offsets
- row 039: task dict shape `{"task","done"}` → normalized `{"text","done","tag","carried"}` (`"task"` legacy input key only; stale claim was causing a live bug pattern — see scheduler.py:60)
- PROJECT.md carries a header NOTE naming `dayctl-architecture-contract` canonical on conflict

## User checkpoint (M5) — decisions

Approved 2026-07-09 with two tweaks: (1) DROPPED list approved as posted; (2) pytest commands carried in venv form (rows 008–010, `resolved:` notes); (3) user approved editing .gitignore as an explicit exception to the onboarding write-scope: `.claude/` → `.claude/*` + `!.claude/skills/` so the skill library is committable (verified: `git check-ignore` still ignores `.claude/settings.local.json` and `.claude/worktrees`; `.claude/skills/` contents tracked).

