# Handoff — Issue #13: route all day creation through init_or_load_plan

Paste-ready bootstrap for a fresh session. Repo: daily-operating-system, branch off `develop` (HEAD `7bc1243`). Read `.claude/skills/dayctl-architecture-contract/SKILL.md` ("Day materialization" section) BEFORE any edit — it owns the must-hold rules. Kit routing (CLAUDE.md) applies: this is a >2-file change, expect PLAN.md to fire.

## The problem (verified 2026-07-09)

Two day-creation paths exist; only one attempts carry-forward:

- SAFE: `init_or_load_plan(day, profile_key)` — `storage.py:53`; callers: CLI `cmd_init` (`cli.py:76`), web `view_day` (`web.py:74`).
- FOOTGUN: bare `load_plan(day)` → backend auto-create via `DayPlan.new` with `rolled_over=False`, no carry attempt — `json_backend.py:24`, `sqlite_backend.py:37`; callers: every other CLI handler and every web/API mutation route (`add_task`, `toggle_task`, `delete_task`, `edit_field` in `server/web.py`, plus `server/api.py` equivalents).

Since `3914a50` (#12 fix) this self-heals on the next `init_or_load_plan` visit, so this is hardening, not a live regression.

## The decision (make it FIRST, with the user)

Issue #13 lists three candidate designs; none is chosen. Present trade-offs, get the user's pick before implementing:

1. **Mutation routes call `init_or_load_plan`** — smallest diff, but every future caller must remember the rule (footgun persists structurally).
2. **Fold carry attempt into `load_plan`/backend auto-create** — single choke point, but makes `load_plan` side-effectful for all callers incl. the remote backend, and needs a profile-override story.
3. **Stop auto-creating in `load_plan`; require explicit init** — cleanest contract, biggest blast radius (every `load_plan` caller and test that relies on auto-create; `load_plan()` auto-creates is documented behavior).

## Must-hold rules (from dayctl-architecture-contract — re-read the originals)

- `rolled_over=True` only after a real predecessor existed and carry ran (contract comment `storage.py:65-70`).
- Carry idempotency: `rolled_over` flag + text dedup in `carry_forward()` (`models.py:324`).
- Carried tasks get `"carried": true`.
- `day init --force` stays delete-then-`init_or_load_plan` (`cli.py:72-76`).
- W3 (no cross-process locking) and W4 (backend lru_cache) are accepted constraints — don't "fix" them in passing.

## Acceptance (from the issue)

- No code path creates a day record without a carry-forward attempt.
- `test_carry_forward_when_day_touched_before_yesterday_exists` (and the rest of the 148) stay green.
- NEW test covering the web-mutation creation path (e.g. POST a task to a nonexistent day with a pending predecessor → carried tasks appear).

Verify: `.venv/bin/python -m pytest tests/ -q` → expect 149+ passed. Then deploy-check locally: `launchctl kickstart -k gui/$(id -u)/com.dayos.web` and exercise one mutation on a fresh day via curl (see dayctl-validation-and-qa manual block — port 8001 + sqlite temp storage for the dev-server variant).

## Workflow

Feature branch off `develop` → PR with `Closes #13` in the body (user merges). No Co-Authored-By lines. User commits nothing mid-stream; you commit on the branch.

## Recommended Model
- Model: opus
- Reason: First step is choosing among three architectural options with different blast radii; implementation follows only after that design call.
- Resume: `/model opus`
