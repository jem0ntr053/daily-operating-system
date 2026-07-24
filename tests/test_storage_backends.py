import pytest
from datetime import date
from dayctl.models import DayPlan
from dayctl.storage_backends.json_backend import JSONBackend


@pytest.fixture
def json_backend(tmp_path):
    return JSONBackend(root=tmp_path / "days")


def test_load_missing_day_raises(json_backend):
    # Backends never materialize (#13); creation lives in storage.init_or_load_plan.
    with pytest.raises(KeyError):
        json_backend.load_plan("2026-04-12")


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


from dayctl.storage_backends.sqlite_backend import SQLiteBackend


@pytest.fixture
def sqlite_backend(tmp_path):
    return SQLiteBackend(path=str(tmp_path / "dayctl.db"))


@pytest.fixture(params=["json", "sqlite"])
def backend(request, json_backend, sqlite_backend):
    return {"json": json_backend, "sqlite": sqlite_backend}[request.param]


def test_contract_load_missing_raises(backend):
    with pytest.raises(KeyError):
        backend.load_plan("2026-04-12")


def test_contract_roundtrip(backend):
    plan = DayPlan.new("2026-04-12")
    plan.focus = "x"
    backend.save_plan(plan)
    assert backend.load_plan("2026-04-12").focus == "x"


def test_contract_list_sorted(backend):
    for d in ["2026-04-13", "2026-04-11"]:
        backend.save_plan(DayPlan.new(d))
    assert backend.list_days() == ["2026-04-11", "2026-04-13"]


def test_contract_delete(backend):
    backend.save_plan(DayPlan.new("2026-04-12"))
    backend.delete_plan("2026-04-12")
    assert not backend.exists("2026-04-12")
