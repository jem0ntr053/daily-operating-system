| Gap | Status | Action |
|---|---|---|
| Idea Vault bucket pills (Capture/Music/…) | omitted (I simplified to hidden "Capture") | implement |
| Idea Vault "CROSS-DISCIPLINE" tag | omitted | implement |
| Programming sprint/commits/PR counters | omitted area-stats | implement (static) |
| Social Media top counters | omitted area-stats | implement (queued = real count, rest static) |
| Marketing campaign/CTR/CPC counters | omitted area-stats | implement (static) |
| Music Studio Track/arrangement/tempo | omitted area-stats | implement (static; tempo uses bpm) |
| YouTube subs/open-tasks/next-upload | omitted area-stats | implement (open = real count, rest static) |
| Notes "TODAY" meta text | omitted | implement (per-note time already shows) |
| Week Summary week number (W22) | omitted | implement |
| Week Summary "0/6" on other days (shows "–") | I treated missing days as "–" | implement (show 0/6) |
| Streak "N logged" count | omitted | implement |
| Header "Synced" pill + "Week N / 52" | omitted | implement |

One I'm not auto-implementing — flagging for your call: the per-task tags (MIX, THUMB, ADS…). The rendering already works (you can see carried/ADS/THUMB pills on the carried tasks). They're blank on default/new tasks only because there's no way to enter a tag from the web yet. That's a small functional add (a tag field on the add-task form). Want it, or leave tags display-only for now?

---

# Frontend Progress — Daily OS Dashboard

**Date:** 2026-05-25 · **Status:** Plan 1 merged to `develop`; Plan 2 merged via **PR #10**.

A running record of the web-UI redesign that replaced the minimal post-Streamlit FastAPI page with the dark "Daily OS" dashboard.

## How it started

The web app was reported "not working." Diagnosis: the old URL (`localhost:8501`) was the retired Streamlit port, and the FastAPI replacement shipped only an 11-line stub stylesheet and a 3-section template — functional but visually bare. The user supplied a richer "Daily OS" design built in Claude Design (React + localStorage mockup: `store.jsx` + `app.jsx`, standalone HTML in iCloud). Decision: port the *look* into the existing server-rendered FastAPI + Jinja + HTMX stack (keep auth, storage, scheduler, Fly, reminders) rather than adopt the localStorage SPA. Spec: `docs/superpowers/specs/2026-05-24-web-dashboard-redesign-design.md`.

## Plan 1 — Backend foundation (merged to `develop`, 2026-05-24)

`docs/superpowers/plans/2026-05-24-dashboard-backend-foundation.md`

- 6-habit template (`fast/gym/music/ship/post/read`), scoring out of 6.
- 5 task areas (`music/youtube/marketing/social/code`) replacing `app_tasks`/`music_tasks`; legacy days migrated in `DayPlan.from_dict`.
- New `DayPlan` fields: `mood`, `bpm`, `flow_minutes`; timestamped notes (`{text,time}`).
- Flat `persistent.json` store: `ideas`, `settings`, `stats` (+ sparkline helper).
- CLI kept working on the `music`+`code` subset (`app` → `code` alias).

## Plan 2 — Web UI (PR #10)

`docs/superpowers/plans/2026-05-24-dashboard-web-ui.md` · branch `feature/dashboard-web-ui` · 144 tests passing.

**Shipped**
- Dark two-column shell; sidebar (brand `JM · v0.2`, nav groups, streak block, compact Settings control); header with date navigation + Week N/52 + Synced pill.
- Daily Pulse: 6 habit toggles + progress bar.
- At-a-glance stat cards: display ↔ edit toggle with SVG sparkline, persisted.
- Left column: Focus (focus/energy/sleep/mood/bpm inline edit), Schedule (real profile), Week Summary (per-day scores + click-to-navigate), Notes (timestamped add/delete).
- Five life-area cards (Music/YouTube/Marketing/Social/Programming): task add/toggle/delete with tags and carried pills, per-card stat rows, decorative widgets as static markup (per spec).
- Idea Vault: add / delete / inline edit text / re-categorize topic.
- Settings: accent palette (cyan/mint/amber/pink) + show-metrics toggle, wired to `/web/settings`.
- Self-hosted latin woff2 fonts (Bricolage Grotesque / Geist / JetBrains Mono) via `scripts/fetch_fonts.py`.

**Fixes surfaced during review**
- Auth cookie set `Secure` even on `http://localhost` → not stored by browsers; now `Secure` only on HTTPS, `SameSite=lax`.
- Stale `/static/style.css` cache → cache-busted with an mtime query param.
- Add-task form (text + tag inputs) lost Enter-to-submit → added a submit button.
- Web didn't carry incomplete tasks across days like the CLI → idempotent per-day carry-forward via a `rolled_over` flag on `DayPlan`.

**Verification**
- `pytest tests/` → 144 passing.
- Manually verified in Firefox + Chrome: shell, habit toggles, field edits, task add/tag/toggle/delete, notes, week navigation, idea add/edit/topic, glance display↔edit, carry-forward across days, accent switch, local fonts.

## Deferred

- **GitHub issue #9** — move the Settings control into a dedicated view under the sidebar's "Settings" nav item, as part of making the sidebar navigation functional (per-area `/area/{id}` views).

## Process note

Mid-session, success was claimed about the shell "matching the design" from a headless screenshot before the user had confirmed in their own browser — a premature claim that was corrected. Later checkpoints distinguished server-side verification from user-confirmed visual results.
