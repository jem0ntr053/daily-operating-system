# Remote Access & Cross-Device Reminders — Design

**Date:** 2026-04-12
**Status:** Approved for planning

## Goal

Make the daily operating system accessible from a phone and deliver schedule-driven reminders to that phone, so the user can stay on task while away from their laptop (e.g., at the gym). Deliberately defers calendar sync.

## Priorities (in order)

1. **Access** — view and update today's plan from phone.
2. **Reminders** — schedule-aware push notifications on phone and laptop.
3. **Capability** — foundation that can grow into calendar sync later.

Out of scope for v1: calendar sync (one-way or two-way), multi-user auth, PWA install, offline mobile mode, notification action buttons that mutate state, automatic local↔remote sync.

## Architecture

```text
┌─ phone/browser ──────┐        ┌─ ntfy.sh ─┐
│ HTML + HTMX (mobile) │        │ push API  │
└──────────┬───────────┘        └─────▲─────┘
           │ HTTPS                    │ POST
           ▼                          │
┌─ Fly.io app (single process)  ──────┴──────┐
│  FastAPI                                   │
│   ├─ routes/web.py    (HTML via Jinja2)    │
│   ├─ routes/api.py    (JSON for CLI)       │
│   ├─ auth: bearer token from env var       │
│   └─ APScheduler: reads today's profile,   │
│                    posts to ntfy topic     │
│  dayctl.models (unchanged)                 │
│  dayctl.storage (SQLite backend added)     │
└──────────┬─────────────────────────────────┘
           │
           ▼
     SQLite on Fly volume
     (/data/dayctl.db)

┌─ laptop CLI ──────────────────┐
│ `day ...`                     │
│   default: local JSON (fast)  │
│   --remote: hits /api/*       │
└───────────────────────────────┘
```

### New modules (under `src/dayctl/`)

- `server/app.py` — FastAPI factory, auth dependency, startup/shutdown hooks.
- `server/web.py` — HTML routes (Jinja2 templates, HTMX fragments).
- `server/api.py` — JSON routes mirroring CLI commands.
- `server/scheduler.py` — APScheduler job + pure `should_fire_now()`.
- `server/ntfy.py` — thin poster wrapper, injectable for tests.
- `server/templates/` — mobile-first Jinja2 templates.
- `server/static/` — minimal CSS; HTMX loaded from CDN.

### Modified modules

- `storage.py` — introduces `StorageBackend` protocol; adds `SQLiteBackend`; keeps `JSONBackend` as default.
- `cli.py` — `--remote` flag (or `DAYCTL_REMOTE` env) routes through `RemoteBackend`.

`models.py` is unchanged.

## Data

### Storage abstraction

`StorageBackend` protocol with `load_plan(date) -> DayPlan`, `save_plan(plan) -> None`, `list_days() -> list[str]`.

Implementations:

- `JSONBackend(root=~/.dayctl/days)` — current behavior, default for local CLI.
- `SQLiteBackend(path)` — server default on Fly. Schema:

  ```sql
  CREATE TABLE plans (
    date       TEXT PRIMARY KEY,
    json       TEXT NOT NULL,
    updated_at TEXT NOT NULL
  );
  ```

  Storing the plan as a JSON blob keyed by date keeps `DayPlan` the single source of truth and avoids schema migrations when fields evolve.
- `RemoteBackend(base_url, token)` — used by `day --remote`; calls `/api/*`.

Backend selected via env: `DAYCTL_STORAGE=sqlite:///data/dayctl.db` on Fly, unset locally, `DAYCTL_REMOTE=https://...` + `DAYCTL_TOKEN=...` for remote CLI.

### Sync between laptop JSON and server

v1 is deliberately manual: no background sync. Users pick one backend per invocation. `day push <date>` and `day pull <date>` copy a day between backends on demand. No merge logic; last writer wins.

## API

Mirrors existing CLI commands. Representative endpoints:

- `GET /api/days/{date}` → DayPlan JSON
- `PUT /api/days/{date}` → replace plan
- `POST /api/days/{date}/tasks` → append task
- `POST /api/days/{date}/tasks/{idx}/toggle` → toggle done
- `DELETE /api/days/{date}/tasks/{idx}` → remove task
- `GET /api/score?range=week` → score table data

All `/api/*` require `Authorization: Bearer <token>`. Errors are `{"error": "..."}` JSON.

## Web UI

Server-rendered HTML with HTMX for interactivity. Mobile-first CSS; no JS framework. Key interactions:

- Load today's plan at `/` (redirects to `/day/today`).
- Tap a task checkbox → `POST /web/task/{idx}/toggle` returns updated `<li>` fragment; HTMX swaps it in place.
- Collapsible schedule block, streak, score display — all server-rendered.
- Auth: first visit with `?token=...` sets an HTTP-only cookie; subsequent requests are authenticated.

Streamlit app is retired.

## Reminders

APScheduler runs inside the FastAPI process. One job ticks every minute and asks: "did any block in today's active profile just start since the last tick?" If yes, POST to ntfy.

**Message shape:**

- Title: block name (e.g., "Deep work").
- Body: next 1–2 incomplete tasks from today's plan.
- Priority: default; high for non-negotiables.
- Action: "Open app" link to web UI.

**Profile awareness.** Reuses `profile_for_date()` and `SCHEDULE_PROFILES` from `models.py`. Day-level profile overrides are respected automatically.

**Quiet hours.** Implicit via the profile window (no reminder outside scheduled blocks). Explicit override: `DAYCTL_QUIET_UNTIL=YYYY-MM-DD` env var for multi-day silencing.

**Config.** `NTFY_TOPIC` (required), `NTFY_AUTH` (optional).

**Failure mode.** ntfy POST failures are logged and swallowed. No retries, no queue. A missed reminder is acceptable; a late one is not.

## Auth

Single user. One long-lived bearer token in `DAYCTL_TOKEN`. FastAPI dependency validates it on every `/api/*` route. Web routes accept the same token via HTTP-only cookie set by `/login?token=...`. No session store, no expiry, no rotation flow in v1.

HTTPS provided by Fly.

## Error handling

- **API:** FastAPI exception handlers; 404 missing day, 401 bad token, 422 bad payload.
- **Web:** HTMX returns a toast fragment on error; no full-page crashes.
- **Scheduler:** exceptions in jobs are logged and swallowed — never kill the loop.
- **Storage:** SQLite writes in transactions; JSON backend keeps existing atomic temp-file rename.

## Testing

- Existing `models.py` and CLI tests stay green (unchanged code paths).
- `tests/test_storage_sqlite.py` — contract tests parameterized over both backends.
- `tests/test_api.py` — FastAPI `TestClient`; auth, CRUD, task toggle.
- `tests/test_web.py` — `TestClient`; asserts HTML fragments and HTMX toggle response.
- `tests/test_scheduler.py` — pure `should_fire_now(profile, now, last_tick)` covered directly; ntfy poster injected as a fake. APScheduler itself is not tested.

## Deployment

Single Fly.io app. 256MB VM, 1GB persistent volume mounted at `/data`. Required env: `DAYCTL_TOKEN`, `DAYCTL_STORAGE=sqlite:///data/dayctl.db`, `NTFY_TOPIC`. Optional: `NTFY_AUTH`, `DAYCTL_QUIET_UNTIL`. Expected cost within free allowance.

## Risks & open questions

- **iOS ntfy delivery latency.** ntfy on iOS uses a shared APNs relay; typical latency is a few seconds but can spike. Acceptable for v1; revisit if reminders feel late.
- **SQLite on a single Fly volume.** Fine for single-user, single-writer. Not a risk until multi-region or multi-user is on the table.
- **Manual push/pull UX.** If it becomes annoying, the next iteration is auto-sync with a simple last-writer-wins rule. Not in v1.

## Success criteria

- User can open the web app on their phone, see today's plan, and toggle tasks.
- User receives a ntfy notification on their phone at each schedule block boundary.
- Existing local CLI workflow is unchanged when `--remote` is not set.
- Test suite passes locally and in CI.
