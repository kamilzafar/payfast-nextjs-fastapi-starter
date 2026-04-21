# PayFast Integration Documentation

This folder contains focused reference material for integrating PayFast into a FastAPI + Next.js subscription billing system.

## Documents

### 1. [PAYFAST_INTEGRATION_GUIDE.md](./PAYFAST_INTEGRATION_GUIDE.md)

**For**: Engineers implementing PayFast integration in a new project.

Covers:
- What PayFast is and its hosted-redirect checkout model
- End-to-end payment flow (browser + IPN)
- Architecture overview (frontend, backend, PayFast)
- Step-by-step integration recipe (10 concrete steps)
- Common gotchas and how we solved them
- Subscription billing layer (how this starter adds recurring billing on top of PayFast)
- Going live (UAT → production checklist)

Read this first if you're new to PayFast or implementing from scratch.

### 2. [PAYFAST_CONTRACT.md](./PAYFAST_CONTRACT.md)

**For**: Looking up exact field names, types, examples, and validation rules.

Covers:
- API endpoints (UAT and Live URLs)
- GetAccessToken request/response field-by-field
- PostTransaction form fields with all details
- IPN payload fields
- validation_hash computation (worked example)
- Error codes reference
- 3DS ACS emulator behavior (UAT only)
- Test card details
- URL role clarification table

Bookmark this for quick lookups.

---

## Using These Docs

**Scenario 1: New integration from scratch**
1. Read PAYFAST_INTEGRATION_GUIDE.md sections 1–3 to understand PayFast basics.
2. Follow the "Step-by-Step Integration Recipe" (section 4).
3. Reference PAYFAST_CONTRACT.md for exact field names and formats.

**Scenario 2: Debugging a payment flow**
1. Check the "Gotchas" section (PAYFAST_INTEGRATION_GUIDE.md section 5) — your issue is probably listed.
2. Look up the field in PAYFAST_CONTRACT.md to verify type/format.
3. Check `backend/app/services/payfast/` for reference implementation.

**Scenario 3: Going live**
1. Follow the "Going from UAT to Live" checklist (PAYFAST_INTEGRATION_GUIDE.md section 7).

---

## Related Documentation

- **Full codebase map and architecture**: See `../CLAUDE.md` (root directory).
- **Official PayFast PDFs** (in repo root):
  - `Merchant Integration Guide 2.3 -updated.pdf` — overall flow, endpoints, field specs
  - `IPN INTEGRATION DOCUMENT (3).pdf` — IPN details and security
  - `IPN Parameters (3).pdf` — real IPN payload sample

---

## Implementation Reference

Key files in this repo:

- `/backend/app/services/payfast/client.py` — GetAccessToken call
- `/backend/app/services/payfast/payload.py` — PostTransaction form builder
- `/backend/app/services/payfast/signature.py` — IPN validation_hash verification
- `/backend/app/routers/invoices.py` — checkout endpoint
- `/backend/app/routers/webhooks_payfast.py` — IPN handler
- `/backend/app/routers/payfast_redirect.py` — return/cancel handlers
- `/backend/app/models/invoice.py`, `subscription.py`, `plan.py` — domain models
- `/backend/app/services/billing.py`, `renewals.py`, `charger.py` — subscription orchestration

---

## Version

Last Updated: 2026-04-21

These docs are generated from the codebase at the time of writing. Always verify field names and URLs against the official PayFast documentation if you're on a different version of the gateway.
