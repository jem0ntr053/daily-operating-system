"""Shared test fixtures."""

import pytest


@pytest.fixture
def day_env(tmp_path, monkeypatch):
    """Patch storage paths to use tmp_path."""
    import dayctl.storage as storage
    monkeypatch.setattr(storage, "DATA_DIR", tmp_path)
    monkeypatch.setattr(storage, "DAYS_DIR", tmp_path / "days")
    return tmp_path
