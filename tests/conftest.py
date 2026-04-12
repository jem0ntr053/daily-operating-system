"""Shared test fixtures."""

import pytest


@pytest.fixture
def day_env(tmp_path, monkeypatch):
    """Patch storage paths to use tmp_path."""
    import dayctl.storage as storage
    from dayctl.storage_backends.json_backend import JSONBackend

    monkeypatch.setattr(storage, "DATA_DIR", tmp_path)
    monkeypatch.setattr(storage, "DAYS_DIR", tmp_path / "days")
    monkeypatch.setattr(storage, "CONFIG_PATH", tmp_path / "config.json")
    monkeypatch.setattr(storage, "select_backend",
                        lambda: JSONBackend(root=tmp_path / "days"))
    storage._reset_backend_cache()

    yield tmp_path

    storage._reset_backend_cache()
