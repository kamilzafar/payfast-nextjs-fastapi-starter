"""PayFast IPN (webhook) endpoint.

PayFast POSTs the IPN to the `CHECKOUT_URL` we provide in the checkout form.
Body may be application/x-www-form-urlencoded or application/json per the
Apr 2026 IPN spec. Authentication is via the `validation_hash` field in the
body:

    validation_hash = SHA256(basket_id|secured_key|merchant_id|err_code)

Idempotency: transaction_id from payload is the provider_event_id.
             Falls back to SHA-256(raw_body) if transaction_id is absent.

Atomicity:   webhook_event insert + invoice update + subscription update
             all happen inside a single DB transaction (commit at end).
"""

from __future__ import annotations

import json
import urllib.parse
import uuid as _uuid
from typing import Any

from fastapi import APIRouter, HTTPException, Request, status

from app.db import get_async_session
from app.repositories import webhook_events as we_repo
from app.repositories import invoices as inv_repo
from app.services.billing import apply_successful_payment, record_failed_attempt
from app.services.payfast import verify_ipn
from app.services.payfast.constants import SUCCESS_ERR_CODE
from app.config import settings

router = APIRouter(prefix="/webhooks/payfast", tags=["webhooks"])


def _parse_body(raw: bytes, content_type: str) -> dict[str, Any]:
    """Parse the IPN body. Supports JSON and form-urlencoded."""
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        return {}

    ct = (content_type or "").lower()
    if "application/json" in ct:
        try:
            data = json.loads(text)
            return data if isinstance(data, dict) else {}
        except json.JSONDecodeError:
            return {}

    return dict(urllib.parse.parse_qsl(text, keep_blank_values=True))


@router.post("")
async def payfast_ipn(request: Request) -> dict[str, str]:
    """Handle a PayFast IPN notification.

    Flow:
      1. Read raw body.
      2. Parse (JSON or form) into dict.
      3. verify_ipn(payload, secured_key, merchant_id) — 403 on mismatch.
      4. Derive idempotency key; try_insert webhook_event.
         If duplicate -> 200 immediately.
      5. Look up invoice by basket_id.
      6. If err_code == "000": apply_successful_payment.
         Else: record_failed_attempt with err_msg as reason.
      7. Commit in one transaction.
    """
    raw_body = await request.body()
    parsed = _parse_body(raw_body, request.headers.get("content-type", ""))

    # 1. Signature verification via in-body validation_hash
    if not verify_ipn(
        parsed,
        settings.PAYFAST_SECURED_KEY,
        settings.PAYFAST_MERCHANT_ID,
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="invalid validation_hash",
        )

    basket_id_str = (parsed.get("basket_id") or "").strip()
    err_code = (parsed.get("err_code") or "").strip()
    err_msg = (parsed.get("err_msg") or "").strip()
    transaction_id = (parsed.get("transaction_id") or "").strip()

    # 2. Idempotency
    event_id = we_repo.derive_event_id(raw_body, parsed)

    async for db in get_async_session():
        is_new = await we_repo.try_insert(db, event_id, parsed)
        if not is_new:
            await db.commit()
            return {"status": "ok"}

        # 3. Invoice lookup
        try:
            basket_uuid = _uuid.UUID(basket_id_str)
        except ValueError:
            # Unrecognised basket_id — event is saved for audit; ack.
            await db.commit()
            return {"status": "ok"}

        invoice = await inv_repo.get_by_basket_id(db, basket_uuid)
        if invoice is None:
            await db.commit()
            return {"status": "ok"}

        # 4. Apply success or failure
        if err_code == SUCCESS_ERR_CODE:
            await apply_successful_payment(
                db,
                invoice,
                transaction_id or event_id,
            )
        else:
            await record_failed_attempt(
                db,
                invoice,
                reason=err_msg or f"err_code={err_code}",
            )

        await db.commit()
        return {"status": "ok"}
