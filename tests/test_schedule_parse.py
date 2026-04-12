from datetime import time
from dayctl.schedule_parse import parse_block


def test_parses_am():
    t, label = parse_block("6:30 AM  Wake")
    assert t == time(6, 30)
    assert label == "Wake"


def test_parses_pm():
    t, label = parse_block("4:20 PM  Leave for Gym")
    assert t == time(16, 20)


def test_parses_range_takes_start():
    t, label = parse_block("8:00 AM–4:00 PM  Remote Work")
    assert t == time(8, 0)
    assert label == "Remote Work"


def test_returns_none_on_unparseable():
    assert parse_block("9:30 PM onward  Social / Show Prep") is not None  # still parses 9:30 PM
    assert parse_block("no time here") is None
