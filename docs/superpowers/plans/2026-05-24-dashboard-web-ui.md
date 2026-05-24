# Dashboard Web UI — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers-extended-cc:subagent-driven-development (recommended) or superpowers-extended-cc:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Render the "Daily OS" dashboard design as the dayctl web UI — dark two-column layout, sidebar, habit pulse, life-area cards, week summary, idea vault — server-rendered with Jinja + HTMX against the Plan-1 backend.

**Architecture:** Plan 2 of 2. Keeps the existing FastAPI server (auth, storage, scheduler, Fly). The React/localStorage mockup (`app.jsx`/`store.jsx`) is the visual+behavioral reference, NOT shipped — every interaction becomes an HTMX `POST → HTML fragment` against `load_plan`/`save_plan` and `persistent.py`. A thin view-model builder feeds templates; routes stay small.

**Tech Stack:** FastAPI, Jinja2, HTMX 1.9.12 (already loaded via CDN in `base.html`), hand-written CSS. No JS build step, no new Python deps.

**Spec:** `docs/superpowers/specs/2026-05-24-web-dashboard-redesign-design.md`

## Design source files (ground truth — read these for verbatim CSS/markup)
- **CSS:** the second `<style>` block (the `:root`/`.app`/cards CSS, ~280 lines) in `~/Library/Mobile Documents/com~apple~CloudDocs/Sites/Daily Opr/Daily OS _standalone_.html`. A clean extraction already exists at `/tmp/nf_template.html` (lines ~441–725). Implementers must re-derive it from the iCloud file if `/tmp` is gone.
- **Components/behavior:** `~/Downloads/app.jsx` (component tree, markup, which widgets are real vs. mock) and `~/Downloads/store.jsx` (data shapes, derived week/streak logic).

## Environment
Editable install, venv at repo root. Run the server with `DAYCTL_TOKEN=devtoken .venv/bin/uvicorn dayctl.server.app:create_app --factory --port 8000`. Run tests with `.venv/bin/python -m pytest tests/ -q` from repo root. Login URL: `http://127.0.0.1:8000/login?token=devtoken`.

## Backend contract available (from Plan 1)
- `dayctl.models`: `HABIT_TEMPLATE` (list of `{id,name,meta}`), `HABIT_KEYS`, `AREAS` (`["music","youtube","marketing","social","code"]`), `score_plan(plan)→0..6`, `compute_streak(day_scores, threshold)`, `week_dates(iso)→[7 Mon–Sun isos]`, `profile_for_date`, `SCHEDULE_PROFILES[key]["label"]`, `_norm_task`.
- `DayPlan` fields: `day, profile, focus, energy, sleep_hours, fasting_window, schedule (list "TIME  Activity"), completed (dict by habit id), tasks (dict by area → list of {text,done,tag,carried}), notes (list of {text,time}), mood, bpm, flow_minutes`.
- `dayctl.storage`: `load_plan, save_plan, list_days, exists`.
- `dayctl.persistent`: `load_persistent()→{ideas, settings:{accent,show_glance}, stats:{key:{label,v,d,trend,spark,updated_at}}}`, `save_persistent(data)`, `update_stat(data, key, patch)`.
- `dayctl.server.auth.require_token`; `web.py` uses cookie `dayctl_token`.

---

## File Structure

| File | Responsibility | Change |
|---|---|---|
| `src/dayctl/server/static/style.css` | Full design CSS | Replace stub |
| `src/dayctl/server/static/fonts/*.woff2` | Self-hosted fonts | Create (Task 8) |
| `src/dayctl/server/templates/base.html` | `.app` shell, `<head>` | Rewrite |
| `src/dayctl/server/templates/day.html` | Compose partials | Rewrite |
| `src/dayctl/server/templates/_sidebar.html` `_header.html` `_pulse.html` `_focus.html` `_schedule.html` `_week.html` `_notes.html` `_glance.html` | Dashboard sections | Create |
| `src/dayctl/server/templates/_area_card.html` `_task_list.html` `_task_row.html` `_area_*.html` (music/youtube/marketing/social/code/ideas) | Life-area cards | Create / rewrite `_task_row` |
| `src/dayctl/server/viewmodel.py` | Build day-view context (week, streak, parsed schedule) | Create |
| `src/dayctl/server/web.py` | HTMX routes | Rewrite/extend |
| `tests/test_server_web.py` | Web route + render tests | Extend |

**Interaction model (every route gated by `require_token`, returns the smallest fragment):**

| Action | Method + path | Returns |
|---|---|---|
| View day | `GET /day/{day}` | full page |
| Toggle habit | `POST /web/day/{day}/habit/{id}/toggle` | `_pulse.html` |
| Edit field | `POST /web/day/{day}/field/{name}` (name∈focus,energy,sleep,mood,bpm) | field fragment |
| Add task | `POST /web/day/{day}/tasks/{area}/add` | `_task_list.html` |
| Toggle task | `POST /web/day/{day}/tasks/{area}/{idx}/toggle` | `_task_row.html` |
| Delete task | `POST /web/day/{day}/tasks/{area}/{idx}/delete` | `_task_list.html` |
| Add note | `POST /web/day/{day}/notes/add` | `_notes.html` |
| Delete note | `POST /web/day/{day}/notes/{idx}/delete` | `_notes.html` |
| Add idea | `POST /web/ideas/add` | `_area_ideas.html` |
| Delete idea | `POST /web/ideas/{idx}/delete` | `_area_ideas.html` |
| Update stat | `POST /web/stats/{key}` | `_glance.html` |
| Update settings | `POST /web/settings` | redirect to `/day/{today}` |

---

### Task 1: Design system + app shell + sidebar/header (fidelity checkpoint)

**Goal:** Replace the stub CSS with the design CSS, rewrite `base.html` into the `.app` shell, and render a dark two-column page with a working sidebar and header (real date/profile/date-nav) — no pulse/cards yet. This is the visual checkpoint before wiring interactions.

**Files:**
- Replace: `src/dayctl/server/static/style.css`
- Rewrite: `src/dayctl/server/templates/base.html`, `src/dayctl/server/templates/day.html`
- Create: `src/dayctl/server/templates/_sidebar.html`, `_header.html`, `src/dayctl/server/viewmodel.py`
- Modify: `src/dayctl/server/web.py` (`view_day` uses viewmodel)
- Test: `tests/test_server_web.py`

**Acceptance Criteria:**
- [ ] `style.css` is the design CSS (dark `--bg:#0d1626`, `.app` grid, sidebar, header, card rules). Font-families keep system fallbacks (`"Geist", -apple-system, system-ui, sans-serif` etc.) so it works before Task 8.
- [ ] `GET /day/{today}` returns 200 containing `class="app"`, the brand `Daily OS`, the formatted date, the profile label, and the `date-nav` TODAY control.
- [ ] Date-nav prev/next/today are links to `/day/{iso}`.
- [ ] Existing tests still pass.

