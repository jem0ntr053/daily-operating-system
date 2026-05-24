# Dashboard Backend Foundation — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers-extended-cc:subagent-driven-development (recommended) or superpowers-extended-cc:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Evolve the `dayctl` data model to back the Daily OS dashboard — 6 habits (`÷6` scoring), 5 task areas, `mood`/`bpm`/`flow_minutes`, timestamped notes, and a persistent store for ideas/settings/stats — keeping the CLI green throughout.

**Architecture:** Plan 1 of 2. This plan changes only the backend (`models.py`, `cli.py`, `display.py`, new `persistent.py`) plus tests. Plan 2 (web UI) depends on the model shape this plan establishes. No web/template work here.

**Tech Stack:** Pure stdlib Python (`dataclasses`, `json`), pytest. No new dependencies.

**Spec:** `docs/superpowers/specs/2026-05-24-web-dashboard-redesign-design.md`

---

## File Structure

| File | Responsibility | Change |
|---|---|---|
| `src/dayctl/models.py` | `DayPlan`, habit template, scoring, streak, carry-forward | Modify |
| `src/dayctl/display.py` | Terminal rendering | Modify (scoring `/6`, task areas, notes) |
| `src/dayctl/cli.py` | argparse subcommands | Modify (6 habits, `music`+`code` task subset, `app` alias, notes) |
| `src/dayctl/persistent.py` | Cross-day persistent store (ideas/settings/stats) | **Create** |
| `src/dayctl/storage.py` | Path constants | Modify (add `PERSISTENT_PATH`) |
| `tests/test_models.py`, `test_display.py`, `test_cli.py` | Existing suites | Modify |
| `tests/test_persistent.py` | Persistent store tests | **Create** |

Migration of legacy stored days is handled entirely inside `DayPlan.from_dict` (no file rewrites): days upgrade on load.

---

### Task 1: Switch non-negotiables to the 6-habit template

**Goal:** Replace the 4 non-negotiables with the 6-habit template and move scoring to `÷6` across model, display, and CLI.

**Files:**
- Modify: `src/dayctl/models.py` (`NON_NEGOTIABLE_KEYS`, `score_plan`, `DayPlan.new`)
- Modify: `src/dayctl/display.py` (`_score_bar`, `print_plan`, `print_score_table`)
- Modify: `src/dayctl/cli.py` (`cmd_score`, `_set_completed`, `cmd_streak` threshold)
- Test: `tests/test_models.py`, `tests/test_display.py`, `tests/test_cli.py`

**Acceptance Criteria:**
- [ ] `HABIT_TEMPLATE` defines 6 habits with `id`/`name`/`meta`; `HABIT_KEYS` derives the ids.
- [ ] `score_plan` returns 0–6 (count of completed habit keys).
- [ ] A new plan seeds all 6 habit keys to `False`.
- [ ] Terminal score readouts say `/6` and the score bar scales to 6.
- [ ] Full test suite passes.

**Verify:** `pytest tests/ -q` → all pass

**Steps:**

- [ ] **Step 1: Write failing model tests**

In `tests/test_models.py`, add:

```python
from dayctl.models import HABIT_TEMPLATE, HABIT_KEYS, DayPlan, score_plan

def test_habit_template_has_six():
    assert [h["id"] for h in HABIT_TEMPLATE] == ["fast", "gym", "music", "ship", "post", "read"]
    assert HABIT_KEYS == ["fast", "gym", "music", "ship", "post", "read"]

def test_new_plan_seeds_six_habits():
    plan = DayPlan.new("2026-05-24")
    assert set(plan.completed) == set(HABIT_KEYS)
    assert all(v is False for v in plan.completed.values())

def test_score_counts_completed_out_of_six():
    plan = DayPlan.new("2026-05-24")
    for k in ("fast", "gym", "music"):
        plan.completed[k] = True
    assert score_plan(plan) == 3
```

- [ ] **Step 2: Run, verify failure**

Run: `pytest tests/test_models.py -k "habit or score_counts" -q`
Expected: FAIL (`HABIT_TEMPLATE`/`HABIT_KEYS` undefined).

- [ ] **Step 3: Update `models.py`**

Replace the line `NON_NEGOTIABLE_KEYS = ["fast", "gym", "app", "music"]` with:

