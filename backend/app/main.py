"""FastAPI application entrypoint."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import httpx
import structlog
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

from app.config import settings
from app.logging_config import configure_logging
from app.middleware import RequestContextMiddleware
from app.rate_limit import AUTH_PATH_LIMITS, PathLimitMiddleware, limiter
from app.routers import (
    auth as auth_router,
)
from app.routers import (
    invoices as invoices_router,
)
from app.routers import (
    me as me_router,
)
from app.routers import (
    payfast_redirect as payfast_redirect_router,
)
from app.routers import (
    plans as plans_router,
)
from app.routers import (
    subscriptions as subscriptions_router,
)
from app.routers import (
    webhooks_payfast as webhooks_payfast_router,
)

# Configure structlog once at import time so tests and scripts share the
# same formatting. JSON in production; pretty console in dev.
configure_logging(env=settings.ENV)
log = structlog.get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Application lifespan.

    Startup:
      - Creates a shared httpx.AsyncClient.
      - Wires APScheduler with the three Phase 5 jobs (if SCHEDULER_ENABLED).

    Shutdown:
      - Shuts down the scheduler gracefully (waits for running jobs).
      - Closes the HTTP client.
    """
    log.info("startup", env=settings.ENV)

    # Create a single shared HTTP client for the application lifetime.
    app.state.http_client = httpx.AsyncClient(timeout=30.0)

    scheduler = None
    if settings.SCHEDULER_ENABLED:
        from contextlib import asynccontextmanager as _acm  # noqa: PLC0415

        from app.services.charger import HostedRedirectCharger  # noqa: PLC0415
        from app.services.email import get_email_sender  # noqa: PLC0415
        from app.workers.scheduler import build_scheduler  # noqa: PLC0415

        email_sender = get_email_sender(settings)
        charger = HostedRedirectCharger(
            email_sender=email_sender,
            template_name="payment_due",
            settings=settings,
        )

        # Build a session factory for the scheduler jobs
        engine = create_async_engine(settings.DATABASE_URL, pool_pre_ping=True)
        SessionLocal = async_sessionmaker(engine, expire_on_commit=False)

        @asynccontextmanager
        async def db_session_factory():
            async with SessionLocal() as session:
                yield session

        scheduler = build_scheduler(
            db_session_factory=db_session_factory,
            settings=settings,
            charger=charger,
            email_sender=email_sender,
            http_client=app.state.http_client,
        )
        scheduler.start()
        job_count = len(scheduler.get_jobs())
        log.info("Scheduler started", job_count=job_count)

    yield

    if scheduler is not None:
        scheduler.shutdown(wait=False)
        log.info("Scheduler stopped")

    await app.state.http_client.aclose()
    log.info("shutdown", env=settings.ENV)


app = FastAPI(
    title="PayFast Subscription Billing",
    version="0.1.0",
    lifespan=lifespan,
)

# --- Rate limiting -----------------------------------------------------------
# slowapi wiring: attach the limiter to app.state so @limiter.limit decorators
# resolve, and register its 429 handler for RateLimitExceeded.
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)


# --- CORS lockdown -----------------------------------------------------------
# CORS applies only to browser-origin requests. PayFast's IPN is server-to-server,
# so it doesn't need CORS headers and we explicitly strip them from /webhooks/*
# to avoid any chance of a browser replaying a captured IPN from an allowed origin.
class _CORSWebhookStripper(BaseHTTPMiddleware):
    """Strip any CORS response headers from `/webhooks/*` responses.

    Starlette's CORSMiddleware adds Access-Control-* headers based on the
    request Origin. For webhook endpoints (server-to-server), those headers
    are meaningless and a belt-and-braces defence against accidental browser
    replay is to drop them unconditionally.
    """

    async def dispatch(self, request: Request, call_next) -> Response:
        response = await call_next(request)
        if request.url.path.startswith("/webhooks/"):
            for h in list(response.headers.keys()):
                if h.lower().startswith("access-control-"):
                    del response.headers[h]
        return response


# Order matters: middlewares run outer-to-inner for requests, inner-to-outer
# for responses. We add in reverse of the desired run order.
app.add_middleware(_CORSWebhookStripper)  # runs LAST on response → final scrub
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(PathLimitMiddleware, limits=AUTH_PATH_LIMITS)
app.add_middleware(RequestContextMiddleware)


@app.get("/health", tags=["health"])
async def health() -> dict[str, str]:
    """Liveness probe."""
    return {"status": "ok"}


# Mount routers
app.include_router(auth_router.router)
app.include_router(me_router.router)
app.include_router(plans_router.router)
app.include_router(subscriptions_router.router)
app.include_router(invoices_router.router)
app.include_router(webhooks_payfast_router.router)
app.include_router(payfast_redirect_router.router)
