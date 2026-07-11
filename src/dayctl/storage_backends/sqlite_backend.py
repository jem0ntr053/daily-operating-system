"""SQLite storage backend — one row per day, plan stored as JSON blob."""
from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from dayctl.models import DayPlan


class SQLiteBackend:
    def __init__(self, path: str) -> None:
        self.path = path
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        self._connection = sqlite3.connect(
            self.path,
            isolation_level=None,
            check_same_thread=False,
        )
        row = self._connection.execute("PRAGMA journal_mode=WAL").fetchone()
        if row is None or row[0] != "wal":
            raise RuntimeError(
                f"WAL mode unavailable on {self.path!r} (got {row[0] if row else None!r})"
            )
        self._connection.execute(
            "CREATE TABLE IF NOT EXISTS plans ("
            "date TEXT PRIMARY KEY, json TEXT NOT NULL, updated_at TEXT NOT NULL)"
        )

    def exists(self, day_str: str) -> bool:
        row = self._connection.execute(
            "SELECT 1 FROM plans WHERE date = ?", (day_str,)
        ).fetchone()
        return row is not None

    def load_plan(self, day_str: str) -> DayPlan:
        row = self._connection.execute(
            "SELECT json FROM plans WHERE date = ?", (day_str,)
        ).fetchone()
        if row is None:
            raise KeyError(day_str)
        return DayPlan.from_dict(json.loads(row[0]))

    def save_plan(self, plan: DayPlan) -> None:
        now = datetime.now(timezone.utc).isoformat()
        blob = json.dumps(plan.to_dict())
        self._connection.execute(
            "INSERT INTO plans(date, json, updated_at) VALUES(?,?,?) "
            "ON CONFLICT(date) DO UPDATE SET json=excluded.json, updated_at=excluded.updated_at",
            (plan.day, blob, now),
        )

    def list_days(self) -> list[str]:
        rows = self._connection.execute(
            "SELECT date FROM plans ORDER BY date"
        ).fetchall()
        return [r[0] for r in rows]

    def delete_plan(self, day_str: str) -> None:
        self._connection.execute("DELETE FROM plans WHERE date = ?", (day_str,))
