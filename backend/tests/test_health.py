"""Health endpoint — no DB required."""

from __future__ import annotations

import os

# Make sure settings can load even without a .env file.
os.environ.setdefault("JWT_SECRET", "test-secret-not-for-production")

import pytest
from httpx import ASGITransport, AsyncClient


@pytest.mark.asyncio
async def test_health_returns_ok() -> None:
    from app.main import app  # local import — env vars set above

    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport, base_url="http://testserver"
    ) as ac:
        resp = await ac.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}
