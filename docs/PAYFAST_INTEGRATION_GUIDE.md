# PayFast Integration Guide

**Last Updated:** 2026-04-21

## What PayFast is

PayFast is a Pakistani payment gateway (gopayfast.com). It accepts card payments (Visa, Mastercard), Google Pay, mobile wallets (Easypaisa, JazzCash), and account transfers from customers. The gateway operates in two environments: UAT at `https://ipguat.apps.net.pk` (testing) and Live at `https://ipg1.apps.net.pk` (production). PayFast uses a hosted-redirect checkout model: you send the customer to PayFast's page, they enter payment details, then PayFast posts a server-to-server notification (IPN) to confirm the outcome. Currently PayFast does not support merchant-initiated token charges (MIT) or subscriptions natively — this codebase layers subscription billing on top of single-transaction PayFast payments.

## End-to-End Payment Flow

```
User at Frontend              Backend                PayFast
     |                           |                       |
     | POST /invoices/{id}       |                       |
     |-------------------------> |                       |
     |                           | POST GetAccessToken   |
     |                           |---------------------> |
     |                           |      { ACCESS_TOKEN } |
     |                           | <--------------------- |
     |                           |                       |
     | { action_url, fields }    |                       |
     | <------------------------ |                       |
     |                           |                       |
     | Auto-POST form to         |                       |
     | action_url (PostTransaction)                      |
     |                           |                       |
     |-------- User pays --------|-------- User pays ----|
     |                           |                       |
     |                           | <------ IPN POST -----|
     |                           | (validation_hash auth)|
     |                           |                       |
     | 302 to return_url         |                       |
     | <------------------------ | Mark invoice paid     |
     |                           |                       |
```

**Key distinction: SUCCESS_URL vs CHECKOUT_URL**

- **SUCCESS_URL** / **FAILURE_URL**: Browser redirect. User sees a 302 response and lands on the merchant's page. NOT authoritative for payment status (user might close the tab before the redirect). Use this for UX only.
- **CHECKOUT_URL**: Server-to-server IPN (Instant Payment Notification) POST from PayFast to your backend. Authentication via `validation_hash` field in the body. This is the source of truth for payment completion — it arrives independently of whether the user's browser completes the redirect.

## Architecture in This Repo

```
┌──────────────────────────────────────────────────────┐
│                     Frontend (Next.js)               │
│         Thin shell; renders forms, links             │
│              http://localhost:3000                   │
└────────────────┬─────────────────────────────────────┘
                 │ API calls
                 ▼
┌──────────────────────────────────────────────────────┐
│                  Backend (FastAPI)                   │
│  Services: PayFast client, billing, renewals, email  │
│  Models: Invoice, Subscription, Plan, User           │
│  Routers: invoices, webhooks_payfast, payfast_       │
│           redirect, subscriptions                     │
│           http://localhost:8000                      │
└────────────────┬──────────────────┬──────────────────┘
                 │                  │ IPN POST
                 │              PayFast
         Postgres 16          (UAT or Live)
         localhost:5432
```

**Data flow for a subscription renewal:**
1. APScheduler daily_renewal_sweep checks for subscriptions with unpaid invoices past due.
2. For each past-due subscription, create a new Invoice row (amount = plan.amount_minor).
3. Email user a link: `/invoices/{invoice_id}/checkout` (frontend intercepts, calls the backend).
4. Backend generates PayFast token and returns HTML form (`action_url` + `fields`).
5. Frontend auto-POSTs form to `action_url` (PayFast's checkout endpoint).
6. User completes payment on PayFast.
7. PayFast POSTs IPN to `CHECKOUT_URL` (e.g., `https://example.com/webhooks/payfast`).
8. Backend verifies `validation_hash`, marks invoice paid, updates subscription status to active.

## Step-by-Step Integration Recipe

### 1. Provision PayFast Credentials

Contact PayFast (gopayfast.com) to obtain:
- `MERCHANT_ID` (numeric, e.g., "102")
- `SECURED_KEY` (alphanumeric, e.g., "zWHjBp2AlttNu1sK")

Start in UAT environment.

### 2. Set Environment Variables

```bash
# backend/.env
PAYFAST_MERCHANT_ID=<your_merchant_id>
PAYFAST_SECURED_KEY=<your_secured_key>
PAYFAST_BASE_URL=https://ipguat.apps.net.pk  # Change to ipg1.apps.net.pk for live
PAYFAST_RETURN_URL=https://your-domain.com/payfast/return
PAYFAST_CANCEL_URL=https://your-domain.com/payfast/cancel
PAYFAST_CHECKOUT_URL=https://your-domain.com/webhooks/payfast  # Must be publicly reachable
```

### 3. Implement PayFast Service Primitives

The three core operations are already in place in the starter. If integrating into a new project, implement these three functions (reference: `backend/app/services/payfast/`):

**a) `get_access_token(merchant_id, secured_key, basket_id, amount_minor, currency="PKR", base_url, timeout)`**

