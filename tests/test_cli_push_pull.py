import pytest

pytest.importorskip("fastapi")


@pytest.fixture
def server(tmp_path, monkeypatch):
    monkeypatch.setenv("DAYCTL_TOKEN", "tok")
    monkeypatch.setenv("DAYCTL_STORAGE", f"sqlite://{tmp_path}/srv.db")
    from dayctl.storage import _reset_backend_cache
    _reset_backend_cache()
    from dayctl.server.app import create_app
    from fastapi.testclient import TestClient
    return TestClient(create_app())


def test_push_copies_local_to_remote(server, tmp_path):
    from dayctl.storage_backends.json_backend import JSONBackend
    from dayctl.storage_backends.remote_backend import RemoteBackend
    from dayctl.models import DayPlan
    from dayctl.cli import push_day

    local = JSONBackend(root=tmp_path / "local")
    p = DayPlan.new("2026-04-12")
    p.focus = "pushed"
    local.save_plan(p)

    remote = RemoteBackend(base_url="http://testserver", token="tok")
    remote._client = server

    push_day("2026-04-12", local, remote)
    assert remote.load_plan("2026-04-12").focus == "pushed"


def test_push_missing_local_day_exits(server, tmp_path):
    from dayctl.storage_backends.json_backend import JSONBackend
    from dayctl.storage_backends.remote_backend import RemoteBackend
    from dayctl.cli import push_day

    local = JSONBackend(root=tmp_path / "local")
    remote = RemoteBackend(base_url="http://testserver", token="tok")
    remote._client = server

    with pytest.raises(SystemExit):
        push_day("2026-04-13", local, remote)
    assert not local.exists("2026-04-13")  # no empty day materialized


def test_pull_copies_remote_to_local(server, tmp_path):
    from dayctl.storage_backends.json_backend import JSONBackend
    from dayctl.storage_backends.remote_backend import RemoteBackend
    from dayctl.models import DayPlan
    from dayctl.cli import pull_day

    remote = RemoteBackend(base_url="http://testserver", token="tok")
    remote._client = server
    p = DayPlan.new("2026-04-12")
    p.focus = "pulled"
    remote.save_plan(p)

    local = JSONBackend(root=tmp_path / "local")
    pull_day("2026-04-12", local, remote)
    assert local.load_plan("2026-04-12").focus == "pulled"
