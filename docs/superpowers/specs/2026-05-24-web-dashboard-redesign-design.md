# Web Dashboard Redesign — Design Spec

**Date:** 2026-05-24
**Status:** Approved — ready for implementation plan
**Topic:** Replace the minimal FastAPI web UI with the "Daily OS" dashboard design, server-rendered.

## Problem

The Streamlit→FastAPI migration shipped a minimal web UI: an 11-line light-mode stylesheet and a 3-section single-column template (`day.html`). It surfaces a fraction of the data model and looks unstyled (white background, serif headings). The user produced a richer "Daily OS" dashboard design in Claude Design — a dark, two-column creator dashboard with sidebar, habit pulse, life-area cards, week summary, and an idea vault.

The design ships as a **React + localStorage SPA** (`store.jsx`, `app.jsx`). Adopting it as-is would discard the server, multi-device sync, token auth, and ntfy/APScheduler push reminders the project just built ("remote access and reminders"). 

## Goals

- Reproduce the Daily OS dashboard look and interactions in the existing **server-rendered FastAPI + Jinja + HTMX** stack.
- Keep the server backend: SQLite/JSON storage, token auth, scheduler/reminders, Fly deploy.
- Extend the data model to back every *functional* element of the design (6 habits, mood/bpm/flow, multi-area tasks, timestamped notes, idea vault, manual stats).
- Render *decorative* widgets (no data/logic in the mockup) as static placeholders to preserve visual density.
- Single coherent stack — no JS build toolchain, no client-side SPA.

## Non-Goals (v1)

- No React/SPA, no JSON-API-backed client. (Revisit only if heavy client interactivity is needed later.)
- No per-area pages — the sidebar nav is **visual-only** in v1. Model and routes are structured so per-area views (`/area/{id}`) can be added later without rework.
- No real integrations (SoundCloud/YouTube/Meta APIs). Stats are manually entered, as in the mockup.
- No porting of the Claude-Design "Tweaks" preview panel (it is a design-tool harness, not part of the app).

## Approach

Port the design's **component tree and CSS** into Jinja partials wired with HTMX. The React component structure maps almost 1:1 to server-side partials; every interaction in `app.jsx` is a toggle / inline edit / add / delete — all expressible as HTMX `POST → returns HTML fragment`, the pattern the app already uses for `toggle_task`.

`store.jsx`'s `localStorage` layer is replaced by the existing `load_plan` / `save_plan` (+ a new persistent store for cross-day data). Client-only flourishes (accent palette swap, "saved" flash, sparkline append) become small CSS / inline-JS touches — no framework.

### Real vs. decorative (defines what gets a data model)

| Functional (gets real data + HTMX) | Decorative (static placeholder) |
|---|---|
| 6 habit toggles → pulse / week / streak | Music waveform, "Track 03", arrangement timer |
| focus, energy, sleep, **mood, bpm** | YouTube video rows (PUB/EDIT/SHOOT) |
| timestamped notes (add/delete) | Marketing funnel + CTR/CPC stats |
| tasks across 5 areas + carry-forward | Social post rows |
| Idea Vault (cross-day, bucketed) | Code commits / lang-bar / sprint stats |
| Glance stats (manual, w/ sparkline) | — |
| date nav (prev/next/today), week-row nav | Sidebar nav items (visual-only) |
| accent / showGlance settings | — |

Schedule: the mockup's schedule is **hardcoded mock**. The backend already has a **real, profile-driven schedule** — keep the backend's; it is strictly better.

## Data Model Changes

### DayPlan (per-day) — `models.py`

All new fields get defaults so `from_dict` stays backward-compatible with existing stored days (it filters to known fields and calls `cls(**filtered)`; missing field → default).

Add:
- `mood: str = ""`
- `bpm: str = ""`
- `flow_minutes: int = 0`

Change:
- `notes: List[str]` → `List[dict]` of `{"text": str, "time": str}`. `from_dict` normalizes legacy `str` notes to `{"text": s, "time": ""}`.
- `app_tasks` / `music_tasks` → generalized `tasks: Dict[str, List[dict]]` keyed by area, where a task is `{"text": str, "done": bool, "tag": str, "carried": bool}`. Areas: `music, youtube, marketing, social, code`. `from_dict` migrates legacy `music_tasks → tasks["music"]` and `app_tasks → tasks["code"]`, normalizing the old `{"task","done"}` shape to the new `{"text","done",...}`. There is **no `app` area** — "app work" is software work and lives under `code` (Programming), which is where the design renders it.

