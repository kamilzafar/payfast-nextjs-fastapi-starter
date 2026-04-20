# PayFast Backend

FastAPI + async SQLAlchemy + Postgres backend for the PayFast subscription
billing platform (phases 0–6 complete).

## Prerequisites

- Python 3.13
- [uv](https://docs.astral.sh/uv/) (package manager)
- Postgres 14+ running locally (needs the `pgcrypto` extension; the migration
  creates it)

## Quickstart

```bash
# 1. Install deps
cd backend
uv sync

# 2. Configure env
cp .env.example .env
# edit .env — at minimum set JWT_SECRET to a random string

# 3. Create databases (one for dev, one for tests)
createdb payfast
createdb payfast_test   # optional — only needed to run DB-backed tests

# 4. Apply migrations
uv run alembic upgrade head

# 5. Seed plans (Basic 1500 PKR / Pro 4500 PKR, both monthly w/ 7-day trial)
uv run python scripts/seed.py

# 6. Run the dev server
uv run uvicorn app.main:app --reload
```

Browse:

- Swagger UI: http://localhost:8000/docs
- Health:     http://localhost:8000/health
- Plans:      http://localhost:8000/plans

## Tests

```bash
uv run pytest
```

Tests that need Postgres will **skip** (not fail) if `DATABASE_URL_TEST` is not
reachable.

## Layout

```
backend/
  app/
    main.py             # FastAPI app + lifespan + routers
    config.py           # pydantic-settings
    db.py               # async engine + session
    deps.py             # get_db, get_current_user
    auth/               # fastapi-users setup (JWT bearer)
    models/             # SQLAlchemy models
    repositories/       # stubs — phase 2+
    routers/            # HTTP routers (stubs return 501)
    services/           # phase 2+ (empty)
  alembic/              # migrations
  scripts/seed.py       # seeds Basic + Pro plans
  tests/                # pytest suite
```

## Scope delivered

- **Auth** — register / login / me via fastapi-users + JWT bearer.
- **Plans** — listed from `plans` table, seeded by `scripts/seed.py`.
- **Subscriptions** — create, cancel (at-period-end or immediate), list.
- **Invoices** — list + initiate PayFast hosted checkout (`POST /invoices/{id}/checkout`).
- **PayFast redirect** — return + cancel handlers that re-route the browser back to the frontend with state.
- **Webhook** — signed IPN handler with idempotent processing via `webhook_events`.
- **Scheduler (Phase 5)** — APScheduler in lifespan fires renewal pre-notice, hourly dunning, and charge retry jobs.
- **Hardening (Phase 6)** — slowapi rate limits, structlog JSON logging, request-ID middleware, CORS stripped on `/webhooks/*`, multi-stage production Dockerfile.

## Rate limits

Enforced in `app/rate_limit.py`:

| Path | Method | Rate | Key |
| --- | --- | --- | --- |
| `/auth/register` | POST | 5/minute | IP |
| `/auth/jwt/login` | POST | 10/minute | IP |
| `/auth/jwt/refresh` | POST | 30/minute | IP |
| `/subscriptions` | POST | 5/minute | user (or IP) |
| `/invoices/{id}/checkout` | POST | 10/minute | user (or IP) |
| `/webhooks/payfast` | POST | *exempt* | — |

Disable globally with `RATE_LIMIT_ENABLED=false` (the test suite does this).

## Logging

`app/logging_config.py` wires structlog. `ENV=production` → JSON one-line-per-
event; otherwise pretty console. Every request gets a request ID from the
`X-Request-ID` header (or fresh UUID4) and it's echoed back in the response.
Example log line:

```
{"event": "http.request", "request_id": "5b7f...", "path": "/plans", "method": "GET", "status": 200, "duration_ms": 12.8, "timestamp": "..."}
```