```python
HABIT_TEMPLATE = [
    {"id": "fast",  "name": "FAST",   "meta": "11p → 4p"},
    {"id": "gym",   "name": "GYM",    "meta": "Push · 6:30a"},
    {"id": "music", "name": "STUDIO", "meta": "90 min block"},
    {"id": "ship",  "name": "SHIP",   "meta": "1 commit min"},
    {"id": "post",  "name": "POST",   "meta": "1 short"},
    {"id": "read",  "name": "READ",   "meta": "20 pages"},
]
HABIT_KEYS = [h["id"] for h in HABIT_TEMPLATE]
# Backwards-compatible alias for existing imports.
NON_NEGOTIABLE_KEYS = HABIT_KEYS
```

In `DayPlan.new`, `completed={k: False for k in NON_NEGOTIABLE_KEYS}` already works (alias). `score_plan` already iterates `NON_NEGOTIABLE_KEYS` — now 6. No change to those two function bodies.

- [ ] **Step 4: Update `display.py` for `/6`**

`_score_bar` signature → default max 6:

```python
def _score_bar(t: dict[str, str], score: int, max_score: int = 6) -> str:
```

In `print_plan`, change the score fraction:

```python
    nn_parts.append(f"{bar} {s}/6")
```

In `print_score_table`, change `right = f"{_score_bar(t, score)} {score}/4"` to `.../6`, and the average line `f"{avg:.1f}/4"` to `.../6`.

- [ ] **Step 5: Update `cli.py` for `/6`**

`cmd_score`: `print(f"{plan.day} score: {score_plan(plan)} / 6")`.
`cmd_streak`: if it passes a literal `threshold=3`, change the default to `len(HABIT_KEYS)` (import `HABIT_KEYS`). If `cmd_streak` reads `--threshold`, set its argparse default to 6 in `build_parser`.

- [ ] **Step 6: Update existing assertions**

Update any `test_display.py` / `test_cli.py` / `test_models.py` assertions referencing `/4` or 4-habit completion to `/6` and the 6 keys.

- [ ] **Step 7: Run full suite, commit**

Run: `pytest tests/ -q` → all pass

```bash
git add src/dayctl/models.py src/dayctl/display.py src/dayctl/cli.py tests/
git commit -m "feat(model): 6-habit template, score out of 6"
```

---

### Task 2: Add scalar day fields (mood, bpm, flow_minutes)

**Goal:** Add three additive `DayPlan` fields the dashboard surfaces, backward-compatible with existing stored days.

**Files:**
- Modify: `src/dayctl/models.py` (`DayPlan` dataclass, `DayPlan.new`)
- Test: `tests/test_models.py`

**Acceptance Criteria:**
- [ ] `DayPlan` has `mood: str = ""`, `bpm: str = ""`, `flow_minutes: int = 0`.
- [ ] `DayPlan.new` initializes them to defaults.
- [ ] A legacy dict lacking these keys loads via `from_dict` with defaults (no error).

**Verify:** `pytest tests/test_models.py -q` → all pass

**Steps:**

- [ ] **Step 1: Write failing tests**

```python
def test_new_plan_has_scalar_defaults():
    plan = DayPlan.new("2026-05-24")
    assert plan.mood == "" and plan.bpm == "" and plan.flow_minutes == 0

def test_from_dict_backfills_scalar_fields():
    legacy = DayPlan.new("2026-05-24").to_dict()
    legacy.pop("mood"); legacy.pop("bpm"); legacy.pop("flow_minutes")
    plan = DayPlan.from_dict(legacy)
    assert plan.mood == "" and plan.bpm == "" and plan.flow_minutes == 0
```

- [ ] **Step 2: Run, verify failure**

Run: `pytest tests/test_models.py -k scalar -q` → FAIL (`mood` missing).

- [ ] **Step 3: Add dataclass fields**

In the `DayPlan` dataclass, after `notes`, add (defaults required so existing positional construction and `from_dict` stay valid):

```python
    mood: str = ""
    bpm: str = ""
    flow_minutes: int = 0
```

In `DayPlan.new(...)`, add `mood="", bpm="", flow_minutes=0,` to the constructor call.

`from_dict` filters to known fields and constructs with `cls(**filtered)`; missing keys now fall back to the dataclass defaults. No `from_dict` change needed for these.

- [ ] **Step 4: Run, commit**

Run: `pytest tests/test_models.py -q` → pass

```bash
git add src/dayctl/models.py tests/test_models.py
git commit -m "feat(model): add mood, bpm, flow_minutes day fields"
```

