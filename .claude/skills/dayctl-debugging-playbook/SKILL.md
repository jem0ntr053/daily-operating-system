---
name: dayctl-debugging-playbook
description: Use when debugging dayctl/Daily OS — tasks that vanish or fail to carry forward, "Unauthorized" or login-cookie problems on the web dashboard, a fix that "didn't take effect" after deploy, the 6 AM autoinit job not creating days, day-file/storage corruption fears, or a bug that reproduces in production data (~/.dayctl) but not in tests. Contains symptom→triage table, storied traps from real commits, and cheap discriminating experiments.
---

# dayctl debugging playbook

Project-specific debugging knowledge for this repo only. Generic debugging discipline (reproduce first, environment re-verification, escalation ladder) is owned by `docs/guardrails/DEBUG.md` — follow that checklist; this skill supplies the dayctl-specific traps and experiments to plug into it.

**When NOT to use:**
- Layout/dependency-flow questions ("where does X live", "may cli import server?") → `dayctl-architecture-contract`
- Install, venv, extras, launchd *setup* → `dayctl-build-and-env`
- "What tests to run / what evidence before claiming done" → `dayctl-validation-and-qa`
- Starting/operating the server or CLI normally (not broken) → `dayctl-run-and-operate`

## 1. Triage table

Symptom → first check → likely cause → where to look.

