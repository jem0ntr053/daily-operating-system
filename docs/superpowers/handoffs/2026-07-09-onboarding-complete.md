# Handoff — cc-config onboarding complete, two live bugs next

Session 2026-07-09. Fresh-session state lives in docs/STATE.md (kit convention) — this doc is its superset.

## What landed
- guardrails-kit v1.0 migrated into CLAUDE.md + docs/guardrails/ (commit 8361f19; full line-accounting in docs/guardrails/MIGRATION-LOG.md; pre-migration snapshot untracked at repo root, user deletes after review).
- 5 project skills under .claude/skills/ (commit e90906a), 3-pass reviewed (FACTUAL/PROCESS/USABILITY), 34 fixes applied. `.gitignore` now `.claude/*` + `!.claude/skills/`.
- Verified: `.venv/bin/python -m pytest tests/ -q` -> 146 passed in 1.71s.

## Next session: fix the two live automation bugs (both found during review)
1. **Reminders never send.** src/dayctl/server/scheduler.py:60 `_body_for` reads `t['task']`; normalized tasks (models.py:163 `_norm_task`) carry `'text'`. KeyError is swallowed in `tick_once`'s try. Plan: write failing test for `_body_for` with a normalized task dict, fix key, run suite, `launchctl kickstart -k gui/$(id -u)/com.dayos.web` to deploy. Not yet reproduced empirically — do that first (one-liner in STATE.md Open items).
2. **Auto-init fails daily (exit 78).** /opt/homebrew/bin/day is a stale shim, shebang points at removed python@3.11. Plan: edit com.dayos.autoinit plist in ~/Library/LaunchAgents to call .venv/bin/day, kickstart, confirm exit 0 in `launchctl list | grep dayos`. Do NOT reinstall globally (dayctl-build-and-env forbids).
Both may already have chips; file GitHub issues first (issues canonical).

Then: issue #13 (creation-path unification — read dayctl-architecture-contract first), #11, #9.

## Load-bearing context
- Kit routing is live: follow CLAUDE.md TRIGGER table; never edit inside KIT CORE/FOOTER markers.
- Skills are the deep docs; dayctl-architecture-contract canonical on conflicts with PROJECT.md.
- Repo norms: user commits/merges, no Co-Authored-By, "Closes #N" in PR bodies.

## Recommended Model
- Model: sonnet
- Reason: Executing two well-specified bug fixes with written verify steps in docs/STATE.md; no design decisions remain.
- Resume: `/model sonnet`
