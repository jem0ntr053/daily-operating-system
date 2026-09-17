# dayos Habit Module v1 — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers-extended-cc:subagent-driven-development (recommended) or superpowers-extended-cc:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking. This repo has a guardrails-kit (`CLAUDE.md`): before your first code edit, follow its CODE.md trigger; claim "done" only beside fresh test output (VERIFY.md).

**Goal:** Add an ADHD-friendly, Atomic-Habits "evening stack" to dayos that shows up every day, is checkable from CLI/web/ntfy, and never resets your real tasks — a relapse-recovery restart, deliberately tiny.

**Architecture:** Reuse the existing `tasks` area machinery. The evening stack is a new task area (`stack`) seeded fresh daily (tagged `seed` so it re-seeds cleanly and is excluded from carry-forward). One diagnosed carry-forward defect (placeholder collision) is fixed first so real one-off tasks persist. Nudges are free — `incomplete_tasks` already feeds the ntfy body once `stack` is in `AREAS`. One-tap "done" from the phone and a "never miss twice" alarm are fast-follows, gated behind the loop working.

**Tech Stack:** Python 3.14, argparse CLI, dataclass model, JSON backend (`~/.dayctl/days/*.json`), FastAPI web/API, APScheduler + ntfy.sh push, launchd (`com.dayos.*`).

**Storage target:** local `~/.dayctl` + `com.dayos.web` on `localhost:8000` (confirmed live). Fly.io is a documented, un-deployed future path — out of scope.

**Phasing:**
- **v1 (MVP, ship first):** Task 1 + Task 2 — the stack appears daily and is checkable; real tasks carry.
- **v1.1 (fast-follows):** Task 3 (one-tap from phone), Task 4 (never-miss-twice alarm). Build only after v1 is proven in real use.

---

### Task 1: Fix carry-forward (seed tagging + exclusion)

**Goal:** Real one-off tasks carry to the next day; the daily seed/placeholder tasks re-seed cleanly instead of colliding and reading as "nothing carried."

