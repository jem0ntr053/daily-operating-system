"""Single-user bearer token auth."""
from __future__ import annotations

import hmac
import os

from fastapi import Header, HTTPException, Request


def _expected_token() -> str:
    return os.environ.get("DAYCTL_TOKEN", "")


def require_token(
    request: Request,
    authorization: str | None = Header(default=None),
) -> None:
    expected = _expected_token()
    header_token = ""
    if authorization and authorization.lower().startswith("bearer "):
        header_token = authorization.split(" ", 1)[1].strip()
    cookie_token = request.cookies.get("dayctl_token", "")
    if not hmac.compare_digest(header_token, expected) and not hmac.compare_digest(cookie_token, expected):
        raise HTTPException(status_code=401, detail="Unauthorized")