**Verify:** `.venv/bin/python -m pytest tests/test_server_web.py -q` → pass; manual: login URL renders dark sidebar+header.

**Steps:**

- [ ] **Step 1: Install the CSS.** Extract the second `<style>` block (the app CSS beginning at `:root {`, NOT the `@font-face` block) from the design source and write it verbatim as `src/dayctl/server/static/style.css`. Source: `/tmp/nf_template.html` lines ~442–725 (or re-extract from the iCloud standalone HTML). Do not modify the rules; the `font-family` declarations already include system fallbacks.

- [ ] **Step 2: Create `src/dayctl/server/viewmodel.py`:**
```python
"""Build the day-view context for templates."""
from __future__ import annotations

from datetime import date, timedelta

from dayctl.models import (
    HABIT_TEMPLATE, HABIT_KEYS, SCHEDULE_PROFILES,
    compute_streak, profile_for_date, score_plan, week_dates,
)
from dayctl.persistent import load_persistent
from dayctl.storage import exists, list_days, load_plan


def _profile_label(plan) -> str:
    prof = SCHEDULE_PROFILES.get(plan.profile)
    return prof["label"] if prof else profile_for_date(plan.day)["label"]


def _parse_schedule(plan) -> list[dict]:
    rows = []
    for line in plan.schedule:
        parts = line.split("  ", 1)
        if len(parts) == 2:
            rows.append({"time": parts[0].strip(), "title": parts[1].strip()})
        else:
            rows.append({"time": "", "title": line.strip()})
    return rows


def _week(day: str) -> list[dict]:
    today = date.today().isoformat()
    out = []
    for iso in week_dates(day):
        wscore = score_plan(load_plan(iso)) if exists(iso) else None
        out.append({
            "iso": iso,
            "label": date.fromisoformat(iso).strftime("%a %m/%d"),
            "score": wscore,
            "total": len(HABIT_KEYS),
            "is_today": iso == today,
            "is_view": iso == day,
            "is_future": iso > today,
        })
    return out


def _streak() -> int:
    days = sorted(list_days())
    scores = [(d, score_plan(load_plan(d))) for d in days]
    return compute_streak(scores, threshold=len(HABIT_KEYS))


def build_day_view(day: str) -> dict:
    plan = load_plan(day)
    today = date.today().isoformat()
    return {
        "plan": plan,
        "day": day,
        "score": score_plan(plan),
        "habits": HABIT_TEMPLATE,
        "total": len(HABIT_KEYS),
        "schedule": _parse_schedule(plan),
        "week": _week(day),
        "streak": _streak(),
        "profile_label": _profile_label(plan),
        "persistent": load_persistent(),
        "is_today": day == today,
        "prev_day": (date.fromisoformat(day) - timedelta(days=1)).isoformat(),
        "next_day": (date.fromisoformat(day) + timedelta(days=1)).isoformat(),
        "today": today,
        "date_long": date.fromisoformat(day).strftime("%A, %B %-d"),
    }
```

- [ ] **Step 3: Rewrite `base.html`:**
```html
<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Daily OS — {{ day }}</title>
<link rel="stylesheet" href="/static/style.css">
<script src="https://unpkg.com/htmx.org@1.9.12"></script>
</head>
<body{% if persistent and persistent.settings.accent and persistent.settings.accent != 'cyan' %} data-accent="{{ persistent.settings.accent }}"{% endif %}>
<div class="app">
  {% include "_sidebar.html" %}
  <main class="main">
    {% block main %}{% endblock %}
  </main>
</div>
</body>
</html>
```

- [ ] **Step 4: Create `_sidebar.html`** — translate the `Sidebar` + `StreakBlock` components from `app.jsx` (the `NAV` const groups Today/Craft/Growth/System, the brand block, and the streak block). Nav items are static and non-interactive in v1 (no links yet). Use the real `streak` value and `score`/`total` for the streak block. Concrete skeleton:
```html
<aside class="side">
  <div class="brand">
    <div class="brand-mark">D</div>
    <div><div class="brand-name">Daily OS</div><div class="brand-sub">dayctl</div></div>
  </div>
  {# NAV groups: copy the labels/badges/colors from app.jsx NAV; render nav-item divs (no href in v1) #}
  <div class="nav-section">
    <div class="nav-label"><span>Today</span></div>
    <div class="nav-item active"><span class="dot"></span><span>Dashboard</span><span class="badge">•</span></div>
    {# ...Schedule, Inbox, then Craft/Growth/System groups per app.jsx... #}
  </div>
  <div class="side-foot">
    <div class="streak">
      <div class="streak-row"><div class="streak-num">{{ streak }}</div><div class="streak-label">day streak</div></div>
      <div class="streak-dots">{% for i in range(14) %}<span></span>{% endfor %}</div>
      <div style="margin-top:10px;font-family:'JetBrains Mono';font-size:10px;color:var(--text-mute);letter-spacing:.08em;text-transform:uppercase;">Today · {{ score }}/{{ total }}</div>
    </div>
  </div>
</aside>
```
(The 14 streak dots may be left inert for v1; if quick, color them from the week data. Keep it simple.)

- [ ] **Step 5: Create `_header.html`** — translate the `Header` component. Real data: date (`date_long`), profile label, fasting window (`plan.fasting_window`), and the date-nav as links:
```html
<div class="head">
  <div class="head-l">
    <h1>{{ date_long }}{% if not is_today %}<span class="day-tag {{ 'future' if day > today else 'past' }}">{{ 'future' if day > today else 'past' }}</span>{% else %}<span class="day-tag">today</span>{% endif %}</h1>
    <div class="sub">{{ profile_label }}<span class="sep">·</span><span class="mono">Fasting {{ plan.fasting_window }}</span></div>
  </div>
  <div class="head-r">
    <div class="date-nav">
      <a href="/day/{{ prev_day }}" title="Previous day"><button>‹</button></a>
      <a href="/day/{{ today }}"><button class="today-btn{% if is_today %} viewing-today{% endif %}">TODAY</button></a>
      <a href="/day/{{ next_day }}" title="Next day"><button>›</button></a>
    </div>
  </div>
</div>
```

- [ ] **Step 6: Rewrite `day.html`:**
```html
{% extends "base.html" %}
{% block main %}
  {% include "_header.html" %}
  {# pulse, glance, grid added in later tasks #}
{% endblock %}
```