**Why:** Diagnosed root cause — `DayPlan.new` re-seeds identical placeholder tasks every day (`models.py:233,237`) and `carry_forward` dedups by exact text (`models.py:330`). Yesterday's untouched placeholders match today's fresh ones and are silently dropped. Custom tasks already carry (verified); the fix removes the placeholder noise and makes daily-routine seeds (Task 2's stack) exclude themselves from carry by construction.

**Files:**
- Modify: `src/dayctl/models.py` (`DayPlan.new` tasks dict ~232-238; `carry_forward` 324-334)
- Test: `tests/test_carry_forward.py` (create)

**Acceptance Criteria:**
- [ ] A custom incomplete task on day N appears on day N+1 with `carried: True`.
- [ ] Seeded placeholder tasks (tag `seed`) do NOT carry (they re-seed daily).
- [ ] Full existing suite still green.

**Verify:** `.venv/bin/python -m pytest tests/test_carry_forward.py tests/ -q` → all pass

**Steps:**

- [ ] **Step 1: Write the failing test**

Create `tests/test_carry_forward.py`:

```python
from dayctl.models import DayPlan, carry_forward, _norm_task


def test_custom_task_carries_forward():
    prev = DayPlan.new("2026-09-01")
    prev.tasks["code"].append(_norm_task({"text": "Call dentist"}))  # real task, incomplete
    today = DayPlan.new("2026-09-02")
    carried = carry_forward(today, prev)
    assert "Call dentist" in carried
    assert any(t["text"] == "Call dentist" and t["carried"] for t in today.tasks["code"])


def test_seed_placeholders_do_not_carry():
    prev = DayPlan.new("2026-09-01")   # only seeded placeholders, all incomplete
    today = DayPlan.new("2026-09-02")
    carried = carry_forward(today, prev)
    assert carried == []               # seeds re-seed daily, never carry
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_carry_forward.py -v`
Expected: `test_seed_placeholders_do_not_carry` FAILS (currently placeholders are untagged, so `carried` is non-empty). `test_custom_task_carries_forward` likely already passes.

- [ ] **Step 3: Tag seeded placeholders in `DayPlan.new`**

In `src/dayctl/models.py`, the `tasks={...}` block inside `DayPlan.new` (currently lines 232-238) — add `"tag": "seed"` to the seeded music/code items:

```python
            tasks={
                "music": [_norm_task({"text": t, "tag": "seed"}) for t in DEFAULT_TASKS["music"]],
                "youtube": [],
                "marketing": [],
                "social": [],
                "code": [_norm_task({"text": t, "tag": "seed"}) for t in DEFAULT_TASKS["code"]],
            },
```

- [ ] **Step 4: Exclude seed tasks from `carry_forward`**

Replace `carry_forward` (currently lines 324-334) with:

```python
def carry_forward(plan: DayPlan, previous: DayPlan) -> list[str]:
    """Carry incomplete tasks from previous day into plan. Returns list of carried descriptions.

    Seed tasks (tag == "seed") are daily routine/placeholder items that DayPlan.new
    re-seeds every day; they are never carried — carrying them would duplicate the fresh
    seed and made real carry-forward look broken (see docs/superpowers/plans/
    2026-09-01-habit-module-v1.md).
    """
    carried: list[str] = []
    for area, tasks in incomplete_tasks(previous).items():
        existing = {t["text"] for t in plan.tasks.get(area, [])}
        for t in tasks:
            if t.get("tag") == "seed":
                continue
            if t["text"] in existing:
                continue
            plan.tasks.setdefault(area, []).append({**_norm_task(t), "carried": True})
            carried.append(t["text"])
    return carried
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/test_carry_forward.py -v` → both PASS
Then full suite: `.venv/bin/python -m pytest tests/ -q` → all pass. If a pre-existing test asserted the old seed tag `""`, update that assertion to `"seed"` (do NOT weaken it — the seed tag is the intended new behavior).

- [ ] **Step 6: Commit**

```bash
git add src/dayctl/models.py tests/test_carry_forward.py
git commit -m "fix: exclude re-seeded placeholders from carry-forward"
```

---

### Task 2: Add the `stack` area and seed the evening stack

**Goal:** The evening stack appears every day in `day show`, the web dashboard, and ntfy pushes; each step is checkable via `day stack N done` and the API.

**Why:** This is the v1 payload — the Atomic-Habits chain, hung on your real anchors, seeded daily. Reuses `tasks`; `incomplete_tasks` iterates `AREAS` (`models.py:317`) so adding `stack` auto-feeds the ntfy body and `from_dict` round-trip (`models.py:267`). Seeded with tag `seed` (Task 1) so it re-seeds fresh each day and never carries.

**Files:**
- Modify: `src/dayctl/models.py` (`DEFAULT_TASKS` ~149-158; `AREAS` 160; `DayPlan.new` tasks dict)
- Modify: `src/dayctl/display.py` (`print_plan`, insert after schedule divider ~197)
- Modify: `src/dayctl/cli.py` (`task` category choices 468; shortcut loop 475)
- Modify: `src/dayctl/server/api.py` (`Category` literal 15)
- Test: `tests/test_stack_area.py` (create)

**Acceptance Criteria:**
- [ ] `DayPlan.new` produces a `stack` area with 7 seeded items, all `tag == "seed"`.
- [ ] `from_dict` round-trips the `stack` area.
- [ ] `day stack 1 done` marks the first stack item complete.
- [ ] `day show` renders a `STACK` section.
- [ ] `POST /api/days/{day}/tasks/stack/0/toggle` returns 200 (area accepted).

**Verify:** `.venv/bin/python -m pytest tests/test_stack_area.py tests/ -q` → all pass

**Steps:**

- [ ] **Step 1: Write the failing test**

Create `tests/test_stack_area.py`:

```python
from dayctl.models import DayPlan, AREAS


def test_stack_area_seeded():
    plan = DayPlan.new("2026-09-01")
    assert "stack" in AREAS
    assert len(plan.tasks["stack"]) == 7
    assert all(t["tag"] == "seed" for t in plan.tasks["stack"])
    assert all(not t["done"] for t in plan.tasks["stack"])


def test_stack_area_roundtrips():
    plan = DayPlan.new("2026-09-01")
    plan.tasks["stack"][0]["done"] = True
    restored = DayPlan.from_dict(plan.to_dict())
    assert len(restored.tasks["stack"]) == 7
    assert restored.tasks["stack"][0]["done"] is True
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_stack_area.py -v`
Expected: FAIL — `"stack" not in AREAS`, `KeyError: 'stack'`.

- [ ] **Step 3: Add `stack` to `DEFAULT_TASKS` and `AREAS`**

In `src/dayctl/models.py`, extend `DEFAULT_TASKS` (currently 149-158) with a `stack` key, and append `"stack"` to `AREAS` (currently line 160):

```python
DEFAULT_TASKS = {
    "code": [
        "Define today's highest-value application task",
        "Complete one meaningful step",
    ],
    "music": [
        "Define today's highest-value music task",
        "Complete one meaningful step",
    ],
    "stack": [
        "Laptop off → gym clothes on (no browsing)",
        "Water bottle → head to gym",
        "Post-gym: shower + snack (protein+carb, 15m)",
        "Sit 5 min, let energy settle",
        "Open DAW, load current project",
        "20–30 min on ONE task (mix/edit/layer)",
        "Export date-stamped, close DAW",
    ],
}

AREAS = ["music", "youtube", "marketing", "social", "code", "stack"]
```

(`→` = →, `–` = –; keeps items short enough for the 55-wide box in `print_plan`.)

- [ ] **Step 4: Seed `stack` in `DayPlan.new`**

In the `tasks={...}` block of `DayPlan.new` (the one edited in Task 1), add a `stack` entry:

```python
            tasks={
                "music": [_norm_task({"text": t, "tag": "seed"}) for t in DEFAULT_TASKS["music"]],
                "youtube": [],
                "marketing": [],
                "social": [],
                "code": [_norm_task({"text": t, "tag": "seed"}) for t in DEFAULT_TASKS["code"]],
                "stack": [_norm_task({"text": t, "tag": "seed"}) for t in DEFAULT_TASKS["stack"]],
            },
```

(`from_dict` needs no change — line 267 already rebuilds every area in `AREAS`.)

- [ ] **Step 5: Run the model test — expect PASS**

Run: `.venv/bin/python -m pytest tests/test_stack_area.py -v` → both PASS.

- [ ] **Step 6: Render the stack in `print_plan`**

In `src/dayctl/display.py`, immediately after the schedule block's closing divider (currently line 197, `lines.append(_box_div(t))` that follows the `for item in plan.schedule` loop) and BEFORE the `# === Code Tasks ===` block, insert:

```python
    # === Stack (evening routine chain) ===
    lines.append(_box_row(t, _c(t["heading"], "STACK")))
    for idx, item in enumerate(plan.tasks.get("stack", []), start=1):
        mark = _render_check(t, bool(item["done"]))
        lines.append(_box_row(t, f"  {idx}. {mark} {item['text']}"))
    lines.append(_box_div(t))
```

- [ ] **Step 7: Allow `stack` on the CLI**

In `src/dayctl/cli.py`:
- Line 468, add `"stack"` to the `task` subparser choices:
  ```python
      p_task.add_argument("category", choices=["music", "code", "app", "stack"], help="Task area (app = code alias)")
  ```
- Line 475, add `"stack"` to the shortcut loop so `day stack add ...` / `day stack N done` work:
  ```python
      for category in ("music", "code", "stack"):
  ```

- [ ] **Step 8: Allow `stack` on the API**

In `src/dayctl/server/api.py`, line 15, add `"stack"` to the `Category` literal:

```python
Category = Literal["app", "music", "code", "youtube", "marketing", "social", "stack"]
```

- [ ] **Step 9: Manual verify CLI + render**

```bash
.venv/bin/python -m dayctl init --date 2026-09-02 --force
.venv/bin/python -m dayctl stack 1 done --date 2026-09-02
.venv/bin/python -m dayctl show --date 2026-09-02
```
Expected: `Completed: stack task #1`, and `day show` prints a `STACK` section with item 1 checked (✓).

- [ ] **Step 10: Run full suite + commit**

Run: `.venv/bin/python -m pytest tests/ -q` → all pass

```bash
git add src/dayctl/models.py src/dayctl/display.py src/dayctl/cli.py src/dayctl/server/api.py tests/test_stack_area.py
git commit -m "feat: add evening stack area, seeded daily and checkable"
```

**→ v1 MVP complete after this task. Use it for real before building Task 3/4.**

---

### Task 3 (v1.1): One-tap "done" from the phone

**Goal:** An ntfy nudge carries a "Done ✓" button that marks the next incomplete stack step done, without opening anything.

**Why:** Q10a. The existing toggle endpoint needs an index and un-does on a second tap; a stable "advance the next incomplete" action is one tap and idempotent-forward.

**⚠️ Reachability constraint (read before building):** ntfy action buttons are tapped on your **phone**, which cannot reach `localhost:8000`. This works only when the phone is on the **same wifi** as the mac, using the mac's **LAN IP** — set `DAYCTL_PUBLIC_URL` (e.g. `http://192.168.1.50:8000`). Off-wifi requires a tunnel or the (un-deployed) Fly path — out of scope. If `DAYCTL_PUBLIC_URL` is unset, the nudge stays plain (no button). **Security:** the bearer token is embedded in the ntfy message, so the `NTFY_TOPIC` must be private/authed (`NTFY_AUTH`).

**Files:**
- Modify: `src/dayctl/server/api.py` (new `advance` route)
- Modify: `src/dayctl/server/ntfy.py` (`post_ntfy` gains `actions`)
- Modify: `src/dayctl/server/scheduler.py` (`Poster` type 18; `tick_once` 64-79)
- Test: `tests/test_advance.py` (create)

**Acceptance Criteria:**
- [ ] `POST /api/days/{day}/tasks/stack/advance` marks the first incomplete `stack` task done and returns its text; returns `{"advanced": null}` when none remain.
- [ ] `post_ntfy` sets an `Actions` header only when `actions` is provided.
- [ ] With `DAYCTL_PUBLIC_URL` set, a fired nudge that has pending stack items includes an advance action; unset → no action, unchanged behavior.

**Verify:** `.venv/bin/python -m pytest tests/test_advance.py tests/ -q` → all pass

**Steps:**

- [ ] **Step 1: Write the failing test**

Create `tests/test_advance.py` (uses the `day_env` fixture — confirm its name in `tests/conftest.py` and match existing API tests' client setup; the shape below assumes a FastAPI `TestClient` with the token header helper other API tests use):

```python
from dayctl.models import DayPlan


def test_advance_marks_first_incomplete(day_env, client, auth_headers):
    plan = DayPlan.new("2026-09-02")
    # persist via the app's save path used by other api tests:
    from dayctl.storage import save_plan
    save_plan(plan)
    r = client.post("/api/days/2026-09-02/tasks/stack/advance", headers=auth_headers)
    assert r.status_code == 200
    assert r.json()["advanced"] == plan.tasks["stack"][0]["text"]
    r2 = client.get("/api/days/2026-09-02", headers=auth_headers)
    assert r2.json()["tasks"]["stack"][0]["done"] is True
```

- [ ] **Step 2: Run to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_advance.py -v`
Expected: FAIL — 404 (route not defined).

- [ ] **Step 3: Add the `advance` route**

In `src/dayctl/server/api.py`, after `toggle_task` (ends line 75), add:

```python
@router.post("/days/{day}/tasks/{cat}/advance")
def advance_task(day: str = Path(..., pattern=r"^\d{4}-\d{2}-\d{2}$"), cat: Category = ...) -> dict:
    """Mark the first incomplete task in an area done — a stable one-tap 'next step'."""
    plan = load_plan(day)
    area = _resolve_area(cat)
    for t in plan.tasks.get(area, []):
        if not t["done"]:
            t["done"] = True
            save_plan(plan)
            return {"advanced": t["text"], "plan": plan.to_dict()}
    return {"advanced": None, "plan": plan.to_dict()}
```

- [ ] **Step 4: Run to verify it passes**

Run: `.venv/bin/python -m pytest tests/test_advance.py -v` → PASS. (If the fixture/client wiring differs, adjust the test harness to match `tests/` conventions — do not change the route.)

- [ ] **Step 5: Add `actions` to `post_ntfy`**

In `src/dayctl/server/ntfy.py`, replace `post_ntfy` (12-22) with:

```python
def post_ntfy(topic: str, title: str, body: str, priority: str = "default", actions: str | None = None) -> None:
    """POST to ntfy topic. Failures are logged and swallowed."""
    headers = {"Title": title, "Priority": priority}
    if actions:
        headers["Actions"] = actions
    auth = os.environ.get("NTFY_AUTH")
    if auth:
        headers["Authorization"] = f"Bearer {auth}"
    try:
        r = httpx.post(topic, content=body.encode("utf-8"), headers=headers, timeout=5.0)
        r.raise_for_status()
    except Exception as e:
        log.warning("ntfy post failed: %s", e)
```

- [ ] **Step 6: Build the action in `tick_once`**

In `src/dayctl/server/scheduler.py`: change the `Poster` type (line 18) to `Poster = Callable[..., None]`, then replace `tick_once` (64-79) with:

```python
def _stack_action(plan: Optional[DayPlan], day: str) -> Optional[str]:
    """ntfy http-action that advances the next incomplete stack step. LAN-only.
    Returns None unless DAYCTL_PUBLIC_URL is set and a pending stack item exists."""
    base = os.environ.get("DAYCTL_PUBLIC_URL", "").strip().rstrip("/")
    token = os.environ.get("DAYCTL_TOKEN", "").strip()
    if not base or not token or plan is None:
        return None
    if not any(not t["done"] for t in plan.tasks.get("stack", [])):
        return None
    url = f"{base}/api/days/{day}/tasks/stack/advance"
    return f"http, Done ✓, {url}, method=POST, headers.Authorization=Bearer {token}, clear=true"


def tick_once(
    profile: dict,
    now: datetime,
    last_tick: datetime,
    poster: Poster,
    plan: Optional[DayPlan],
) -> None:
    topic = os.environ.get("NTFY_TOPIC", "")
    if not topic:
        return
    fires = should_fire_now(profile, now, last_tick)
    action = _stack_action(plan, now.date().isoformat())
    for _, label in fires:
        try:
            poster(topic, label, _body_for(plan), "default", action)
        except Exception as e:
            log.warning("poster failed: %s", e)
```

- [ ] **Step 7: Run full suite + commit**

Run: `.venv/bin/python -m pytest tests/ -q` → all pass

```bash
git add src/dayctl/server/api.py src/dayctl/server/ntfy.py src/dayctl/server/scheduler.py tests/test_advance.py
git commit -m "feat: one-tap ntfy advance for the evening stack (LAN)"
```

- [ ] **Step 8: Manual end-to-end (optional, needs phone on LAN)**

Set `DAYCTL_PUBLIC_URL` to the mac's LAN IP in the `com.dayos.web` plist env, restart the service (see `.claude/skills/dayctl-run-and-operate`), trigger a nudge, tap "Done ✓", confirm `day show` reflects it.

---

### Task 4 (v1.1): "Never miss twice" alarm

**Goal:** If the whole evening stack is missed two days running, one escalated ntfy fires — the only alarm. Missing one day stays silent.

**Why:** Q5a. This is the single Atomic-Habits accountability rule that ADHD tolerates — no penalties, no gamification, just "don't break twice."

**Files:**
- Modify: `src/dayctl/models.py` (add `stack_complete`, `missed_twice`)
- Modify: `src/dayctl/server/scheduler.py` (fire alarm once/day when `missed_twice`)
- Test: `tests/test_miss_twice.py` (create)

**Acceptance Criteria:**
- [ ] `stack_complete(plan)` is True iff every `stack` item is done.
- [ ] `missed_twice(prev_plan, prev2_plan)` is True iff the stack was incomplete on both prior days.
- [ ] The alarm fires at most once per day (guarded), and only when yesterday and the day before were both misses.

**Verify:** `.venv/bin/python -m pytest tests/test_miss_twice.py tests/ -q` → all pass

**Steps:**

- [ ] **Step 1: Write the failing test**

Create `tests/test_miss_twice.py`:

```python
from dayctl.models import DayPlan, stack_complete, missed_twice


def test_stack_complete():
    plan = DayPlan.new("2026-09-01")
    assert stack_complete(plan) is False
    for t in plan.tasks["stack"]:
        t["done"] = True
    assert stack_complete(plan) is True


def test_missed_twice():
    a = DayPlan.new("2026-08-30")   # incomplete stack
    b = DayPlan.new("2026-08-31")   # incomplete stack
    assert missed_twice(b, a) is True
    for t in b.tasks["stack"]:
        t["done"] = True
    assert missed_twice(b, a) is False
```

- [ ] **Step 2: Run to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_miss_twice.py -v`
Expected: FAIL — `ImportError: cannot import name 'stack_complete'`.

- [ ] **Step 3: Add the helpers**

In `src/dayctl/models.py`, after `score_plan` (ends line 280), add:

```python
def stack_complete(plan: DayPlan) -> bool:
    """True iff every evening-stack item is done (empty stack counts as incomplete)."""
    items = plan.tasks.get("stack", [])
    return bool(items) and all(t["done"] for t in items)


def missed_twice(prev: DayPlan, prev2: DayPlan) -> bool:
    """True iff the stack was left incomplete on both of the two prior days."""
    return not stack_complete(prev) and not stack_complete(prev2)
```

- [ ] **Step 4: Run to verify it passes**

Run: `.venv/bin/python -m pytest tests/test_miss_twice.py -v` → PASS.

- [ ] **Step 5: Fire the alarm once/day in the scheduler**

In `src/dayctl/server/scheduler.py`, import the helpers (`from dayctl.models import ..., stack_complete, missed_twice`) and in `ReminderScheduler._run` (94-103), after loading `plan`, add a guarded once-per-day check that loads the two prior days via `dayctl.storage` and, when `missed_twice`, posts one high-priority ntfy. Guard with an instance flag `self._alarm_date` set to today so it fires at most once per day:

```python
    def _run(self) -> None:
        now = datetime.now()
        today = now.date().isoformat()
        profile = profile_for_date(today)
        try:
            plan = load_plan(today)
        except Exception:
            plan = None
        tick_once(profile, now, self._last_tick, post_ntfy, plan)
        self._maybe_miss_alarm(now)
        self._last_tick = now

    def _maybe_miss_alarm(self, now: datetime) -> None:
        topic = os.environ.get("NTFY_TOPIC", "")
        today = now.date().isoformat()
        if not topic or getattr(self, "_alarm_date", None) == today:
            return
        from datetime import timedelta as _td
        d1 = (now.date() - _td(days=1)).isoformat()
        d2 = (now.date() - _td(days=2)).isoformat()
        try:
            prev, prev2 = load_plan(d1), load_plan(d2)
        except Exception:
            return
        if missed_twice(prev, prev2):
            try:
                post_ntfy(topic, "Don't miss twice", "Stack missed 2 days. Do one tiny step tonight.", "high")
            except Exception as e:
                log.warning("miss alarm failed: %s", e)
        self._alarm_date = today
```

Initialize `self._alarm_date = None` in `__init__` (after `self._last_tick`, line 85).

- [ ] **Step 6: Run full suite + commit**

Run: `.venv/bin/python -m pytest tests/ -q` → all pass

```bash
git add src/dayctl/models.py src/dayctl/server/scheduler.py tests/test_miss_twice.py
git commit -m "feat: never-miss-twice stack alarm"
```

---

## Deferred (v2+, intentionally out of scope)

Notion phone mirror · groceries agent · diet targets · gym/bike as Calendar events · finance (Gmail→Notion) · Splice music curation · additional stacks (morning, desk/focus) · one-tap on the 6 core habits (needs a JSON habit endpoint — only `/web/day/{day}/habit/{id}/toggle` exists today) · off-LAN one-tap (tunnel/Fly). Add only after v1 runs in real life.

## Self-review notes

- **Spec coverage:** 1c hybrid → engine-only in v1, Notion deferred (§Deferred). 2a chores/stack-first → Task 2. 3c ntfy+CLI → Task 2 (CLI/render) + Task 3 (ntfy one-tap). 4a free-form carried area → Task 2 (`stack` in `AREAS`, carry via Task 1). 5a per-habit + never-miss-twice → Task 4. 6a few/tappable → nudges ride existing schedule blocks (no new spam) + Task 3 button. 8a tiny ramp → one stack, seeded, `§Phasing`. 10a one-tap → Task 3 with the honest LAN caveat.
- **Type consistency:** `advance_task`/`_stack_action`/`stack_complete`/`missed_twice` names used consistently across tasks. `Category` literal, `AREAS`, `DEFAULT_TASKS["stack"]` all include `stack`.
- **Assumption to confirm during execution:** `tests/test_advance.py` assumes the repo's existing API-test fixtures (`client`/`auth_headers` or equivalent). Match `tests/conftest.py` conventions before running Step 1.
