## Goal
Apply cc-config (guardrails kit + project skill library) to daily-operating-system and finish the repo's open work.

## Now
Issue #13 merged (PR #16 -> develop, 8869d0a) and deployed to live dashboard (kickstart, health 200, 2026-07-24).

## Next
1. Issues #11 (Tailscale phone access), #9 (Settings view).

## Constraints
No Co-Authored-By lines in commits. GitHub issues are canonical — no markdown punchlists mirroring them. User commits/merges; put "Closes #N" in PR bodies.

## Decisions
DECISION: pytest carried in venv form (.venv/bin/python -m pytest) — bare pytest fails via rtk proxy, homebrew pytest is wrong env.
DECISION: .gitignore narrowed to `.claude/*` + `!.claude/skills/` — skill library must be committable (user-approved 2026-07-09).
DECISION: on conflict between docs/guardrails/PROJECT.md (verbatim archive) and dayctl-architecture-contract skill, the skill is canonical.

## Facts
Test command: `.venv/bin/python -m pytest tests/ -q` -> 151 passed (2026-07-10, issue-13 branch).
Storage contract since #13 fix: backends raise KeyError on missing day; storage.load_plan delegates to init_or_load_plan (every load may create+carry).
Dashboard: launchd com.dayos.web, port 8000, logs ~/.dayctl/web.log (installed plist diverges from repo scripts/com.dayos.web.plist which says /tmp/dayos-web.log). No auto-reload: `launchctl kickstart -k gui/$(id -u)/com.dayos.web` to deploy.
Task dict shape: `{"text","done","tag","carried"}` via _norm_task (models.py:163); "task" legacy input key only.
Kit source: ~/cc-config/kit; CLAUDE.md kit zones must stay byte-identical (upgrade = block swap).

## Done
Habit module v1.1 (one-tap ntfy advance + never-miss-twice alarm) — RESULT: committed 7472a6f (advance route + post_ntfy actions + _stack_action, 9 tests) + 5907a5a (stack_complete/missed_twice + _maybe_miss_alarm, 9 tests) + d39a1a3 (NTFY_AUTH exposure warning, user-requested after a security-review notification) + 5c14eab (2 review-finding fixes: try/except around the corrupt-prior-day-file case, and gating the NTFY_AUTH warning to only fire when a nudge actually posts); 181 passed. Reviewed via mattpocock-skills:code-review two-axis over the full v1.1 range (e1d0998..HEAD): Standards found 1 real gap (missing try/except, matched against _run's existing pattern for the identical load_plan call), Spec found 1 real gap (warning fired every tick, not just on-fire) — both fixed same session; judgement calls left as-is (Poster=Callable[...,None] vs a typed Protocol, advance_task/toggle_task's small duplication, ad-hoc os.environ reads) since the axis itself called them premature to extract at current scale. Both plan deviations (Task 1 fold-in, Task 4 exists() guard) independently re-verified sound by the Spec axis. v1.1 complete — habit module v1+v1.1 both done. See docs/superpowers/plans/2026-09-01-habit-module-v1.md.
Habit module v1 MVP (evening stack) — RESULT: committed 0be3e04 (models/cli/display/api + tag="seed" carry-exclusion, 6 new tests) then e5d1739 (web dashboard _area_stack.html, 2 new tests); 159 passed. Reviewed via mattpocock-skills:code-review two-axis (Standards: 1 hard violation — RS5 sweep missed day.html include chain — found and fixed same session; Spec: 0 findings, re-scope independently verified sound). v1.1 (one-tap ntfy advance, never-miss-twice alarm) remains — see docs/superpowers/plans/2026-09-01-habit-module-v1.md Tasks 3-4.
Issue #13 fix (design 2: fold carry into load_plan) — RESULT: committed 7e53ac7; backends raise KeyError on missing day, storage.load_plan delegates to init_or_load_plan; 151 passed (+3 new tests incl. web-mutation carry); e2e curl on :8001 sqlite scratch showed carried:true. Merged via PR #16 (8869d0a), deployed via kickstart, live /health 200 (2026-07-24).
cc-config onboarding — RESULT: kit v1.0 installed (M8 9/9 checks green), 5 skills authored + 3-pass reviewed (34 fixes applied), committed 8361f19 + e90906a; 146 tests pass.
Scheduler reminder fix (#14) — RESULT: reproduced KeyError 'task' at scheduler.py:60, TDD red→green, suite 148 passed, deployed via kickstart (health=200).
Autoinit fix (#15) — RESULT: installed plist + scripts template repointed at .venv/bin/day; exit 78 → 0; log wrote "Created: 2026-07-09 (6:30 AM wake)".

## Open items
- Reminders still off in live service: com.dayos.web plist env lacks NTFY_TOPIC (and DAYCTL_ENABLE_SCHEDULER) — user must configure to activate the now-fixed path. Note separate com.dayos.notify job also exists (exit 0) — clarify which mechanism is intended.
- /opt/homebrew/bin/day PATH shim still dead — terminal `day` fails; either delete the stale shim or leave (venv is canonical).
- Delete CLAUDE.md.pre-migration-20260709-1054 after reviewing docs/guardrails/MIGRATION-LOG.md.
- Reconcile stale worktree .claude/worktrees/feature+web-ui-polish (uncommitted style.css/base.html/day.html changes).
- Compare ~/cc-config/kit vs plugin cache kit: `diff -rq ~/cc-config/kit /Users/montrose/.claude/plugins/cache/cc-config-marketplace/cc-config/1.0.0/kit`.

## Failed attempts
(none this session)

## Plan changes
PLAN CHANGE (2026-09-03): plan Task 4 Step 5's literal code calls
load_plan(d1), load_plan(d2) unconditionally for the two prior days. Reproduced
(see below): load_plan() on a never-visited date silently creates+saves a day
file via init_or_load_plan's else-branch, with a fresh all-incomplete stack.
Consequence: on first run after adoption (or after any gap where a day was
never `day init`-ed), this would fabricate 2 backfill day files polluting
history/streak/week, AND missed_twice would trivially be True (fresh stack =
incomplete) -> a false "don't miss twice" alarm on day one, not an earned one.
Evidence: HOME=<scratch> load_plan("2026-08-30") on a fresh store -> exists()
False before, True after, stack all-incomplete. Revised: _maybe_miss_alarm
checks storage.exists(d1) and exists(d2) BEFORE loading; either missing ->
skip silently (can't judge a day that was never tracked), no fabrication, no
false alarm. Still sets _alarm_date to avoid re-checking existence every tick.

PLAN CHANGE (2026-09-01): assumed carry-forward was broken (plan Task 1, from
docs/superpowers/plans/2026-09-01-habit-module-v1.md); actually reproduction via
init_or_load_plan shows real custom tasks DO carry (evidence: REAL task carried=True
across 2026-09-01→09-02), and placeholder-only days already produce carried=[] via
existing text-dedup (models.py:330) with or without a seed tag. Live ~/.dayctl/days/
2026-08-28..09-01 show 5 straight untouched-placeholder days (carried:false) — the
"doesn't carry forward" report is explained by no real task ever having been logged,
not a code defect. Revised: skip the standalone "fix" framing; fold tag="seed" into
Task 2 (stack area) instead, where it has real value — protecting the stack's forward
carry once its wording changes (user: "I will add more later"). Verified stack-area
carry needs AREAS to include "stack" first, so Task 1+2 are now one unit.
