# PayFast API Contract Reference

**Last Updated:** 2026-04-21

Precise field-by-field reference for integrating with PayFast. Extracted from official PayFast documentation (Merchant Integration Guide 2.3, IPN Integration Document, and payment.php sample).

---

## API Endpoints

| Environment | Purpose | Path | Method | Content-Type |
|---|---|---|---|---|
| UAT | Get access token | `https://ipguat.apps.net.pk/Ecommerce/api/Transaction/GetAccessToken` | POST | `application/x-www-form-urlencoded` |
| UAT | Post transaction (redirect user) | `https://ipguat.apps.net.pk/Ecommerce/api/Transaction/PostTransaction` | POST | `application/x-www-form-urlencoded` (HTML form) |
| Live | Get access token | `https://ipg1.apps.net.pk/Ecommerce/api/Transaction/GetAccessToken` | POST | `application/x-www-form-urlencoded` |
| Live | Post transaction (redirect user) | `https://ipg1.apps.net.pk/Ecommerce/api/Transaction/PostTransaction` | POST | `application/x-www-form-urlencoded` (HTML form) |

---

## GetAccessToken Request

| Field | Type | Example | Required? | Notes |
|---|---|---|---|---|
| `MERCHANT_ID` | String | `102` | Yes | Numeric merchant ID assigned by PayFast |
| `SECURED_KEY` | String | `zWHjBp2AlttNu1sK` | Yes | Alphanumeric secured key (secret; never expose to client) |
| `BASKET_ID` | String | `BASKET-ABC123` | Yes | Merchant's order/invoice identifier; must be unique per GetAccessToken call |
| `TXNAMT` | String | `1500.00` | Yes | Transaction amount in major units (PKR) with 2 decimal places. Do NOT pass minor units. |
| `CURRENCY_CODE` | String | `PKR` | Yes | Currency code. Currently only `PKR` is supported. |

**HTTP Headers**: Set `User-Agent` to a non-empty string (PayFast rejects empty User-Agent). Suggested: `CURL/PHP PayFast Example` or your app identifier.

**Implementation reference**: `/backend/app/services/payfast/client.py`

---

## GetAccessToken Response

| Field | Type | Example | Notes |
|---|---|---|---|
| `ACCESS_TOKEN` | String | `iK7nN2mP9qL...` | One-time token used in the PostTransaction form. Expires after one use or within a time window (exact TTL not documented). Token is case-sensitive. |

**Response format**: JSON object. Example:
```json
{
  "ACCESS_TOKEN": "iK7nN2mP9qL..."
}
```

**Error response**: Non-2xx HTTP status code. Example: 400, 401, 500. Body may contain error details (not standardized).

**Known failure modes**:
- Merchant account not activated by PayFast → may return NullReferenceException (malformed JSON response).
- Invalid MERCHANT_ID or SECURED_KEY → 401.
- CURRENCY_CODE missing or invalid → 400.

---

## PostTransaction Form Fields (Hosted Checkout)

User's browser POSTs this form to `{base_url}/Ecommerce/api/Transaction/PostTransaction`. All fields are case-sensitive. PayFast's checkout page uses these fields to identify the transaction and route IPN responses.

