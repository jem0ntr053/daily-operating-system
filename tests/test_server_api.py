import pytest
pytest.importorskip("fastapi")

import os
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


def test_rejects_malformed_day(client):
    r = client.get("/api/days/not-a-date", headers=AUTH)
    assert r.status_code == 422
    r = client.get("/api/days/..%2F..%2Fetc/passwd", headers=AUTH)
    assert r.status_code in (404, 422)
