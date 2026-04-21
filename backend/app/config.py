"""Application configuration loaded from environment variables."""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from `.env` / environment.

    `JWT_SECRET` has no default — the app will fail to start without it.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Core
    ENV: str = "development"

    # Database
    DATABASE_URL: str = (
        "postgresql+asyncpg://postgres:postgres@localhost:5432/payfast"
    )
    DATABASE_URL_TEST: str | None = None

    # Auth
    JWT_SECRET: str = Field(..., description="JWT signing secret (required).")
    JWT_LIFETIME_SECONDS: int = 3600
    REFRESH_TOKEN_LIFETIME_SECONDS: int = 604800

    # CORS — JSON list in env, e.g. ["http://localhost:3000"]
    CORS_ORIGINS: list[str] = ["http://localhost:3000"]

    # PayFast — UAT: https://ipguat.apps.net.pk  /  Live: https://ipg1.apps.net.pk
    PAYFAST_MERCHANT_ID: str = ""
    PAYFAST_SECURED_KEY: str = ""
    PAYFAST_MERCHANT_NAME: str = "PayFast Subscriptions"
    PAYFAST_BASE_URL: str = "https://ipguat.apps.net.pk"
    PAYFAST_RETURN_URL: str = "http://localhost:8000/payfast/return"
    PAYFAST_CANCEL_URL: str = "http://localhost:8000/payfast/cancel"
    # IPN endpoint — PayFast POSTs payment notifications here. Must be public.
    PAYFAST_CHECKOUT_URL: str = "http://localhost:8000/webhooks/payfast"

    # Frontend (phase 3 — redirect targets)
    FRONTEND_URL: str = "http://localhost:3000"

    # Phase 5 — Scheduler
    SCHEDULER_ENABLED: bool = True

    # Phase 6 — Rate limiting (slowapi). Disable in tests/local debug if noisy.
    RATE_LIMIT_ENABLED: bool = True

    # Phase 6 — Logging
    LOG_LEVEL: str = "INFO"

    # Phase 5 — Dunning / renewal
    DUNNING_GRACE_DAYS: int = 7
    DUNNING_REMINDER_DAYS: list[int] = [3, 5]
    RENEWAL_PRE_NOTICE_DAYS: int = 3

    # Phase 5 — Email
    EMAIL_BACKEND: Literal["smtp", "resend"] = "smtp"
    SMTP_HOST: str = "localhost"
    SMTP_PORT: int = 1025
    EMAIL_FROM: str = "billing@payfast.local"
    RESEND_API_KEY: str = ""


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Cached settings accessor."""
    return Settings()  # type: ignore[call-arg]


settings = get_settings()
