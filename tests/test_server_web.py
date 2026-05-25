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


def test_idea_add_delete(client, tmp_path, monkeypatch):
    monkeypatch.setattr("dayctl.persistent.PERSISTENT_PATH", tmp_path / "persistent.json")
    r = client.post("/web/ideas/add", data={"text": "sample fridge hum", "bucket": "Music"}, headers={"HX-Request": "true"})
    assert "sample fridge hum" in r.text
    from dayctl.persistent import load_persistent
    assert load_persistent()["ideas"][0]["text"] == "sample fridge hum"
    client.post("/web/ideas/0/delete", headers={"HX-Request": "true"})
    assert load_persistent()["ideas"] == []


def test_stat_update_appends_spark(client, tmp_path, monkeypatch):
    monkeypatch.setattr("dayctl.persistent.PERSISTENT_PATH", tmp_path / "persistent.json")
    r = client.post("/web/stats/ytSubs", data={"v": "12.5K", "d": "+10", "trend": "up"}, headers={"HX-Request": "true"})
    from dayctl.persistent import load_persistent
    st = load_persistent()["stats"]["ytSubs"]
    assert st["v"] == "12.5K" and st["spark"][-1] == 12.5
    assert "glance-ytSubs" in r.text


def test_web_carries_incomplete_tasks_forward(client):
    from dayctl.storage import load_plan, save_plan
    # seed an incomplete music task on a day
    p = load_plan("2026-07-01")
    p.tasks["music"] = [{"text": "carry me", "done": False, "tag": "", "carried": False}]
    save_plan(p)
    # open the NEXT day via the web -> should carry forward
    client.get("/day/2026-07-02")
    nxt = load_plan("2026-07-02")
    assert any(t["text"] == "carry me" and t["carried"] for t in nxt.tasks["music"])


def test_task_add_with_tag(client):
    client.post("/web/day/2026-05-25/tasks/music/add", data={"text": "tagged task", "tag": "mix"}, headers={"HX-Request": "true"})
    from dayctl.storage import load_plan
    t = load_plan("2026-05-25").tasks["music"][-1]
    assert t["text"] == "tagged task" and t["tag"] == "MIX"


def test_glance_display_then_edit(client, tmp_path, monkeypatch):
    monkeypatch.setattr("dayctl.persistent.PERSISTENT_PATH", tmp_path / "persistent.json")
    body = client.get("/day/2026-05-25").text
    assert "tap to update" in body            # display mode by default
    edit = client.get("/web/stats/ytSubs/edit").text
    assert 'name="v"' in edit                 # edit form on demand


def test_polish_elements_present(client):
    body = client.get("/day/2026-05-25").text
    assert "Week " in body and "/ 52" in body          # header week
    assert "logged" in body                              # streak logged count
    assert "current project" in body                     # music area-stats
    assert "open campaigns" in body                      # marketing area-stats
    assert "CROSS-DISCIPLINE" in body                    # idea vault tag
    assert "idea-bucket" in body                         # bucket pills


def test_add_task_form_has_submit_button(client):
    # text + tag inputs need a submit button for Enter-to-submit to work.
    body = client.get("/day/2026-05-25").text
    assert 'type="submit"' in body


def test_idea_edit_updates_text(client, tmp_path, monkeypatch):
    monkeypatch.setattr("dayctl.persistent.PERSISTENT_PATH", tmp_path / "persistent.json")
    client.post("/web/ideas/add", data={"text": "first idea", "bucket": "Music"}, headers={"HX-Request": "true"})
    # edit form available
    edit = client.get("/web/ideas/0/edit").text
    assert 'name="text"' in edit and "first idea" in edit
    # save new text
    r = client.post("/web/ideas/0/save", data={"text": "edited idea"}, headers={"HX-Request": "true"})
    assert "edited idea" in r.text
    from dayctl.persistent import load_persistent
    assert load_persistent()["ideas"][0]["text"] == "edited idea"


def test_idea_edit_changes_topic(client, tmp_path, monkeypatch):
    monkeypatch.setattr("dayctl.persistent.PERSISTENT_PATH", tmp_path / "persistent.json")
    client.post("/web/ideas/add", data={"text": "beat idea", "bucket": "Music"}, headers={"HX-Request": "true"})
    edit = client.get("/web/ideas/0/edit").text
    assert "idea-edit-buckets" in edit          # topic pills in edit form
    client.post("/web/ideas/0/save", data={"text": "beat idea", "bucket": "Content"}, headers={"HX-Request": "true"})
    from dayctl.persistent import load_persistent
    assert load_persistent()["ideas"][0]["from"] == "Content"


def test_selfhosted_fonts_served(client):
    # @font-face declared and the woff2 assets are served locally.
    assert "@font-face" in client.get("/static/style.css").text
    r = client.get("/static/fonts/Geist-400.woff2")
    assert r.status_code == 200