| Symptom | First check (cheap) | Likely cause | Open |
|---|---|---|---|
| "My fix didn't take effect" on the dashboard | Was `com.dayos.web` restarted? `launchctl kickstart -k gui/$(id -u)/com.dayos.web` | launchd service has NO auto-reload; it runs the code loaded at start | `scripts/com.dayos.web.plist`; dayctl-run-and-operate — THE TRAP |
| Incomplete tasks from yesterday "vanished" / never carried | `python3 -c "import json;print(json.load(open('$HOME/.dayctl/days/<DAY>.json'))['rolled_over'])"` | Day materialized without a carry-forward attempt (issue #13 class); pre-3914a50 data may have `rolled_over` burned | `src/dayctl/storage.py:53-77`, trap 2A/2D below |
| Web dashboard says "Unauthorized" | Fresh login: `curl -si 'http://127.0.0.1:8000/login?token=<TOK>' \| grep -i set-cookie` | Cookie not stored (Secure over http) or session cookie dropped on browser quit (both fixed; regressions possible) | `src/dayctl/server/web.py:47-63`, `src/dayctl/server/auth.py:17-27`, trap 2B |
| Server won't start / 500s at startup | `tail ~/.dayctl/web.log` | `DAYCTL_TOKEN` unset → `RuntimeError` from `_expected_token()` | startup RuntimeError: `src/dayctl/server/app.py:32-33` (`create_app`); per-request 500s: `src/dayctl/server/auth.py:10-14` |
| Days not auto-created at 6 AM | `launchctl list com.dayos.autoinit` — nonzero `LastExitStatus` = failing | `/opt/homebrew/bin/day` shim has a dangling shebang (trap 2E) | `scripts/com.dayos.autoinit.plist`, trap 2E |
| Bug in real data but tests pass | Diff the real day JSON against what the fixture creates | Tests run in `tmp_path` via `day_env`; production state (legacy fields, missing predecessor days) not reproduced | `tests/conftest.py`, experiment 3A |
| `pytest` errors immediately | Run `.venv/bin/python -m pytest` instead | Bare `pytest` on this machine is intercepted by the rtk proxy and fails to spawn (verified 2026-07-09: "rtk: Failed to run pytest: Failed to spawn process") | `dayctl-build-and-env` |
| CLI behaves as if edits ignored | `.venv/bin/python -c "import dayctl; print(dayctl.__file__)"` — must print this repo's `src/` | Running a different install (e.g. the homebrew-python shim) instead of the editable venv install | experiment 3C |
| Wrong schedule profile on Saturday | Intentional: Saturday defaults to `saturday_no_show` | Use `--profile saturday_show` to override | `src/dayctl/models.py` (`SCHEDULE_PROFILES`) |

## 2. Storied traps

Every trap below cost real time in this repo. Cite the commit before re-deriving the lesson.

### 2A. Carry-forward flag burned when yesterday didn't exist (#12, fixed in 3914a50)

- **Symptom:** tasks added to yesterday *after* today was first visited never rolled in — they appeared to vanish.
- **Root cause:** `init_or_load_plan` stamped `rolled_over=True` even when yesterday's file did not exist, so the one-shot flag was consumed with nothing carried. Regression introduced in b5390aa (the commit that *added* the idempotency flag).
- **Fix:** only set `rolled_over=True` (and save) after carry-forward actually ran against an existing predecessor — `src/dayctl/storage.py:71-77`. A day with no yesterday stays `rolled_over=False` and self-heals on the next visit.
- **Regression test:** `test_carry_forward_when_day_touched_before_yesterday_exists` in `tests/test_storage.py`.
- **Lesson:** any "run at most once" flag must only be consumed when the guarded work actually ran. If carry-forward misbehaves again, check `rolled_over` in the raw day JSON first.

### 2B. Login cookie — two separate bugs, same symptom ("Unauthorized")

1. **941aeac** — cookie was set with `secure=True` unconditionally, so browsers refused to store it over `http://localhost`. Fix: `secure=request.url.scheme == "https"` and `samesite="lax"` (strict broke link-based first-navigation login). `src/dayctl/server/web.py:61-62`.
2. **df5192c** — cookie had no `max_age`, making it a session cookie that browsers drop on quit → "Unauthorized" after every browser restart. Fix: `COOKIE_MAX_AGE` (~10 years, single-user localhost) at `src/dayctl/server/web.py:27,59`. Test: `test_login_cookie_is_persistent` in `tests/test_server_web.py`.

- **Lesson:** "auth stopped working" on the dashboard is usually cookie *storage*, not token *validation*. `auth.py` accepts bearer header OR cookie (`src/dayctl/server/auth.py:26`) — use that to discriminate (experiment 3B).

### 2C. Restart-to-deploy: launchd runs stale code

Read-only first check: compare the service's start time (`launchctl print gui/$(id -u)/com.dayos.web`) against your edited file's mtime.

```bash
launchctl kickstart -k gui/$(id -u)/com.dayos.web   # state-changing: restarts the live dashboard and deploys whatever is in the working tree
```

Full story and service anatomy: dayctl-run-and-operate — THE TRAP.

Log path per the INSTALLED plist (`~/.dayctl/web.log`), not the repo template — see dayctl-run-and-operate.

### 2D. Duplicate day-creation paths (issue #13 — OPEN as of 2026-07-09)

Days can be materialized through paths that never attempt carry-forward:

- `JSONBackend.load_plan` auto-creates a missing day (`src/dayctl/storage_backends/json_backend.py:27-30`) with `rolled_over=False`.
- Web mutation routes (`add_task`, `toggle_task`, `delete_task`, edit routes — `src/dayctl/server/web.py:88,103,123,...`) call `load_plan()`, not `init_or_load_plan()`. Only `view_day` (`web.py:74`) runs the carry-forward path.
- The 6 AM `com.dayos.autoinit` job and backward navigation can create a day before its predecessor exists.

Since 3914a50 this self-heals on the next `init_or_load_plan` visit, but a fix applied to one creation path may not cover the others (discriminating experiment: 3D). Design options and must-hold rules: dayctl-architecture-contract; read issue #13 before structural fixes.

### 2E. The `day` shim on PATH is broken — autoinit silently fails [RESOLVED 2026-07-09, issue #15]

`/opt/homebrew/bin/day` is a 185-byte console-script shim whose shebang points at `/opt/homebrew/opt/python@3.11/bin/python3.11` — **which no longer exists** (homebrew python upgraded). Consequences observed before the fix:

- `launchctl list com.dayos.autoinit` → `LastExitStatus = 19968` (exit code 78): the 6 AM `day init` job failed every run, so days were not auto-created — exactly the precondition for the #12/#13 bug class.
- Its log `/tmp/dayos-autoinit.log` stayed empty (0 bytes) — the job never got far enough to write.
- RESOLUTION: installed plist and `scripts/com.dayos.autoinit.plist` now invoke `.venv/bin/day` (absolute path); verified exit 0 after bootout/bootstrap/kickstart. The PATH shim itself is still dead — any terminal `day` via PATH fails; use `.venv/bin/day` or `.venv/bin/python -m dayctl`.

Also note there was a data-integrity scare around the #12 fix: `~/.dayctl/days.bak-20260530T221340/` (43 day files, backed up 2026-05-30 — the same day 3914a50 landed). Before any risky storage change, take the same kind of timestamped backup of `~/.dayctl/days/`.

## 3. Discriminating experiments

Cheap tests to tell cause A from cause B.

### 3A. Code bug vs production-data state

Tests use the `day_env` fixture (`tests/conftest.py`) which patches `DATA_DIR`/`DAYS_DIR`/`select_backend` to `tmp_path` — real `~/.dayctl` is never touched, and real-data state (legacy task shapes, missing predecessors, burned `rolled_over` flags) is never reproduced unless you craft it. To discriminate:

```bash
# Reproduce against a COPY of real data, never the live dir:
cp -r ~/.dayctl /tmp/dayctl-repro
# then in a python snippet, monkeypatch/point the backend at /tmp/dayctl-repro/days
```

If it reproduces with copied real data but not with fixture data → data-state bug; write a test that crafts that state (see `test_carry_forward_when_day_touched_before_yesterday_exists` for the pattern of creating day N+1 before day N).

### 3B. Server bug vs browser/cookie bug

`require_token` accepts bearer header or cookie (`src/dayctl/server/auth.py:17-27`). Bypass the browser entirely:

```bash
curl -si -H "Authorization: Bearer $DAYCTL_TOKEN" http://127.0.0.1:8000/day/$(date +%F) | head -1
```

- 200 via curl but browser fails → cookie storage problem (trap 2B): inspect `set-cookie` on `/login` for `Max-Age`, `Secure`, `SameSite`.
- 401 via curl too → server-side: token mismatch between your shell and the launchd plist's `DAYCTL_TOKEN` (the installed plist embeds its own copy).

### 3C. Stale service/interpreter vs actual code bug

Before debugging "my change does nothing":

```bash
launchctl kickstart -k gui/$(id -u)/com.dayos.web        # dashboard: restart first (trap 2C)
.venv/bin/python -c "import dayctl; print(dayctl.__file__)"  # CLI: confirm repo editable install (dayctl-build-and-env Trap 2)
head -1 /opt/homebrew/bin/day                             # shim: dead shebang? (trap 2E)
```

Only if the right code is provably running does it become a code bug.

### 3D. Which creation path made this day file

A day file that exists with `"rolled_over": false` and a predecessor that *does* exist means it was created by a non-init path (trap 2D: web mutation route, backend auto-create) — carry-forward will run on the next `view_day`/`day init` visit. Check:

```bash
python3 -c "import json,sys; d=json.load(open(sys.argv[1])); print(d['day'], d.get('rolled_over'))" ~/.dayctl/days/<DAY>.json
```

### 3E. launchd job health

```bash
launchctl list | grep dayos          # col1 pid (running), col2 last exit status
tail -20 ~/.dayctl/web.log           # web service log (installed plist path)
```

Exit status shown by `launchctl list <label>` is `code << 8` (e.g. 19968 = exit 78).

## Provenance and maintenance

All claims verified 2026-07-09 on branch `develop` (HEAD 3914a50). Re-verify with:

- Carry-forward logic & flag semantics: `git show 3914a50` and read `src/dayctl/storage.py:53-77`
- Cookie fixes: `git show df5192c 941aeac`
- Issue #13 still open / creation call sites: `gh issue view 13`; `grep -n "load_plan(" src/dayctl/server/web.py`
- Broken shim + autoinit failure: `head -1 /opt/homebrew/bin/day` (does the shebang target exist?); `launchctl list com.dayos.autoinit`
- Installed vs repo plist log paths: `grep -A1 StandardOutPath ~/Library/LaunchAgents/com.dayos.web.plist scripts/com.dayos.web.plist`
- Test isolation: read `tests/conftest.py` (`day_env`)
- rtk pytest trap: `pytest --version` (fails) vs `.venv/bin/python -m pytest --version` (works)
