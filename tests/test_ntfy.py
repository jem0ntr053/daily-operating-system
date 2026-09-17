"""Tests for dayctl.server.ntfy."""

import pytest
pytest.importorskip("httpx")

from dayctl.server import ntfy


def test_post_ntfy_omits_actions_header_by_default(monkeypatch):
    calls = []
    monkeypatch.setattr(ntfy.httpx, "post", lambda url, content, headers, timeout: calls.append(headers))
    ntfy.post_ntfy("https://ntfy.sh/test", "Title", "Body")
    assert "Actions" not in calls[0]


def test_post_ntfy_sets_actions_header_when_provided(monkeypatch):
    calls = []
    monkeypatch.setattr(ntfy.httpx, "post", lambda url, content, headers, timeout: calls.append(headers))
    ntfy.post_ntfy("https://ntfy.sh/test", "Title", "Body", actions="http, Done, https://x")
    assert calls[0]["Actions"] == "http, Done, https://x"
