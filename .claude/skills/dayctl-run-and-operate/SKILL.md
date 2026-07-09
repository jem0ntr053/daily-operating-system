---
name: dayctl-run-and-operate
description: Use when running, deploying, or operating dayctl / Daily OS — invoking the day/dayctl CLI, starting the dev server, inspecting or restarting the com.dayos.web launchd service, reading server logs, deploying to Fly.io, wiring DAYCTL_TOKEN/DAYCTL_REMOTE/NTFY env vars, or asking "why isn't my code change showing on the dashboard" (restart-to-deploy trap). Covers command anatomy, service lifecycle, and where data lands locally vs remote.
---

# dayctl: run and operate

Runbook for running the CLI, the web dashboard (dev and local-prod), and the Fly.io remote. All commands verified against `src/dayctl/cli.py`, `scripts/com.dayos.web.plist`, the live launchd service, `Dockerfile`, `fly.toml`, and README on 2026-07-09 — except the Fly.io deploy sequence (README-sourced, unverified).

**When NOT to use this skill:**
- Module layout, dataclasses, storage-backend design → `dayctl-architecture-contract`
- Installing the package, venv, extras, dependency questions → `dayctl-build-and-env`
- Running tests, pre-merge evidence, "did that break anything" → `dayctl-validation-and-qa`
- A running service misbehaving, tracebacks, wrong output → `dayctl-debugging-playbook`

## THE TRAP: code changes do not appear until you restart the service

The local dashboard runs under launchd (`com.dayos.web`) with **no auto-reload** (`uvicorn` is started without `--reload`). Editing code in this repo does nothing to the running dashboard until you restart the service. This has bitten before — user-confirmed. After any change to `src/dayctl/server/` (or anything it imports), restart:

```bash
launchctl kickstart -k gui/$(id -u)/com.dayos.web
```

`-k` kills the running instance; launchd restarts it immediately (`KeepAlive` is true). Alternative from the README (stop/start):

```bash
launchctl bootout   gui/$(id -u) ~/Library/LaunchAgents/com.dayos.web.plist   # stop
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.dayos.web.plist   # start
```

Pure template/static edits also require the restart — Jinja templates are loaded by the app process. If the dashboard still looks stale after a restart, hard-refresh the browser (cached static assets).

## CLI command anatomy

> WARNING: the PATH `day` shim (/opt/homebrew/bin/day) is broken on this machine (dangling python@3.11 shebang) — use `.venv/bin/day` or `.venv/bin/python -m dayctl`. Story: dayctl-debugging-playbook trap 2E.

Three equivalent entry points: `day`, `dayctl` (pyproject `[project.scripts]`) and `python -m dayctl` (`__main__.py`). Running with **no subcommand defaults to `show`**.

```
day [--remote URL] [--token TOKEN] <command> [args] [--date DATE]
```

Global flags: `--remote` overrides `DAYCTL_REMOTE`, `--token` overrides `DAYCTL_TOKEN` (they set the env vars and reset the storage-backend cache, so any command can run against a remote server).

`--date` accepts: `YYYY-MM-DD`, `today`, `yesterday`, a day name (`monday`/`mon` … most recent occurrence), or `-N` (N days ago). Implemented in `resolve_date()` in `src/dayctl/cli.py`.

| Command | What it does | Notes |
|---|---|---|
| `day init` | Create today's plan | `--force` delete + re-init (re-runs carry-forward), `--profile <key>` schedule override; carries forward unfinished tasks from yesterday |
| `day show` | Print the plan | Default when no subcommand given |
| `day check <item>` / `day uncheck <item>` | Toggle a non-negotiable | Items: `fast, gym, music, ship, post, read` |
| `day note "<text>"` | Timestamped note | |
| `day score` | Score for the day (`N / 6`) | |
| `day set <field> <value>` | Set a field | Fields: `focus`, `energy`, `sleep` |
| `day task <category> add "<text>"` | Add task | Categories: `music`, `code`, `app` (`app` = legacy alias for `code`) |
| `day task <category> <N> done\|undo\|"new text"` | Complete/undo/edit task N (1-based) | |
| `day music …` / `day code …` / `day app …` | Top-level shortcuts for `task <category> …` | |
| `day tonight [show\|off]` | Toggle show/no-show profile | Fri & Sat profiles only; no arg = toggle |
| `day week` | Scores, past 7 days | |
| `day summary` | Current ISO week Mon–Sun | |
| `day history` | Scores, all tracked days | |
| `day streak [--threshold N]` | Consecutive days ≥ threshold (default 6) | |
| `day config theme [name]` | View/set CLI theme | Omit name to list available |
| `day push [date]` / `day pull [date]` | Copy one day local↔remote JSON | Requires `DAYCTL_REMOTE`; date defaults to `today` |

