## Goal
Apply cc-config (guardrails kit + project skill library) to daily-operating-system and finish the repo's open work.

## Now
Onboarding complete and committed (8361f19 kit, e90906a skills). Session paused.

## Next
1. Fix scheduler reminder bug: src/dayctl/server/scheduler.py:60 `_body_for` reads `t['task']`, normalized key is `'text'` — add failing test, fix, restart com.dayos.web.
2. Fix 6 AM auto-init: /opt/homebrew/bin/day shim has dead python@3.11 shebang; repoint com.dayos.autoinit plist (~/Library/LaunchAgents) at .venv/bin/day; verify exit 0 via `launchctl list | grep dayos`.
3. Issue #13: route all day creation through init_or_load_plan (design options in .claude/skills/dayctl-architecture-contract/SKILL.md).
4. Issues #11 (Tailscale phone access), #9 (Settings view).

## Constraints
No Co-Authored-By lines in commits. GitHub issues are canonical — no markdown punchlists mirroring them. User commits/merges; put "Closes #N" in PR bodies.

## Decisions
DECISION: pytest carried in venv form (.venv/bin/python -m pytest) — bare pytest fails via rtk proxy, homebrew pytest is wrong env.
DECISION: .gitignore narrowed to `.claude/*` + `!.claude/skills/` — skill library must be committable (user-approved 2026-07-09).
DECISION: on conflict between docs/guardrails/PROJECT.md (verbatim archive) and dayctl-architecture-contract skill, the skill is canonical.

## Facts
Test command: `.venv/bin/python -m pytest tests/ -q` -> 146 passed (2026-07-09).
Dashboard: launchd com.dayos.web, port 8000, logs ~/.dayctl/web.log (installed plist diverges from repo scripts/com.dayos.web.plist which says /tmp/dayos-web.log). No auto-reload: `launchctl kickstart -k gui/$(id -u)/com.dayos.web` to deploy.
Task dict shape: `{"text","done","tag","carried"}` via _norm_task (models.py:163); "task" legacy input key only.
Kit source: ~/cc-config/kit; CLAUDE.md kit zones must stay byte-identical (upgrade = block swap).

## Done
cc-config onboarding — RESULT: kit v1.0 installed (M8 9/9 checks green), 5 skills authored + 3-pass reviewed (34 fixes applied), committed 8361f19 + e90906a; 146 tests pass.

## Open items
- Verify scheduler KeyError empirically: `.venv/bin/python -c "from dayctl.server.scheduler import _body_for; print(_body_for({'app':[{'text':'x','done':False,'tag':'','carried':False}]}))"` (expect KeyError — then fix).
- File GitHub issues for the two live bugs (issues canonical; currently only in skills/chips/memory).
- Delete CLAUDE.md.pre-migration-20260709-1054 after reviewing docs/guardrails/MIGRATION-LOG.md.
- Reconcile stale worktree .claude/worktrees/feature+web-ui-polish (uncommitted style.css/base.html/day.html changes).
- Compare ~/cc-config/kit vs plugin cache kit: `diff -rq ~/cc-config/kit /Users/montrose/.claude/plugins/cache/cc-config-marketplace/cc-config/1.0.0/kit`.

## Failed attempts
(none this session)
