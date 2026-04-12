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
