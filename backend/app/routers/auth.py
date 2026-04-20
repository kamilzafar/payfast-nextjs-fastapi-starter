"""Auth router — mounts fastapi-users' login/register/reset flows.

Exposes:
  POST /auth/jwt/login
  POST /auth/jwt/logout
  POST /auth/register
  POST /auth/forgot-password
  POST /auth/reset-password
  POST /auth/request-verify-token
  POST /auth/verify
"""

from __future__ import annotations

from fastapi import APIRouter

from app.auth.schemas import UserCreate, UserRead
from app.auth.users import auth_backend, fastapi_users

router = APIRouter()

# Login / logout
router.include_router(
    fastapi_users.get_auth_router(auth_backend),
    prefix="/auth/jwt",
    tags=["auth"],
)

# Register
router.include_router(
    fastapi_users.get_register_router(UserRead, UserCreate),
    prefix="/auth",
    tags=["auth"],
)

# Password reset
router.include_router(
    fastapi_users.get_reset_password_router(),
    prefix="/auth",
    tags=["auth"],
)

# Email verification
router.include_router(
    fastapi_users.get_verify_router(UserRead),
    prefix="/auth",
    tags=["auth"],
)