Note: the README's Fly.io section shows `day today` — there is no `today` subcommand; use `day show`.

## Dev server (foreground, throwaway)

```bash
.venv/bin/pip install -e '.[server]'    # once; see dayctl-build-and-env
DAYCTL_TOKEN=dev .venv/bin/uvicorn dayctl.server.app:create_app --factory --port 8000
open "http://127.0.0.1:8000/login?token=dev"
```

- `DAYCTL_TOKEN` is **required** — `create_app()` raises `RuntimeError` without it (`src/dayctl/server/app.py`).
- `/login?token=…` sets a `dayctl_token` cookie and redirects; afterwards plain `http://127.0.0.1:8000` works. API calls can instead send `Authorization: Bearer <token>` (`src/dayctl/server/auth.py`).
- The reminder scheduler only starts when `DAYCTL_ENABLE_SCHEDULER=1` — off by default in dev, on in the Docker image.
- Port 8000 collides with the launchd service if it's running (as of 2026-07-09 it is). Use `--port 8001` for a side-by-side dev run, or stop the service first.

## Local prod: launchd service `com.dayos.web`

Repo template: `scripts/com.dayos.web.plist`. Installed copy: `~/Library/LaunchAgents/com.dayos.web.plist` (on this machine the installed copy has drifted from the template — see log path below). The plist runs `.venv/bin/uvicorn dayctl.server.app:create_app --factory --host 127.0.0.1 --port 8000` with `WorkingDirectory` set to this repo, `RunAtLoad` + `KeepAlive` true, and `DAYCTL_TOKEN` embedded in `EnvironmentVariables` (generate with `openssl rand -hex 24`; the real token lives only in the installed plist — never commit it).

Inspect / logs (read-only, safe anytime):

```bash
launchctl print gui/$(id -u)/com.dayos.web   # state, PID, args, env, log paths
tail -f ~/.dayctl/web.log                    # installed plist log path on this machine (verified 2026-07-09)
tail -f /tmp/dayos-web.log                   # repo-template log path (fresh installs from scripts/)
```

Install / start / stop / restart:

```bash
cp scripts/com.dayos.web.plist ~/Library/LaunchAgents/          # then edit: token, paths
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.dayos.web.plist  # start
launchctl bootout   gui/$(id -u) ~/Library/LaunchAgents/com.dayos.web.plist  # stop
launchctl kickstart -k gui/$(id -u)/com.dayos.web               # restart (deploy code changes)
```

Changing `EnvironmentVariables` in the plist requires bootout + bootstrap (kickstart reuses the loaded plist definition).

