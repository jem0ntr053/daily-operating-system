import pytest
from datetime import date
from dayctl.models import DayPlan
from dayctl.storage_backends.json_backend import JSONBackend


@pytest.fixture
def json_backend(tmp_path):
    return JSONBackend(root=tmp_path / "days")


def test_load_missing_day_creates_plan(json_backend):
    plan = json_backend.load_plan("2026-04-12")
    assert isinstance(plan, DayPlan)
    assert plan.day == "2026-04-12"


def test_save_then_load_roundtrips(json_backend):
    plan = DayPlan.new("2026-04-12")
    plan.focus = "test"
    json_backend.save_plan(plan)
    loaded = json_backend.load_plan("2026-04-12")
    assert loaded.focus == "test"


def test_list_days_returns_sorted(json_backend):
    for d in ["2026-04-13", "2026-04-11", "2026-04-12"]:
        json_backend.save_plan(DayPlan.new(d))
    assert json_backend.list_days() == ["2026-04-11", "2026-04-12", "2026-04-13"]


def test_delete_day_removes_file(json_backend):
    json_backend.save_plan(DayPlan.new("2026-04-12"))
    json_backend.delete_plan("2026-04-12")
    assert "2026-04-12" not in json_backend.list_days()
