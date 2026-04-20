"""Shared FastAPI dependencies."""

from __future__ import annotations

from fastapi import Request

import httpx

from app.auth.users import current_active_user
from app.db import get_async_session

# Convenience aliases with more conventional names.
get_db = get_async_session
get_current_user = current_active_user


def get_http_client(request: Request) -> httpx.AsyncClient:
    """Return the lifespan-managed shared httpx.AsyncClient from app state.

    The client is created once in main.py lifespan and stored at
    app.state.http_client.  This avoids spinning up a new client per request.
    """
    return request.app.state.http_client  # type: ignore[no-any-return]


__all__ = ["get_db", "get_current_user", "get_http_client"]
