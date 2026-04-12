# Remote Access & Cross-Device Reminders Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make dayctl accessible from a phone via a cloud-hosted web UI, deliver schedule-driven push reminders to the phone via ntfy.sh, and keep the existing local CLI working unchanged.

**Architecture:** Introduce a `StorageBackend` protocol with JSON, SQLite, and Remote implementations. Add a FastAPI server (web + JSON API) that runs on Fly.io backed by SQLite, with an APScheduler job posting to ntfy at schedule block boundaries. Retire the Streamlit UI.

**Tech Stack:** Python 3.11+, FastAPI, Uvicorn, Jinja2, HTMX (CDN), APScheduler, httpx (for RemoteBackend + ntfy), SQLite (stdlib), pytest, Fly.io.

**Spec:** `docs/superpowers/specs/2026-04-12-remote-access-and-reminders-design.md`

---

## File Structure

**Create:**
- `src/dayctl/storage_backends/__init__.py` — backend protocol + selector
- `src/dayctl/storage_backends/json_backend.py`
- `src/dayctl/storage_backends/sqlite_backend.py`
- `src/dayctl/storage_backends/remote_backend.py`
- `src/dayctl/server/__init__.py`
- `src/dayctl/server/app.py`
- `src/dayctl/server/auth.py`
- `src/dayctl/server/api.py`
- `src/dayctl/server/web.py`
- `src/dayctl/server/ntfy.py`
- `src/dayctl/server/scheduler.py`
- `src/dayctl/server/templates/base.html`
- `src/dayctl/server/templates/day.html`
- `src/dayctl/server/templates/_task_row.html`
- `src/dayctl/server/static/style.css`
- `src/dayctl/schedule_parse.py` — parse "6:30 AM  Wake" into (time, label)
- `tests/test_storage_backends.py` — parameterized over JSON/SQLite
- `tests/test_remote_backend.py`
- `tests/test_server_api.py`
- `tests/test_server_web.py`
- `tests/test_schedule_parse.py`
- `tests/test_scheduler_logic.py`
- `Dockerfile`
- `fly.toml`

**Modify:**
- `src/dayctl/storage.py` — delegate to selected backend via env
- `src/dayctl/cli.py` — add `--remote`, `push`, `pull` subcommands
- `pyproject.toml` — add extras: `[project.optional-dependencies].server`
- `README.md` — brief note about `dayctl[server]`

**Delete (Task 11):**
- Existing Streamlit app files (identified during that task)

---

## Task 1: StorageBackend protocol + JSONBackend refactor

**Files:**
- Create: `src/dayctl/storage_backends/__init__.py`
- Create: `src/dayctl/storage_backends/json_backend.py`
- Modify: `src/dayctl/storage.py`
- Test: `tests/test_storage_backends.py`

- [ ] **Step 1: Write the failing tests**

`tests/test_storage_backends.py`:
```python
import pytest
from datetime import date
from dayctl.models import DayPlan
from dayctl.storage_backends.json_backend import JSONBackend


@pytest.fixture
def json_backend(tmp_path):
    return JSONBackend(root=tmp_path / "days")


def test_load_missing_day_creates_plan(json_backend):
    plan = json_backend.load_plan("2026-04-12")
    assert isinstance(plan, DayPlan)
    assert plan.day == "2026-04-12"


def test_save_then_load_roundtrips(json_backend):
    plan = DayPlan.new("2026-04-12")
    plan.focus = "test"
    json_backend.save_plan(plan)
    loaded = json_backend.load_plan("2026-04-12")
    assert loaded.focus == "test"


def test_list_days_returns_sorted(json_backend):
    for d in ["2026-04-13", "2026-04-11", "2026-04-12"]:
        json_backend.save_plan(DayPlan.new(d))
    assert json_backend.list_days() == ["2026-04-11", "2026-04-12", "2026-04-13"]


def test_delete_day_removes_file(json_backend):
    json_backend.save_plan(DayPlan.new("2026-04-12"))
    json_backend.delete_plan("2026-04-12")
    assert "2026-04-12" not in json_backend.list_days()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_storage_backends.py -v`
Expected: FAIL (module not found).

- [ ] **Step 3: Create the backend protocol**

`src/dayctl/storage_backends/__init__.py`:
```python
"""Storage backends for dayctl plans."""
from __future__ import annotations

import os
from typing import Protocol

from dayctl.models import DayPlan


class StorageBackend(Protocol):
    def load_plan(self, day_str: str) -> DayPlan: ...
    def save_plan(self, plan: DayPlan) -> None: ...
    def list_days(self) -> list[str]: ...
    def delete_plan(self, day_str: str) -> None: ...
    def exists(self, day_str: str) -> bool: ...


def select_backend() -> StorageBackend:
    """Pick a backend based on env vars. Default: JSONBackend at ~/.dayctl/days."""
    from pathlib import Path

    remote = os.environ.get("DAYCTL_REMOTE")
    if remote:
        from dayctl.storage_backends.remote_backend import RemoteBackend
        return RemoteBackend(base_url=remote, token=os.environ.get("DAYCTL_TOKEN", ""))

    storage_url = os.environ.get("DAYCTL_STORAGE", "")
    if storage_url.startswith("sqlite://"):
        from dayctl.storage_backends.sqlite_backend import SQLiteBackend
        return SQLiteBackend(path=storage_url.removeprefix("sqlite://"))

    from dayctl.storage_backends.json_backend import JSONBackend
    return JSONBackend(root=Path.home() / ".dayctl" / "days")
```

- [ ] **Step 4: Create JSONBackend**

`src/dayctl/storage_backends/json_backend.py`:
```python
"""JSON-file storage backend — preserves legacy ~/.dayctl/days behavior."""
from __future__ import annotations

import json
from pathlib import Path

from dayctl.models import DayPlan


class JSONBackend:
    def __init__(self, root: Path) -> None:
        self.root = Path(root)

    def _ensure(self) -> None:
        self.root.mkdir(parents=True, exist_ok=True)

    def _path(self, day_str: str) -> Path:
        return self.root / f"{day_str}.json"

    def exists(self, day_str: str) -> bool:
        return self._path(day_str).exists()

    def load_plan(self, day_str: str) -> DayPlan:
        self._ensure()
        path = self._path(day_str)
        if not path.exists():
            plan = DayPlan.new(day_str)
            self.save_plan(plan)
            return plan
        data = json.loads(path.read_text(encoding="utf-8"))
        return DayPlan.from_dict(data)

    def save_plan(self, plan: DayPlan) -> None:
        self._ensure()
        path = self._path(plan.day)
        tmp = path.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(plan.to_dict(), indent=2), encoding="utf-8")
        tmp.replace(path)

    def list_days(self) -> list[str]:
        self._ensure()
        return sorted(p.stem for p in self.root.glob("*.json"))

    def delete_plan(self, day_str: str) -> None:
        p = self._path(day_str)
        if p.exists():
            p.unlink()
```

