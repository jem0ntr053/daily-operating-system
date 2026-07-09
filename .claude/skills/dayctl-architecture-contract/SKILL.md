---
name: dayctl-architecture-contract
description: Use before changing how dayctl creates, loads, saves, or shapes day data — touching models.py, storage.py, storage_backends/, or any server route that calls load_plan/init_or_load_plan; when adding a field to DayPlan, a new storage backend, a new CLI subcommand or web route that materializes a day; when asked "why is it structured this way", why carry-forward exists, or anything about issue #13 / duplicate day-creation paths. Holds the layering invariants, data-shape contract, and known-weak points.
---

# dayctl architecture contract

Load-bearing design decisions, the invariants that keep them true, and the known-weak points. Commands, module inventory, and test/run instructions live in CLAUDE.md and the sibling skills — this file is the WHY and the MUST-HOLD.

Jargon used once, defined once:

| Term | Meaning here |
|---|---|
| day / plan | One `DayPlan` record keyed by ISO date string `YYYY-MM-DD` |
| carry-forward | Copying yesterday's incomplete tasks into today, marked `"carried": true` |
| materialize | Bring a day record into existence in storage (file / row / remote) |
| backend | An object satisfying the `StorageBackend` Protocol in `src/dayctl/storage_backends/__init__.py` |

## Layering contract (the one-way arrows)

```
cli.py ─┐
server/ ─┼─► storage.py ─► storage_backends/ ─► models.py
display ─┘        (models.py depends on NOTHING in the package)
```

| Invariant | Enforced by | Why it exists |
|---|---|---|
| `models.py` does zero I/O — imports only `dataclasses`, `datetime`, `typing` | Convention only; verify with the provenance grep below | Pure logic is testable without fixtures and reusable by every backend and the server |
| CLI core (`cli.py`, `models.py`, `storage.py`, `display.py`, `storage_backends/`) never imports `dayctl.server` | Convention; `pip install -e .` without `[server]` extra would crash on import if violated | The CLI must work with zero third-party deps; FastAPI/Jinja/httpx are opt-in |
| Third-party imports allowed only in `server/` and `storage_backends/remote_backend.py` (httpx) | `select_backend()` imports `remote_backend` lazily, only when `DAYCTL_REMOTE` is set | Default install stays pure-stdlib even though a backend module needs httpx |
| All persistence flows through the `StorageBackend` Protocol (`load_plan/save_plan/list_days/delete_plan/exists`) | `storage.py` is a thin delegator; nothing else touches files/DB/HTTP for day data | Swappable JSON / SQLite / remote storage without touching callers |
| Backend is picked ONCE per process (`@lru_cache` on `storage._backend()`) from env: `DAYCTL_REMOTE` > `DAYCTL_STORAGE=sqlite://...` > JSON default at `~/.dayctl/days/` | `select_backend()` + `_backend()` cache in `storage.py` | Avoids re-reading env per call — but see weak point W4 |
| Dates are ISO strings end-to-end; `datetime.date` objects exist only transiently inside functions | `resolve_date()` (cli.py) normalizes all user input; server routes enforce `^\d{4}-\d{2}-\d{2}$` path pattern | String keys double as filenames, SQLite primary keys, and URL segments with no conversion layer |
| `DayPlan.from_dict()` is the ONLY deserialization gate — filters unknown keys, backfills missing `profile` from weekday, migrates legacy `app_tasks`/`music_tasks`, normalizes every task and note | All three backends call it on load | Old on-disk JSON from any era must load; schema evolution happens in one place |
| Server writes go through the same `storage.py` functions the CLI uses | `server/web.py`, `server/api.py` import from `dayctl.storage` | CLI and dashboard edit the same day file and cannot diverge in format |

If a change breaks one of these arrows (e.g. models.py gaining a file read, cli.py importing server code), that is the bug — do not "fix" it by weakening the rule.

## Day materialization — the load-bearing decision and its footgun

Two creation paths exist ON PURPOSE, and their split is the repo's known-weak point (issue #13, open as of 2026-07-09):

| Path | Where | Carry-forward? | Profile override? |
|---|---|---|---|
| `init_or_load_plan(day, profile_key)` | `storage.py:53` | YES — attempts it, idempotent via `rolled_over` flag | YES |
| `load_plan(day)` → backend auto-create (`DayPlan.new`) | `json_backend.py:24`, `sqlite_backend.py:37` | NO | NO |

Callers today: CLI `day init` and web `GET /day/{day}` (`server/web.py:74`) use `init_or_load_plan`. Every other CLI handler and every web/API mutation route (`add_task`, `toggle_task`, `delete_task`, `edit_field`, ...) uses bare `load_plan` — which silently materializes a missing day with `rolled_over=False` and no carry attempt.

Rules that must hold when touching this area:

- [ ] `rolled_over` is set to `True` ONLY after a real predecessor day existed and carry-forward ran. Setting it when yesterday is absent was bug #12 (fixed in commit `3914a50`); the comment block in `storage.py:65-70` is the contract — keep it.
- [ ] Carry-forward is idempotent two ways: the `rolled_over` flag (never runs twice) and text dedup inside `carry_forward()` (`models.py:324` — a task whose `text` already exists in the target area is skipped).
- [ ] Carried tasks get `"carried": true` so the UI can distinguish them.
- [ ] Any NEW code path that can materialize a day must use `init_or_load_plan`, not `load_plan`. Do not add more instances of the footgun; issue #13's acceptance is "no code path creates a day record without a carry-forward attempt."
- [ ] `day init --force` works by delete-then-`init_or_load_plan` (`cli.py:72-76`), not by overwrite — preserve that, it's what makes forced re-init re-run carry-forward.

