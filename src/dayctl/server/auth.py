"""Single-user bearer token auth."""
from __future__ import annotations

import os

from fastapi import Header, HTTPException, Request


def _expected_token() -> str:
    tok = os.environ.get("DAYCTL_TOKEN", "")
    if not tok:
        raise RuntimeError("DAYCTL_TOKEN env var not set")
    return tok


def require_token(
    request: Request,
    authorization: str | None = Header(default=None),
) -> None:
    expected = _expected_token()
    header_token = ""
    if authorization and authorization.lower().startswith("bearer "):
        header_token = authorization.split(" ", 1)[1].strip()
    cookie_token = request.cookies.get("dayctl_token", "")
    if header_token != expected and cookie_token != expected:
        raise HTTPException(status_code=401, detail="Unauthorized")