| Field | Type | Example | Required? | Notes |
|---|---|---|---|---|
| `CURRENCY_CODE` | String | `PKR` | Yes | Must match GetAccessToken request. |
| `MERCHANT_ID` | String | `102` | Yes | Same merchant ID as GetAccessToken. |
| `MERCHANT_NAME` | String | `PayFast Subscriptions` | Yes | Display name shown to customer during checkout. PayFast docs use `Merchant_Name` in older samples; use `MERCHANT_NAME` (all caps). |
| `TOKEN` | String | `iK7nN2mP9qL...` | Yes | Access token returned by GetAccessToken. |
| `BASKET_ID` | String | `BASKET-ABC123` | Yes | Same basket_id as GetAccessToken request. Must be unique; used as correlation key in IPN. |
| `TXNAMT` | String | `1500.00` | Yes | Same transaction amount (major units, 2 dp) as GetAccessToken. Must match for security. |
| `ORDER_DATE` | String | `2026-04-21 14:30:00` | Yes | Date/time when order was created. Format: `YYYY-MM-DD HH:MM:SS` (UTC recommended). Not validated strictly, but must be a valid datetime. |
| `SUCCESS_URL` | String | `https://example.com/checkout/success` | Yes | Browser redirect URL after successful payment. Merchant endpoint; receives GET request with query params (basket_id, txn_id, status). Non-authoritative (may not fire if user closes browser). |
| `FAILURE_URL` | String | `https://example.com/checkout/failure` | Yes | Browser redirect URL after failed/cancelled payment. GET request. |
| `CHECKOUT_URL` | String | `https://example.com/webhooks/payfast` | Yes | Server-to-server IPN endpoint. PayFast POSTs here (not browser redirect). Must be HTTPS and publicly reachable. Authentication via `validation_hash` in body. |
| `CUSTOMER_EMAIL_ADDRESS` | String | `user@example.com` | Yes | Customer's email. Used for PayFast notifications (not your transactional emails). |
| `CUSTOMER_MOBILE_NO` | String | `03001234567` | No | Customer's phone number. Format: Pakistani +92 format without +, e.g., `03001234567`. If blank, pass empty string. |
| `SIGNATURE` | String | `abc123-BASKET-ABC123` | Yes | Merchant-chosen correlation tag (not cryptographic). PayFast ignores the value; use for your own audit trail. Suggestion: `{random_hex}-{basket_id}`. |
| `VERSION` | String | `MERCHANTCART-0.1` | Yes | Protocol version. Must be exactly `MERCHANTCART-0.1` (no dashes in the word "MERCHANT"). Older docs may show `MERCHANT-CART-0.1` — use the no-dash version. |
| `TXNDESC` | String | `Invoice #5 - Monthly Plan` | No | Transaction description (receipt line item). Shown to customer. |
| `PROCCODE` | String | `00` | Yes | Processing code. Always `00` for standard e-commerce. |
| `TRAN_TYPE` | String | `ECOMM_PURCHASE` | Yes | Transaction type. Must be `ECOMM_PURCHASE` (exact spelling, with underscore). |
| `STORE_ID` | String | ` ` | No | Optional store/terminal identifier. Pass empty string if not used. |
| `RECURRING_TXN` | String | `TRUE` or ` ` | No | Create a recurring/subscription token? `TRUE` to enable, empty string to disable. PayFast does not yet support MIT on these tokens, but field is parsed. |

