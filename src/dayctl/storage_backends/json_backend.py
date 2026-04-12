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
        self._ensure()
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