The service is `127.0.0.1`-only by design — not reachable from other devices. Free phone access via Tailscale is **planned, not built** (issue #11); the built remote option is Fly.io.

Two sibling agents (same install pattern, `scripts/`): `com.dayos.autoinit` (runs `day init` daily at 6:00 AM, log `/tmp/dayos-autoinit.log`) and `com.dayos.notify` (macOS notification 5 min before each schedule block via `scripts/notify_schedule.py`, log `/tmp/dayos-notify.log`). Pause notifications with `launchctl unload`, resume with `launchctl load` (README pattern for these two).

## Remote: Fly.io

`Dockerfile` runs the same app factory on `0.0.0.0:8080` with `DAYCTL_STORAGE=sqlite:///data/dayctl.db` and `DAYCTL_ENABLE_SCHEDULER=1` baked in. `fly.toml` (app name is a `<APP_NAME>` placeholder in-repo; real name not recorded here) mounts volume `dayctl_data` at `/data`, `internal_port 8080`, `min_machines_running 1`, region `iad`.

README-documented deploy sequence (requires `fly` CLI + account; not runnable/verifiable from this machine session):

```bash
fly launch --no-deploy                 # reconcile generated fly.toml with the repo's
fly volumes create dayctl_data --size 1
fly secrets set DAYCTL_TOKEN=$(openssl rand -hex 32) NTFY_TOPIC=https://ntfy.sh/<private-topic>
fly deploy
# then on the phone: https://<app>.fly.dev/login?token=<token> → Add to Home Screen
```

[UNVERIFIED 2026-07-09: whether a Fly app is currently deployed for this repo, and its name/URL — fly.toml only has a placeholder and no fly CLI state was inspected.]

Point the local CLI at the remote (all commands then read/write the server instead of local JSON):

```bash
export DAYCTL_REMOTE=https://<app>.fly.dev
export DAYCTL_TOKEN=<token>
day show
```

Backend selection (`src/dayctl/storage_backends/__init__.py`): `DAYCTL_REMOTE` set → RemoteBackend; else `DAYCTL_STORAGE=sqlite://<path>` → SQLiteBackend; else JSON at `~/.dayctl/days/`. One-day manual sync between local JSON and remote: `day push <date>` / `day pull <date>`.

### Reminders (ntfy)

Server-side scheduler (`src/dayctl/server/scheduler.py` + `ntfy.py`, APScheduler tick every minute): fires an HTTP POST to the **full topic URL** in `NTFY_TOPIC` at each schedule-block boundary, with up to 2 pending tasks per category in the body (KNOWN BUG as of 2026-07-09: `_body_for` at scheduler.py:60 reads `t['task']` instead of `t['text']`, so reminders with pending tasks fail with a swallowed KeyError and never send.). Needs `DAYCTL_ENABLE_SCHEDULER=1` to run at all; silently no-ops if `NTFY_TOPIC` is unset. Optional: `NTFY_AUTH` (bearer for protected topics), `DAYCTL_QUIET_UNTIL=YYYY-MM-DD` (suppress through that date, inclusive).

## Env var matrix

| Variable | Consumed by | Effect |
|---|---|---|
| `DAYCTL_TOKEN` | server `auth.py`, `app.py`; CLI remote mode | Server: required, the single bearer/cookie auth token. CLI: token sent to `DAYCTL_REMOTE` |
| `DAYCTL_REMOTE` | `storage_backends/__init__.py`, `push`/`pull` | Base URL of remote server; switches CLI to RemoteBackend |
| `DAYCTL_STORAGE` | `storage_backends/__init__.py` | `sqlite://<path>` → SQLiteBackend (used in Docker); ignored if `DAYCTL_REMOTE` set |
| `DAYCTL_ENABLE_SCHEDULER` | `server/app.py` | `1` → start ntfy reminder scheduler |
| `NTFY_TOPIC` | `server/scheduler.py` | Full ntfy topic URL to POST reminders to; unset = no reminders |
| `NTFY_AUTH` | `server/ntfy.py` | Optional bearer token for protected ntfy topics |
| `DAYCTL_QUIET_UNTIL` | `server/scheduler.py` | `YYYY-MM-DD`: suppress reminders through that date |
| `NO_COLOR` | `display.py` | Disable ANSI colors in CLI output |

## Where data lands

| Location | What | Written by |
|---|---|---|
| `~/.dayctl/days/{YYYY-MM-DD}.json` | Per-day plans (local default) | CLI + local dashboard |
| `~/.dayctl/persistent.json` | Cross-day ideas/settings/stats | dashboard (`src/dayctl/persistent.py`) |
| `~/.dayctl/config.json` | CLI config (theme) | `day config` |
| `~/.dayctl/web.log` | Dashboard service log (this machine) | launchd |
| `/data/dayctl.db` (Fly volume `dayctl_data`) | SQLite plans on remote | Fly deployment |

**All `~/.dayctl/` contents are live production data for the user's actual days. Never delete, truncate, or bulk-rewrite them during development** — tests already isolate via the `day_env` fixture; use it.

Local JSON and remote SQLite do **not** sync automatically; `day push`/`day pull` move one day at a time.

## Provenance and maintenance

Re-verify each claim's source when touching this file:

- CLI commands/flags: `grep -n "add_parser\|add_argument" src/dayctl/cli.py`
- Entry points/extras: `sed -n '/project.scripts/,/^$/p' pyproject.toml`
- Env vars: `grep -rn "environ" src/dayctl --include='*.py'`
- Service state + real log path/port/token location: `launchctl print gui/$(id -u)/com.dayos.web`
- Plist template vs installed: `diff scripts/com.dayos.web.plist ~/Library/LaunchAgents/com.dayos.web.plist`
- Docker/Fly facts: `cat Dockerfile fly.toml`
- Tailscale status (still open?): `gh issue view 11`

Volatile facts date-stamped 2026-07-09: port 8000 local, 8080 in-container, installed-plist log path `~/.dayctl/web.log`, fly.toml app-name placeholder, issue #11 open.