---

### Task 3: Generalize tasks to a 5-area dict with legacy migration

**Goal:** Replace `app_tasks`/`music_tasks` with `tasks: Dict[str, List[dict]]` over 5 areas, migrate legacy data, and rewire CLI (`music`+`code` subset, `app` alias) and display.

**Files:**
- Modify: `src/dayctl/models.py` (`DayPlan`, `from_dict`, `DEFAULT_TASKS`, `incomplete_tasks`, `carry_forward`)
- Modify: `src/dayctl/cli.py` (`TASK_LIST_ATTR`, `_task_*`, `cmd_task`, `build_parser` task category)
- Modify: `src/dayctl/display.py` (`print_plan` task sections)
- Test: `tests/test_models.py`, `tests/test_cli.py`, `tests/test_display.py`

**Acceptance Criteria:**
- [ ] `AREAS == ["music", "youtube", "marketing", "social", "code"]`; task shape `{"text","done","tag","carried"}`.
- [ ] `from_dict` migrates legacy `app_tasks → tasks["code"]`, `music_tasks → tasks["music"]`, normalizing `{"task","done"}` → new shape.
- [ ] `DayPlan.new` seeds all 5 areas (music/code with defaults, others empty).
- [ ] `carry_forward` carries incomplete tasks per area, marking `carried=True`.
- [ ] CLI `task music|code add|N done|undo|"text"` works; `app` is an alias for `code`.
- [ ] Terminal shows CODE TASKS and MUSIC TASKS using `item["text"]`.

**Verify:** `pytest tests/ -q` → all pass

**Steps:**

- [ ] **Step 1: Write failing model tests**

```python
from dayctl.models import AREAS, DayPlan, carry_forward

def test_areas_and_new_seeding():
    assert AREAS == ["music", "youtube", "marketing", "social", "code"]
    plan = DayPlan.new("2026-05-24")
    assert set(plan.tasks) == set(AREAS)
    assert all({"text", "done", "tag", "carried"} <= set(t) for t in plan.tasks["music"])

def test_from_dict_migrates_legacy_tasks():
    legacy = {
        "day": "2026-05-24", "profile": "weekday", "focus": "", "energy": "",
        "sleep_hours": "8", "fasting_window": "x", "schedule": [],
        "completed": {}, "notes": [],
        "app_tasks": [{"task": "ship it", "done": True}],
        "music_tasks": [{"task": "mix", "done": False}],
    }
    plan = DayPlan.from_dict(legacy)
    assert plan.tasks["code"] == [{"text": "ship it", "done": True, "tag": "", "carried": False}]
    assert plan.tasks["music"] == [{"text": "mix", "done": False, "tag": "", "carried": False}]

def test_carry_forward_marks_carried():
    prev = DayPlan.new("2026-05-23")
    prev.tasks["code"] = [{"text": "todo", "done": False, "tag": "", "carried": False}]
    today = DayPlan.new("2026-05-24")
    today.tasks["code"] = []
    carry_forward(today, prev)
    assert today.tasks["code"][0]["text"] == "todo"
    assert today.tasks["code"][0]["carried"] is True
```

- [ ] **Step 2: Run, verify failure**

Run: `pytest tests/test_models.py -k "areas or migrate or carried" -q` → FAIL.

- [ ] **Step 3: Update `models.py`**

Add near the constants:

```python
AREAS = ["music", "youtube", "marketing", "social", "code"]

def _norm_task(t: dict) -> dict:
    return {
        "text": str(t.get("text", t.get("task", ""))),
        "done": bool(t.get("done", False)),
        "tag": str(t.get("tag", "")),
        "carried": bool(t.get("carried", False)),
    }
```

Rename `DEFAULT_TASKS` key `"app"` to `"code"` (keep the same default text), leaving `"music"` as-is.

In the `DayPlan` dataclass, **remove** `app_tasks` and `music_tasks`; **add** (after `notes`, with default):

```python
    tasks: Dict[str, List[Dict[str, object]]] = field(default_factory=dict)
```

(Add `field` to the existing `from dataclasses import ...` import.)

In `DayPlan.new`, replace the `app_tasks=`/`music_tasks=` arguments with:

```python
            tasks={
                "music": [_norm_task({"text": t}) for t in DEFAULT_TASKS["music"]],
                "youtube": [],
                "marketing": [],
                "social": [],
                "code": [_norm_task({"text": t}) for t in DEFAULT_TASKS["code"]],
            },
```

