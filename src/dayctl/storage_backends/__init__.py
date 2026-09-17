"""Storage backends for dayctl plans."""
from __future__ import annotations

import os
from typing import Protocol

from dayctl.models import DayPlan


class StorageBackend(Protocol):
    # load_plan raises KeyError for a missing day — backends never materialize.
    # Day creation (with carry-forward) lives in storage.init_or_load_plan (#13).
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
