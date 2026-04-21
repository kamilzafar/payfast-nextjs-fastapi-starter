# CLAUDE.md — PayFast Subscription Billing Platform

**Stripe-like monthly subscription billing for Pakistan**, built on the PayFast hosted-redirect gateway (Bank AlFalah / APPS). FastAPI backend + Next.js 16 frontend + local Postgres. Production-ready through phase 6; live UAT verified.

## Stack

| Layer | Tech | Package Manager |
|-------|------|-----------------|
| Backend | Python 3.13, FastAPI, SQLAlchemy async, Alembic migrations, fastapi-users JWT, APScheduler, slowapi, structlog, Jinja2 + aiosmtplib (prod: resend), httpx | uv |
| Frontend | Next.js 16 App Router, TypeScript strict, Tailwind, Base UI (shadcn variant, no `asChild`), Zod, React Hook Form, Vitest, Playwright | pnpm |
| Infra | docker-compose: postgres:16-alpine, mailhog, adminer; cloudflared tunnel for IPN | docker |

## Repo Layout

```
payfast_payment_gateway/
  backend/
    app/
      auth/              fastapi-users config, JWT/refresh logic
      models/            ORM: users, plans, subscriptions, invoices, webhook_events, etc
      repositories/      data access layer
      routers/           API endpoints (auth, plans, invoices, webhooks, payfast redirect)
      schemas/           Pydantic request/response models
      services/          business logic (billing, renewals, charger, email, payfast)
        payfast/         client.py (token fetch), payload.py (checkout form), signature.py (IPN verify)
      workers/           scheduler.py (APScheduler lifespan wiring)
      templates/email/   Jinja2 templates for dunning, renewal notices
      config.py          Settings from .env
      main.py            FastAPI app, lifespan (scheduler startup)
    alembic/             migration scripts
    scripts/seed.py      create baseline plans/users
    tests/               pytest suite (async event loop per session)
  frontend/
    app/
      (marketing)/       pricing page
      (auth)/            login, signup
      (app)/             dashboard, settings (gated by proxy.ts)
      checkout/          initiate, [invoiceId], success, cancel pages
    components/          UI: plan-card, subscription-card, invoice-table, auth-form, etc
    lib/
      auth-context.tsx   React context: login, signup, logout, user/token state
      auth-storage.ts    localStorage + refresh cookie handling
      api-client.ts      httpx-like fetch wrapper, token refresh logic
      types.ts           Zod schemas for API contracts
    proxy.ts             Next.js 16 proxy (formerly middleware.ts) — auth gating for /dashboard, /checkout
  infra/
    docker-compose.yml   postgres, mailhog, adminer services
  Makefile               help, dev, db-*, migrate, seed, backend, frontend, test, lint, ngrok
  docs/                  (will be populated by sibling agent)
  (PDF reference docs at root — git-ignored by default .gitignore)
```

## Local Dev Commands

```bash
# 1. env files + secret
cp backend/.env.example backend/.env
cp frontend/.env.example frontend/.env.local
# Ensure JWT_SECRET in backend/.env — generate with: openssl rand -hex 32

# 2. Start infra (Postgres, MailHog, Adminer)
make db-up
# Postgres: postgresql://postgres:postgres@localhost:5432/payfast
# MailHog SMTP: localhost:1025  |  UI: http://localhost:8025

# 3. Migrations + seed
make migrate
make seed

# 4. Backend (terminal 1)
make backend
# FastAPI on :8000, OpenAPI docs at /docs

# 5. Frontend (terminal 2)
make frontend
# Next.js dev on :3000

# 6. Open app
open http://localhost:3000

# Tests
make test              # pytest + vitest
make lint              # ruff + eslint

# IPN testing (requires public URL)
make ngrok             # prints setup checklist
# Then: cloudflared tunnel --url http://localhost:8000 (alternative to ngrok)
```

## PayFast Contract (Gotchas)

- **Base URLs:** UAT `https://ipguat.apps.net.pk` | Live `https://ipg1.apps.net.pk`. Override in `PAYFAST_BASE_URL`.
- **Token endpoint** POSTs form-urlencoded: `MERCHANT_ID`, `SECURED_KEY`, `BASKET_ID`, `TXNAMT` (major units, 2dp), `CURRENCY_CODE=PKR`. Response: JSON with `ACCESS_TOKEN` key.
- **Checkout form fields** are case-sensitive, from `payment.php`: `MERCHANT_NAME` all-caps, `VERSION=MERCHANTCART-0.1` (no dash), `ORDER_DATE='YYYY-MM-DD HH:MM:SS'` UTC, `TRAN_TYPE=ECOMM_PURCHASE`, `PROCCODE=00`.
- **SUCCESS_URL / FAILURE_URL** are browser redirects (UX). **CHECKOUT_URL** is the IPN server-to-server endpoint (auth via body hash).
- **IPN authentication** via `validation_hash` IN the body (not a header HMAC): `SHA256(basket_id|secured_key|merchant_id|err_code)`. See `backend/app/services/payfast/signature.py`.
- **`err_code = "000"`** means success. Any other value is a failure; the `err_msg` field carries the reason.
- **No native MIT** (merchant-initiated / auto-charge). Renewals are customer-initiated via emailed payment links. `backend/app/services/charger.py` abstracts this; `TokenCharger` stub is ready for future PayFast MIT API.
- **Live IPN needs a public URL.** For local dev: `cloudflared tunnel --url http://localhost:8000` or `ngrok http 8000`, then set `PAYFAST_CHECKOUT_URL` env var to the public tunnel and restart backend.
- **UAT test card:** 5123-4500-0000-0008, exp 01/39, CVV 100. 3DS shows an ACS emulator — pick `(Y) Successful`.
- **Reference docs** at repo root (PDFs, git-ignored by default): *Merchant Integration Guide 2.3*, *IPN INTEGRATION DOCUMENT*, *IPN Parameters*, *validation_hash_calculation.txt*, *payment.php*. **These are the source of truth.**