In `from_dict`, replace the `for key in ("app_tasks", "music_tasks")` normalization block with migration + normalization:

```python
        tasks = dict(filtered.get("tasks") or {})
        # migrate legacy flat fields
        if "code" not in tasks and data.get("app_tasks"):
            tasks["code"] = [_norm_task(t) for t in data["app_tasks"]]
        if "music" not in tasks and data.get("music_tasks"):
            tasks["music"] = [_norm_task(t) for t in data["music_tasks"]]
        # ensure every area exists and is normalized
        filtered["tasks"] = {a: [_norm_task(t) for t in tasks.get(a, [])] for a in AREAS}
```

Update `incomplete_tasks` and `carry_forward` to iterate `AREAS` over `plan.tasks[area]` (use `"text"` as the identity key), and have `carry_forward` append carried tasks with `carried=True`:

```python
def incomplete_tasks(plan: DayPlan) -> dict[str, list[dict]]:
    result: dict[str, list[dict]] = {}
    for area in AREAS:
        pending = [t for t in plan.tasks.get(area, []) if not t.get("done", False)]
        if pending:
            result[area] = [dict(t) for t in pending]
    return result


def carry_forward(plan: DayPlan, previous: DayPlan) -> list[str]:
    carried: list[str] = []
    for area, tasks in incomplete_tasks(previous).items():
        existing = {t["text"] for t in plan.tasks.get(area, [])}
        for t in tasks:
            if t["text"] in existing:
                continue
            plan.tasks.setdefault(area, []).append({**_norm_task(t), "carried": True})
            carried.append(t["text"])
    return carried
```

- [ ] **Step 4: Update `cli.py`**

Replace `TASK_LIST_ATTR = {"app": "app_tasks", "music": "music_tasks"}` with an alias map and area resolver:

```python
TASK_AREA_ALIAS = {"app": "code"}  # legacy alias

def _resolve_area(category: str) -> str:
    return TASK_AREA_ALIAS.get(category, category)
```

In `cmd_task`, replace `tasks = getattr(plan, TASK_LIST_ATTR[args.category])` with:

```python
    area = _resolve_area(args.category)
    tasks = plan.tasks.setdefault(area, [])
```

In `_task_add`, change the appended dict to `_norm_task({"text": value})` (import `_norm_task` from models) so new tasks have the full shape. In `_task_edit`/`_task_toggle`, change `tasks[idx]["task"]` to `tasks[idx]["text"]`.

In `build_parser`, change the task category choices and the per-category aliases:

```python
    p_task.add_argument("category", choices=["music", "code", "app"], help="Task area (app = code alias)")
    ...
    for category in ("music", "code"):
        p = sub.add_parser(category, help=f"Manage {category} tasks.")
```

Keep an `app` top-level alias parser pointing at the same handler if one existed, so `dayctl app ...` still works.

- [ ] **Step 5: Update `display.py`**

Replace the APP TASKS / MUSIC TASKS sections. Render CODE then MUSIC using the new shape:

```python
    # === Code Tasks ===
    lines.append(_box_row(t, _c(t["heading"], "CODE TASKS")))
    for idx, item in enumerate(plan.tasks.get("code", []), start=1):
        mark = _render_check(t, bool(item["done"]))
        lines.append(_box_row(t, f"  {idx}. {mark} {item['text']}"))
    lines.append(_box_div(t))
    # === Music Tasks ===
    lines.append(_box_row(t, _c(t["heading"], "MUSIC TASKS")))
    for idx, item in enumerate(plan.tasks.get("music", []), start=1):
        mark = _render_check(t, bool(item["done"]))
        lines.append(_box_row(t, f"  {idx}. {mark} {item['text']}"))
```

- [ ] **Step 6: Update existing tests**

Fix `test_cli.py`/`test_display.py`/`test_models.py` references to `app_tasks`/`music_tasks` and `"task"` key to the new `tasks[area]` / `"text"` shape.

- [ ] **Step 7: Run full suite, commit**

Run: `pytest tests/ -q` → all pass

```bash
git add src/dayctl/models.py src/dayctl/cli.py src/dayctl/display.py tests/
git commit -m "feat(model): generalize tasks to 5 areas with legacy migration"
```

---

### Task 4: Timestamped notes