### Habits (6) — `models.py`

Replace `NON_NEGOTIABLE_KEYS` (4) with a `HABIT_TEMPLATE` constant of 6:

```
fast  (FAST,   "11p → 4p")
gym   (GYM,    "Push · 6:30a")
music (STUDIO, "90 min block")
ship  (SHIP,   "1 commit min")
post  (POST,   "1 short")
read  (READ,   "20 pages")
```

- `completed` is keyed by these 6 ids; `DayPlan.new` seeds all to `False`.
- `score_plan` becomes "count of completed habits" out of 6.
- `compute_streak` threshold: the mockup's streak counts days where **all** habits are done. Adopt that (threshold = `len(HABIT_TEMPLATE)`), replacing the current default of 3.
- **Migration note:** stored days carry `completed = {fast,gym,app,music}`. Reinterpreting against the 6 ids drops the old `app` flag and defaults `ship/post/read` to `False`; historical scores will read lower (max 4/6 for pre-existing data). Accepted for a redesign — no value remapping. Flagged for review.

### Persistent store (cross-day) — new

The mockup's `persistent` (ideas, settings, stats) needs a home outside per-day plans. Add a sibling **`persistent.json`** at `~/.dayctl/persistent.json`, mirroring the React `store.persistent` schema; `config.json` stays for app config only (ideas/stats are user content, settings are preferences — neither is app config). The SQLite backend gets an equivalent single key/value entry. Contents:

- `ideas: List[{from, text, created_at}]` — bucketed (Capture/Music/Content/Marketing/Code), newest-first, delete-able.
- `settings: {accent: "cyan"|"mint"|"amber"|"pink", show_glance: bool}` — `fasting_window` stays per-day (profile-driven); drop the mockup's duplicate.
- `stats: {key: {label, v, d, trend, spark: [int], updated_at}}` for `scPlays, scFollowers, ytSubs, campaigns` — manual edit; on value change, append numeric to `spark` (cap 8).
- `habitTemplate` stays a **code constant** in v1 (not user-editable; no UI edits it).

## Component → Jinja Partial Mapping

`base.html` provides the `.app` grid (sidebar + main) + `<head>` (CSS, fonts). `day.html` composes partials:

| React component | Partial | Functional? |
|---|---|---|
| `Sidebar` / `StreakBlock` | `_sidebar.html` | nav visual-only; streak real |
| `Header` (date nav, saved flash) | `_header.html` | date nav real |
| `Pulse` + habits | `_pulse.html` | real |
| `Glance` / `GlanceCard` / `Spark` | `_glance.html` | real (manual) |
| `FocusCard` (focus/energy/sleep/mood/bpm) | `_focus.html` | real |
| `ScheduleCard` | `_schedule.html` | real (backend profile) |
| `WeekCard` | `_week.html` | real |
| `NotesCard` | `_notes.html` | real |
| `MusicCard` | `_area_music.html` | tasks real; waveform/stats static |
| `YouTubeCard` | `_area_youtube.html` | tasks real; video rows static |
| `MarketingCard` | `_area_marketing.html` | tasks real; funnel static |
| `SocialCard` | `_area_social.html` | tasks real; post rows static |
| `CodeCard` | `_area_code.html` | tasks real; commits/lang static |
| `IdeasCard` | `_area_ideas.html` | real |
| `AreaCard` / `TaskListBound` | `_area_card.html`, `_task_list.html`, `_task_row.html` | real |

`_task_row.html` already exists; extend it for tags/carried/delete and the new `tasks[area]` shape.

## HTMX Routes (`web.py`)

All gated by `require_token`; all return the smallest fragment to swap. Day-scoped routes keep the `^\d{4}-\d{2}-\d{2}$` path pattern.