- [ ] **Step 5: Make storage.py delegate to the selected backend**

Replace `src/dayctl/storage.py` contents with:
```python
"""Filesystem persistence for dayctl — delegates to the selected backend."""
from __future__ import annotations

import json
from datetime import date, timedelta
from functools import lru_cache
from pathlib import Path

from dayctl.models import DayPlan, carry_forward
from dayctl.storage_backends import select_backend

DATA_DIR = Path.home() / ".dayctl"
DAYS_DIR = DATA_DIR / "days"
CONFIG_PATH = DATA_DIR / "config.json"


@lru_cache(maxsize=1)
def _backend():
    return select_backend()


def _reset_backend_cache() -> None:
    """Test hook: clear cached backend after env changes."""
    _backend.cache_clear()


def ensure_dirs() -> None:
    DAYS_DIR.mkdir(parents=True, exist_ok=True)


def today_str() -> str:
    return date.today().isoformat()


def plan_path(day_str: str) -> Path:
    return DAYS_DIR / f"{day_str}.json"


def load_plan(day_str: str | None = None) -> DayPlan:
    ds = day_str or today_str()
    return _backend().load_plan(ds)


def save_plan(plan: DayPlan) -> None:
    _backend().save_plan(plan)


def list_days() -> list[str]:
    return _backend().list_days()


def init_or_load_plan(day_str: str, profile_key: str | None = None) -> tuple[DayPlan, list[str]]:
    """Load existing plan or create a new one with carry-forward."""
    b = _backend()
    carried: list[str] = []
    if b.exists(day_str):
        plan = b.load_plan(day_str)
        if profile_key and plan.profile != profile_key:
            plan.switch_profile(profile_key)
            b.save_plan(plan)
    else:
        plan = DayPlan.new(day_str, profile_key=profile_key)
        yesterday = (date.fromisoformat(day_str) - timedelta(days=1)).isoformat()
        if b.exists(yesterday):
            prev = b.load_plan(yesterday)
            carried = carry_forward(plan, prev)
        b.save_plan(plan)
    return plan, carried


def load_config() -> dict:
    ensure_dirs()
    if not CONFIG_PATH.exists():
        return {}
    return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))


def save_config(config: dict) -> None:
    ensure_dirs()
    CONFIG_PATH.write_text(json.dumps(config, indent=2), encoding="utf-8")
```

Note: existing tests patch `storage.DATA_DIR` / `storage.DAYS_DIR`. The `conftest.py` fixture must now also patch the backend. Update it:

