"""Test fixtures.

- If `DATABASE_URL_TEST` (or `DATABASE_URL`) points at a reachable Postgres,
  create the schema before the session and drop it after.
- If Postgres is unreachable, DB-backed tests are skipped gracefully rather
  than failing the whole suite.
"""

from __future__ import annotations

import os
from collections.abc import AsyncGenerator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

# Ensure required env vars exist BEFORE we import the app. This lets tests
# run in a bare environment (no .env) without the settings loader crashing.
os.environ.setdefault("JWT_SECRET", "test-secret-not-for-production")
os.environ.setdefault(
    "DATABASE_URL",
    os.environ.get(
        "DATABASE_URL_TEST",
        "postgresql+asyncpg://postgres:postgres@localhost:5432/payfast_test",
    ),
)
# Rate limiting off in the test suite — we exercise endpoints densely and
# need deterministic behaviour. Enforcement is covered by smoke/E2E.
os.environ.setdefault("RATE_LIMIT_ENABLED", "false")


TEST_DATABASE_URL = os.environ.get(
    "DATABASE_URL_TEST",
    os.environ.get(
        "DATABASE_URL",
        "postgresql+asyncpg://postgres:postgres@localhost:5432/payfast_test",
    ),
)

# ---------------------------------------------------------------------------
# Session-scoped infrastructure (created once per test run)
# ---------------------------------------------------------------------------


def _run_sync(coro):
    """Run a coroutine synchronously in a fresh event loop."""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


@pytest_asyncio.fixture(scope="session")
async def _db_available() -> bool:
    """Probe the test DB — return True if we can connect, else False."""
    engine = create_async_engine(TEST_DATABASE_URL, pool_pre_ping=True)
    try:
        async with engine.connect():
            pass
        available = True
    except Exception:
        available = False
    # Dispose without waiting — avoid event-loop teardown issues
    try:
        await engine.dispose()
    except Exception:
        pass
    return available


# Module-level shared engine — created once, never disposed (GC handles it).
# This avoids per-test engine disposal which triggers asyncpg pool teardown
# that races with event loop shutdown on Windows.
_SHARED_ENGINE: AsyncEngine | None = None


def _get_shared_engine() -> AsyncEngine:
    global _SHARED_ENGINE
    if _SHARED_ENGINE is None:
        _SHARED_ENGINE = create_async_engine(
            TEST_DATABASE_URL,
            pool_pre_ping=True,
            pool_size=5,
            max_overflow=10,
        )
    return _SHARED_ENGINE


@pytest_asyncio.fixture(scope="session")
async def _schema(_db_available: bool) -> AsyncGenerator[None, None]:
    """Create all tables once for the test session, drop at teardown."""
    if not _db_available:
        yield
        return

    # Import AFTER env vars are in place.
    from app.models import Base  # noqa: PLC0415

    engine = _get_shared_engine()
    async with engine.begin() as conn:
        await conn.exec_driver_sql("CREATE EXTENSION IF NOT EXISTS pgcrypto")
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)

    yield

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


# ---------------------------------------------------------------------------
# Per-test fixtures
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def db_session(
    _db_available: bool, _schema: None
) -> AsyncGenerator[AsyncSession, None]:
    if not _db_available:
        pytest.skip("Test Postgres not reachable — skipping DB test.")
    engine = _get_shared_engine()
    SessionLocal = async_sessionmaker(engine, expire_on_commit=False)
    async with SessionLocal() as session:
        yield session


@pytest_asyncio.fixture
async def client(
    _db_available: bool, _schema: None
) -> AsyncGenerator[AsyncClient, None]:
    """HTTP client against the ASGI app.

    Truncates app tables before each test so state doesn't leak.
    Bootstraps app.state.http_client so the invoices/checkout endpoint
    can resolve the shared HTTP client dependency (the lifespan is not
    triggered by ASGITransport in tests).
    """
    if not _db_available:
        pytest.skip("Test Postgres not reachable — skipping API test.")

    import httpx  # noqa: PLC0415

    # Import app after schema fixture has prepared DB.
    from app.main import app  # noqa: PLC0415
    from app.models import Base  # noqa: PLC0415

    engine = _get_shared_engine()
    async with engine.begin() as conn:
        # TRUNCATE is faster than drop+create between tests.
        table_names = ", ".join(
            f'"{t.name}"' for t in reversed(Base.metadata.sorted_tables)
        )
        await conn.exec_driver_sql(
            f"TRUNCATE {table_names} RESTART IDENTITY CASCADE"
        )

    # Manually seed app.state so get_http_client() works in tests.
    # (ASGITransport does not run the FastAPI lifespan context manager.)
    test_http_client = httpx.AsyncClient(timeout=30.0)
    app.state.http_client = test_http_client

    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport, base_url="http://testserver"
    ) as ac:
        yield ac

    try:
        await test_http_client.aclose()
    except Exception:
        pass