**Goal:** Notes become `{"text","time"}` dicts; legacy string notes normalize on load; CLI stamps the time; display renders text.

**Files:**
- Modify: `src/dayctl/models.py` (`from_dict` notes normalization)
- Modify: `src/dayctl/cli.py` (`cmd_note`)
- Modify: `src/dayctl/display.py` (`print_plan` notes section)
- Test: `tests/test_models.py`, `tests/test_cli.py`

**Acceptance Criteria:**
- [ ] `from_dict` converts legacy `notes: ["text"]` → `[{"text":"text","time":""}]`.
- [ ] `cmd_note` appends `{"text": <text>, "time": "HH:MM"}`.
- [ ] Display renders `note["text"]`.

**Verify:** `pytest tests/ -q` → all pass

**Steps:**

- [ ] **Step 1: Write failing tests**

```python
def test_from_dict_normalizes_string_notes():
    legacy = DayPlan.new("2026-05-24").to_dict()
    legacy["notes"] = ["belly felt weird", "note 2"]
    plan = DayPlan.from_dict(legacy)
    assert plan.notes == [{"text": "belly felt weird", "time": ""}, {"text": "note 2", "time": ""}]
```

- [ ] **Step 2: Run, verify failure**

Run: `pytest tests/test_models.py -k notes -q` → FAIL.

- [ ] **Step 3: Normalize notes in `from_dict`**

In `from_dict`, after building `filtered`, add:

```python
        if "notes" in filtered:
            filtered["notes"] = [
                n if isinstance(n, dict) else {"text": str(n), "time": ""}
                for n in filtered["notes"]
            ]
```

- [ ] **Step 4: Update `cmd_note`**

```python
def cmd_note(args: argparse.Namespace) -> None:
    from datetime import datetime
    plan = load_plan(resolve_date(args.date))
    now = datetime.now()
    plan.notes.append({"text": args.text, "time": f"{now.hour:02d}:{now.minute:02d}"})
    save_plan(plan)
    print("Note added.")
```

- [ ] **Step 5: Update display notes**

In `print_plan`, change `lines.append(_box_row(t, f"  • {n}"))` to `f"  • {n['text']}"`.

- [ ] **Step 6: Fix existing note assertions, run, commit**

Run: `pytest tests/ -q` → pass

```bash
git add src/dayctl/models.py src/dayctl/cli.py src/dayctl/display.py tests/
git commit -m "feat(model): timestamped notes with legacy normalization"
```

---

### Task 5: Persistent store (`persistent.json`)

**Goal:** A backend-agnostic cross-day store for ideas, settings, and stats, with a stat-update helper that appends sparkline samples (cap 8).

**Files:**
- Create: `src/dayctl/persistent.py`
- Modify: `src/dayctl/storage.py` (add `PERSISTENT_PATH`)
- Test: `tests/test_persistent.py` (create)

**Acceptance Criteria:**
- [ ] `load_persistent()` returns defaults (`ideas=[]`, `settings={accent:"cyan",show_glance:True}`, seeded `stats`) when the file is absent.
- [ ] `save_persistent` then `load_persistent` round-trips.
- [ ] `update_stat(p, key, {"v": ...})` appends a numeric sample to that stat's `spark`, capping length at 8 and setting `updated_at`.

**Verify:** `pytest tests/test_persistent.py -q` → all pass

**Steps:**

- [ ] **Step 1: Write failing tests**

```python
# tests/test_persistent.py
import dayctl.persistent as p

def test_load_returns_defaults(tmp_path, monkeypatch):
    monkeypatch.setattr(p, "PERSISTENT_PATH", tmp_path / "persistent.json")
    data = p.load_persistent()
    assert data["ideas"] == []
    assert data["settings"]["accent"] == "cyan"
    assert data["settings"]["show_glance"] is True
    assert "ytSubs" in data["stats"]

def test_round_trip(tmp_path, monkeypatch):
    monkeypatch.setattr(p, "PERSISTENT_PATH", tmp_path / "persistent.json")
    data = p.load_persistent()
    data["ideas"].append({"from": "Music", "text": "idea", "created_at": 1})
    p.save_persistent(data)
    assert p.load_persistent()["ideas"][0]["text"] == "idea"

def test_update_stat_appends_spark_cap_8(tmp_path, monkeypatch):
    monkeypatch.setattr(p, "PERSISTENT_PATH", tmp_path / "persistent.json")
    data = p.load_persistent()
    data["stats"]["ytSubs"]["spark"] = list(range(8))
    p.update_stat(data, "ytSubs", {"v": "12.5K"})
    spark = data["stats"]["ytSubs"]["spark"]
    assert len(spark) == 8 and spark[-1] == 12.5
    assert data["stats"]["ytSubs"]["updated_at"]
```