`tests/conftest.py` — inside `day_env` fixture, after setting `DAYS_DIR`, add:
```python
from dayctl.storage_backends.json_backend import JSONBackend
monkeypatch.setattr(storage, "_backend", lambda: JSONBackend(root=tmp_path / "days"))
```
(Replace the `lru_cache`'d function reference with a lambda for test isolation.)

- [ ] **Step 6: Run full test suite**

Run: `pytest -v`
Expected: all existing tests pass + 4 new tests pass.

- [ ] **Step 7: Commit**

```bash
git add src/dayctl/storage.py src/dayctl/storage_backends/ tests/test_storage_backends.py tests/conftest.py
git commit -m "Refactor storage into pluggable backend protocol"
```

---

## Task 2: SQLiteBackend

**Files:**
- Create: `src/dayctl/storage_backends/sqlite_backend.py`
- Modify: `tests/test_storage_backends.py` (parameterize over both backends)

- [ ] **Step 1: Add parameterized contract tests**

Append to `tests/test_storage_backends.py`:
```python
from dayctl.storage_backends.sqlite_backend import SQLiteBackend


@pytest.fixture
def sqlite_backend(tmp_path):
    return SQLiteBackend(path=str(tmp_path / "dayctl.db"))


@pytest.fixture(params=["json", "sqlite"])
def backend(request, json_backend, sqlite_backend):
    return {"json": json_backend, "sqlite": sqlite_backend}[request.param]


def test_contract_load_missing_creates(backend):
    plan = backend.load_plan("2026-04-12")
    assert plan.day == "2026-04-12"


def test_contract_roundtrip(backend):
    plan = DayPlan.new("2026-04-12")
    plan.focus = "x"
    backend.save_plan(plan)
    assert backend.load_plan("2026-04-12").focus == "x"


def test_contract_list_sorted(backend):
    for d in ["2026-04-13", "2026-04-11"]:
        backend.save_plan(DayPlan.new(d))
    assert backend.list_days() == ["2026-04-11", "2026-04-13"]


def test_contract_delete(backend):
    backend.save_plan(DayPlan.new("2026-04-12"))
    backend.delete_plan("2026-04-12")
    assert not backend.exists("2026-04-12")
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_storage_backends.py -v`
Expected: FAIL (SQLiteBackend missing).

- [ ] **Step 3: Implement SQLiteBackend**

`src/dayctl/storage_backends/sqlite_backend.py`:
```python
"""SQLite storage backend — one row per day, plan stored as JSON blob."""
from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from dayctl.models import DayPlan

_SCHEMA = """
CREATE TABLE IF NOT EXISTS plans (
  date       TEXT PRIMARY KEY,
  json       TEXT NOT NULL,
  updated_at TEXT NOT NULL
);
"""


class SQLiteBackend:
    def __init__(self, path: str) -> None:
        self.path = path
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        with self._conn() as c:
            c.executescript(_SCHEMA)

    def _conn(self) -> sqlite3.Connection:
        c = sqlite3.connect(self.path, isolation_level=None)
        c.execute("PRAGMA journal_mode=WAL")
        return c

    def exists(self, day_str: str) -> bool:
        with self._conn() as c:
            row = c.execute("SELECT 1 FROM plans WHERE date = ?", (day_str,)).fetchone()
            return row is not None

    def load_plan(self, day_str: str) -> DayPlan:
        with self._conn() as c:
            row = c.execute("SELECT json FROM plans WHERE date = ?", (day_str,)).fetchone()
        if row is None:
            plan = DayPlan.new(day_str)
            self.save_plan(plan)
            return plan
        return DayPlan.from_dict(json.loads(row[0]))

    def save_plan(self, plan: DayPlan) -> None:
        now = datetime.now(timezone.utc).isoformat()
        blob = json.dumps(plan.to_dict())
        with self._conn() as c:
            c.execute(
                "INSERT INTO plans(date, json, updated_at) VALUES(?,?,?) "
                "ON CONFLICT(date) DO UPDATE SET json=excluded.json, updated_at=excluded.updated_at",
                (plan.day, blob, now),
            )

    def list_days(self) -> list[str]:
        with self._conn() as c:
            rows = c.execute("SELECT date FROM plans ORDER BY date").fetchall()
        return [r[0] for r in rows]

    def delete_plan(self, day_str: str) -> None:
        with self._conn() as c:
            c.execute("DELETE FROM plans WHERE date = ?", (day_str,))
```

- [ ] **Step 4: Run tests**

Run: `pytest tests/test_storage_backends.py -v`
Expected: PASS (all contract tests pass for both backends).

- [ ] **Step 5: Commit**

```bash
git add src/dayctl/storage_backends/sqlite_backend.py tests/test_storage_backends.py
git commit -m "Add SQLite storage backend"
```

---

## Task 3: Schedule line parser

**Files:**
- Create: `src/dayctl/schedule_parse.py`
- Test: `tests/test_schedule_parse.py`

Rationale: `SCHEDULE_PROFILES` entries look like `"6:30 AM  Wake"` — structured time is buried in the prefix. The scheduler needs `time` objects to detect block transitions.

- [ ] **Step 1: Write failing tests**

`tests/test_schedule_parse.py`:
```python
from datetime import time
from dayctl.schedule_parse import parse_block


def test_parses_am():
    t, label = parse_block("6:30 AM  Wake")
    assert t == time(6, 30)
    assert label == "Wake"


def test_parses_pm():
    t, label = parse_block("4:20 PM  Leave for Gym")
    assert t == time(16, 20)


def test_parses_range_takes_start():
    t, label = parse_block("8:00 AM–4:00 PM  Remote Work")
    assert t == time(8, 0)
    assert label == "Remote Work"


def test_returns_none_on_unparseable():
    assert parse_block("9:30 PM onward  Social / Show Prep") is not None  # still parses 9:30 PM
    assert parse_block("no time here") is None
```

- [ ] **Step 2: Verify failure**

Run: `pytest tests/test_schedule_parse.py -v`
Expected: FAIL (module missing).

- [ ] **Step 3: Implement parser**

`src/dayctl/schedule_parse.py`:
```python
"""Parse schedule block strings like '6:30 AM  Wake' or '8:00 AM-4:00 PM  Remote Work'."""
from __future__ import annotations

import re
from datetime import time

_TIME_RE = re.compile(r"^\s*(\d{1,2}):(\d{2})\s*(AM|PM)", re.IGNORECASE)


def parse_block(line: str) -> tuple[time, str] | None:
    """Return (start_time, label) or None if no leading time found.

    For ranges like '8:00 AM-4:00 PM  Remote Work', returns the start time.
    The label is everything after the first double-space separator, stripped.
    """
    m = _TIME_RE.match(line)
    if not m:
        return None
    hour = int(m.group(1)) % 12
    if m.group(3).upper() == "PM":
        hour += 12
    minute = int(m.group(2))
    parts = line.split("  ", 1)
    label = parts[1].strip() if len(parts) == 2 else ""
    return time(hour, minute), label
```

- [ ] **Step 4: Run tests**

Run: `pytest tests/test_schedule_parse.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/dayctl/schedule_parse.py tests/test_schedule_parse.py
git commit -m "Add schedule block line parser"
```

---

## Task 4: FastAPI app scaffold + auth

**Files:**
- Create: `src/dayctl/server/__init__.py` (empty)
- Create: `src/dayctl/server/auth.py`
- Create: `src/dayctl/server/app.py`
- Modify: `pyproject.toml`

- [ ] **Step 1: Add server extras to pyproject.toml**

Under `[project.optional-dependencies]` add:
```toml
server = [
  "fastapi>=0.110",
  "uvicorn[standard]>=0.29",
  "jinja2>=3.1",
  "apscheduler>=3.10",
  "httpx>=0.27",
]
```

Install: `pip install -e '.[server]'`

- [ ] **Step 2: Write failing test**

`tests/test_server_api.py`:
```python
import os
import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("DAYCTL_TOKEN", "testtoken")
    monkeypatch.setenv("DAYCTL_STORAGE", f"sqlite://{tmp_path}/dayctl.db")
    from dayctl.storage import _backend
    _backend.cache_clear()
    from dayctl.server.app import create_app
    return TestClient(create_app())


def test_health_no_auth_required(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"ok": True}


def test_api_requires_auth(client):
    r = client.get("/api/days/2026-04-12")
    assert r.status_code == 401


def test_api_accepts_valid_token(client):
    r = client.get("/api/days/2026-04-12", headers={"Authorization": "Bearer testtoken"})
    assert r.status_code == 200
```

- [ ] **Step 3: Verify failure**

Run: `pytest tests/test_server_api.py -v`
Expected: FAIL (module missing).

- [ ] **Step 4: Implement auth**

`src/dayctl/server/auth.py`:
```python
"""Single-user bearer token auth."""
from __future__ import annotations

import os

from fastapi import Header, HTTPException, Request


def _expected_token() -> str:
    tok = os.environ.get("DAYCTL_TOKEN", "")
    if not tok:
        raise RuntimeError("DAYCTL_TOKEN env var not set")
    return tok


def require_token(
    authorization: str | None = Header(default=None),
    request: Request = None,  # type: ignore[assignment]
) -> None:
    expected = _expected_token()
    header_token = ""
    if authorization and authorization.lower().startswith("bearer "):
        header_token = authorization.split(" ", 1)[1].strip()
    cookie_token = request.cookies.get("dayctl_token", "") if request else ""
    if header_token != expected and cookie_token != expected:
        raise HTTPException(status_code=401, detail="Unauthorized")
```

- [ ] **Step 5: Implement app factory**

`src/dayctl/server/app.py`:
```python
"""FastAPI application factory for dayctl server."""
from __future__ import annotations

from fastapi import Depends, FastAPI

from dayctl.server.auth import require_token


def create_app() -> FastAPI:
    app = FastAPI(title="dayctl")

    @app.get("/health")
    def health() -> dict:
        return {"ok": True}

    # Placeholder protected route — replaced in Task 5
    @app.get("/api/days/{day}", dependencies=[Depends(require_token)])
    def get_day(day: str) -> dict:
        from dayctl.storage import load_plan
        return load_plan(day).to_dict()

    return app
```

`src/dayctl/server/__init__.py`: empty file.

- [ ] **Step 6: Run tests**

Run: `pytest tests/test_server_api.py -v`
Expected: PASS (3 tests).

- [ ] **Step 7: Commit**

```bash
git add pyproject.toml src/dayctl/server/ tests/test_server_api.py
git commit -m "Add FastAPI server scaffold with bearer token auth"
```

---

## Task 5: API routes — days and tasks

**Files:**
- Create: `src/dayctl/server/api.py`
- Modify: `src/dayctl/server/app.py`
- Modify: `tests/test_server_api.py`

- [ ] **Step 1: Add failing tests**

Append to `tests/test_server_api.py`:
```python
AUTH = {"Authorization": "Bearer testtoken"}


def test_put_day_replaces_plan(client):
    from dayctl.models import DayPlan
    p = DayPlan.new("2026-04-12")
    p.focus = "updated"
    r = client.put("/api/days/2026-04-12", json=p.to_dict(), headers=AUTH)
    assert r.status_code == 200
    assert client.get("/api/days/2026-04-12", headers=AUTH).json()["focus"] == "updated"


def test_toggle_app_task(client):
    client.get("/api/days/2026-04-12", headers=AUTH)  # create
    r = client.post("/api/days/2026-04-12/tasks/app/0/toggle", headers=AUTH)
    assert r.status_code == 200
    assert r.json()["app_tasks"][0]["done"] is True


def test_add_app_task(client):
    r = client.post(
        "/api/days/2026-04-12/tasks/app",
        json={"task": "new thing"},
        headers=AUTH,
    )
    assert r.status_code == 200
    assert any(t["task"] == "new thing" for t in r.json()["app_tasks"])


def test_delete_app_task(client):
    client.post("/api/days/2026-04-12/tasks/app", json={"task": "gone"}, headers=AUTH)
    plan = client.get("/api/days/2026-04-12", headers=AUTH).json()
    idx = next(i for i, t in enumerate(plan["app_tasks"]) if t["task"] == "gone")
    r = client.delete(f"/api/days/2026-04-12/tasks/app/{idx}", headers=AUTH)
    assert r.status_code == 200
    assert all(t["task"] != "gone" for t in r.json()["app_tasks"])


def test_list_days(client):
    client.get("/api/days/2026-04-12", headers=AUTH)
    client.get("/api/days/2026-04-13", headers=AUTH)
    r = client.get("/api/days", headers=AUTH)
    assert r.status_code == 200
    assert "2026-04-12" in r.json()["days"]
```

- [ ] **Step 2: Verify failure**

Run: `pytest tests/test_server_api.py -v`
Expected: new tests FAIL (routes missing).

- [ ] **Step 3: Implement API router**

`src/dayctl/server/api.py`:
```python
"""JSON API routes mirroring CLI commands."""
from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from dayctl.models import DayPlan
from dayctl.server.auth import require_token
from dayctl.storage import list_days, load_plan, save_plan

router = APIRouter(prefix="/api", dependencies=[Depends(require_token)])

Category = Literal["app", "music"]


class TaskBody(BaseModel):
    task: str


def _tasks_attr(cat: Category) -> str:
    return f"{cat}_tasks"


@router.get("/days")
def list_all_days() -> dict:
    return {"days": list_days()}


@router.get("/days/{day}")
def get_day(day: str) -> dict:
    return load_plan(day).to_dict()


@router.put("/days/{day}")
def put_day(day: str, payload: dict) -> dict:
    if payload.get("day") != day:
        raise HTTPException(400, "payload day mismatch")
    plan = DayPlan.from_dict(payload)
    save_plan(plan)
    return plan.to_dict()


@router.post("/days/{day}/tasks/{cat}")
def add_task(day: str, cat: Category, body: TaskBody) -> dict:
    plan = load_plan(day)
    getattr(plan, _tasks_attr(cat)).append({"task": body.task, "done": False})
    save_plan(plan)
    return plan.to_dict()


@router.post("/days/{day}/tasks/{cat}/{idx}/toggle")
def toggle_task(day: str, cat: Category, idx: int) -> dict:
    plan = load_plan(day)
    tasks = getattr(plan, _tasks_attr(cat))
    if idx < 0 or idx >= len(tasks):
        raise HTTPException(404, "task index out of range")
    tasks[idx]["done"] = not tasks[idx]["done"]
    save_plan(plan)
    return plan.to_dict()


@router.delete("/days/{day}/tasks/{cat}/{idx}")
def delete_task(day: str, cat: Category, idx: int) -> dict:
    plan = load_plan(day)
    tasks = getattr(plan, _tasks_attr(cat))
    if idx < 0 or idx >= len(tasks):
        raise HTTPException(404, "task index out of range")
    tasks.pop(idx)
    save_plan(plan)
    return plan.to_dict()
```

- [ ] **Step 4: Wire router in app.py**

Replace the placeholder route in `src/dayctl/server/app.py` with:
```python
from fastapi import FastAPI

from dayctl.server.api import router as api_router


def create_app() -> FastAPI:
    app = FastAPI(title="dayctl")

    @app.get("/health")
    def health() -> dict:
        return {"ok": True}

    app.include_router(api_router)
    return app
```

- [ ] **Step 5: Run tests**

Run: `pytest tests/test_server_api.py -v`
Expected: PASS (all tests).

- [ ] **Step 6: Commit**

```bash
git add src/dayctl/server/api.py src/dayctl/server/app.py tests/test_server_api.py
git commit -m "Add JSON API routes for days and tasks"
```

---

## Task 6: RemoteBackend + CLI `--remote`

**Files:**
- Create: `src/dayctl/storage_backends/remote_backend.py`
- Create: `tests/test_remote_backend.py`
- Modify: `src/dayctl/cli.py`

- [ ] **Step 1: Write failing tests**

`tests/test_remote_backend.py`:
```python
import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def remote(tmp_path, monkeypatch):
    monkeypatch.setenv("DAYCTL_TOKEN", "tok")
    monkeypatch.setenv("DAYCTL_STORAGE", f"sqlite://{tmp_path}/d.db")
    from dayctl.storage import _backend
    _backend.cache_clear()
    from dayctl.server.app import create_app
    app = create_app()
    client = TestClient(app)

    from dayctl.storage_backends.remote_backend import RemoteBackend
    r = RemoteBackend(base_url="http://testserver", token="tok")
    r._client = client  # inject test client
    return r


def test_remote_load_and_save(remote):
    from dayctl.models import DayPlan
    p = DayPlan.new("2026-04-12")
    p.focus = "remote"
    remote.save_plan(p)
    loaded = remote.load_plan("2026-04-12")
    assert loaded.focus == "remote"


def test_remote_list_days(remote):
    from dayctl.models import DayPlan
    remote.save_plan(DayPlan.new("2026-04-12"))
    assert "2026-04-12" in remote.list_days()
```

- [ ] **Step 2: Verify failure**

Run: `pytest tests/test_remote_backend.py -v`
Expected: FAIL (module missing).

- [ ] **Step 3: Implement RemoteBackend**

`src/dayctl/storage_backends/remote_backend.py`:
```python
"""HTTP client storage backend — talks to the dayctl server."""
from __future__ import annotations

import httpx

from dayctl.models import DayPlan


class RemoteBackend:
    def __init__(self, base_url: str, token: str) -> None:
        self.base_url = base_url.rstrip("/")
        self.token = token
        self._client: httpx.Client | None = None  # may be injected for tests

    def _http(self):
        if self._client is None:
            self._client = httpx.Client(base_url=self.base_url, timeout=10.0)
        return self._client

    def _headers(self) -> dict:
        return {"Authorization": f"Bearer {self.token}"}

    def exists(self, day_str: str) -> bool:
        return day_str in self.list_days()

    def load_plan(self, day_str: str) -> DayPlan:
        r = self._http().get(f"/api/days/{day_str}", headers=self._headers())
        r.raise_for_status()
        return DayPlan.from_dict(r.json())

    def save_plan(self, plan: DayPlan) -> None:
        r = self._http().put(
            f"/api/days/{plan.day}", json=plan.to_dict(), headers=self._headers()
        )
        r.raise_for_status()

    def list_days(self) -> list[str]:
        r = self._http().get("/api/days", headers=self._headers())
        r.raise_for_status()
        return r.json()["days"]

    def delete_plan(self, day_str: str) -> None:
        raise NotImplementedError("delete not exposed over API in v1")
```

- [ ] **Step 4: Add `--remote` CLI flag**

In `src/dayctl/cli.py`, at the top of the argparse parser setup, add a global flag. Locate the parser creation (search for `ArgumentParser`) and add:
```python
parser.add_argument(
    "--remote",
    help="Base URL of a remote dayctl server (overrides DAYCTL_REMOTE env)",
)
parser.add_argument(
    "--token",
    help="Bearer token for remote server (overrides DAYCTL_TOKEN env)",
)
```

Early in `main()`, right after `args = parser.parse_args()`:
```python
import os
if args.remote:
    os.environ["DAYCTL_REMOTE"] = args.remote
if args.token:
    os.environ["DAYCTL_TOKEN"] = args.token
if args.remote or args.token:
    from dayctl.storage import _backend
    _backend.cache_clear()
```

- [ ] **Step 5: Run tests**

Run: `pytest -v`
Expected: all pass.

- [ ] **Step 6: Commit**

```bash
git add src/dayctl/storage_backends/remote_backend.py src/dayctl/cli.py tests/test_remote_backend.py
git commit -m "Add remote backend and --remote CLI flag"
```

---

## Task 7: `day push` / `day pull` commands

**Files:**
- Modify: `src/dayctl/cli.py`
- Create: `tests/test_cli_push_pull.py`

- [ ] **Step 1: Write failing tests**

`tests/test_cli_push_pull.py`:
```python
import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def server(tmp_path, monkeypatch):
    monkeypatch.setenv("DAYCTL_TOKEN", "tok")
    monkeypatch.setenv("DAYCTL_STORAGE", f"sqlite://{tmp_path}/srv.db")
    from dayctl.storage import _backend
    _backend.cache_clear()
    from dayctl.server.app import create_app
    return TestClient(create_app())


def test_push_copies_local_to_remote(server, tmp_path, monkeypatch):
    # local JSON backend
    from dayctl.storage_backends.json_backend import JSONBackend
    from dayctl.storage_backends.remote_backend import RemoteBackend
    from dayctl.models import DayPlan
    from dayctl.cli import push_day

    local = JSONBackend(root=tmp_path / "local")
    p = DayPlan.new("2026-04-12")
    p.focus = "pushed"
    local.save_plan(p)

    remote = RemoteBackend(base_url="http://testserver", token="tok")
    remote._client = server

    push_day("2026-04-12", local, remote)
    assert remote.load_plan("2026-04-12").focus == "pushed"


def test_pull_copies_remote_to_local(server, tmp_path):
    from dayctl.storage_backends.json_backend import JSONBackend
    from dayctl.storage_backends.remote_backend import RemoteBackend
    from dayctl.models import DayPlan
    from dayctl.cli import pull_day

    remote = RemoteBackend(base_url="http://testserver", token="tok")
    remote._client = server
    p = DayPlan.new("2026-04-12")
    p.focus = "pulled"
    remote.save_plan(p)

    local = JSONBackend(root=tmp_path / "local")
    pull_day("2026-04-12", local, remote)
    assert local.load_plan("2026-04-12").focus == "pulled"
```

- [ ] **Step 2: Verify failure**

Run: `pytest tests/test_cli_push_pull.py -v`
Expected: FAIL (`push_day`/`pull_day` missing).

- [ ] **Step 3: Implement push/pull helpers and subcommands**

In `src/dayctl/cli.py`, add near other helpers:
```python
def push_day(day_str: str, local, remote) -> None:
    """Copy a day from local backend to remote backend."""
    plan = local.load_plan(day_str)
    remote.save_plan(plan)


def pull_day(day_str: str, local, remote) -> None:
    """Copy a day from remote backend to local backend."""
    plan = remote.load_plan(day_str)
    local.save_plan(plan)
```

Add subparsers `push` and `pull`:
```python
p_push = subparsers.add_parser("push", help="Push a day from local to remote")
p_push.add_argument("date", nargs="?", default="today")

p_pull = subparsers.add_parser("pull", help="Pull a day from remote to local")
p_pull.add_argument("date", nargs="?", default="today")
```

Handlers (add `cmd_push`, `cmd_pull` following the existing `cmd_*` pattern):
```python
def cmd_push(args) -> None:
    import os
    from pathlib import Path
    from dayctl.storage_backends.json_backend import JSONBackend
    from dayctl.storage_backends.remote_backend import RemoteBackend
    if not os.environ.get("DAYCTL_REMOTE"):
        raise SystemExit("DAYCTL_REMOTE not set (or pass --remote)")
    day_str = resolve_date(args.date)
    local = JSONBackend(root=Path.home() / ".dayctl" / "days")
    remote = RemoteBackend(os.environ["DAYCTL_REMOTE"], os.environ.get("DAYCTL_TOKEN", ""))
    push_day(day_str, local, remote)
    print(f"Pushed {day_str}")


def cmd_pull(args) -> None:
    import os
    from pathlib import Path
    from dayctl.storage_backends.json_backend import JSONBackend
    from dayctl.storage_backends.remote_backend import RemoteBackend
    if not os.environ.get("DAYCTL_REMOTE"):
        raise SystemExit("DAYCTL_REMOTE not set (or pass --remote)")
    day_str = resolve_date(args.date)
    local = JSONBackend(root=Path.home() / ".dayctl" / "days")
    remote = RemoteBackend(os.environ["DAYCTL_REMOTE"], os.environ.get("DAYCTL_TOKEN", ""))
    pull_day(day_str, local, remote)
    print(f"Pulled {day_str}")
```

Wire into the command dispatch dict/if-chain.

- [ ] **Step 4: Run tests**

Run: `pytest -v`
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add src/dayctl/cli.py tests/test_cli_push_pull.py
git commit -m "Add day push and day pull subcommands"
```

---

## Task 8: Web UI — templates + HTMX task toggle

**Files:**
- Create: `src/dayctl/server/web.py`
- Create: `src/dayctl/server/templates/base.html`
- Create: `src/dayctl/server/templates/day.html`
- Create: `src/dayctl/server/templates/_task_row.html`
- Create: `src/dayctl/server/static/style.css`
- Create: `tests/test_server_web.py`
- Modify: `src/dayctl/server/app.py`

- [ ] **Step 1: Write failing tests**

`tests/test_server_web.py`:
```python
import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("DAYCTL_TOKEN", "tok")
    monkeypatch.setenv("DAYCTL_STORAGE", f"sqlite://{tmp_path}/w.db")
    from dayctl.storage import _backend
    _backend.cache_clear()
    from dayctl.server.app import create_app
    c = TestClient(create_app())
    c.cookies.set("dayctl_token", "tok")
    return c


def test_root_redirects_to_today(client):
    r = client.get("/", follow_redirects=False)
    assert r.status_code in (302, 307)
    assert "/day/" in r.headers["location"]


def test_day_page_renders(client):
    r = client.get("/day/2026-04-12")
    assert r.status_code == 200
    assert b"2026-04-12" in r.content
    assert b"app_tasks" in r.content or b"App" in r.content


def test_login_sets_cookie(client):
    c = TestClient(client.app)
    r = c.get("/login?token=tok", follow_redirects=False)
    assert r.status_code in (302, 307)
    assert "dayctl_token=tok" in r.headers.get("set-cookie", "")


def test_toggle_returns_updated_fragment(client):
    client.get("/day/2026-04-12")
    r = client.post("/web/day/2026-04-12/tasks/app/0/toggle")
    assert r.status_code == 200
    assert b"checked" in r.content.lower() or b"done" in r.content.lower()
```

- [ ] **Step 2: Verify failure**

Run: `pytest tests/test_server_web.py -v`
Expected: FAIL.

- [ ] **Step 3: Create templates**

`src/dayctl/server/templates/base.html`:
```html
<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>dayctl — {{ day }}</title>
<link rel="stylesheet" href="/static/style.css">
<script src="https://unpkg.com/htmx.org@1.9.12"></script>
</head>
<body>
{% block content %}{% endblock %}
</body>
</html>
```

`src/dayctl/server/templates/day.html`:
```html
{% extends "base.html" %}
{% block content %}
<main>
  <header>
    <h1>{{ plan.day }}</h1>
    <p class="focus">{{ plan.focus or "(no focus set)" }}</p>
    <p class="score">Score: {{ score }}/4</p>
  </header>

  <section>
    <h2>App</h2>
    <ul id="app-tasks">
      {% for t in plan.app_tasks %}
        {% include "_task_row.html" with context %}
      {% endfor %}
    </ul>
  </section>

  <section>
    <h2>Music</h2>
    <ul id="music-tasks">
      {% for t in plan.music_tasks %}
        {% set cat = "music" %}
        {% include "_task_row.html" with context %}
      {% endfor %}
    </ul>
  </section>

  <section>
    <h2>Schedule</h2>
    <ul class="schedule">
      {% for line in plan.schedule %}<li>{{ line }}</li>{% endfor %}
    </ul>
  </section>
</main>
{% endblock %}
```

`src/dayctl/server/templates/_task_row.html`:
```html
{% set cat = cat or "app" %}
<li id="task-{{ cat }}-{{ loop.index0 }}" class="task {% if t.done %}done{% endif %}">
  <form hx-post="/web/day/{{ plan.day }}/tasks/{{ cat }}/{{ loop.index0 }}/toggle"
        hx-target="#task-{{ cat }}-{{ loop.index0 }}"
        hx-swap="outerHTML">
    <button type="submit" aria-label="toggle">
      <input type="checkbox" {% if t.done %}checked{% endif %} disabled>
    </button>
    <span>{{ t.task }}</span>
  </form>
</li>
```

`src/dayctl/server/static/style.css`:
```css
:root { font-family: -apple-system, system-ui, sans-serif; }
body { max-width: 640px; margin: 0 auto; padding: 1rem; }
h1 { margin: 0; }
.focus { color: #666; margin: 0 0 .5rem; }
.score { font-weight: 600; }
ul { list-style: none; padding: 0; }
li.task { padding: .5rem 0; border-bottom: 1px solid #eee; }
li.task.done span { text-decoration: line-through; color: #999; }
li.task form { display: flex; gap: .5rem; align-items: center; }
li.task button { background: none; border: none; padding: 0; cursor: pointer; }
.schedule li { padding: .25rem 0; color: #444; font-size: .9rem; }
```

- [ ] **Step 4: Implement web router**

`src/dayctl/server/web.py`:
```python
"""HTML routes with HTMX fragment responses."""
from __future__ import annotations

import os
from datetime import date
from pathlib import Path
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from dayctl.models import score_plan
from dayctl.server.auth import require_token
from dayctl.storage import load_plan, save_plan

TEMPLATES_DIR = Path(__file__).parent / "templates"
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

router = APIRouter()
Category = Literal["app", "music"]


@router.get("/login")
def login(token: str) -> RedirectResponse:
    expected = os.environ.get("DAYCTL_TOKEN", "")
    if not expected or token != expected:
        raise HTTPException(401, "bad token")
    resp = RedirectResponse(url="/", status_code=302)
    resp.set_cookie("dayctl_token", token, httponly=True, samesite="lax")
    return resp


@router.get("/", dependencies=[Depends(require_token)])
def root() -> RedirectResponse:
    return RedirectResponse(url=f"/day/{date.today().isoformat()}", status_code=302)


@router.get("/day/{day}", response_class=HTMLResponse, dependencies=[Depends(require_token)])
def view_day(day: str, request: Request) -> HTMLResponse:
    plan = load_plan(day)
    return templates.TemplateResponse(
        "day.html",
        {"request": request, "plan": plan, "day": day, "score": score_plan(plan), "cat": "app"},
    )


@router.post(
    "/web/day/{day}/tasks/{cat}/{idx}/toggle",
    response_class=HTMLResponse,
    dependencies=[Depends(require_token)],
)
def toggle_task(day: str, cat: Category, idx: int, request: Request) -> HTMLResponse:
    plan = load_plan(day)
    tasks = getattr(plan, f"{cat}_tasks")
    if idx < 0 or idx >= len(tasks):
        raise HTTPException(404, "task index out of range")
    tasks[idx]["done"] = not tasks[idx]["done"]
    save_plan(plan)
    # Render single row fragment
    return templates.TemplateResponse(
        "_task_row.html",
        {
            "request": request,
            "t": tasks[idx],
            "plan": plan,
            "cat": cat,
            "loop": type("L", (), {"index0": idx})(),
        },
    )
```

- [ ] **Step 5: Wire web router and static files in app.py**

Update `src/dayctl/server/app.py`:
```python
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from dayctl.server.api import router as api_router
from dayctl.server.web import router as web_router

STATIC_DIR = Path(__file__).parent / "static"


def create_app() -> FastAPI:
    app = FastAPI(title="dayctl")

    @app.get("/health")
    def health() -> dict:
        return {"ok": True}

    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
    app.include_router(api_router)
    app.include_router(web_router)
    return app
```

- [ ] **Step 6: Run tests**

Run: `pytest tests/test_server_web.py -v`
Expected: PASS.

- [ ] **Step 7: Manual smoke test**

```bash
DAYCTL_TOKEN=dev DAYCTL_STORAGE=sqlite:///tmp/dev.db uvicorn dayctl.server.app:create_app --factory --port 8000
```
Open `http://localhost:8000/login?token=dev`. Verify the day page loads and a task toggle updates in place.

- [ ] **Step 8: Commit**

```bash
git add src/dayctl/server/web.py src/dayctl/server/templates/ src/dayctl/server/static/ src/dayctl/server/app.py tests/test_server_web.py
git commit -m "Add mobile-first web UI with HTMX task toggles"
```

---

## Task 9: Scheduler pure logic — `should_fire_now`

**Files:**
- Create: `src/dayctl/server/scheduler.py`
- Test: `tests/test_scheduler_logic.py`

- [ ] **Step 1: Write failing tests**

`tests/test_scheduler_logic.py`:
```python
from datetime import datetime, time

from dayctl.server.scheduler import should_fire_now


def _profile():
    return {
        "schedule": [
            "6:30 AM  Wake",
            "7:00 AM  App Work",
            "no time line — ignored",
            "4:30 PM  Gym",
        ],
    }


def test_fires_on_block_start():
    now = datetime(2026, 4, 12, 7, 0, 30)
    last = datetime(2026, 4, 12, 6, 59, 0)
    fires = should_fire_now(_profile(), now, last)
    assert len(fires) == 1
    assert fires[0][0] == time(7, 0)
    assert fires[0][1] == "App Work"


def test_no_fire_when_no_block_in_window():
    now = datetime(2026, 4, 12, 7, 30, 0)
    last = datetime(2026, 4, 12, 7, 15, 0)
    assert should_fire_now(_profile(), now, last) == []


def test_ignores_unparseable_lines():
    now = datetime(2026, 4, 12, 16, 30, 30)
    last = datetime(2026, 4, 12, 16, 29, 0)
    fires = should_fire_now(_profile(), now, last)
    assert fires == [(time(16, 30), "Gym")]


def test_handles_quiet_until(monkeypatch):
    monkeypatch.setenv("DAYCTL_QUIET_UNTIL", "2026-04-20")
    now = datetime(2026, 4, 12, 7, 0, 30)
    last = datetime(2026, 4, 12, 6, 59, 0)
    assert should_fire_now(_profile(), now, last) == []
```

- [ ] **Step 2: Verify failure**

Run: `pytest tests/test_scheduler_logic.py -v`
Expected: FAIL.

- [ ] **Step 3: Implement scheduler logic**

`src/dayctl/server/scheduler.py`:
```python
"""Schedule-driven reminder logic. Pure functions here; APScheduler glue in Task 10."""
from __future__ import annotations

import os
from datetime import date, datetime, time

from dayctl.schedule_parse import parse_block


def _in_quiet_window(now: datetime) -> bool:
    quiet = os.environ.get("DAYCTL_QUIET_UNTIL", "").strip()
    if not quiet:
        return False
    try:
        until = date.fromisoformat(quiet)
    except ValueError:
        return False
    return now.date() <= until


def should_fire_now(
    profile: dict, now: datetime, last_tick: datetime
) -> list[tuple[time, str]]:
    """Return (time, label) for any schedule block whose start time
    falls strictly after `last_tick` and at or before `now`."""
    if _in_quiet_window(now):
        return []
    if last_tick >= now:
        return []
    fires: list[tuple[time, str]] = []
    for line in profile.get("schedule", []):
        parsed = parse_block(line)
        if parsed is None:
            continue
        t, label = parsed
        block_today = datetime.combine(now.date(), t)
        if last_tick < block_today <= now:
            fires.append((t, label))
    return fires
```

- [ ] **Step 4: Run tests**

Run: `pytest tests/test_scheduler_logic.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/dayctl/server/scheduler.py tests/test_scheduler_logic.py
git commit -m "Add pure should_fire_now scheduler logic"
```

---

## Task 10: ntfy poster + APScheduler integration

**Files:**
- Create: `src/dayctl/server/ntfy.py`
- Modify: `src/dayctl/server/scheduler.py`
- Modify: `src/dayctl/server/app.py`

- [ ] **Step 1: Write failing test**

Append to `tests/test_scheduler_logic.py`:
```python
def test_tick_calls_poster_for_fires(monkeypatch):
    from datetime import datetime
    from dayctl.server.scheduler import tick_once

    monkeypatch.setenv("NTFY_TOPIC", "https://ntfy.sh/test")
    posted: list[dict] = []

    def fake_post(topic, title, body, priority):
        posted.append({"topic": topic, "title": title, "body": body})

    # Simulate now = 7:00, last tick at 6:59, profile has 7:00 AM block
    now = datetime(2026, 4, 12, 7, 0, 30)
    last = datetime(2026, 4, 12, 6, 59, 0)
    profile = {"schedule": ["7:00 AM  App Work"]}
    tick_once(profile=profile, now=now, last_tick=last, poster=fake_post, plan=None)
    assert len(posted) == 1
    assert posted[0]["title"] == "App Work"
```

- [ ] **Step 2: Verify failure**

Run: `pytest tests/test_scheduler_logic.py -v -k tick`
Expected: FAIL (`tick_once` missing).

- [ ] **Step 3: Implement ntfy poster**

`src/dayctl/server/ntfy.py`:
```python
"""Thin wrapper around ntfy.sh publish API."""
from __future__ import annotations

import logging
import os

import httpx

log = logging.getLogger(__name__)


def post_ntfy(topic: str, title: str, body: str, priority: str = "default") -> None:
    """POST to ntfy topic. Failures are logged and swallowed."""
    headers = {"Title": title, "Priority": priority}
    auth = os.environ.get("NTFY_AUTH")
    if auth:
        headers["Authorization"] = f"Bearer {auth}"
    try:
        r = httpx.post(topic, content=body.encode("utf-8"), headers=headers, timeout=5.0)
        r.raise_for_status()
    except Exception as e:  # noqa: BLE001
        log.warning("ntfy post failed: %s", e)
```

- [ ] **Step 4: Add `tick_once` and APScheduler glue**

Append to `src/dayctl/server/scheduler.py`:
```python
import logging
from datetime import datetime, timedelta
from typing import Callable, Optional

from apscheduler.schedulers.background import BackgroundScheduler

from dayctl.models import DayPlan, incomplete_tasks, profile_for_date
from dayctl.server.ntfy import post_ntfy
from dayctl.storage import load_plan

log = logging.getLogger(__name__)

Poster = Callable[[str, str, str, str], None]


def _body_for(plan: Optional[DayPlan]) -> str:
    if plan is None:
        return ""
    pending = incomplete_tasks(plan)
    lines: list[str] = []
    for cat, tasks in pending.items():
        for t in tasks[:2]:
            lines.append(f"• {t['task']}")
    return "\n".join(lines)


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
    for _, label in fires:
        try:
            poster(topic, label, _body_for(plan), "default")
        except Exception as e:  # noqa: BLE001
            log.warning("poster failed: %s", e)


class ReminderScheduler:
    def __init__(self) -> None:
        self._scheduler = BackgroundScheduler()
        self._last_tick: datetime = datetime.now() - timedelta(minutes=1)

    def start(self) -> None:
        self._scheduler.add_job(self._run, "interval", minutes=1, id="dayctl_tick")
        self._scheduler.start()

    def stop(self) -> None:
        self._scheduler.shutdown(wait=False)

    def _run(self) -> None:
        now = datetime.now()
        today = now.date().isoformat()
        profile = profile_for_date(today)
        try:
            plan = load_plan(today)
        except Exception:
            plan = None
        tick_once(profile, now, self._last_tick, post_ntfy, plan)
        self._last_tick = now
```

- [ ] **Step 5: Start/stop scheduler with the app**

Update `src/dayctl/server/app.py` — add lifespan:
```python
from contextlib import asynccontextmanager

from dayctl.server.scheduler import ReminderScheduler


@asynccontextmanager
async def _lifespan(app: FastAPI):
    sched = ReminderScheduler()
    sched.start()
    try:
        yield
    finally:
        sched.stop()


def create_app() -> FastAPI:
    app = FastAPI(title="dayctl", lifespan=_lifespan)
    # ... rest unchanged
```

- [ ] **Step 6: Run tests**

Run: `pytest -v`
Expected: all pass.

- [ ] **Step 7: Commit**

```bash
git add src/dayctl/server/ntfy.py src/dayctl/server/scheduler.py src/dayctl/server/app.py tests/test_scheduler_logic.py
git commit -m "Integrate ntfy poster with APScheduler reminder loop"
```

---

## Task 11: Retire Streamlit UI

**Files:**
- Identify during task (run `git grep -l streamlit` and `ls`).

- [ ] **Step 1: Find Streamlit files**

Run: `git grep -l streamlit` and `rg -l "streamlit" pyproject.toml README.md`.
Expected: a list of files including Streamlit entrypoint(s) and dependency entries.

- [ ] **Step 2: Delete Streamlit code**

Remove the Streamlit entrypoint file(s) and any helper modules used only by it. Remove `streamlit` from `pyproject.toml` deps (if present). Remove Streamlit-specific docs from README. Do NOT remove `themes.py` or `web_themes.py` unless confirmed unused — run `rg` first.

- [ ] **Step 3: Run full test suite**

Run: `pytest -v`
Expected: all pass.

- [ ] **Step 4: Commit**

```bash
git add -A
git commit -m "Retire Streamlit UI in favor of FastAPI web app"
```

---

## Task 12: Fly.io deployment config

**Files:**
- Create: `Dockerfile`
- Create: `fly.toml`
- Create: `.dockerignore`

- [ ] **Step 1: Create Dockerfile**

`Dockerfile`:
```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY pyproject.toml README.md ./
COPY src ./src
RUN pip install --no-cache-dir -e '.[server]'
ENV DAYCTL_STORAGE=sqlite:///data/dayctl.db
EXPOSE 8080
CMD ["uvicorn", "dayctl.server.app:create_app", "--factory", "--host", "0.0.0.0", "--port", "8080"]
```

- [ ] **Step 2: Create .dockerignore**

`.dockerignore`:
```
.git
.venv
__pycache__
*.pyc
tests
docs
.pytest_cache
```

- [ ] **Step 3: Create fly.toml**

`fly.toml` (replace `<APP_NAME>` with the user's chosen Fly app name):
```toml
app = "<APP_NAME>"
primary_region = "iad"

[build]

[env]

[mounts]
  source = "dayctl_data"
  destination = "/data"

[http_service]
  internal_port = 8080
  force_https = true
  auto_stop_machines = true
  auto_start_machines = true
  min_machines_running = 1

[[vm]]
  cpu_kind = "shared"
  cpus = 1
  memory_mb = 256
```

- [ ] **Step 4: Document deployment in README**

Append to `README.md`:
```markdown
## Remote deployment (Fly.io)

1. `pip install -e '.[server]'` locally to verify the server boots.
2. `fly launch --no-deploy` (edit generated `fly.toml` to match the one in this repo, or accept ours).
3. `fly volumes create dayctl_data --size 1`
4. `fly secrets set DAYCTL_TOKEN=$(openssl rand -hex 32) NTFY_TOPIC=https://ntfy.sh/<your-private-topic>`
5. `fly deploy`
6. Open `https://<app>.fly.dev/login?token=<token>` on your phone, Add to Home Screen.

On your laptop, point the CLI at the server when you want shared state:
```
export DAYCTL_REMOTE=https://<app>.fly.dev
export DAYCTL_TOKEN=<token>
day today
```
```

- [ ] **Step 5: Commit**

```bash
git add Dockerfile .dockerignore fly.toml README.md
git commit -m "Add Fly.io deployment config and docs"
```

- [ ] **Step 6: Deploy (manual — user runs)**

Leave this to the user. They should follow the README steps on their own machine with their own Fly account.

---

## Post-plan verification

- [ ] Run full test suite: `pytest -v` — all tests pass.
- [ ] Manual smoke: start server locally with `DAYCTL_TOKEN=dev DAYCTL_STORAGE=sqlite:///tmp/dev.db NTFY_TOPIC=https://ntfy.sh/<your-topic> uvicorn dayctl.server.app:create_app --factory`. Visit `/login?token=dev`, toggle a task, confirm it persists across reload.
- [ ] Local CLI regression: `day today` still works unchanged with no env vars set.
- [ ] Remote CLI: `DAYCTL_REMOTE=http://localhost:8000 DAYCTL_TOKEN=dev day today` hits the server.
- [ ] Scheduler: set `NTFY_TOPIC` to a real ntfy topic subscribed on phone; wait for next block boundary; confirm push arrives.
