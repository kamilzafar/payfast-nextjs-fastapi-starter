# PayFast Billing — Frontend

Next.js 16 (App Router) + TypeScript + Tailwind v4 + shadcn/ui. Talks directly
to the FastAPI backend over `NEXT_PUBLIC_API_URL`.

## Prerequisites

- Node.js 20+
- pnpm 10+ (`npm i -g pnpm`)

## Install

```bash
cd frontend
pnpm install
```

## Env setup

Copy the sample env file and point it at your running backend:

```bash
cp .env.example .env.local
```

`.env.local` just needs `NEXT_PUBLIC_API_URL`. Default is
`http://localhost:8000`.

## Run the dev server

```bash
pnpm dev
```

Open http://localhost:3000. Routes:

- `/` — marketing landing
- `/pricing` — plans (server-rendered from `GET /plans`)
- `/login`, `/signup` — auth forms (fastapi-users compatible)
- `/dashboard`, `/dashboard/invoices`, `/settings` — authed placeholders

If the backend isn't running, `/pricing` shows a graceful "API unreachable"
state and the auth forms surface a toast on submit.

## Commands

```bash
pnpm dev        # dev server on :3000
pnpm build      # production build (also runs type/lint check)
pnpm start      # serve the built app
pnpm lint       # eslint
pnpm test       # vitest (one-shot)
pnpm test:watch # vitest (watch mode)
```

## Structure

```
app/
  (marketing)/pricing/  # server-rendered plan list
  (auth)/login|signup/  # client forms
  (app)/dashboard|...   # authed placeholders (phase 4)
components/
  ui/                   # shadcn primitives
  site-nav.tsx          # top nav (public + authed variants)
  plan-card.tsx
  auth-form.tsx
  theme-provider.tsx    # next-themes wrapper
  theme-toggle.tsx
lib/
  api-client.ts         # typed fetch + 401 refresh
  auth-context.tsx      # React context for user/session
  auth-storage.ts       # localStorage access-token helpers
  env.ts                # typed env access
  types.ts              # Zod schemas mirroring backend
proxy.ts                # Next 16 proxy (formerly middleware) — bounces unauth
                        # users off /dashboard/* and /settings based on a
                        # non-httpOnly session sentinel cookie.
```

## Auth model

- Access token: short-lived JWT stored in `localStorage`, attached to every
  request as `Authorization: Bearer`.
- Refresh token: httpOnly cookie set by FastAPI, never seen by JS.
- On 401 the API client calls `/auth/jwt/refresh` once, retries the original
  request, and on failure clears the session.
- `proxy.ts` does an optimistic edge redirect by looking for a
  `payfast.session` sentinel cookie set by the backend alongside the refresh
  cookie.

## Not yet done

- Checkout redirect page — phase 3
- Billing dashboard content (subscriptions, invoices table) — phase 4
- TanStack Query — phase 4
