---
name: dayctl-build-and-env
description: Use when setting up, rebuilding, or repairing the dayctl development environment in this repo — fresh clone to green tests, creating/recreating .venv, editable installs, installing the [server] extra, or diagnosing "pytest not found", "Failed to spawn process", ModuleNotFoundError for dayctl/fastapi, or homebrew-Python-vs-venv confusion.
---

# dayctl: build and environment

Runbook for recreating and verifying the dev environment of `daily-operating-system` (the `day`/`dayctl` CLI plus optional FastAPI dashboard). Everything below was executed and verified in-repo on 2026-07-09 unless marked otherwise.

## When NOT to use

| You actually need | Go to sibling skill |
|---|---|
| Why the code is layered the way it is, module boundaries, data-shape contracts | `dayctl-architecture-contract` |
| How to write/extend tests, fixtures, what evidence counts before "done" | `dayctl-validation-and-qa` |
| Running the CLI/dashboard for real use, launchd service, deploy, restart | `dayctl-run-and-operate` |
| A test is failing or behavior is wrong and the env is already healthy | `dayctl-debugging-playbook` |

This file owns env/build facts only: interpreters, venv, installs, and the traps around them.

## Environment map (verified 2026-07-09)

| Fact | Value |
|---|---|
| Repo root | `/Users/montrose/Developer/GitRepositories/daily-operating-system` |
| Build system | setuptools (src layout, `[tool.setuptools.packages.find] where = ["src"]`) |
| Package name / version | `daily-operating-system` 0.2.0 (version in `pyproject.toml`, volatile) |
| Entry points | `day` and `dayctl`, both → `dayctl.cli:main` |
| Python floor | `requires-python = ">=3.10"` |
| Actual venv Python | 3.14.6, symlinked from `/opt/homebrew/opt/python@3.14/bin/python3.14` (volatile) |
| Core runtime deps | **none** — CLI core is pure stdlib |
| `[server]` extra | fastapi, `uvicorn[standard]`, jinja2, apscheduler, httpx, python-multipart |
| Venv location | `.venv/` at repo root (gitignored; currently has server extra + pytest installed) |
| Test count | 146 passing in ~1.7s (volatile; re-run to confirm) |
| User data dir | `~/.dayctl/` — **real data on this machine**; tests never touch it (`day_env` fixture patches storage dirs to `tmp_path`) |

## Canonical command forms

Always address the venv by explicit path. Never rely on `PATH`.

```bash
cd /Users/montrose/Developer/GitRepositories/daily-operating-system

.venv/bin/python -m pytest tests/ -q     # tests — the ONLY sanctioned pytest form
.venv/bin/pip install -e .               # core (no deps)
.venv/bin/pip install -e '.[server]'     # core + dashboard extras
.venv/bin/day --help                     # CLI smoke test
```

Full run-form catalog (single file / -k / markers): dayctl-validation-and-qa.

## Trap 1: bare `pytest` fails on this machine (verified 2026-07-09)

Bare `pytest` in a Claude Code shell here is rewritten through the rtk proxy hook and **fails with "Failed to spawn process"**. Additionally, `/opt/homebrew/bin/pytest` exists but belongs to the homebrew global interpreter, not this repo's venv — even if it spawned, it would test against the wrong environment.

Rules:
- Run tests as `.venv/bin/python -m pytest ...`, nothing else.
- `.venv/bin/pytest` and `.venv/bin/py.test` exist and point at the right interpreter, but the `python -m pytest` form is the canonical one (immune to shebang/PATH ambiguity).
- If you see "Failed to spawn process" from a test command, you used bare `pytest`. Do not debug the proxy; switch forms.

## Trap 2: homebrew Python vs venv

Both `/opt/homebrew/bin/python3` and `.venv/bin/python` report the same version (3.14.6 as of 2026-07-09), which makes misfires invisible until imports break. Disambiguate with:

```bash
.venv/bin/python -c "import dayctl, sys; print(dayctl.__file__, sys.prefix)"
# expected:
# /Users/montrose/Developer/GitRepositories/daily-operating-system/src/dayctl/__init__.py  .../daily-operating-system/.venv
```

If `dayctl.__file__` is not under this repo's `src/`, or `sys.prefix` is not the repo `.venv`, you are on the wrong interpreter.

## Do NOT install globally

- Never `pip install` this package, pytest, fastapi, or anything else into homebrew Python (`/opt/homebrew/bin/pip3`) for this repo. Homebrew Python stays clean; all repo deps live in `.venv/`.
- Never `pip install daily-operating-system` non-editable — the editable install (`__editable__...pth` in site-packages) is what makes `src/` changes live without reinstall.
- Never point tests or the server at `~/.dayctl/` deliberately — that is live user data.

## Fresh clone → green tests (full rebuild runbook) (reconstructed from .claude/settings.local.json permission history; full sequence not re-executed 2026-07-09)

Use this after a fresh clone or to repair a broken `.venv` (delete it first: `rm -rf .venv`).

| # | Step | Command | Verify | Expected |
|---|---|---|---|---|
| 1 | Create venv | `python3 -m venv .venv` | `ls .venv/bin/python` | symlink exists |
| 2 | Confirm interpreter | `.venv/bin/python --version` | — | `Python 3.14.6` (any ≥3.10 acceptable) |
| 3 | Editable core install | `.venv/bin/pip install -e .` | `.venv/bin/pip show daily-operating-system \| grep -i editable` | `Editable project location: .../daily-operating-system` |
| 4 | Entry points | `.venv/bin/day --help` | — | usage text starting `usage: day <command> [options]` |
| 5 | Import path sanity | `.venv/bin/python -c "import dayctl; print(dayctl.__file__)"` | — | path under repo `src/dayctl/` |
| 6 | Test tooling | `.venv/bin/pip install pytest` | `.venv/bin/python -m pytest --version` | pytest version line [UNVERIFIED 2026-07-09: pytest is not declared in pyproject.toml (no dev/test extra), so it must be installed manually; current venv already had it] |
| 7 | Tests green | `.venv/bin/python -m pytest tests/ -q` | — | `146 passed in ~1.7s` (count volatile) |
| 8 | Server extras (only if touching `src/dayctl/server/`) | `.venv/bin/pip install -e '.[server]'` | `.venv/bin/python -c "import fastapi, uvicorn, jinja2, apscheduler, httpx"` | no output, exit 0 |

Step 1 note: `python3 -m venv .venv` uses whatever `python3` resolves to (homebrew 3.14 here) — that is fine; the venv snapshots it via symlink. This matches how the current env was rebuilt (recorded in `.claude/settings.local.json` permission history: `python3 -m venv .venv`, then `.venv/bin/pip install ...`).

Steps 3–8 are idempotent; re-run any of them freely.

## Quick health check (existing env)

```bash
cd /Users/montrose/Developer/GitRepositories/daily-operating-system
.venv/bin/python -c "import dayctl; print(dayctl.__file__)" \
  && .venv/bin/python -m pytest tests/ -q
```

Healthy output (2026-07-09): the `src/dayctl/__init__.py` path, then `146 passed in 1.69s`. Anything else → rebuild via the runbook above.

## Provenance and maintenance

Verified 2026-07-09 against repo HEAD on branch `develop`. Re-verify each claim with:

- Entry points / extras / python floor: `grep -A8 'project.scripts\|optional-dependencies\|requires-python' pyproject.toml`
- Venv interpreter + symlink: `ls -la .venv/bin/python3.14 && .venv/bin/python --version`
- Editable install: `.venv/bin/pip show daily-operating-system | grep -i editable`
- Tests: `.venv/bin/python -m pytest tests/ -q`
- CLI: `.venv/bin/day --help | head -3`
- rtk trap: attempt bare `pytest --version` in a Claude Code shell; expect spawn failure (do this only to re-confirm the trap)
