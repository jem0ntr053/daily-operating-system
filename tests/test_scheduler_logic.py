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

    def fake_post(topic, title, body, priority, actions=None):
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

    def fake_post(topic, title, body, priority, actions=None):
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


def test_stack_action_none_without_public_url(monkeypatch):
    from dayctl.models import DayPlan
    from dayctl.server.scheduler import _stack_action

    monkeypatch.delenv("DAYCTL_PUBLIC_URL", raising=False)
    monkeypatch.setenv("DAYCTL_TOKEN", "tok")
    plan = DayPlan.new("2026-04-12")
    assert _stack_action(plan, "2026-04-12") is None


def test_stack_action_none_when_stack_all_done(monkeypatch):
    from dayctl.models import DayPlan
    from dayctl.server.scheduler import _stack_action

    monkeypatch.setenv("DAYCTL_PUBLIC_URL", "http://192.168.1.50:8000")
    monkeypatch.setenv("DAYCTL_TOKEN", "tok")
    plan = DayPlan.new("2026-04-12")
    for t in plan.tasks["stack"]:
        t["done"] = True
    assert _stack_action(plan, "2026-04-12") is None


def test_stack_action_builds_advance_url_when_configured(monkeypatch):
    from dayctl.models import DayPlan
    from dayctl.server.scheduler import _stack_action

    monkeypatch.setenv("DAYCTL_PUBLIC_URL", "http://192.168.1.50:8000")
    monkeypatch.setenv("DAYCTL_TOKEN", "tok")
    plan = DayPlan.new("2026-04-12")
    action = _stack_action(plan, "2026-04-12")
    assert action is not None
    assert "http://192.168.1.50:8000/api/days/2026-04-12/tasks/stack/advance" in action
    assert "headers.Authorization=Bearer tok" in action


def test_stack_action_warns_when_ntfy_auth_unset(monkeypatch, caplog):
    from dayctl.models import DayPlan
    from dayctl.server.scheduler import _stack_action

    monkeypatch.setenv("DAYCTL_PUBLIC_URL", "http://192.168.1.50:8000")
    monkeypatch.setenv("DAYCTL_TOKEN", "tok")
    monkeypatch.delenv("NTFY_AUTH", raising=False)
    plan = DayPlan.new("2026-04-12")
    with caplog.at_level("WARNING"):
        action = _stack_action(plan, "2026-04-12")
    assert action is not None
    assert any("NTFY_AUTH" in r.message for r in caplog.records)


def test_stack_action_silent_when_ntfy_auth_set(monkeypatch, caplog):
    from dayctl.models import DayPlan
    from dayctl.server.scheduler import _stack_action

    monkeypatch.setenv("DAYCTL_PUBLIC_URL", "http://192.168.1.50:8000")
    monkeypatch.setenv("DAYCTL_TOKEN", "tok")
    monkeypatch.setenv("NTFY_AUTH", "ntfy-secret")
    plan = DayPlan.new("2026-04-12")
    with caplog.at_level("WARNING"):
        action = _stack_action(plan, "2026-04-12")
    assert action is not None
    assert not any("NTFY_AUTH" in r.message for r in caplog.records)


def test_no_ntfy_auth_warning_on_tick_with_no_fires(monkeypatch, caplog):
    # _stack_action (and its NTFY_AUTH warning) must only run when a nudge is
    # actually about to post — not on every 1-minute tick regardless of fires.
    from datetime import datetime
    from dayctl.models import DayPlan
    from dayctl.server.scheduler import tick_once

    monkeypatch.setenv("NTFY_TOPIC", "https://ntfy.sh/test")
    monkeypatch.setenv("DAYCTL_PUBLIC_URL", "http://192.168.1.50:8000")
    monkeypatch.setenv("DAYCTL_TOKEN", "tok")
    monkeypatch.delenv("NTFY_AUTH", raising=False)
    plan = DayPlan.new("2026-04-12")

    with caplog.at_level("WARNING"):
        tick_once(
            profile={"schedule": ["7:00 AM  App Work"]},  # no block in this window
            now=datetime(2026, 4, 12, 7, 30, 0),
            last_tick=datetime(2026, 4, 12, 7, 15, 0),
            poster=lambda *a, **kw: None,
            plan=plan,
        )
    assert not any("NTFY_AUTH" in r.message for r in caplog.records)


def test_tick_includes_advance_action_when_public_url_set(monkeypatch):
    from datetime import datetime
    from dayctl.models import DayPlan
    from dayctl.server.scheduler import tick_once

    monkeypatch.setenv("NTFY_TOPIC", "https://ntfy.sh/test")
    monkeypatch.setenv("DAYCTL_PUBLIC_URL", "http://192.168.1.50:8000")
    monkeypatch.setenv("DAYCTL_TOKEN", "tok")
    posted: list[dict] = []

    def fake_post(topic, title, body, priority, actions=None):
        posted.append({"actions": actions})

    plan = DayPlan.new("2026-04-12")
    tick_once(
        profile={"schedule": ["7:00 AM  App Work"]},
        now=datetime(2026, 4, 12, 7, 0, 30),
        last_tick=datetime(2026, 4, 12, 6, 59, 0),
        poster=fake_post,
        plan=plan,
    )
    assert posted[0]["actions"] is not None
    assert "tasks/stack/advance" in posted[0]["actions"]


