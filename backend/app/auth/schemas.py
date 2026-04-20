"""Pydantic schemas for fastapi-users endpoints."""

from __future__ import annotations

from fastapi_users import schemas


class UserRead(schemas.BaseUser[int]):
    name: str | None = None
    phone: str | None = None


class UserCreate(schemas.BaseUserCreate):
    name: str | None = None
    phone: str | None = None


class UserUpdate(schemas.BaseUserUpdate):
    name: str | None = None
    phone: str | None = None
