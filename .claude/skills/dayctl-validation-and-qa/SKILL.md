---
name: dayctl-validation-and-qa
description: Use before claiming any change to this repo works — after editing CLI, storage, models, or server code; when adding tests for a new CLI subcommand, storage behavior, or web route; when asked "how do I run the tests", "did that break anything", or what evidence counts before commit/PR. Also use for manual verification of the web dashboard. Covers pytest run commands, the day_env fixture contract, and what a green run does NOT prove.
---

# dayctl validation and QA

What counts as evidence in this repo, how to run and add tests, and how to manually verify the web dashboard. This is the project-specific layer on top of `docs/guardrails/VERIFY.md` (which governs done-claims and the echo protocol — read it before writing "done"; do not restate it, follow it).

## The evidence bar (2026-07-09)

**Local tests are the only automated gate.** Verified 2026-07-09: no `.github/` directory (no CI), no lint/type config anywhere (`ruff.toml`, `.ruff.toml`, `.flake8`, `setup.cfg`, `tox.ini`, `.pre-commit-config.yaml` all absent; `pyproject.toml` has no ruff/flake8/mypy sections). Nothing runs on push. If you didn't run pytest locally, nothing did.

Acceptance threshold: **all tests pass, zero failures, zero unexplained skips**. Baseline as of 2026-07-09: `146 passed in 1.83s`. Any `skipped` count means fastapi is missing from your env (see below) — that is a degraded run, not a pass, for server-touching changes.

## Run commands

Always use the venv python. Bare `pytest` fails on this machine (rtk proxy spawn failure — dated 2026-07-09, machine-specific) (why: dayctl-build-and-env Trap 1).

```bash
cd /Users/montrose/Developer/GitRepositories/daily-operating-system

# All tests (the gate)
.venv/bin/python -m pytest tests/ -q

# Single file
.venv/bin/python -m pytest tests/test_storage.py -q

# Single test by name (substring match)
.venv/bin/python -m pytest -k test_week -v

# One exact test
.venv/bin/python -m pytest tests/test_storage.py::test_carry_forward_into_preexisting_day -v
```

`pyproject.toml` sets `testpaths = ["tests"]`, so `.venv/bin/python -m pytest -q` from repo root is equivalent to passing `tests/`.

Test inventory (13 files, 2026-07-09): `test_cli.py`, `test_cli_push_pull.py`, `test_display.py`, `test_models.py`, `test_persistent.py`, `test_remote_backend.py`, `test_schedule_parse.py`, `test_scheduler_logic.py`, `test_server_api.py`, `test_server_web.py`, `test_storage.py`, `test_storage_backends.py`, `test_themes.py`.

## The day_env fixture contract

`tests/conftest.py` defines one shared fixture, `day_env(tmp_path, monkeypatch)`. It:

1. Patches `storage.DATA_DIR`, `storage.DAYS_DIR`, `storage.CONFIG_PATH` to `tmp_path`.
2. Patches `storage.select_backend` to return `JSONBackend(root=tmp_path / "days")`.
3. Calls `storage._reset_backend_cache()` before yield **and** in teardown (the backend is memoized via `@lru_cache`; stale cache = tests silently sharing a backend).
4. Yields `tmp_path`.

Contract for you:

| Rule | Why |
|---|---|
| Any test that loads/saves plans MUST take `day_env` (or patch equivalents itself) | `~/.dayctl/` is the user's real data. A test without the fixture writes there. |
| `day_env` does NOT patch `dayctl.persistent.PERSISTENT_PATH` | `persistent.py` imports it by value at module load (`from dayctl.storage import PERSISTENT_PATH`), so the storage patch never reaches it. Tests touching ideas/stats/settings add `monkeypatch.setattr("dayctl.persistent.PERSISTENT_PATH", tmp_path / "persistent.json")` themselves — see `test_server_web.py::test_idea_add_delete`. Forget this and the test mutates real `~/.dayctl/persistent.json`. |
| Server tests use env vars, not `day_env` | They set `DAYCTL_STORAGE=sqlite://{tmp_path}/w.db` + call `storage._reset_backend_cache()` (see the `client` fixtures in `test_server_api.py` / `test_server_web.py`). |
| If you change backend selection or env at test time, call `_reset_backend_cache()` | Otherwise the lru_cache serves the previous test's backend. |

## Adding a test for a new CLI subcommand

Pattern from `tests/test_cli.py` — drive `main()` with patched `sys.argv`, capture stdout via a patched `StringIO`, then assert on both output and persisted state:

```python
import sys
from io import StringIO
from dayctl.cli import main
from dayctl.storage import load_plan

def _run(day_env, args: list[str], monkeypatch) -> str:
    monkeypatch.setattr(sys, "argv", ["dayctl"] + args)
    buf = StringIO()
    monkeypatch.setattr(sys, "stdout", buf)
    main()
    return buf.getvalue()

def test_mycmd(day_env, monkeypatch):
    _run(day_env, ["init", "--date", "2026-03-17"], monkeypatch)
    out = _run(day_env, ["mycmd", "--date", "2026-03-17"], monkeypatch)
    assert "expected phrase" in out                # user-visible output
    plan = load_plan("2026-03-17")
    assert plan.some_field == "expected"           # persisted state
```

Conventions: use fixed ISO dates (`2026-03-17` is a Tuesday, `2026-03-21` a Saturday — profile defaults depend on weekday); assert on both stdout AND the reloaded plan — output-only tests miss persistence bugs; remember `tasks["code"]` is the storage key behind the `app` CLI alias.

