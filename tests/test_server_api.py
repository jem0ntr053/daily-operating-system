import os
import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("DAYCTL_TOKEN", "testtoken")
    monkeypatch.setenv("DAYCTL_STORAGE", f"sqlite://{tmp_path}/dayctl.db")
    from dayctl.storage import _reset_backend_cache
    _reset_backend_cache()
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