- POST form-encoded data to `{base_url}/Ecommerce/api/Transaction/GetAccessToken`
- Fields: `MERCHANT_ID`, `SECURED_KEY`, `BASKET_ID`, `TXNAMT` (major units, e.g., "1500.00"), `CURRENCY_CODE`
- Response: JSON with `ACCESS_TOKEN` key
- Raises exception on non-2xx status or missing token
- See: `/backend/app/services/payfast/client.py`

**b) `build_checkout_payload(invoice, user, token, return_url, cancel_url, checkout_url, merchant_id, ...)`**

- Construct a dict of form fields to auto-POST to PayFast's PostTransaction endpoint
- Fields: `CURRENCY_CODE`, `MERCHANT_ID`, `MERCHANT_NAME`, `TOKEN`, `BASKET_ID`, `TXNAMT`, `ORDER_DATE`, `SUCCESS_URL`, `FAILURE_URL`, `CHECKOUT_URL`, `CUSTOMER_EMAIL_ADDRESS`, `CUSTOMER_MOBILE_NO`, `SIGNATURE`, `VERSION`, `TXNDESC`, `PROCCODE`, `TRAN_TYPE`, `STORE_ID`, `RECURRING_TXN`
- See: `/backend/app/services/payfast/payload.py`

**c) `verify_ipn(payload, secured_key, merchant_id)`**

- Parse the IPN body (form-urlencoded or JSON)
- Extract `basket_id`, `err_code`, `validation_hash` from the payload
- Compute expected hash: `SHA256(basket_id|secured_key|merchant_id|err_code)`
- Return True iff computed hash matches received hash (use constant-time comparison)
- See: `/backend/app/services/payfast/signature.py`

### 4. Add Database Models

Create models for:
- `Invoice` (basket_id [UUID, unique], amount [minor units], status [open/paid/void], due_at, paid_at, payfast_txn_id)
- `Subscription` (status [trialing/active/past_due/canceled], current_period_start, current_period_end, cancel_at_period_end)
- `Plan` (name, amount_minor, billing_interval [monthly/yearly], trial_days)
- `User` (email, phone, hashed_password, ...)
- `WebhookEvent` (provider_event_id [unique], provider_name, payload [JSON], processed_at)

See: `/backend/app/models/`

### 5. Wire Checkout Endpoint

Implement `POST /invoices/{invoice_id}/checkout`:

```python
# backend/app/routers/invoices.py excerpt
@router.post("/{invoice_id}/checkout", response_model=InvoiceCheckoutResponse)
async def checkout_invoice(
    invoice_id: int,
    user: User = Depends(current_active_user),
    db: AsyncSession = Depends(get_db),
    http_client: httpx.AsyncClient = Depends(get_http_client),
) -> InvoiceCheckoutResponse:
    # 1. Load invoice scoped to user
    invoice = await inv_repo.get_by_id_for_user(db, invoice_id, user.id)
    # 2. Verify invoice status is open (not already paid)
    # 3. Call get_access_token(...)
    # 4. Call build_checkout_payload(...)
    # 5. Return { action_url, fields }
```

Frontend receives `{ action_url: "https://ipguat.apps.net.pk/...", fields: {...} }` and auto-POSTs it as an HTML form.

### 6. Wire IPN Webhook Endpoint

Implement `POST /webhooks/payfast`:

```python
# backend/app/routers/webhooks_payfast.py excerpt
@router.post("")
async def payfast_ipn(request: Request) -> dict[str, str]:
    # 1. Read raw body
    raw_body = await request.body()
    
    # 2. Parse (JSON or form-urlencoded)
    parsed = _parse_body(raw_body, request.headers.get("content-type"))
    
    # 3. Verify IPN signature
    if not verify_ipn(parsed, settings.PAYFAST_SECURED_KEY, settings.PAYFAST_MERCHANT_ID):
        raise HTTPException(status_code=403, detail="invalid validation_hash")
    
    # 4. Idempotency: derive event_id from transaction_id or body hash
    event_id = derive_event_id(raw_body, parsed)
    
    # 5. Try insert webhook_event; if duplicate, return 200 immediately
    is_new = await webhook_events_repo.try_insert(db, event_id, parsed)
    if not is_new:
        return {"status": "ok"}
    
    # 6. Look up invoice by basket_id
    basket_uuid = uuid.UUID(parsed.get("basket_id"))
    invoice = await invoices_repo.get_by_basket_id(db, basket_uuid)
    
    # 7. If err_code == "000": mark invoice paid, activate subscription
    #    Else: record payment attempt as failed
    
    # 8. Commit in one transaction
    await db.commit()
    return {"status": "ok"}
```

### 7. Wire Redirect Handlers

Implement `GET /payfast/return` and `GET /payfast/cancel`:

- **return**: Parse `basket_id` from query params, 302 to frontend success page with the basket_id (non-authoritative, for UX only)
- **cancel**: Parse `basket_id`, if valid insert a failed `PaymentAttempt` record, 302 to frontend cancel page

See: `/backend/app/routers/payfast_redirect.py`

### 8. Make CHECKOUT_URL Publicly Reachable

During development:
```bash
# Terminal 1: Start backend
make backend

# Terminal 2: Create a public tunnel
cloudflare tunnel --url http://localhost:8000
# Output: Tunnel running at https://xxx-yyy.trycloudflare.com
```

Set `PAYFAST_CHECKOUT_URL=https://xxx-yyy.trycloudflare.com/webhooks/payfast` in your `.env`.

For production, replace with a stable domain (e.g., `api.example.com/webhooks/payfast`).

### 9. Test with PayFast Test Card

In UAT, use card: **5123-4500-0000-0008**, exp: **01/39**, CVV: **100**.

PayFast will present a 3DS ACS emulator (not real 3DS). Press `(Y)` to simulate a successful challenge. If you press `(N)` or `(U)`, the transaction will fail.

### 10. Subscription Billing Layer

This starter adds a subscription abstraction on top of PayFast's per-transaction model. See the `Subscription State Machine` section below.

---

## Gotchas We Learned the Hard Way

- **ASP.NET NullReferenceException on GetAccessToken**: If your merchant account is not "activated" by PayFast, the ASP.NET backend may return a NullReferenceException (looks like a malformed response). Contact PayFast support to confirm your merchant is active.

- **CURRENCY_CODE is required**: Older PayFast SDKs sometimes omitted this on the token request. Always include `CURRENCY_CODE=PKR`.

- **Response key is ACCESS_TOKEN**: Not `TOKEN` or `token`. The official sample uses `ACCESS_TOKEN` (all caps). Our client checks all three variants for robustness (`backend/app/services/payfast/client.py` line 94–95).

- **VERSION field is MERCHANTCART-0.1**: Not `MERCHANT-CART-0.1` (with dashes). No dashes.

- **MERCHANT_NAME is case-sensitive**: In the `payment.php` sample, it's `MERCHANT_NAME` (all caps). Use that casing in your form.

- **ORDER_DATE format**: Must be `YYYY-MM-DD HH:MM:SS` (UTC). Not `YYYYMMDDHHMMSS` or any other format. See `backend/app/services/payfast/payload.py` line 69.

- **SIGNATURE is NOT cryptographic**: The `SIGNATURE` field in the form is just a merchant-chosen correlation tag (our starter uses a random hex prefix + basket_id). PayFast ignores its value. Real IPN authentication is the `validation_hash` inside the IPN body.

- **validation_hash formula**: `SHA256(basket_id|secured_key|merchant_id|err_code)` with literal pipe characters. Example: `"BAS-01|jdnkaabcks|102|000"` → `e8192a7554dd699975adf39619c703a492392edf5e416a61e183866ecdf6a2a2`. See `backend/app/services/payfast/signature.py`.

- **IPN body encoding**: Can be `application/x-www-form-urlencoded` or `application/json`. Always parse both. See `backend/app/routers/webhooks_payfast.py` line 37.