**Optional fields in PayFast's payment.php sample (not used in this starter)**:
- `MERCHANT_USERAGENT` — Browser user agent string (optional; PayFast's sample includes it).
- `ITEMS[*][SKU]`, `ITEMS[*][NAME]`, `ITEMS[*][PRICE]`, `ITEMS[*][QTY]` — Line item breakdown (optional; used for receipt display). This starter aggregates to a single `TXNDESC` instead.

**Implementation reference**: `/backend/app/services/payfast/payload.py`

---

## IPN (Instant Payment Notification) Payload

PayFast POSTs this to your `CHECKOUT_URL` after transaction completion. Body can be `application/x-www-form-urlencoded` or `application/json`. All field names are lowercase with underscores.

### Core Fields (Always Present)

| Field | Type | Example | Notes |
|---|---|---|---|
| `err_code` | String | `000` | Status code. `000` = success. Other values indicate failure (see Error Codes table). |
| `err_msg` | String | `Transaction has been completed.` | Human-readable message. |
| `basket_id` | String | `BASKET-ABC123` | Matches POST request. Used to look up invoice. |
| `order_date` | String | `2026-04-21` | Date (YYYY-MM-DD format) from POST request. |
| `transaction_id` | String | `271d23dd-8aa2-a25b-c1ea-bccbf6dae1b7` | Unique transaction ID assigned by PayFast. Used for idempotency. UUID format. |
| `validation_hash` | String | `ef7295c23baf7cc3cc89808b347db33f7ea9a457a481e14a15d18dfd6481c648` | SHA-256 hash for IPN authentication (see Validation Hash section). |

### Transaction Amount Fields

| Field | Type | Example | Notes |
|---|---|---|---|
| `transaction_amount` | String | `3.98` | Amount charged to customer (major units, 2 dp). |
| `merchant_amount` | String | `2.00` | Amount credited to merchant after PayFast fees (major units, 2 dp). |
| `transaction_currency` | String | `PKR` | Currency code. |
| `discounted_amount` | String | `0` | Discount applied (if any). |

### Payment Instrument Fields

| Field | Type | Example | Notes |
|---|---|---|---|
| `PaymentName` | String | `Card` | Payment method. Possible values: `Card`, `Account` (bank account), `Wallet` (mobile wallet), etc. |
| `masked_pan` | String | `0300XXX8180` | Masked card/account number (last 4 digits visible). |
| `issuer_name` | String | `N/A` | Bank/issuer name if available. |
| `is_international` | String | `false` | Boolean (as string). `true` if card is international. |

### Customer Fields

| Field | Type | Example | Notes |
|---|---|---|---|
| `email_address` | String | `user@example.com` or `null` | Customer email (may be null). |
| `mobile_no` | String | `03008888180` or `` | Customer phone (may be empty string). |
| `customer_id` | String | `` | Customer identifier (often blank). |

### Recurring / Token Fields

| Field | Type | Example | Notes |
|---|---|---|---|
| `recurring_txn` | String | `false` | Boolean (as string). `true` if merchant requested token. |
| `Instrument_token` | String | (varies) | Token for future charges if `recurring_txn=true`. Format undocumented; not yet used by this starter. |

### Additional / Metadata Fields

| Field | Type | Example | Notes |
|---|---|---|---|
| `bill_number` | String | `N/A` | Bill number (may be N/A). |
| `additional_value` | String | `null` | Extra metadata (typically null). |
| `Response_Key` / `responseKey` | String | `F76B273E064D2E0CF280DA76005EBFB9` | Alternate response identifier (appears in both cases in the docs; same value). |
| `rdv_message_key` | String | `N/A` | Message key (typically N/A). |

**Implementation reference**: `/backend/app/routers/webhooks_payfast.py` (parsing), `/backend/app/services/payfast/signature.py` (validation)

---

## Validation Hash Computation

IPN authentication: compute a SHA-256 hash and compare it to the `validation_hash` field in the IPN body.

**Formula**:
```
validation_hash = SHA256(basket_id | secured_key | merchant_id | err_code)
```

**Components** (in exact order):
1. `basket_id` — from IPN payload
2. `|` — literal pipe character
3. `secured_key` — your PAYFAST_SECURED_KEY (same secret used in GetAccessToken)
4. `|` — literal pipe character
5. `merchant_id` — your PAYFAST_MERCHANT_ID
6. `|` — literal pipe character
7. `err_code` — from IPN payload (e.g., "000" for success)

**Worked Example**:
```
basket_id = "BAS-01"
secured_key = "jdnkaabcks"
merchant_id = "102"
err_code = "000"

Raw string: "BAS-01|jdnkaabcks|102|000"
SHA-256:    e8192a7554dd699975adf39619c703a492392edf5e416a61e183866ecdf6a2a2
```

**Verification**:
1. Extract `validation_hash` from IPN body.
2. Extract `basket_id`, `err_code` from IPN body.
3. Compute expected hash using your `secured_key` and `merchant_id`.
4. Compare using constant-time comparison (not `==`, use `hmac.compare_digest` or equivalent).
5. If mismatch → reject IPN as fraudulent (HTTP 403).

**Implementation reference**: `/backend/app/services/payfast/signature.py`

---

## Error Codes

PayFast returns error codes in the `err_code` field of both API responses and IPN payloads. Only `000` indicates success; all others are failures.

| err_code | Meaning | Customer-Facing Message |
|---|---|---|
| `000` | Success | Transaction has been completed. |
| `13` | Card expired | You have entered an Expired Card. |
| `14` | Incorrect PIN | You have entered an Incorrect PIN. |
| `15` | Inactive card | You have entered an Inactive Card number. |
| `21` | Invalid amount | You have entered an Invalid Amount. |
| `41` | Mismatched details | Your entered details are Mismatched. |
| `42` | Invalid CNIC | You have entered an Invalid CNIC. |
| `75` | Max PIN retries exceeded | Maximum PIN Retries has been Exceeded. |
| `126` | Card expired | Your Card has Expired. |
| `423` | Cannot process | We are unable to process your request at the moment; please try again later. |

**Note**: The full error code space is not exhaustively documented by PayFast. If you receive an unknown `err_code`:
- Treat it as a failure (payment did not complete).
- Log `err_msg` for debugging.
- Do not crash; gracefully degrade.
- Consider re-attempting the payment (via dunning workflow).

---

## 3DS ACS Emulator (UAT Only)

In the UAT environment, PayFast replaces real 3DS (3D Secure) with an interactive chooser after the customer enters card details.

**User will see**:
```
Strong Customer Authentication

[Y] – Approve
[N] – Decline
[U] – Unavailable
[A] – Attempted
[R] – Rejected
```

**Outcomes**:
- **[Y]** → Transaction succeeds, `err_code=000` in IPN.
- **[N]**, **[U]**, **[R]** → Transaction fails, non-zero `err_code` in IPN.
- **[A]** → Attempted (unsure outcome; check IPN).

**To test a successful payment in UAT**: Press `[Y]`.

In Live, real 3DS authentication (OTP via SMS/email/authenticator app) applies.

---

## Test Card

| Card Number | Expiry | CVV | Network | Expected Outcome (UAT) |
|---|---|---|---|---|
| `5123-4500-0000-0008` | `01/39` | `100` | Mastercard | Success (when 3DS is passed with `[Y]`) |

**To use**: Enter this card number in the PayFast checkout page. When prompted by the 3DS emulator, press `[Y]`. The transaction will complete successfully and IPN will contain `err_code=000`.

---

## URL Roles — Confusion Table

Three URLs serve different purposes. Do not confuse them.

| URL Type | Name | Who Calls | When | What Happens | Example |
|---|---|---|---|---|---|
| Browser redirect | `SUCCESS_URL` | User's browser | After user completes checkout (success) | 302 redirect to your success page. Query params: `basket_id`, `txn_id`, `status`. Non-authoritative. | `https://example.com/checkout/success?basket_id=...` |
| Browser redirect | `FAILURE_URL` | User's browser | After user cancels or payment fails | 302 redirect to your failure/cancel page. Non-authoritative. | `https://example.com/checkout/failure` |
| Server webhook | `CHECKOUT_URL` | PayFast server | Immediately after payment (success or fail) | Asynchronous POST (can retry multiple times). Body contains full transaction details + `validation_hash`. Authoritative source of truth. | `https://example.com/webhooks/payfast` (must be HTTPS, publicly reachable) |

**Key insight**: SUCCESS_URL and FAILURE_URL are UX conveniences (show the user a page). CHECKOUT_URL (IPN) is where real payment truth lives. Handle both, but never trust SUCCESS_URL alone for payment confirmation.

---

## Integration Checklist

- [ ] GetAccessToken request includes CURRENCY_CODE.
- [ ] PostTransaction form field order matches PayFast sample (though order should not matter for form POST, tested).
- [ ] ORDER_DATE is formatted as `YYYY-MM-DD HH:MM:SS`.
- [ ] VERSION is exactly `MERCHANTCART-0.1` (no dashes in MERCHANTCART).
- [ ] TRAN_TYPE is exactly `ECOMM_PURCHASE`.
- [ ] PROCCODE is exactly `00`.
- [ ] SIGNATURE is a merchant-chosen string (no validation by PayFast).
- [ ] SUCCESS_URL, FAILURE_URL, CHECKOUT_URL are all different endpoints.
- [ ] CHECKOUT_URL is HTTPS and publicly reachable.
- [ ] IPN handler verifies `validation_hash` using constant-time comparison.
- [ ] IPN handler uses `provider_event_id` (transaction_id or body hash) for deduplication.
- [ ] Error handling gracefully deals with unknown `err_code` values.
- [ ] Test card `5123-4500-0000-0008` works in UAT with `[Y]` 3DS response.
- [ ] Migration path documented for UAT → Live (endpoint, credentials, domain, email backend).