| Action | Method + path | Swaps |
|---|---|---|
| View day | `GET /day/{day}` | full page |
| Toggle habit | `POST /web/day/{day}/habit/{id}/toggle` | `_pulse` (incl. progress bar) |
| Edit field (focus/energy/sleep/mood/bpm) | `POST /web/day/{day}/field/{name}` | field fragment |
| Add task | `POST /web/day/{day}/tasks/{area}/add` | `_task_list` |
| Toggle task | `POST /web/day/{day}/tasks/{area}/{idx}/toggle` | `_task_row` |
| Delete task | `POST /web/day/{day}/tasks/{area}/{idx}/delete` | `_task_list` |
| Add note | `POST /web/day/{day}/notes/add` | `_notes` |
| Delete note | `POST /web/day/{day}/notes/{idx}/delete` | `_notes` |
| Add idea | `POST /web/ideas/add` | `_area_ideas` |
| Delete idea | `POST /web/ideas/{idx}/delete` | `_area_ideas` |
| Update stat | `POST /web/stats/{key}` | `_glance` card |
| Set accent / showGlance | `POST /web/settings` | re-render or set CSS var |

Date navigation is plain links/`hx-get` to `/day/{iso}` (prev/next/today, week-row click).

## CSS & Fonts

- Replace the 11-line `static/style.css` with the design's stylesheet (extracted verbatim: `:root` palette, `.app` grid, sidebar, pulse, cards, areas, responsive breakpoints at 1280/980px).
- Fonts: **self-hosted** latin-subset woff2 under `static/fonts/`, trimmed to the weights the CSS uses (Bricolage Grotesque 500/600/700, Geist 300–600, JetBrains Mono 400–600). ~100–200 KB total. No third-party (Google Fonts) request — works offline / on Fly. `@font-face` rules point at local paths.
- Accent palette applied via `--cyan`/`--purple` CSS variables, switched from `settings.accent`.

## CLI & Display Impact (blast radius)

Changing the core model ripples beyond the web layer. In scope:

- `cli.py`: task subcommands assume `app_tasks`/`music_tasks`; update to the `tasks[area]` model. **CLI manages a subset — `music` and `code`** (the web manages all 5 areas). The old `app` command becomes a **deprecated alias → `code`** so muscle memory and the 6am launchd auto-init keep working. Habit completion commands move from 4 keys to 6.
- `display.py`: `print_plan` / score table render notes as `str` and score as `/4`; update for `{text,time}` notes and `/6` scoring.
- `models.py`: `incomplete_tasks` / `carry_forward` iterate `("app_tasks","music_tasks")`; generalize to iterate `tasks` areas (carry-forward marks `carried=True`, matching the mockup's rollover).
- Tests: `test_cli.py` and model/scoring/streak tests will need updates for 6 habits, `/6`, new task shape, and timestamped notes.

## Storage Migration

- JSON backend: handled transparently by `from_dict` normalization (legacy notes, legacy task fields, missing new fields). No file rewrite needed; days upgrade on load.
- SQLite backend: confirm it serializes via `to_dict`/`from_dict` so the same normalization applies; add the persistent key/value storage for ideas/settings/stats.
- Provide a one-time check that loading every existing day under the new model does not raise.

## Phasing (for the implementation plan)

1. **Model + storage** — extend `DayPlan`, `HABIT_TEMPLATE`, scoring/streak, `from_dict` migration, persistent store, carry-forward generalization. Tests green.
2. **Design system + shell (fidelity checkpoint)** — drop in CSS + fonts; build `base.html` + sidebar/header/pulse/grid rendering **real data, no new actions**. Compare to mockup, confirm before continuing.
3. **Functional cards + HTMX routes** — focus/notes/tasks/week/glance/ideas/habits/date-nav/settings, one route + fragment each.
4. **Static placeholder widgets** — waveform, video rows, funnel, post rows, commits/lang-bar inside their area cards.
5. **CLI + display alignment** — update CLI/display for the new model; tests green.
6. **Verify** — run server, diff against mockup screenshot, run test suite, manual test plan → PR.

## Resolved decisions

1. **Habit migration:** drop old `app` completion, no value remap; pre-existing days read lower (max 4/6). Accepted.
2. **Task-area mapping:** legacy `app_tasks → tasks["code"]`, `music_tasks → tasks["music"]`. No separate `app` area — "app work" lives under `code`.
3. **CLI vocabulary:** CLI manages the `music` + `code` subset; old `app` command becomes a deprecated alias → `code`. Web manages all 5 areas.
4. **Fonts:** self-hosted latin-subset woff2, trimmed to used weights.
5. **Persistent store:** new `persistent.json` (mirrors `store.persistent`); `config.json` stays app-config only.