- **IPN idempotency is non-negotiable**: PayFast may retry IPNs if they timeout. Use a unique index on `webhook_events.provider_event_id` to prevent double-processing. Fall back to SHA-256(raw_body) if `transaction_id` is absent from the payload.

- **Email validator rejects .local and .test TLDs**: If using `fastapi-users`, the default email validator blocks `.local` and `.test` domains. In tests, use a routable-looking TLD (e.g., `user@example.com`) or customize the validator.

---

## Subscription Billing on Top

PayFast has no native subscription or recurring charge API. This starter layers one on top using a cron job (APScheduler) that:

1. **Daily sweep** (02:00 UTC): Check for subscriptions with open invoices past due.
2. **Renewal logic**: Create a new invoice for the next billing period.
3. **Dunning emails**: Send payment reminders at T+3, T+5, T+7 days past due.
4. **Auto-cancellation**: Cancel subscriptions 7 days past due if unpaid.

### Subscription State Machine

```
trialing ─── (first payment succeeds) ──→ active
                                           │
                                           ├─ (invoice past due 24h) → past_due
                                           │
                                           ├─ (cancel_at_period_end=True, period ends) → canceled
                                           │
                                      (payment succeeds)
                                           │
past_due ←──────────────────────────────┘
  │
  └─ (7 days unpaid) → canceled
```

### Dunning Windows (Days Since Invoice Due Date)

- **T+0**: Invoice due at this time.
- **T+3**: First dunning email sent.
- **T+5**: Second dunning email sent.
- **T+7**: Automatic subscription cancellation (no more emails after this).

### Key Classes

- **`Subscription`** (`backend/app/models/subscription.py`): Tracks billing state, period, plan.
- **`Invoice`** (`backend/app/models/invoice.py`): One billable cycle per subscription.
- **`PaymentAttempt`** (`backend/app/models/payment_attempt.py`): Audit log of charge attempts (success / failure + reason).
- **`Charger`** interface (`backend/app/services/charger.py`): Encapsulates how we attempt to collect. Today's implementation sends an email link (`HostedRedirectCharger`). Future implementation will do server-initiated MIT charges via PayFast's Permanent Token API (`TokenCharger`).

See `backend/app/services/billing.py` and `backend/app/services/renewals.py` for orchestration logic.

---

## Going from UAT to Live

### Checklist

- [ ] Swap `PAYFAST_BASE_URL` from `https://ipguat.apps.net.pk` to `https://ipg1.apps.net.pk`.
- [ ] Obtain real `PAYFAST_MERCHANT_ID` and `PAYFAST_SECURED_KEY` from PayFast for live.
- [ ] Set up a stable HTTPS domain for `PAYFAST_RETURN_URL`, `PAYFAST_CANCEL_URL`, `PAYFAST_CHECKOUT_URL` (no more Cloudflare tunnel).
- [ ] Replace `EMAIL_BACKEND=smtp` with a real transactional email service. This starter uses MailHog (zero-config) in dev. For live:
  - Option A: `EMAIL_BACKEND=resend`, set `RESEND_API_KEY` (https://resend.com).
  - Option B: `EMAIL_BACKEND=smtp` with production SMTP credentials (SendGrid, AWS SES, etc.).
- [ ] Verify sender email domain in your email service.
- [ ] Set `ENV=production` to enable JSON structlog (for log aggregation).
- [ ] If running multiple backend replicas: set `SCHEDULER_ENABLED=false` on all but one replica. APScheduler uses filesystem locks and will conflict if > 1 instance tries to acquire. See `backend/app/workers/scheduler.py`.
- [ ] Review rate limits in `backend/app/rate_limit.py` and adjust if needed.
- [ ] Load-test the renewal cron job (`daily_renewal_sweep`, `reconciliation_sweep`, `hourly_dunning_check`) to ensure it completes within the time window and doesn't timeout for high subscriber counts.

---

## Related Documentation

- **Detailed field and API contract**: See `docs/PAYFAST_CONTRACT.md`
- **Architecture and full codebase map**: See root `CLAUDE.md`
- **PayFast official docs**: `Merchant Integration Guide 2.3 -updated.pdf`, `IPN INTEGRATION DOCUMENT (3).pdf` (in repo root)
