"""Thin wrapper around ntfy.sh publish API."""
from __future__ import annotations

import logging
import os

import httpx

log = logging.getLogger(__name__)


def post_ntfy(topic: str, title: str, body: str, priority: str = "default") -> None:
    """POST to ntfy topic. Failures are logged and swallowed."""
    headers = {"Title": title, "Priority": priority}
    auth = os.environ.get("NTFY_AUTH")
    if auth:
        headers["Authorization"] = f"Bearer {auth}"
    try:
        r = httpx.post(topic, content=body.encode("utf-8"), headers=headers, timeout=5.0)
        r.raise_for_status()
    except Exception as e:
        log.warning("ntfy post failed: %s", e)