- [ ] **Step 7: Update `view_day` in `web.py`** to use the viewmodel:
```python
from dayctl.server.viewmodel import build_day_view
...
@router.get("/day/{day}", response_class=HTMLResponse, dependencies=[Depends(require_token)])
def view_day(request: Request, day: str = PathParam(..., pattern=_DAY_PATTERN)) -> HTMLResponse:
    ctx = build_day_view(day)
    ctx["request"] = request
    return templates.TemplateResponse(request, "day.html", ctx)
```

- [ ] **Step 8: Test.** In `tests/test_server_web.py`, add a render test (follow the existing pattern in that file for building a test client with `DAYCTL_TOKEN` + cookie):
```python
def test_day_page_renders_shell(client):
    r = client.get("/day/2026-05-24")
    assert r.status_code == 200
    body = r.text
    assert 'class="app"' in body
    assert "Daily OS" in body
    assert "date-nav" in body
```
(Reuse the existing fixture/login helper in the file; if none, replicate how `test_server_web.py` currently authenticates.)

- [ ] **Step 9:** Run `.venv/bin/python -m pytest tests/ -q` → green. Manually start the server and confirm the dark shell renders. Commit:
```bash
git add src/dayctl/server/static/style.css src/dayctl/server/templates/base.html src/dayctl/server/templates/day.html src/dayctl/server/templates/_sidebar.html src/dayctl/server/templates/_header.html src/dayctl/server/viewmodel.py src/dayctl/server/web.py tests/test_server_web.py
git commit -m "feat(web): dark dashboard shell — CSS, base layout, sidebar, header"
```

---

### Task 2: Pulse bar + habit toggles

**Goal:** Render the daily pulse (progress bar + 6 habit cards) and wire habit toggling via HTMX.

**Files:** Create `src/dayctl/server/templates/_pulse.html`; modify `day.html`, `src/dayctl/server/web.py`, `tests/test_server_web.py`.

**Acceptance Criteria:**
- [ ] `_pulse.html` renders a `.pulse` block: title + `{{ score }}/{{ total }}` + progress bar at `score/total*100`%, and `.habits` grid of 6 cards from `habits`, each `.habit` (`.done` when `plan.completed[id]`), showing `name` and `meta`.
- [ ] `POST /web/day/{day}/habit/{id}/toggle` flips `plan.completed[id]`, saves, returns the re-rendered `_pulse.html`.
- [ ] Clicking a habit toggles it and updates the bar (HTMX swaps `#pulse`).

**Verify:** `.venv/bin/python -m pytest tests/test_server_web.py -q` → pass.

**Steps:**

- [ ] **Step 1:** Write failing route test:
```python
def test_toggle_habit_flips_and_returns_pulse(client):
    r = client.post("/web/day/2026-05-24/habit/fast/toggle", headers={"HX-Request": "true"})
    assert r.status_code == 200
    assert "pulse" in r.text
    from dayctl.storage import load_plan
    assert load_plan("2026-05-24").completed["fast"] is True
```

- [ ] **Step 2:** Create `_pulse.html` (translate `Pulse` from `app.jsx`). Root element id `pulse` for swap targeting:
```html
<div class="pulse" id="pulse">
  <div class="pulse-top">
    <div class="pulse-title">Daily Pulse <span class="frac">{{ score }}/{{ total }}</span></div>
    <div class="pulse-bar"><i style="width: {{ (score / total * 100) | round }}%"></i></div>
    <div class="pulse-time">{% if plan.flow_minutes %}{{ plan.flow_minutes // 60 }}h {{ plan.flow_minutes % 60 }}m flow{% else %}tap to mark complete{% endif %}</div>
  </div>
  <div class="habits">
    {% for h in habits %}
    <div class="habit{% if plan.completed.get(h.id) %} done{% endif %}"
         hx-post="/web/day/{{ day }}/habit/{{ h.id }}/toggle"
         hx-target="#pulse" hx-swap="outerHTML">
      <div class="habit-row"><span class="habit-name">{{ h.name }}</span><span class="habit-check">{% if plan.completed.get(h.id) %}✓{% endif %}</span></div>
      <div class="habit-meta">{{ h.meta }}</div>
    </div>
    {% endfor %}
  </div>
</div>
```

- [ ] **Step 3:** Add the route to `web.py` (add `from dayctl.models import HABIT_KEYS`):
```python
@router.post("/web/day/{day}/habit/{habit_id}/toggle", response_class=HTMLResponse, dependencies=[Depends(require_token)])
def toggle_habit(request: Request, habit_id: str, day: str = PathParam(..., pattern=_DAY_PATTERN)) -> HTMLResponse:
    if habit_id not in HABIT_KEYS:
        raise HTTPException(404, "unknown habit")
    plan = load_plan(day)
    plan.completed[habit_id] = not plan.completed.get(habit_id, False)
    save_plan(plan)
    ctx = build_day_view(day)
    ctx["request"] = request
    return templates.TemplateResponse(request, "_pulse.html", ctx)
```

- [ ] **Step 4:** Add `{% include "_pulse.html" %}` to `day.html` after the header.

- [ ] **Step 5:** Run tests green, commit:
```bash
git add src/dayctl/server/templates/_pulse.html src/dayctl/server/templates/day.html src/dayctl/server/web.py tests/test_server_web.py
git commit -m "feat(web): pulse bar with habit toggles"
```

---

### Task 3: Focus card (inline-edit fields) + Schedule card

**Goal:** Left-column Focus card with inline-editable focus/energy/sleep/mood/bpm, and the Schedule card from the real profile schedule.

**Files:** Create `_focus.html`, `_schedule.html`; modify `day.html`, `web.py`, `tests/test_server_web.py`.

**Acceptance Criteria:**
- [ ] `_focus.html`: a textarea for `focus` and inputs for energy/sleep/mood/bpm, each posting on change to `/web/day/{day}/field/{name}` and persisting.
- [ ] `POST /web/day/{day}/field/{name}` maps name→attr (`sleep`→`sleep_hours`, others 1:1), saves, returns a tiny confirmation fragment (or 204).
- [ ] `_schedule.html` renders `schedule` rows (`time` + `title`) using `.sched-row`.

**Verify:** `.venv/bin/python -m pytest tests/test_server_web.py -q` → pass.

**Steps:**

- [ ] **Step 1:** Failing test:
```python
def test_edit_field_persists(client):
    r = client.post("/web/day/2026-05-24/field/focus", data={"value": "ship the UI"}, headers={"HX-Request": "true"})
    assert r.status_code in (200, 204)
    from dayctl.storage import load_plan
    assert load_plan("2026-05-24").focus == "ship the UI"

def test_edit_sleep_maps_to_sleep_hours(client):
    client.post("/web/day/2026-05-24/field/sleep", data={"value": "7.5"}, headers={"HX-Request": "true"})
    from dayctl.storage import load_plan
    assert load_plan("2026-05-24").sleep_hours == "7.5"
```

