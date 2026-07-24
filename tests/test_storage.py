"""Tests for dayctl.storage."""

from dayctl.storage import load_plan, save_plan, plan_path, list_days, init_or_load_plan
from dayctl.models import DayPlan


def test_save_and_load(day_env):
    plan = DayPlan.new("2026-01-01")
    save_plan(plan)
    loaded = load_plan("2026-01-01")
    assert loaded.day == "2026-01-01"
    assert loaded.completed == plan.completed


def test_load_auto_creates(day_env):
    path = plan_path("2026-06-15")
    assert not path.exists()
    plan = load_plan("2026-06-15")
    assert plan.day == "2026-06-15"
    assert path.exists()


def test_load_plan_attempts_carry_forward(day_env):
    # #13: bare load_plan is now a materialization choke point — creating a
    # missing day through it must attempt carry-forward, same as init.
    y = DayPlan.new("2026-06-14")
    y.tasks["social"] = [{"text": "carry via load", "done": False, "tag": "", "carried": False}]
    save_plan(y)
    plan = load_plan("2026-06-15")
    assert any(t["text"] == "carry via load" and t["carried"] for t in plan.tasks["social"])
    assert plan.rolled_over is True


def test_list_days(day_env):
    save_plan(DayPlan.new("2026-01-03"))
    save_plan(DayPlan.new("2026-01-01"))
    save_plan(DayPlan.new("2026-01-02"))
    days = list_days()
    assert days == ["2026-01-01", "2026-01-02", "2026-01-03"]


def test_list_days_empty(day_env):
    assert list_days() == []


def test_carry_forward_into_preexisting_day(day_env):
    # Day A has an incomplete task.
    a = DayPlan.new("2026-03-02")
    a.tasks["social"] = [{"text": "ship short", "done": False, "tag": "", "carried": False}]
    save_plan(a)
    # Day B was pre-created empty (rolled_over defaults False) — simulates a day
    # auto-created by navigation before carry-forward ran.
    b = DayPlan.new("2026-03-03")
    b.tasks["social"] = []
    save_plan(b)

    plan, carried = init_or_load_plan("2026-03-03")
    assert "ship short" in carried
    assert any(t["text"] == "ship short" and t["carried"] for t in plan.tasks["social"])
    assert plan.rolled_over is True

    # Idempotent: a second call must not duplicate or re-carry.
    plan2, carried2 = init_or_load_plan("2026-03-03")
    assert carried2 == []
    assert sum(1 for t in plan2.tasks["social"] if t["text"] == "ship short") == 1


def test_carry_forward_when_day_touched_before_yesterday_exists(day_env):
    # Regression (#12): a day touched before its predecessor exists must not be
    # permanently locked out of carry-forward. init_or_load_plan used to stamp
    # rolled_over=True even when yesterday was absent, so tasks added to yesterday
    # afterward never rolled in — they "vanished" instead of carrying.
    #
    # Day N+1 is created/visited first, while day N does not exist yet.
    init_or_load_plan("2026-05-27")
    # Day N is created afterward with an incomplete task.
    n = DayPlan.new("2026-05-26")
    n.tasks["social"] = [{"text": "carried task test", "done": False, "tag": "", "carried": False}]
    save_plan(n)
    # Revisiting day N+1 must now carry the incomplete task forward.
    plan, carried = init_or_load_plan("2026-05-27")
    assert "carried task test" in carried
    assert any(t["text"] == "carried task test" and t["carried"] for t in plan.tasks["social"])


def test_rolled_over_defaults_false_and_backfills():
    p = DayPlan.new("2026-03-02")
    assert p.rolled_over is False
    d = p.to_dict()
    d.pop("rolled_over")
    assert DayPlan.from_dict(d).rolled_over is False
