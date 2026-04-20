"""Test helpers for authentication.

Creates a user and returns a valid JWT access token without going through HTTP.
"""

from __future__ import annotations

from httpx import AsyncClient


async def create_user_and_token(
    client: AsyncClient,
    email: str = "testuser@example.com",
    password: str = "TestPass123!",
) -> tuple[dict, str]:
    """Register a user via HTTP and return (user_dict, access_token).

    Uses the app's own /auth/register and /auth/jwt/login endpoints so
    the token is a real JWT signed by the same secret.
    """
    r = await client.post(
        "/auth/register",
        json={"email": email, "password": password},
    )
    assert r.status_code == 201, f"Registration failed: {r.text}"
    user = r.json()

    r = await client.post(
        "/auth/jwt/login",
        data={"username": email, "password": password},
    )
    assert r.status_code == 200, f"Login failed: {r.text}"
    token = r.json()["access_token"]

    return user, token
