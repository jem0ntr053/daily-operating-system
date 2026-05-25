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


def test_toggle_works_without_htmx_header(client):
    # The new design does not gate on HX-Request; toggle must succeed regardless.
    client.get("/day/2026-04-12")
    r = client.post("/web/day/2026-04-12/tasks/app/0/toggle")
    assert r.status_code == 200


def test_task_add_toggle_delete(client):
    client.post("/web/day/2026-05-24/tasks/music/add", data={"text": "mix bus"}, headers={"HX-Request": "true"})
    from dayctl.storage import load_plan
    assert load_plan("2026-05-24").tasks["music"][-1]["text"] == "mix bus"
    idx = len(load_plan("2026-05-24").tasks["music"]) - 1
    client.post(f"/web/day/2026-05-24/tasks/music/{idx}/toggle", headers={"HX-Request": "true"})
    assert load_plan("2026-05-24").tasks["music"][idx]["done"] is True
    client.post(f"/web/day/2026-05-24/tasks/music/{idx}/delete", headers={"HX-Request": "true"})
    assert all(t["text"] != "mix bus" for t in load_plan("2026-05-24").tasks["music"])


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


def test_edit_field_persists(client):
    r = client.post("/web/day/2026-05-24/field/focus", data={"value": "ship the UI"}, headers={"HX-Request": "true"})
    assert r.status_code in (200, 204)
    from dayctl.storage import load_plan
    assert load_plan("2026-05-24").focus == "ship the UI"


def test_edit_sleep_maps_to_sleep_hours(client):
    client.post("/web/day/2026-05-24/field/sleep", data={"value": "7.5"}, headers={"HX-Request": "true"})
    from dayctl.storage import load_plan
    assert load_plan("2026-05-24").sleep_hours == "7.5"


def test_week_card_links_and_renders(client):
    r = client.get("/day/2026-05-24")
    assert r.status_code == 200
    assert "week-row" in r.text
    assert 'href="/day/2026-05-' in r.text  # week rows link to days in that week


def test_add_and_delete_note(client):
    r = client.post("/web/day/2026-05-24/notes/add", data={"text": "felt good"}, headers={"HX-Request": "true"})
    assert r.status_code == 200 and "felt good" in r.text
    from dayctl.storage import load_plan
    assert load_plan("2026-05-24").notes[0]["text"] == "felt good"
    r2 = client.post("/web/day/2026-05-24/notes/0/delete", headers={"HX-Request": "true"})
    assert "felt good" not in r2.text
    assert load_plan("2026-05-24").notes == []
