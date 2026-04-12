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