Why not just fold carry-forward into `load_plan`? Undecided — issue #13 lists three candidate designs (mutation routes call `init_or_load_plan`; fold carry into auto-create; stop auto-creating). No option has been chosen. If you implement one, put "Closes #13" in the PR body so the user's merge closes it, and update this section.

## Data-shape contract

Facts here override stale prose elsewhere:

- Task dict (normalized by `_norm_task`, `models.py:163`): `{"text": str, "done": bool, "tag": str, "carried": bool}`. The key is `text`, NOT `task`. `"task"` is accepted as a legacy INPUT key by `_norm_task` and as the JSON API request-body field name (`TaskBody.task` in `server/api.py`), but stored data always uses `text` (CLAUDE.md ## Project carries the corrected shape).
- Tasks live in `DayPlan.tasks: dict[area, list[task]]` with fixed areas `AREAS = ["music", "youtube", "marketing", "social", "code"]`. `"app"` is a legacy alias for `"code"`, resolved at CLI (`TASK_AREA_ALIAS`), web, and API layers — three separate alias dicts that must stay in sync.
- Task indexing: 1-based at the CLI (`cmd_task` does `int(action) - 1`), 0-based in web/API routes and internally.
- Notes are `{"text": str, "time": "HH:MM"}` dicts; `from_dict` upgrades bare-string legacy notes.
- Score = count of `True` values among the 6 `HABIT_KEYS` (`fast, gym, music, ship, post, read`). `NON_NEGOTIABLE_KEYS` is a backwards-compat alias for the same list — new code should use `HABIT_KEYS`.
- `SCHEDULE_PROFILES` has 6 profiles (weekday, friday, friday_show, saturday_show, saturday_no_show, sunday) — older docs say 5. Auto-selection via `_DOW_TO_PROFILE`; Saturday defaults to `saturday_no_show`. `switch_profile()` deliberately replaces ONLY `fasting_window` and `schedule`, preserving tasks/notes/completions — profile is presentation, user data is sacred.
- Cross-day state (ideas, dashboard settings, stats) lives in `~/.dayctl/persistent.json` via `persistent.py`, NOT in day files. Day files never reference each other except through carry-forward at creation time.

## Durability decisions

- JSON backend writes are atomic: write `*.json.tmp`, then `Path.replace()` (`json_backend.py:34-39`). Keep this pattern for any new file write of day data.
- SQLite backend REQUIRES WAL mode and raises `RuntimeError` at construction if unavailable (`sqlite_backend.py:21-25`) — a deliberate refuse-to-start over silent corruption risk.
- A user-data backup dir `~/.dayctl/days.bak-20260530T221340/` exists (verified 2026-07-09) — evidence of a past data-integrity scare. Treat `~/.dayctl` contents as production data; never bulk-rewrite day files in a migration without a dated backup like that one.

## Known-weak points (state of 2026-07-09)

| # | Weak point | Status |
|---|---|---|
| W1 | Duplicate day-materialization paths (see section above) | Open, issue #13; hardest live problem |
| W2 | `save_persistent()` and `save_config()` use direct `write_text` — NOT the tmp+replace atomic pattern the day files get | Open, unfiled; candidate cleanup |
| W3 | No cross-process locking: CLI, launchd auto-init, and the web server can read-modify-write the same day concurrently; last writer wins silently | Accepted risk for a single-user tool; be aware when adding automation |
| W4 | `_backend()` lru_cache means env changes after the first storage call are ignored. `cli.py:main()` must call `_reset_backend_cache()` after applying `--remote`/`--token` — any new code that mutates `DAYCTL_REMOTE`/`DAYCTL_STORAGE`/`DAYCTL_TOKEN` mid-process must do the same | By design; footgun documented |
| W5 | Three parallel `app→code` alias dicts (cli.py, web.py, api.py) can drift | Open, unfiled; low risk |

## When NOT to use

- Install, venv, dependency, or extras questions → **dayctl-build-and-env**
- Running tests, what evidence counts before claiming done → **dayctl-validation-and-qa**
- Starting the CLI/dashboard, launchd agents, deploy, tokens at runtime → **dayctl-run-and-operate**
- A bug is live and you're diagnosing it → **dayctl-debugging-playbook** (come back here only when the fix means changing a creation path or data shape)
- Command syntax and module one-liners → `dayctl-run-and-operate` CLI table (don't duplicate them here)

## Provenance and maintenance

All claims verified against the working tree on 2026-07-09 (branch `develop`, HEAD `3914a50`). Re-verify before trusting:

- Layering (models.py purity): `grep -n "^import\|^from" src/dayctl/models.py` — expect only `__future__`, `dataclasses`, `datetime`, `typing`
- CLI/server isolation: `grep -rn "dayctl\.server" src/dayctl/*.py` — expect zero import lines (a help-string mention in cli.py is fine)
- Day-creation call sites (W1): `grep -rn "DayPlan.new\|init_or_load_plan" src/dayctl --include="*.py"` — auto-create should still exist only in json_backend.py, sqlite_backend.py, storage.py
- Issue #13 status: `gh issue view 13` — if closed, rewrite the materialization section
- Task shape: `grep -n "_norm_task" src/dayctl/models.py` and read the returned dict keys
- Profile count: `python -c "from dayctl.models import SCHEDULE_PROFILES; print(len(SCHEDULE_PROFILES), list(SCHEDULE_PROFILES))"`
- Atomic-write gap (W2): `grep -n "write_text" src/dayctl/persistent.py src/dayctl/storage.py src/dayctl/storage_backends/json_backend.py` — only json_backend should pair it with `.replace(`