- [ ] **Step 2:** Add the field route to `web.py`:
```python
from fastapi import Form

_FIELD_ATTR = {"focus": "focus", "energy": "energy", "sleep": "sleep_hours", "mood": "mood", "bpm": "bpm"}

@router.post("/web/day/{day}/field/{name}", response_class=HTMLResponse, dependencies=[Depends(require_token)])
def edit_field(name: str, value: str = Form(""), day: str = PathParam(..., pattern=_DAY_PATTERN)) -> HTMLResponse:
    attr = _FIELD_ATTR.get(name)
    if attr is None:
        raise HTTPException(404, "unknown field")
    plan = load_plan(day)
    setattr(plan, attr, value)
    save_plan(plan)
    return HTMLResponse('<span class="saved"><span class="dot"></span>Saved</span>')
```

- [ ] **Step 3:** Create `_focus.html` (translate `FocusCard`). Each field posts on change; `hx-swap="none"` (fire-and-forget) or target a small saved indicator. Concrete:
```html
<div class="card">
  <h3><span><span class="icon-dot" style="background:var(--cyan)"></span>Today's Focus</span><span class="meta">#1 priority</span></h3>
  <div class="field">
    <textarea name="value" placeholder="What is the ONE thing today?"
      hx-post="/web/day/{{ day }}/field/focus" hx-trigger="change" hx-swap="none">{{ plan.focus }}</textarea>
  </div>
  <div class="focus-row">
    <div class="field"><label>Energy</label><input name="value" value="{{ plan.energy }}" placeholder="low / med / high" hx-post="/web/day/{{ day }}/field/energy" hx-trigger="change" hx-swap="none"></div>
    <div class="field"><label>Sleep (hrs)</label><input name="value" value="{{ plan.sleep_hours }}" hx-post="/web/day/{{ day }}/field/sleep" hx-trigger="change" hx-swap="none"></div>
  </div>
  <div class="focus-row" style="margin-top:10px">
    <div class="field"><label>Mood</label><input name="value" value="{{ plan.mood }}" placeholder="locked-in / scattered" hx-post="/web/day/{{ day }}/field/mood" hx-trigger="change" hx-swap="none"></div>
    <div class="field"><label>BPM target</label><input name="value" value="{{ plan.bpm }}" hx-post="/web/day/{{ day }}/field/bpm" hx-trigger="change" hx-swap="none"></div>
  </div>
</div>
```

- [ ] **Step 4:** Create `_schedule.html` (translate `ScheduleCard`, using real `schedule`):
```html
<div class="card">
  <h3><span><span class="icon-dot" style="background:var(--purple)"></span>Schedule</span><span class="meta">{{ schedule|length }} BLOCKS</span></h3>
  <div style="padding-left:6px">
    {% for s in schedule %}
    <div class="sched-row"><div class="sched-time">{{ s.time }}</div><div class="sched-block"><div class="title">{{ s.title }}</div></div></div>
    {% endfor %}
  </div>
</div>
```

- [ ] **Step 5:** Add the two-column grid to `day.html` after `_pulse`:
```html
<div class="grid">
  <div class="col">
    {% include "_focus.html" %}
    {% include "_schedule.html" %}
    {# _week, _notes added in Task 4/5 #}
  </div>
  <div class="col">
    {# area cards added in Task 6 #}
  </div>
</div>
```

- [ ] **Step 6:** Tests green, commit:
```bash
git add src/dayctl/server/templates/_focus.html src/dayctl/server/templates/_schedule.html src/dayctl/server/templates/day.html src/dayctl/server/web.py tests/test_server_web.py
git commit -m "feat(web): focus card inline edits + schedule card"
```

---

### Task 4: Week Summary card + real streak/date navigation

**Goal:** Week Summary card with per-day scores and click-to-navigate; ensure streak/dots reflect real data.

**Files:** Create `_week.html`; modify `day.html`, `_sidebar.html` (streak dots from week), `tests/test_server_web.py`.

**Acceptance Criteria:**
- [ ] `_week.html` renders 7 `.week-row` items from `week`, each showing label + dots (filled up to `score`) + `score/total` (or `–` when `score is None`), the viewed day marked `.viewing`, future days `.future`.
- [ ] Each row links to `/day/{iso}`.
- [ ] No new route needed (navigation reuses `GET /day/{day}`).

**Verify:** `.venv/bin/python -m pytest tests/test_server_web.py -q` → pass.

**Steps:**

- [ ] **Step 1:** Failing test:
```python
def test_week_card_links_and_scores(client):
    client.post("/web/day/2026-05-24/habit/fast/toggle", headers={"HX-Request": "true"})
    r = client.get("/day/2026-05-24")
    assert 'href="/day/2026-05-2' in r.text   # week rows link to days
    assert "week-row" in r.text
```

- [ ] **Step 2:** Create `_week.html` (translate `WeekCard`):
```html
<div class="card">
  <h3><span><span class="icon-dot" style="background:var(--green)"></span>Week Summary</span></h3>
  {% for w in week %}
  <a href="/day/{{ w.iso }}" class="week-row{% if w.is_view %} viewing{% endif %}{% if w.is_future %} future{% endif %}" style="text-decoration:none">
    <span><span class="caret">{% if w.is_view %}▸{% endif %}</span> {{ w.label }}</span>
    <div style="display:flex;gap:12px;align-items:center">
      <div class="dots">{% for i in range(w.total) %}<span class="{% if w.score and i < w.score %}on{% endif %}"></span>{% endfor %}</div>
      <span class="frac">{% if w.score is none %}–{% else %}{{ w.score }}/{{ w.total }}{% endif %}</span>
    </div>
  </a>
  {% endfor %}
</div>
```

- [ ] **Step 3:** Add `{% include "_week.html" %}` to the left `.col` in `day.html` (after schedule).