## Adding a test for storage behavior

Two layers, two patterns:

- **Facade layer** (`tests/test_storage.py`): take `day_env`, call `load_plan`/`save_plan`/`init_or_load_plan` from `dayctl.storage`. This is where carry-forward/idempotency regressions live (see `test_carry_forward_when_day_touched_before_yesterday_exists`, regression for #12 — write regression tests with the issue number in a comment).
- **Backend contract** (`tests/test_storage_backends.py`): parametrized fixture runs the same assertions against `JSONBackend` and `SQLiteBackend`. **A new backend method must be added to the `backend` parametrized contract tests, not just one backend's tests** — the fixture is `@pytest.fixture(params=["json", "sqlite"])`.

## Adding a test for a server route

Pattern from `test_server_web.py` / `test_server_api.py`:

```python
import pytest
pytest.importorskip("fastapi")          # first line — keeps core-only envs green
from fastapi.testclient import TestClient

@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("DAYCTL_TOKEN", "tok")
    monkeypatch.setenv("DAYCTL_STORAGE", f"sqlite://{tmp_path}/w.db")
    from dayctl.storage import _reset_backend_cache
    _reset_backend_cache()
    from dayctl.server.app import create_app
    c = TestClient(create_app())
    c.cookies.set("dayctl_token", "tok")   # web routes: cookie auth
    return c                                # api routes: Bearer header instead
```

Web (HTMX) routes: POST with `headers={"HX-Request": "true"}`, assert on fragment text AND on `load_plan(...)` state. API routes: `headers={"Authorization": "Bearer tok"}` (the fixture's `DAYCTL_TOKEN`), assert JSON. Keep `create_app` imports inside fixtures/tests (after env setup), not at module top.

## What a green run does NOT prove

- **No CI ran it elsewhere** — your machine's run is the whole story. A pass with a dirty venv or wrong python proves nothing about a clean checkout.
- **No lint/type checking exists** — 146 green tests coexist happily with unused imports, type errors, and dead code. Nothing checks style.
- **Server tests skip silently without fastapi** — every server test file opens with `pytest.importorskip("fastapi")`. In an env without the `[server]` extra you get a green run that never touched `src/dayctl/server/`. If your diff touches server code, the summary line must show `146 passed` (2026-07-09 baseline) with zero skips, or your server change is unverified.
- **Display/theme coverage is thin** — ANSI rendering is barely asserted; visual output changes need eyeballing (`day show`).
- **Tests never touch the real dashboard process** — `TestClient` is in-process. The launchd service runs old code until restarted (no auto-reload). A green run says nothing about what's live on port 8000.

## Manual verification: web dashboard

Tests pass ≠ dashboard works. For any server-facing change:

```bash
lsof -ti :8000  # the launchd service owns 8000 — never trust probes against it as verification of YOUR code

# Foreground dev run (Ctrl-C to stop). DAYCTL_STORAGE points at a scratch DB —
# without it the default backend reads/writes real ~/.dayctl data.
DAYCTL_STORAGE=sqlite:///tmp/dayctl-verify.db DAYCTL_TOKEN=dev .venv/bin/uvicorn dayctl.server.app:create_app --factory --port 8001

# Health probe (no auth required)
curl -s http://127.0.0.1:8001/health          # -> {"ok":true}

# Auth-gated probe
curl -s -o /dev/null -w "%{http_code}\n" http://127.0.0.1:8001/api/days   # -> 401 without token
curl -s -H "Authorization: Bearer dev" http://127.0.0.1:8001/api/days     # -> {"days":[...]}

# Browser: login sets the cookie, then exercise the changed route
open "http://127.0.0.1:8001/login?token=dev"
```

If verifying against the **launchd service** (the user's live instance), restart it first — see `dayctl-run-and-operate: THE TRAP`:

```bash
launchctl bootout   gui/$(id -u) ~/Library/LaunchAgents/com.dayos.web.plist   # stop
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.dayos.web.plist   # start
```

Per VERIFY.md V11: endpoint-change evidence is a pasted request + response including one case your change was supposed to alter — "listening on :8000" is never evidence.

## When NOT to use

- Structural/design questions (module boundaries, backend selection design, "why is it laid out this way") → `dayctl-architecture-contract`
- Installing, venv setup, `[server]` extras, dependency issues → `dayctl-build-and-env`
- Running the CLI/dashboard for normal operation, launchd agents, deploys → `dayctl-run-and-operate`
- Diagnosing a failure you can't yet explain → `dayctl-debugging-playbook` (come back here to verify the fix)

## Provenance and maintenance

All claims verified 2026-07-09 against the working tree (branch `develop`). Re-verify with:

- Test count/baseline: `.venv/bin/python -m pytest tests/ -q` → last line was `146 passed in 1.83s`
- No CI: `ls /Users/montrose/Developer/GitRepositories/daily-operating-system/.github` → `No such file or directory`
- No lint config: `ls ruff.toml .ruff.toml .flake8 setup.cfg tox.ini .pre-commit-config.yaml` (all missing) and `grep -n "ruff\|flake8\|mypy" pyproject.toml` → no hits
- Fixture contract: read `tests/conftest.py` (single `day_env` fixture, ~20 lines)
- PERSISTENT_PATH trap: `grep -n "PERSISTENT_PATH" src/dayctl/persistent.py tests/test_server_web.py`
- Test file inventory: `ls tests/`
- Dashboard probes: `grep -n "health\|launchctl" README.md` and `src/dayctl/server/api.py`
