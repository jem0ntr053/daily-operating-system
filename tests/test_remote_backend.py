import pytest

pytest.importorskip("fastapi")

from fastapi.testclient import TestClient


@pytest.fixture
def remote(tmp_path, monkeypatch):
    monkeypatch.setenv("DAYCTL_TOKEN", "tok")
    monkeypatch.setenv("DAYCTL_STORAGE", f"sqlite://{tmp_path}/d.db")
    from dayctl.storage import _reset_backend_cache
    _reset_backend_cache()
    from dayctl.server.app import create_app
    app = create_app()
    client = TestClient(app)

    from dayctl.storage_backends.remote_backend import RemoteBackend
    r = RemoteBackend(base_url="http://testserver", token="tok")
    r._client = client  # inject test client in place of httpx
    return r


def test_remote_load_and_save(remote):
    from dayctl.models import DayPlan
    p = DayPlan.new("2026-04-12")
    p.focus = "remote"
    remote.save_plan(p)
    loaded = remote.load_plan("2026-04-12")
    assert loaded.focus == "remote"


def test_remote_list_days(remote):
    from dayctl.models import DayPlan
    remote.save_plan(DayPlan.new("2026-04-12"))
    assert "2026-04-12" in remote.list_days()