- [ ] **Step 4:** Update `_sidebar.html` streak dots to reflect `week` (color dots `.on` where a week day's `score == total`, `.half` where `score > 0`). Replace the inert 14-dot loop with:
```html
<div class="streak-dots">{% for w in week %}<span class="{% if w.score == w.total %}on{% elif w.score %}half{% endif %}"></span>{% endfor %}</div>
```
(7 dots from the current week is fine for v1 — simpler than the mockup's 14.)

- [ ] **Step 5:** Tests green, commit:
```bash
git add src/dayctl/server/templates/_week.html src/dayctl/server/templates/_sidebar.html src/dayctl/server/templates/day.html tests/test_server_web.py
git commit -m "feat(web): week summary card with navigation + real streak dots"
```

---

### Task 5: Notes card (add/delete, timestamped)

**Goal:** Notes card that lists timestamped notes and supports add (Enter) and delete (click), via HTMX fragments.

**Files:** Create `_notes.html`; modify `day.html`, `web.py`, `tests/test_server_web.py`.

**Acceptance Criteria:**
- [ ] `_notes.html` (root id `notes`) lists `plan.notes` (`{text,time}`); an add input posts to `/web/day/{day}/notes/add`; each note deletes via `/web/day/{day}/notes/{idx}/delete`.
- [ ] Add route stamps `HH:MM`, saves, returns `_notes.html`. Delete route removes by index, returns `_notes.html`.

**Verify:** `.venv/bin/python -m pytest tests/test_server_web.py -q` → pass.

**Steps:**

- [ ] **Step 1:** Failing tests:
```python
def test_add_and_delete_note(client):
    r = client.post("/web/day/2026-05-24/notes/add", data={"text": "felt good"}, headers={"HX-Request": "true"})
    assert r.status_code == 200 and "felt good" in r.text
    from dayctl.storage import load_plan
    assert load_plan("2026-05-24").notes[0]["text"] == "felt good"
    r2 = client.post("/web/day/2026-05-24/notes/0/delete", headers={"HX-Request": "true"})
    assert "felt good" not in r2.text
    assert load_plan("2026-05-24").notes == []
```

- [ ] **Step 2:** Routes in `web.py`:
```python
from datetime import datetime

@router.post("/web/day/{day}/notes/add", response_class=HTMLResponse, dependencies=[Depends(require_token)])
def add_note(request: Request, text: str = Form(""), day: str = PathParam(..., pattern=_DAY_PATTERN)) -> HTMLResponse:
    plan = load_plan(day)
    if text.strip():
        now = datetime.now()
        plan.notes.append({"text": text.strip(), "time": f"{now.hour:02d}:{now.minute:02d}"})
        save_plan(plan)
    ctx = build_day_view(day); ctx["request"] = request
    return templates.TemplateResponse(request, "_notes.html", ctx)

@router.post("/web/day/{day}/notes/{idx}/delete", response_class=HTMLResponse, dependencies=[Depends(require_token)])
def delete_note(request: Request, idx: int, day: str = PathParam(..., pattern=_DAY_PATTERN)) -> HTMLResponse:
    plan = load_plan(day)
    if 0 <= idx < len(plan.notes):
        plan.notes.pop(idx)
        save_plan(plan)
    ctx = build_day_view(day); ctx["request"] = request
    return templates.TemplateResponse(request, "_notes.html", ctx)
```

- [ ] **Step 3:** Create `_notes.html` (translate `NotesCard`):
```html
<div class="card" id="notes">
  <h3><span><span class="icon-dot" style="background:var(--yellow)"></span>Notes</span><span class="meta">{{ plan.notes|length }}</span></h3>
  {% if not plan.notes %}<div style="font-size:12px;color:var(--text-mute);padding:8px 4px 0">No notes yet.</div>{% endif %}
  {% for n in plan.notes %}
  <div class="note" hx-post="/web/day/{{ day }}/notes/{{ loop.index0 }}/delete" hx-target="#notes" hx-swap="outerHTML" title="Click to delete" style="cursor:pointer">
    <span class="bullet">›</span><span>{{ n.text }}</span><span class="note-time">{{ n.time }}</span>
  </div>
  {% endfor %}
  <form class="task-add" style="margin-top:10px" hx-post="/web/day/{{ day }}/notes/add" hx-target="#notes" hx-swap="outerHTML" hx-on::after-request="this.reset()">
    <span>+</span><input name="text" placeholder="Quick capture — Enter to commit">
  </form>
</div>
```

- [ ] **Step 4:** Add `{% include "_notes.html" %}` to the left `.col` (after week). Tests green, commit:
```bash
git add src/dayctl/server/templates/_notes.html src/dayctl/server/templates/day.html src/dayctl/server/web.py tests/test_server_web.py
git commit -m "feat(web): notes card add/delete"
```

---

### Task 6: Life-area cards + task lists (5 areas) + static widgets

**Goal:** Right-column area cards (Music/YouTube/Marketing/Social/Code) with working task lists (add/toggle/delete) and the mockup's decorative widgets rendered as static markup; rewrite `_task_row.html` to the new shape.

**Files:** Create `_area_card.html`, `_task_list.html`, `_area_music.html`, `_area_youtube.html`, `_area_marketing.html`, `_area_social.html`, `_area_code.html`; rewrite `_task_row.html`; modify `day.html`, `web.py`, `tests/test_server_web.py`.

**Acceptance Criteria:**
- [ ] `_task_row.html` uses the new shape (`t.text`, `t.tag`, `t.carried`), id `task-{{area}}-{{idx}}`, with toggle + delete controls.
- [ ] `POST /web/day/{day}/tasks/{area}/add` appends `_norm_task({"text":...})`, returns `_task_list.html`; toggle returns `_task_row.html`; delete returns `_task_list.html`. `area` validated against `AREAS` (plus `app`→`code` alias kept).
- [ ] Each of the 5 area cards renders its decorative widget (waveform/video rows/funnel/post rows/commits+lang-bar) as static markup translated from `app.jsx`, plus its `_task_list`.
- [ ] The existing API toggle test and the `Category` typing still pass (update `web.py`'s old `toggle_task` route + `Category` to the area set; keep `app` alias).

**Verify:** `.venv/bin/python -m pytest tests/ -q` → pass.

**Steps:**

- [ ] **Step 1:** Failing tests:
```python
def test_task_add_toggle_delete(client):
    client.post("/web/day/2026-05-24/tasks/music/add", data={"text": "mix bus"}, headers={"HX-Request": "true"})
    from dayctl.storage import load_plan
    assert load_plan("2026-05-24").tasks["music"][-1]["text"] == "mix bus"
    idx = len(load_plan("2026-05-24").tasks["music"]) - 1
    client.post(f"/web/day/2026-05-24/tasks/music/{idx}/toggle", headers={"HX-Request": "true"})
    assert load_plan("2026-05-24").tasks["music"][idx]["done"] is True
    client.post(f"/web/day/2026-05-24/tasks/music/{idx}/delete", headers={"HX-Request": "true"})
    assert all(t["text"] != "mix bus" for t in load_plan("2026-05-24").tasks["music"])
```

- [ ] **Step 2:** Rewrite `_task_row.html` (new shape; accent passed by includer or default):
```html
<li id="task-{{ area }}-{{ idx }}" class="task {% if t.done %}done{% endif %}">
  <span class="check" hx-post="/web/day/{{ plan.day }}/tasks/{{ area }}/{{ idx }}/toggle" hx-target="#task-{{ area }}-{{ idx }}" hx-swap="outerHTML"></span>
  <span class="task-text" hx-post="/web/day/{{ plan.day }}/tasks/{{ area }}/{{ idx }}/toggle" hx-target="#task-{{ area }}-{{ idx }}" hx-swap="outerHTML">{{ t.text }}</span>
  {% if t.carried %}<span class="carried-pill">carried</span>{% endif %}
  {% if t.tag %}<span class="task-tag">{{ t.tag }}</span>{% endif %}
  <span style="color:var(--text-mute);cursor:pointer;padding:0 4px" hx-post="/web/day/{{ plan.day }}/tasks/{{ area }}/{{ idx }}/delete" hx-target="#tasklist-{{ area }}" hx-swap="outerHTML" title="Delete">×</span>
</li>
```

- [ ] **Step 3:** Create `_task_list.html` (root id `tasklist-{{area}}`, wraps rows + add form):
```html
<ul class="task-list" id="tasklist-{{ area }}">
  {% for t in plan.tasks.get(area, []) %}
    {% set idx = loop.index0 %}
    {% include "_task_row.html" %}
  {% endfor %}
  <form class="task-add" hx-post="/web/day/{{ plan.day }}/tasks/{{ area }}/add" hx-target="#tasklist-{{ area }}" hx-swap="outerHTML" hx-on::after-request="this.reset()">
    <span>+</span><input name="text" placeholder="Add task — Enter to commit">
  </form>
</ul>
```
(Note: the add-form lives inside the `<ul>` so the whole list including the form is replaced on add; acceptable. If preferred, wrap list+form in a `<div id="tasklist-{{area}}">` instead — pick one and use it consistently in routes/targets.)

- [ ] **Step 4:** Add routes to `web.py`. Replace the existing `Category = Literal["app","music"]` and old `toggle_task` with area-based handlers. Add `from dayctl.models import AREAS, _norm_task`:
```python
_AREA_ALIAS = {"app": "code"}
def _resolve_area(cat: str) -> str:
    area = _AREA_ALIAS.get(cat, cat)
    if area not in AREAS:
        raise HTTPException(404, "unknown area")
    return area

def _render_task_list(request, day, area):
    ctx = build_day_view(day); ctx["request"] = request; ctx["area"] = area
    return templates.TemplateResponse(request, "_task_list.html", ctx)

@router.post("/web/day/{day}/tasks/{cat}/add", response_class=HTMLResponse, dependencies=[Depends(require_token)])
def add_task(request: Request, cat: str, text: str = Form(""), day: str = PathParam(..., pattern=_DAY_PATTERN)) -> HTMLResponse:
    area = _resolve_area(cat); plan = load_plan(day)
    if text.strip():
        plan.tasks.setdefault(area, []).append(_norm_task({"text": text.strip()}))
        save_plan(plan)
    return _render_task_list(request, day, area)

@router.post("/web/day/{day}/tasks/{cat}/{idx}/toggle", response_class=HTMLResponse, dependencies=[Depends(require_token)])
def toggle_task(request: Request, cat: str, idx: int, day: str = PathParam(..., pattern=_DAY_PATTERN)) -> HTMLResponse:
    area = _resolve_area(cat); plan = load_plan(day)
    tasks = plan.tasks.get(area, [])
    if not (0 <= idx < len(tasks)):
        raise HTTPException(404, "task index out of range")
    tasks[idx]["done"] = not tasks[idx]["done"]; save_plan(plan)
    ctx = build_day_view(day); ctx["request"] = request
    ctx.update({"t": load_plan(day).tasks[area][idx], "area": area, "idx": idx})
    return templates.TemplateResponse(request, "_task_row.html", ctx)

@router.post("/web/day/{day}/tasks/{cat}/{idx}/delete", response_class=HTMLResponse, dependencies=[Depends(require_token)])
def delete_task(request: Request, cat: str, idx: int, day: str = PathParam(..., pattern=_DAY_PATTERN)) -> HTMLResponse:
    area = _resolve_area(cat); plan = load_plan(day)
    tasks = plan.tasks.get(area, [])
    if 0 <= idx < len(tasks):
        tasks.pop(idx); save_plan(plan)
    return _render_task_list(request, day, area)
```
Remove the now-defunct old `toggle_task`/`Category` definitions.

- [ ] **Step 5:** Create `_area_card.html` (shared chrome; accepts `area`, `title`, `tag`, `accent`, and a `widget` template name) and the 5 `_area_*.html` files translating each card's static widget + `{% include "_task_list.html" %}` from `app.jsx`. Use the area accent colors from `app.jsx` (`music #f472b6`, `youtube #ef4444`, `marketing #facc15`, `social #c4a7f7`, `code #7dd3fc`). The decorative markup (waveform spans, `.vid` rows, `.funnel`, `.post-row`, `.commit-row`/`.lang-bar`) is copied verbatim as static HTML from the corresponding component. Example `_area_music.html`:
```html
<div class="area-card" style="--accent:#f472b6">
  <div class="area-head"><div class="area-title"><span class="swatch"></span>Music Studio</div><div class="area-tag">ABLETON</div></div>
  <div class="wave">{% for i in range(48) %}<span class="{% if i < 32 %}played{% endif %}" style="height:{{ 6 + (i % 7) * 3 }}px;background:#f472b6"></span>{% endfor %}</div>
  {% set area = "music" %}{% include "_task_list.html" %}
</div>
```
(Other four follow the same pattern with their static widgets from `app.jsx`. Static stat numbers/text are copied as-is — they are intentional placeholders per the spec.)

- [ ] **Step 6:** Add the right `.col` `area-grid` to `day.html`:
```html
  <div class="col">
    <div class="area-grid">
      {% include "_area_music.html" %}
      {% include "_area_youtube.html" %}
      {% include "_area_marketing.html" %}
      {% include "_area_social.html" %}
      {% include "_area_code.html" %}
      {# _area_ideas added in Task 7 #}
    </div>
  </div>
```

- [ ] **Step 7:** Run `.venv/bin/python -m pytest tests/ -q` → green (incl. `test_server_api.py`). Commit:
```bash
git add src/dayctl/server/templates/_task_row.html src/dayctl/server/templates/_task_list.html src/dayctl/server/templates/_area_card.html src/dayctl/server/templates/_area_music.html src/dayctl/server/templates/_area_youtube.html src/dayctl/server/templates/_area_marketing.html src/dayctl/server/templates/_area_social.html src/dayctl/server/templates/_area_code.html src/dayctl/server/templates/day.html src/dayctl/server/web.py tests/test_server_web.py
git commit -m "feat(web): life-area cards with task lists + static widgets"
```

---

### Task 7: Idea Vault + Glance stats + accent settings (persistent-backed)

**Goal:** Wire the persistent store: Idea Vault (add/delete), at-a-glance editable stats with sparkline, and accent/show-glance settings.

**Files:** Create `_area_ideas.html`, `_glance.html`; modify `day.html`, `web.py`, `tests/test_server_web.py`.

**Acceptance Criteria:**
- [ ] `_area_ideas.html` (id `ideas`) lists `persistent.ideas` newest-first with delete; add form posts to `/web/ideas/add` with a `from` bucket.
- [ ] `POST /web/ideas/add` / `/web/ideas/{idx}/delete` mutate `persistent.ideas` via `save_persistent`, return `_area_ideas.html`.
- [ ] `_glance.html` (id `glance`) renders the 4 stat cards from `persistent.stats` with an inline sparkline (SVG polyline); `POST /web/stats/{key}` calls `update_stat` + `save_persistent`, returns `_glance.html`.
- [ ] `POST /web/settings` sets `accent`/`show_glance` and redirects to today; `base.html` applies `data-accent`; glance hidden when `show_glance` is false.

**Verify:** `.venv/bin/python -m pytest tests/test_server_web.py -q` → pass.

**Steps:**

- [ ] **Step 1:** Failing tests:
```python
def test_idea_add_delete(client):
    r = client.post("/web/ideas/add", data={"text": "sample fridge hum", "bucket": "Music"}, headers={"HX-Request": "true"})
    assert "sample fridge hum" in r.text
    from dayctl.persistent import load_persistent
    assert load_persistent()["ideas"][0]["text"] == "sample fridge hum"
    client.post("/web/ideas/0/delete", headers={"HX-Request": "true"})
    assert load_persistent()["ideas"] == []

def test_stat_update_appends_spark(client):
    client.post("/web/stats/ytSubs", data={"v": "12.5K", "d": "+10", "trend": "up"}, headers={"HX-Request": "true"})
    from dayctl.persistent import load_persistent
    st = load_persistent()["stats"]["ytSubs"]
    assert st["v"] == "12.5K" and st["spark"][-1] == 12.5
```

- [ ] **Step 2:** Routes in `web.py` (add `from dayctl.persistent import load_persistent, save_persistent, update_stat`; `from datetime import date` is already imported):
```python
def _render_ideas(request):
    ctx = {"request": request, "persistent": load_persistent()}
    return templates.TemplateResponse(request, "_area_ideas.html", ctx)

@router.post("/web/ideas/add", response_class=HTMLResponse, dependencies=[Depends(require_token)])
def add_idea(request: Request, text: str = Form(""), bucket: str = Form("Capture")) -> HTMLResponse:
    if text.strip():
        p = load_persistent()
        p["ideas"].insert(0, {"from": bucket, "text": text.strip()})
        save_persistent(p)
    return _render_ideas(request)

@router.post("/web/ideas/{idx}/delete", response_class=HTMLResponse, dependencies=[Depends(require_token)])
def delete_idea(request: Request, idx: int) -> HTMLResponse:
    p = load_persistent()
    if 0 <= idx < len(p["ideas"]):
        p["ideas"].pop(idx); save_persistent(p)
    return _render_ideas(request)

@router.post("/web/stats/{key}", response_class=HTMLResponse, dependencies=[Depends(require_token)])
def edit_stat(request: Request, key: str, v: str = Form(""), d: str = Form(""), trend: str = Form("flat")) -> HTMLResponse:
    p = load_persistent()
    update_stat(p, key, {"v": v, "d": d, "trend": trend})
    save_persistent(p)
    ctx = {"request": request, "persistent": load_persistent()}
    return templates.TemplateResponse(request, "_glance.html", ctx)

@router.post("/web/settings", dependencies=[Depends(require_token)])
def update_settings(accent: str = Form("cyan"), show_glance: str = Form("")) -> RedirectResponse:
    p = load_persistent()
    p["settings"]["accent"] = accent
    p["settings"]["show_glance"] = show_glance == "on"
    save_persistent(p)
    return RedirectResponse(url=f"/day/{date.today().isoformat()}", status_code=303)
```

- [ ] **Step 3:** Create `_area_ideas.html` (translate `IdeasCard`; root id `ideas`). Bucket selection via a hidden default `Capture` (full bucket UI optional in v1):
```html
<div class="area-card" id="ideas" style="--accent:#4ade80">
  <div class="area-head"><div class="area-title"><span class="swatch"></span>Idea Vault</div><div class="area-tag">{{ persistent.ideas|length }}</div></div>
  <div style="margin-top:8px;max-height:280px;overflow-y:auto">
    {% if not persistent.ideas %}<div style="font-size:12px;color:var(--text-mute);padding:4px">Idea vault is empty.</div>{% endif %}
    {% for idea in persistent.ideas %}
    <div class="idea" style="border-left-color:#4ade80;position:relative">
      <span class="from">{{ idea.from }}</span>{{ idea.text }}
      <span hx-post="/web/ideas/{{ loop.index0 }}/delete" hx-target="#ideas" hx-swap="outerHTML" style="position:absolute;right:8px;top:8px;cursor:pointer;color:var(--text-mute)">×</span>
    </div>
    {% endfor %}
  </div>
  <form class="task-add" hx-post="/web/ideas/add" hx-target="#ideas" hx-swap="outerHTML" hx-on::after-request="this.reset()">
    <input type="hidden" name="bucket" value="Capture"><span>+</span>
    <input name="text" placeholder="Capture an idea — Enter to save">
  </form>
</div>
```

- [ ] **Step 4:** Create `_glance.html` (translate `Glance`/`GlanceCard`/`Spark`; root id `glance`). Each card is a small form posting to `/web/stats/{key}`; render the sparkline as an SVG polyline computed in the template. Concrete card (loop over the 4 keys `scPlays, scFollowers, ytSubs, campaigns`):
```html
<div class="glance-grid" id="glance">
  {% for key in ["scPlays","scFollowers","ytSubs","campaigns"] %}
  {% set stat = persistent.stats[key] %}
  <form class="glance" hx-post="/web/stats/{{ key }}" hx-target="#glance" hx-swap="outerHTML">
    <div class="glance-l">{{ stat.label }}</div>
    <input name="v" value="{{ stat.v }}" placeholder="—" style="background:var(--bg-2);border:1px solid var(--border);border-radius:6px;color:var(--text);font-family:'JetBrains Mono';font-size:18px;font-weight:600;width:100%;margin-top:6px;padding:4px 6px">
    <div style="display:flex;gap:6px;margin-top:6px">
      <input name="d" value="{{ stat.d }}" placeholder="+ wk" style="flex:1;background:var(--bg-2);border:1px solid var(--border);border-radius:6px;color:var(--text);font-family:'JetBrains Mono';font-size:11px;padding:3px 6px">
      <select name="trend" style="background:var(--bg-2);border:1px solid var(--border);border-radius:6px;color:var(--text);font-size:11px">
        <option value="up" {% if stat.trend=='up' %}selected{% endif %}>▲</option>
        <option value="flat" {% if stat.trend=='flat' %}selected{% endif %}>—</option>
        <option value="down" {% if stat.trend=='down' %}selected{% endif %}>▼</option>
      </select>
      <button class="btn-primary" type="submit" style="padding:3px 8px">Save</button>
    </div>
  </form>
  {% endfor %}
</div>
```
(Sparkline SVG is optional polish; if included, compute points in the template from `stat.spark`. Keep functional save first.)

- [ ] **Step 5:** Wire into `day.html`: add `{% include "_area_ideas.html" %}` to the `area-grid`, and add glance above the grid honoring the setting:
```html
{% if persistent.settings.show_glance %}{% include "_glance.html" %}{% endif %}
```

- [ ] **Step 6:** Confirm `base.html` `data-accent` is applied. Add accent CSS overrides to `style.css` (append) so `data-accent` swaps the palette:
```css
body[data-accent="mint"]  { --cyan:#4ade80; --purple:#7dd3fc; }
body[data-accent="amber"] { --cyan:#facc15; --purple:#fb923c; }
body[data-accent="pink"]  { --cyan:#f472b6; --purple:#c4a7f7; }
```

- [ ] **Step 7:** Tests green, commit:
```bash
git add src/dayctl/server/templates/_area_ideas.html src/dayctl/server/templates/_glance.html src/dayctl/server/templates/day.html src/dayctl/server/static/style.css src/dayctl/server/web.py tests/test_server_web.py
git commit -m "feat(web): idea vault, glance stats, accent settings (persistent)"
```

---

### Task 8: Self-hosted fonts

**Goal:** Vendor the three font families as latin woff2 and serve them locally via `@font-face`, removing reliance on system fallbacks.

**Files:** Create `src/dayctl/server/static/fonts/*.woff2`; modify `src/dayctl/server/static/style.css` (prepend `@font-face`).

**Acceptance Criteria:**
- [ ] woff2 files for Bricolage Grotesque (500/600/700), Geist (300–600), JetBrains Mono (400–600) exist under `static/fonts/`.
- [ ] `style.css` has `@font-face` rules pointing at `/static/fonts/...`.
- [ ] `GET /static/fonts/<one file>` returns 200; page renders with the real fonts.

**Verify:** `.venv/bin/python -m pytest tests/ -q` → pass; manual: fonts load (Network tab shows local woff2, not gstatic).

**Steps:**

- [ ] **Step 1:** Fetch the fonts. Run this one-time script (`scripts/fetch_fonts.py`) which queries the Google Fonts CSS2 API with a desktop UA (returns latin woff2 URLs) and downloads them:
```python
import re, urllib.request, pathlib
DEST = pathlib.Path("src/dayctl/server/static/fonts"); DEST.mkdir(parents=True, exist_ok=True)
URL = ("https://fonts.googleapis.com/css2?family=Bricolage+Grotesque:wght@500;600;700"
       "&family=Geist:wght@300;400;500;600&family=JetBrains+Mono:wght@400;500;600&display=swap")
UA = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"}
css = urllib.request.urlopen(urllib.request.Request(URL, headers=UA)).read().decode()
# Keep only latin blocks; grab font-family, weight, and woff2 url from each @font-face
faces = re.findall(r"font-family: '([^']+)';.*?font-weight: (\d+);.*?src: url\((https://[^)]+\.woff2)\)", css, re.S)
seen = {}
for fam, wght, url in faces:
    name = f"{fam.replace(' ', '')}-{wght}.woff2"
    if name in seen: continue
    seen[name] = True
    urllib.request.urlretrieve(url, DEST / name)
    print("saved", name)
```
Run: `.venv/bin/python scripts/fetch_fonts.py`. (If the environment has no network, this task is BLOCKED — escalate; the site still works on system-font fallback until then.)

- [ ] **Step 2:** Prepend `@font-face` rules to `style.css` referencing the downloaded files, e.g.:
```css
@font-face { font-family:"Bricolage Grotesque"; font-weight:700; font-display:swap; src:url("/static/fonts/BricolageGrotesque-700.woff2") format("woff2"); }
/* ...one per downloaded file: Bricolage 500/600/700, Geist 300/400/500/600, JetBrains Mono 400/500/600... */
```
Match each `font-family`/`font-weight` to the saved filename from Step 1.

- [ ] **Step 3:** Verify `GET /static/fonts/Geist-400.woff2` → 200 (the existing `StaticFiles` mount serves it). Run `.venv/bin/python -m pytest tests/ -q` → green.

- [ ] **Step 4:** Commit (woff2 are binary assets — that's fine to track):
```bash
git add src/dayctl/server/static/fonts src/dayctl/server/static/style.css scripts/fetch_fonts.py
git commit -m "feat(web): self-host dashboard fonts"
```

---

## Self-Review

- **Spec coverage:** dark two-column layout + sidebar (T1); pulse + habit toggles (T2); focus/energy/sleep/mood/bpm inline edit + schedule (T3); week summary + navigation + streak (T4); notes (T5); 5 area cards + task CRUD + static widgets, `_task_row` rewrite fixing the Plan-1 interim (T6); idea vault + glance stats + accent/show-glance settings (T7); self-hosted fonts (T8). Sidebar visual-only with model-ready structure ✓. Decorative widgets static ✓. ✓
- **Placeholder scan:** routes and interactive partials have complete code; verbatim CSS and static decorative markup reference the design source files by exact path (the source IS the content — not a TODO). No hedge-y "handle edge cases."
- **Type/contract consistency:** task fragments target `#tasklist-{{area}}` (list) and `#task-{{area}}-{{idx}}` (row) consistently between `_task_list.html`, `_task_row.html`, and the add/toggle/delete routes; `area` validated via `_resolve_area` against `AREAS` with the `app→code` alias matching Plan 1 + `api.py`; field name→attr map (`sleep→sleep_hours`) matches the `_FIELD_ATTR` route; `build_day_view` keys (`plan, day, score, habits, total, schedule, week, streak, profile_label, persistent, is_today, prev_day, next_day, today, date_long`) are the same names used across all partials.
- **Note for executor:** Task 6 removes the old `Category = Literal["app","music"]` + original `toggle_task`; ensure `test_server_api.py` (which exercises the JSON API, untouched here) stays green — it has its own routes in `api.py`. The `_task_list.html` add-form-inside-`<ul>` choice is intentional; keep targets consistent. Strict-undefined is NOT enabled, so a missing context key renders empty rather than erroring — still, pass full `build_day_view` context to every day-scoped fragment route (helpers above do this).
