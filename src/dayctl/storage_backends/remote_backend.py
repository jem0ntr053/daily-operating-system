"""HTTP client storage backend — talks to the dayctl server."""
from __future__ import annotations

import httpx

from dayctl.models import DayPlan


class RemoteBackend:
    def __init__(self, base_url: str, token: str) -> None:
        self.base_url = base_url.rstrip("/")
        self.token = token
        self._client = None  # may be httpx.Client or a TestClient (duck-typed)

    def _http(self):
        if self._client is None:
            self._client = httpx.Client(base_url=self.base_url, timeout=10.0)
        return self._client

    def _headers(self) -> dict:
        return {"Authorization": f"Bearer {self.token}"}

    def exists(self, day_str: str) -> bool:
        r = self._http().head(f"/api/days/{day_str}", headers=self._headers())
        if r.status_code == 204:
            return True
        if r.status_code == 404:
            return False
        r.raise_for_status()
        return False

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
        r = self._http().delete(f"/api/days/{day_str}", headers=self._headers())
        r.raise_for_status()
