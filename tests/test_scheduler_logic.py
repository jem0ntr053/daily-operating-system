from datetime import datetime, time

from dayctl.server.scheduler import should_fire_now


def _profile():
    return {
        "schedule": [
            "6:30 AM  Wake",
            "7:00 AM  App Work",
            "no time line — ignored",
            "4:30 PM  Gym",
        ],
    }


def test_fires_on_block_start():
    now = datetime(2026, 4, 12, 7, 0, 30)
    last = datetime(2026, 4, 12, 6, 59, 0)
    fires = should_fire_now(_profile(), now, last)
    assert len(fires) == 1
    assert fires[0][0] == time(7, 0)
    assert fires[0][1] == "App Work"


def test_no_fire_when_no_block_in_window():
    now = datetime(2026, 4, 12, 7, 30, 0)
    last = datetime(2026, 4, 12, 7, 15, 0)
    assert should_fire_now(_profile(), now, last) == []


def test_ignores_unparseable_lines():
    now = datetime(2026, 4, 12, 16, 30, 30)
    last = datetime(2026, 4, 12, 16, 29, 0)
    fires = should_fire_now(_profile(), now, last)
    assert fires == [(time(16, 30), "Gym")]


def test_handles_quiet_until(monkeypatch):
    monkeypatch.setenv("DAYCTL_QUIET_UNTIL", "2026-04-20")
    now = datetime(2026, 4, 12, 7, 0, 30)
    last = datetime(2026, 4, 12, 6, 59, 0)
    assert should_fire_now(_profile(), now, last) == []


def test_tick_calls_poster_for_fires(monkeypatch):
    from datetime import datetime
    from dayctl.server.scheduler import tick_once

    monkeypatch.setenv("NTFY_TOPIC", "https://ntfy.sh/test")
    posted: list[dict] = []

    def fake_post(topic, title, body, priority):
        posted.append({"topic": topic, "title": title, "body": body})

    now = datetime(2026, 4, 12, 7, 0, 30)
    last = datetime(2026, 4, 12, 6, 59, 0)
    profile = {"schedule": ["7:00 AM  App Work"]}
    tick_once(profile=profile, now=now, last_tick=last, poster=fake_post, plan=None)
    assert len(posted) == 1
    assert posted[0]["title"] == "App Work"


def test_body_for_lists_pending_task_text():
    from dayctl.models import DayPlan
    from dayctl.server.scheduler import _body_for

    plan = DayPlan.new("2026-04-12")
    plan.tasks["code"] = [{"text": "Ship login", "done": False, "tag": "", "carried": False}]
    body = _body_for(plan)
    assert "Ship login" in body


def test_tick_posts_body_with_pending_tasks(monkeypatch):
    from datetime import datetime
    from dayctl.models import DayPlan
    from dayctl.server.scheduler import tick_once

    monkeypatch.setenv("NTFY_TOPIC", "https://ntfy.sh/test")
    posted: list[dict] = []

    def fake_post(topic, title, body, priority):
        posted.append({"topic": topic, "title": title, "body": body})

    plan = DayPlan.new("2026-04-12")
    plan.tasks["code"] = [{"text": "Ship login", "done": False, "tag": "", "carried": False}]
    tick_once(
        profile={"schedule": ["7:00 AM  App Work"]},
        now=datetime(2026, 4, 12, 7, 0, 30),
        last_tick=datetime(2026, 4, 12, 6, 59, 0),
        poster=fake_post,
        plan=plan,
    )
    assert len(posted) == 1
    assert "Ship login" in posted[0]["body"]


def test_tick_noop_when_no_topic(monkeypatch):
    from datetime import datetime
    from dayctl.server.scheduler import tick_once

    monkeypatch.delenv("NTFY_TOPIC", raising=False)
    calls: list = []
    tick_once(
        profile={"schedule": ["7:00 AM  Work"]},
        now=datetime(2026, 4, 12, 7, 0, 30),
        last_tick=datetime(2026, 4, 12, 6, 59, 0),
        poster=lambda *a, **kw: calls.append(a),
        plan=None,
    )
    assert calls == []