def test_tick_no_action_when_public_url_unset(monkeypatch):
    from datetime import datetime
    from dayctl.models import DayPlan
    from dayctl.server.scheduler import tick_once

    monkeypatch.setenv("NTFY_TOPIC", "https://ntfy.sh/test")
    monkeypatch.delenv("DAYCTL_PUBLIC_URL", raising=False)
    posted: list[dict] = []

    def fake_post(topic, title, body, priority, actions=None):
        posted.append({"actions": actions})

    plan = DayPlan.new("2026-04-12")
    tick_once(
        profile={"schedule": ["7:00 AM  App Work"]},
        now=datetime(2026, 4, 12, 7, 0, 30),
        last_tick=datetime(2026, 4, 12, 6, 59, 0),
        poster=fake_post,
        plan=plan,
    )
    assert posted[0]["actions"] is None


def test_miss_alarm_fires_when_both_prior_days_missed(day_env, monkeypatch):
    from datetime import date
    from dayctl.models import DayPlan
    from dayctl.storage import save_plan
    from dayctl.server.scheduler import ReminderScheduler
    import dayctl.server.scheduler as scheduler_mod

    monkeypatch.setenv("NTFY_TOPIC", "https://ntfy.sh/test")
    save_plan(DayPlan.new("2026-08-30"))  # incomplete stack
    save_plan(DayPlan.new("2026-08-31"))  # incomplete stack

    posted = []
    monkeypatch.setattr(scheduler_mod, "post_ntfy", lambda *a, **kw: posted.append(a))

    s = ReminderScheduler()
    s._maybe_miss_alarm(datetime(2026, 9, 1, 7, 0, 0))
    assert len(posted) == 1
    assert posted[0][3] == "high"


def test_miss_alarm_silent_when_either_day_complete(day_env, monkeypatch):
    from dayctl.models import DayPlan
    from dayctl.storage import save_plan
    from dayctl.server.scheduler import ReminderScheduler
    import dayctl.server.scheduler as scheduler_mod

    monkeypatch.setenv("NTFY_TOPIC", "https://ntfy.sh/test")
    p1 = DayPlan.new("2026-08-30")
    for t in p1.tasks["stack"]:
        t["done"] = True
    save_plan(p1)
    save_plan(DayPlan.new("2026-08-31"))  # incomplete

    posted = []
    monkeypatch.setattr(scheduler_mod, "post_ntfy", lambda *a, **kw: posted.append(a))

    s = ReminderScheduler()
    s._maybe_miss_alarm(datetime(2026, 9, 1, 7, 0, 0))
    assert posted == []


def test_miss_alarm_silent_when_prior_day_never_existed(day_env, monkeypatch):
    # Neither 2026-08-30 nor 2026-08-31 was ever created — must not fabricate
    # them, and must not fire (can't judge a day that was never tracked).
    from dayctl.server.scheduler import ReminderScheduler
    from dayctl.storage import exists
    import dayctl.server.scheduler as scheduler_mod

    monkeypatch.setenv("NTFY_TOPIC", "https://ntfy.sh/test")
    posted = []
    monkeypatch.setattr(scheduler_mod, "post_ntfy", lambda *a, **kw: posted.append(a))

    s = ReminderScheduler()
    s._maybe_miss_alarm(datetime(2026, 9, 1, 7, 0, 0))
    assert posted == []
    assert exists("2026-08-30") is False
    assert exists("2026-08-31") is False


def test_miss_alarm_survives_corrupt_prior_day_file(day_env, monkeypatch):
    # A day file that exists (passes exists()) but is unreadable/corrupt must
    # not crash _run's calling loop — matches _run's own try/except pattern
    # for the identical load_plan(today) call.
    from dayctl.models import DayPlan
    from dayctl.storage import save_plan
    from dayctl.server.scheduler import ReminderScheduler
    import dayctl.server.scheduler as scheduler_mod

    monkeypatch.setenv("NTFY_TOPIC", "https://ntfy.sh/test")
    save_plan(DayPlan.new("2026-08-30"))
    corrupt_path = day_env / "days" / "2026-08-31.json"
    corrupt_path.write_text("{not valid json", encoding="utf-8")

    posted = []
    monkeypatch.setattr(scheduler_mod, "post_ntfy", lambda *a, **kw: posted.append(a))

    s = ReminderScheduler()
    s._maybe_miss_alarm(datetime(2026, 9, 1, 7, 0, 0))  # must not raise
    assert posted == []


def test_miss_alarm_fires_at_most_once_per_day(day_env, monkeypatch):
    from dayctl.models import DayPlan
    from dayctl.storage import save_plan
    from dayctl.server.scheduler import ReminderScheduler
    import dayctl.server.scheduler as scheduler_mod

    monkeypatch.setenv("NTFY_TOPIC", "https://ntfy.sh/test")
    save_plan(DayPlan.new("2026-08-30"))
    save_plan(DayPlan.new("2026-08-31"))

    posted = []
    monkeypatch.setattr(scheduler_mod, "post_ntfy", lambda *a, **kw: posted.append(a))

    s = ReminderScheduler()
    s._maybe_miss_alarm(datetime(2026, 9, 1, 7, 0, 0))
    s._maybe_miss_alarm(datetime(2026, 9, 1, 7, 5, 0))  # same day, later tick
    assert len(posted) == 1


def test_miss_alarm_noop_without_topic(day_env, monkeypatch):
    from dayctl.models import DayPlan
    from dayctl.storage import save_plan
    from dayctl.server.scheduler import ReminderScheduler
    import dayctl.server.scheduler as scheduler_mod

    monkeypatch.delenv("NTFY_TOPIC", raising=False)
    save_plan(DayPlan.new("2026-08-30"))
    save_plan(DayPlan.new("2026-08-31"))

    posted = []
    monkeypatch.setattr(scheduler_mod, "post_ntfy", lambda *a, **kw: posted.append(a))

    s = ReminderScheduler()
    s._maybe_miss_alarm(datetime(2026, 9, 1, 7, 0, 0))
    assert posted == []


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
