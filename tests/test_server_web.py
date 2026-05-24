import pytest

pytest.importorskip("fastapi")

from fastapi.testclient import TestClient


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("DAYCTL_TOKEN", "tok")
    monkeypatch.setenv("DAYCTL_STORAGE", f"sqlite://{tmp_path}/w.db")
    from dayctl.storage import _reset_backend_cache
    _reset_backend_cache()
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


def test_login_sets_cookie(client):
    from dayctl.server.app import create_app
    c = TestClient(create_app())
    r = c.get("/login?token=tok", follow_redirects=False)
    assert r.status_code in (302, 307)
    assert "dayctl_token=tok" in r.headers.get("set-cookie", "")


def test_toggle_returns_updated_fragment(client):
    client.get("/day/2026-04-12")
    r = client.post(
        "/web/day/2026-04-12/tasks/app/0/toggle",
        headers={"HX-Request": "true"},
    )
    assert r.status_code == 200
    content = r.content.lower()
    assert b"checked" in content or b"done" in content


def test_toggle_rejects_non_htmx(client):
    client.get("/day/2026-04-12")
    r = client.post("/web/day/2026-04-12/tasks/app/0/toggle")
    assert r.status_code == 403


def test_day_page_renders_shell(client):
    r = client.get("/day/2026-05-24")
    assert r.status_code == 200
    body = r.text
    assert 'class="app"' in body
    assert "Daily OS" in body
    assert "date-nav" in body


def test_toggle_habit_flips_and_returns_pulse(client):
    r = client.post("/web/day/2026-05-24/habit/fast/toggle", headers={"HX-Request": "true"})
    assert r.status_code == 200
    assert "pulse" in r.text
    from dayctl.storage import load_plan
    assert load_plan("2026-05-24").completed["fast"] is True