## Architecture Decisions

- **Split stack** (Next + FastAPI, not Next API routes): language-specific strengths. Frontend is a thin presentation shell; zero business logic in `frontend/app/api/`. Always talk to FastAPI.
- **Auth:** fastapi-users self-hosted JWT + refresh cookie. Access token in localStorage + non-httpOnly `payfast.session` sentinel cookie. Read by `proxy.ts` for edge-level gating before shipping client bundle.
- **Money:** always integer minor units (paisa). Never floats. `backend/app/services/payfast/client.py#_minor_to_major()` converts to major for API calls.
- **Renewal via Charger abstraction** in `backend/app/services/charger.py`: `HostedRedirectCharger` today (email pay links), `TokenCharger` stub for future MIT.
- **IPN idempotency:** `webhook_events(provider, provider_event_id UNIQUE)` + INSERT ... ON CONFLICT DO NOTHING. Key = `transaction_id` from payload, falls back to SHA-256(raw body).
- **Scheduler:** APScheduler in-process inside FastAPI lifespan (`backend/app/workers/scheduler.py`). Single-writer today. See Dockerfile NOTE: with `--workers > 1`, jobs duplicate-fire (idempotent jobs tolerate it short-term).
- **CORS locked** to `CORS_ORIGINS` env. `/webhooks/*` strips CORS headers via `_CORSWebhookStripper` middleware to prevent leaking signed payloads.

## Where Things Live (Cheat Sheet)

| Task | Touch |
|------|-------|
| Add plan tier | `backend/scripts/seed.py` → `make seed` (or admin UI later) |
| Change PayFast field shape | `backend/app/services/payfast/{client,payload,signature}.py` + tests in `backend/tests/services/payfast/` |
| Modify IPN processing | `backend/app/routers/webhooks_payfast.py` + `backend/app/services/billing.py` |
| Tweak dunning logic | `backend/app/services/renewals.py`, `backend/app/services/charger.py`, email templates in `backend/app/templates/email/` |
| Add frontend page | Create under `frontend/app/(app\|auth\|marketing)/` or standalone in `frontend/app/`, mirror existing layout groups |
| Add shadcn component | `pnpm dlx shadcn@latest add <name>` — uses Base UI variant (no `asChild`) |
| Modify auth flow | `frontend/lib/auth-context.tsx` (login/signup/logout), `frontend/lib/auth-storage.ts` (token persist), `frontend/proxy.ts` (routing gating) |

## Conventions (Enforce in Edits)

- **Python:** PEP 8, type hints on public functions, docstrings (what + why, not how), ruff check, async-first, no sync I/O in request path, money as `int` minor units.
- **TypeScript:** strict mode, Zod at API boundaries, no `any`, named exports for components (no defaults), path alias `@/`.
- **Tests:** pytest async (session-scoped event loop), Vitest for frontend, Playwright for E2E (gated on `PAYFAST_MERCHANT_ID`).
- **Git:** never push without explicit user say-so. Never `--no-verify`. Lockfiles committed; `.env` files never.
- **Comments:** default to zero. Only WHY, not WHAT.

## Known Limitations / TODOs

- No native MIT/auto-charge (PayFast limitation; abstraction ready).
- APScheduler duplicates with `--workers > 1` (documented in Dockerfile; idempotent jobs tolerate it).
- PayFast IPN signature is the only auth — relies on `PAYFAST_SECURED_KEY` secrecy.
- Playwright E2E payment flow (`frontend/e2e/payment.spec.ts.skip`) gated behind UAT creds; rename `.skip` when ready.
- Single currency (PKR), single tenant, single scheduler process today.

## Frontend-Specific: Next.js 16 Proxy

Next.js 16 renamed `middleware.ts` to `proxy.ts`. Before touching routing, read `node_modules/next/dist/docs/01-app/01-getting-started/16-proxy.md`. shadcn in this project uses Base UI — `<Button asChild>` patterns from Radix-based docs don't apply. Use the Base UI slot prop pattern instead.

## Cross-Reference

- Deep PayFast integration details → `docs/PAYFAST_INTEGRATION_GUIDE.md` (sibling agent)
- PayFast contract validation → `docs/PAYFAST_CONTRACT.md` (sibling agent)
