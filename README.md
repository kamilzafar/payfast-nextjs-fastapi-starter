# PayFast Subscription Billing Platform

Stripe-like subscription billing for Pakistan, built on top of the PayFast payment gateway. Local-first developer experience: everything runs on your machine against a local Postgres, with ngrok used only when you need PayFast to reach your backend for IPN testing.

## What this is

A small, focused platform that lets a merchant define products and recurring plans, onboard subscribers, collect payments through PayFast, and handle the subscription lifecycle (trials, renewals, upgrades, dunning, cancellations). Think of it as the subset of Stripe Billing that makes sense for Pakistani merchants who must route card payments through PayFast.

## Architecture

- **Backend**: FastAPI (Python 3.13, async SQLAlchemy + Alembic, Pydantic v2) on port `8000`.
- **Frontend**: Next.js (App Router, TypeScript) on port `3000`.
- **Database**: Postgres 16, local container.
- **Dev support**: MailHog as a zero-config SMTP sink, Adminer for quick DB inspection.

The stack is intentionally split: the frontend is a dedicated Next.js app and the backend is a first-class FastAPI service, rather than using Next.js API routes. This keeps the billing domain (webhooks, IPN verification, subscription schedulers, background jobs) on a Python runtime where those workloads belong, and lets the frontend be deployed, scaled, and owned independently.

## Prerequisites

| Tool | Version | Install |
| --- | --- | --- |
| Docker Desktop | latest | https://www.docker.com/products/docker-desktop |
| Python | 3.13+ | https://www.python.org/downloads/ |
| uv | latest | `pip install uv` or see https://docs.astral.sh/uv/ |
| Node.js | 20+ | https://nodejs.org/ |
| pnpm | latest | `npm i -g pnpm` |
| ngrok | latest | https://ngrok.com/download (only needed for PayFast IPN testing) |

`make`, `git`, and a POSIX shell are assumed. On Windows, the Makefile targets run under Git Bash.

## Quick start

1. Copy env templates and fill in secrets.

   ```bash
   cp backend/.env.example backend/.env
   cp frontend/.env.example frontend/.env.local
   ```

   At minimum, set `JWT_SECRET` in `backend/.env`. Generate a strong value with:

   ```bash
   openssl rand -hex 32
   ```

2. Start local infrastructure (Postgres, MailHog, Adminer).

   ```bash
   make db-up
   ```

3. Apply migrations and seed baseline data.

   ```bash
   make migrate
   make seed
   ```

4. Start the backend (terminal 1).

   ```bash
   make backend
   ```

5. Start the frontend (terminal 2).

   ```bash
   make frontend
   ```

6. Open the app.

   http://localhost:3000

## Services and ports

| Service | URL / port | Notes |
| --- | --- | --- |
| Postgres | `localhost:5432` | db `payfast`, user/pass `postgres/postgres` |
| MailHog SMTP | `localhost:1025` | Backend sends mail here in dev |
| MailHog UI | http://localhost:8025 | Inspect captured emails |
| Adminer | http://localhost:8080 | DB GUI; server field: `postgres` |
| FastAPI backend | http://localhost:8000 | OpenAPI docs at `/docs` |
| Next.js frontend | http://localhost:3000 | |

Connection string: `postgresql://postgres:postgres@localhost:5432/payfast`

## Testing PayFast IPN locally

PayFast posts IPN notifications to a publicly reachable URL. Your laptop is not publicly reachable, so use ngrok while developing.

1. Install ngrok and add your authtoken: `ngrok config add-authtoken <YOUR_TOKEN>`.
2. Start the backend: `make backend`.
3. In another terminal: `ngrok http 8000`. Copy the `https://...ngrok-free.app` URL it prints.
4. Update `backend/.env`:
   - `PAYFAST_RETURN_URL=<ngrok-url>/api/payfast/return`
   - `PAYFAST_CANCEL_URL=<ngrok-url>/api/payfast/cancel`
5. Provide `<ngrok-url>/api/payfast/ipn` to PayFast (via their dashboard or support ticket) as the IPN endpoint for your merchant profile.
6. Restart the backend so the new env values are loaded.

`make ngrok` prints this same checklist on demand.

## Project layout

```
payfast_payment_gateway/
  backend/           FastAPI service, SQLAlchemy models, Alembic migrations
    app/             Application code (routers, services, schemas)
    alembic/         Migration scripts
    scripts/         Operational scripts (e.g. seed.py)
    tests/           Pytest suite
  frontend/          Next.js App Router application
    app/             Routes, layouts, server/client components
    components/      Shared UI
    lib/             Client-side helpers (api client, auth, etc.)
  infra/             Local dev infrastructure
    docker-compose.yml   Postgres + MailHog + Adminer
  Makefile           Developer entry points (make help)
  README.md          You are here
```

## Current status

All planned phases (0–6) are complete:

- **Phase 0** — local infrastructure (Postgres, MailHog, Adminer), Makefile, env templates.
- **Phase 1** — backend + frontend scaffolds: FastAPI skeleton, Next.js App Router, Alembic, shared deps.
- **Phase 2** — domain models: `users`, `plans`, `subscriptions`, `invoices`, `webhook_events`. Alembic migrations wired.
- **Phase 3** — PayFast integration: hosted checkout (`get_access_token`, `build_checkout_payload`), IPN signature verification, redirect return/cancel endpoints, idempotent webhook processing.
- **Phase 4** — subscription lifecycle: create / cancel (at-period-end + immediate), invoice generation on renewal, billing service with atomic `apply_successful_payment`.
- **Phase 5** — scheduler + dunning: APScheduler wired in `lifespan`, nightly renewal pre-notice, hourly dunning reminders and grace-period cancellation, email templates (SMTP for dev, Resend for prod).
- **Phase 6** — hardening: rate limiting (slowapi), structured logging (structlog JSON in prod), request-ID middleware, CORS lockdown for webhook paths, production multi-stage Dockerfile, Playwright smoke, GitHub Actions CI, `.env.example` audit.

### What works today

- Sign up + log in (email/password, JWT auth via fastapi-users).
- Plan listing (`GET /plans`) — seeded with a basic/pro pair.
- Subscribe to a plan — creates a subscription + first open invoice.
- PayFast hosted redirect — initiates checkout via `POST /invoices/{id}/checkout` and auto-submits to the gateway.
- IPN webhook — marks invoice paid, activates subscription, extends period (idempotent against duplicate deliveries).
- Billing dashboard — current subscription state, invoice list, cancel flow.
- Cancellation — at-period-end flag or immediate, idempotent.
- Renewal cron — opens next invoice automatically for active subscriptions (runs hourly).
- Dunning emails — reminder on day 3/5, cancel-for-nonpayment after `DUNNING_GRACE_DAYS`.

### Known limitations

- **PayFast protocol — fully verified**: the gateway contract in `backend/app/services/payfast/` matches PayFast's Merchant Integration Guide 2.3 and the IPN Integration Document. Live UAT token fetch and IPN validation-hash verification are both green. See `docs/PAYFAST_CONTRACT.md` for the field-by-field reference.
- **No true MIT / auto-charge**: the Phase 5 charger implements hosted-redirect retries (email the customer a pay link) rather than server-side MIT charges. PayFast's MIT API is the eventual next step, but requires merchant onboarding + additional compliance review.
- **E2E gated on UAT creds**: `frontend/e2e/smoke.spec.ts` runs the auth + nav happy path; `frontend/e2e/payment.spec.ts.skip` holds the planned full-payment journey — rename it and unblock once UAT access lands.
- **Scheduler + workers**: the APScheduler runs in-process. The production Dockerfile uses `--workers 2`, which duplicates job firings. Jobs are idempotent (webhook dedupe, invoice state checks) so it's acceptable short-term, but scale out requires either `--workers 1` or extracting the scheduler to a separate process. See the NOTE comment in `backend/Dockerfile`.
- **Single currency (PKR)** and **single tenant** today — multi-tenant / multi-currency / 3DS edge cases are deferred.

## How to verify end-to-end

A manual smoke against a running local stack (assumes `make db-up` + migrations + seed already ran):

1. **Backend & frontend up.**
   Terminal 1: `make backend` — should print `Scheduler started job_count=...`.
   Terminal 2: `make frontend` — Next dev server on http://localhost:3000.
2. **Sign up** at http://localhost:3000/signup. You should land on `/dashboard`.
3. **Pick a plan** at http://localhost:3000/pricing, click Subscribe.
4. You'll hit `/checkout/initiate` which auto-submits to PayFast. With no UAT creds this fails at PayFast's end — that's expected. The subscription + invoice are created regardless.
5. **Check the DB** at http://localhost:8080 (Adminer) — tables `users`, `subscriptions`, `invoices`, `webhook_events` should all have rows.
6. **Cancel** from `/dashboard` → "Cancel subscription". Idempotent.
7. **Dunning email** simulation: in Adminer, backdate an invoice's `due_at` by 4 days. Wait up to an hour, or set `SCHEDULER_ENABLED=true` and restart. Reminder email lands in MailHog (http://localhost:8025).
8. **Webhook idempotency**: send the same signed IPN payload twice (`curl -X POST ...`) → only one `webhook_events` row, invoice stays paid, no duplicate period extension.
9. **Rate limit check**: `for i in $(seq 1 12); do curl -i -X POST http://localhost:8000/auth/jwt/login -d 'username=x&password=y' -H 'content-type: application/x-www-form-urlencoded'; done` — after the 10th request in a minute you should see HTTP 429.
10. **Request ID echo**: `curl -i http://localhost:8000/health` → response has `X-Request-ID: <uuid>`. Pass one in, get the same back.

For the full payment flow, you need PayFast UAT credentials in `backend/.env` — see "Known limitations" above.

## Documentation references

- PayFast developer docs: https://gopayfast.com/docs/
- Google Pay integration notes: see the Google Pay PDF in project documentation.
- FastAPI: https://fastapi.tiangolo.com/
- Next.js App Router: https://nextjs.org/docs/app
- Alembic: https://alembic.sqlalchemy.org/
- uv: https://docs.astral.sh/uv/