- [ ] **Step 2: Run, verify failure**

Run: `pytest tests/test_persistent.py -q` → FAIL (module missing).

- [ ] **Step 3: Add `PERSISTENT_PATH` to `storage.py`**

After `CONFIG_PATH = DATA_DIR / "config.json"` add:

```python
PERSISTENT_PATH = DATA_DIR / "persistent.json"
```

- [ ] **Step 4: Create `src/dayctl/persistent.py`**

```python
"""Cross-day persistent store: ideas, settings, stats. Flat JSON on DATA_DIR."""
from __future__ import annotations

import json
import re
from datetime import datetime

from dayctl.storage import PERSISTENT_PATH, ensure_dirs

SPARK_CAP = 8


def _defaults() -> dict:
    return {
        "ideas": [],
        "settings": {"accent": "cyan", "show_glance": True},
        "stats": {
            "scPlays":     {"label": "SC Plays · 7d", "v": "", "d": "", "trend": "flat", "spark": [], "updated_at": ""},
            "scFollowers": {"label": "SC Followers",     "v": "", "d": "", "trend": "flat", "spark": [], "updated_at": ""},
            "ytSubs":      {"label": "YouTube Subs",     "v": "", "d": "", "trend": "flat", "spark": [], "updated_at": ""},
            "campaigns":   {"label": "Open campaigns",   "v": "", "d": "", "trend": "flat", "spark": [], "updated_at": ""},
        },
    }


def load_persistent() -> dict:
    if not PERSISTENT_PATH.exists():
        return _defaults()
    try:
        data = json.loads(PERSISTENT_PATH.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return _defaults()
    base = _defaults()
    base.update({k: data[k] for k in ("ideas", "settings", "stats") if k in data})
    return base


def save_persistent(data: dict) -> None:
    ensure_dirs()
    PERSISTENT_PATH.write_text(json.dumps(data, indent=2), encoding="utf-8")


def update_stat(data: dict, key: str, patch: dict) -> None:
    stat = data["stats"].setdefault(key, {"label": key, "v": "", "d": "", "trend": "flat", "spark": [], "updated_at": ""})
    if "v" in patch and patch["v"] != stat.get("v"):
        num = float(re.sub(r"[^0-9.]", "", str(patch["v"])) or 0)
        stat["spark"] = ([*stat.get("spark", []), num])[-SPARK_CAP:]
    stat.update({k: v for k, v in patch.items() if k in ("v", "d", "trend", "label")})
    stat["updated_at"] = datetime.now().isoformat()
```

- [ ] **Step 5: Run, commit**

Run: `pytest tests/test_persistent.py -q` → pass; then `pytest tests/ -q` → all pass.

```bash
git add src/dayctl/persistent.py src/dayctl/storage.py tests/test_persistent.py
git commit -m "feat(store): persistent.json for ideas, settings, stats"
```

---

## Self-Review

- **Spec coverage:** habits 6/`÷6` (T1), mood/bpm/flow (T2), 5 task areas + migration + carry-forward (T3), timestamped notes (T4), persistent store ideas/settings/stats (T5), CLI subset `music`+`code`+`app` alias (T3). Web UI, fonts, templates, HTMX routes → deferred to Plan 2 (explicitly out of scope here). ✓
- **Placeholders:** none — every code/test step shows concrete content. ✓
- **Type consistency:** task shape `{"text","done","tag","carried"}` used identically in `_norm_task`, `DayPlan.new`, `from_dict`, `carry_forward`, CLI, display, and tests; notes `{"text","time"}` consistent across model/cli/display. `HABIT_KEYS` used by score/streak. ✓
- **Note for executor:** `storage_backends` is a package (`json_backend.JSONBackend`, sqlite, remote); the SQLite/remote day backends serialize via `to_dict`/`from_dict`, so the additive `DayPlan` changes flow through automatically — verify by loading an existing day under the new model. The persistent store is deliberately a flat file (not backend-routed) and lives on `DATA_DIR` (the Fly volume in production).
