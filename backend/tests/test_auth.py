"""Auth flow: register -> login -> /me."""

from __future__ import annotations

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_register_login_me_roundtrip(client: AsyncClient) -> None:
    # 1. Register
    register_payload = {
        "email": "alice@example.com",
        "password": "s3cret-password!",
        "name": "Alice",
        "phone": "+923001234567",
    }
    r = await client.post("/auth/register", json=register_payload)
    assert r.status_code == 201, r.text
    user = r.json()
    assert user["email"] == "alice@example.com"
    assert user["name"] == "Alice"
    assert user["phone"] == "+923001234567"

    # 2. Login — fastapi-users login uses form-urlencoded OAuth2 style.
    login_form = {
        "username": "alice@example.com",
        "password": "s3cret-password!",
    }
    r = await client.post("/auth/jwt/login", data=login_form)
    assert r.status_code == 200, r.text
    token = r.json()["access_token"]
    assert token

    # 3. /me with bearer token
    r = await client.get("/me", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200, r.text
    me = r.json()
    assert me["email"] == "alice@example.com"
    assert me["name"] == "Alice"


@pytest.mark.asyncio
async def test_me_requires_auth(client: AsyncClient) -> None:
    r = await client.get("/me")
    assert r.status_code == 401
