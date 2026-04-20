"""PayFast IPN (webhook) endpoint — Phase 3 implementation.

Idempotency: uses txn_id from payload as provider_event_id.
             Falls back to SHA-256(raw_body) if txn_id is absent.
             See repositories/webhook_events.py for full strategy doc.

Atomicity:   webhook_event insert + invoice update + subscription update
             all happen inside a single DB transaction (commit at end).
             If any step fails, nothing is persisted.
"""

from __future__ import annotations

import urllib.parse
from typing import Any

from fastapi import APIRouter, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_async_session
from app.repositories import webhook_events as we_repo
from app.repositories import invoices as inv_repo
from app.repositories import subscriptions as sub_repo
from app.services.billing import apply_successful_payment
from app.services.payfast import verify_ipn
from app.config import settings

router = APIRouter(prefix="/webhooks/payfast", tags=["webhooks"])


def _parse_form_body(raw: bytes) -> dict[str, Any]:
    """Parse application/x-www-form-urlencoded body into a dict."""
    try:
        text = raw.decode("utf-8")
        return dict(urllib.parse.parse_qsl(text, keep_blank_values=True))
    except Exception:
        return {}


@router.post("")
async def payfast_ipn(request: Request) -> dict[str, str]:
    """Handle a PayFast IPN notification.

    Flow:
      1. Read raw body (needed for signature verification).
      2. Verify HMAC signature — 403 on failure.
      3. Parse body to extract basket_id, txn_id.
      4. Derive idempotency key; try_insert webhook_event.
         If duplicate → return 200 immediately (no re-processing).
      5. Look up invoice by basket_id.
      6. Apply successful payment (mark invoice paid, activate sub, extend period).
      7. Commit all in one transaction.
    """
    raw_body = await request.body()
    headers = dict(request.headers)

    # 1. Signature verification
    if not verify_ipn(raw_body, headers, settings.PAYFAST_WEBHOOK_SECRET):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="invalid signature",
        )

    # 2. Parse payload
    parsed = _parse_form_body(raw_body)
    basket_id_str = parsed.get("basket_id") or parsed.get("BASKET_ID") or ""
    txn_id = parsed.get("txn_id") or parsed.get("TXNID") or ""

    # 3. Derive idempotency key
    event_id = we_repo.derive_event_id(raw_body, parsed)

    # 4. All DB work in a single transaction
    async for db in get_async_session():
        # Insert webhook event — idempotent
        is_new = await we_repo.try_insert(db, event_id, parsed)
        if not is_new:
            # Duplicate delivery — acknowledge without re-processing
            await db.commit()
            return {"status": "ok"}

        # 5. Look up invoice by basket_id
        import uuid as _uuid  # noqa: PLC0415
        try:
            basket_uuid = _uuid.UUID(basket_id_str)
        except ValueError:
            # Unrecognised basket_id — we already inserted the event for audit;
            # commit and return ok (don't 4xx as PayFast may retry forever).
            await db.commit()
            return {"status": "ok"}

        invoice = await inv_repo.get_by_basket_id(db, basket_uuid)
        if invoice is None:
            await db.commit()
            return {"status": "ok"}

        # 6. Apply payment: marks invoice paid, activates subscription, extends period
        await apply_successful_payment(db, invoice, txn_id or event_id)

        # 7. Commit — all three writes (webhook_event, invoice, subscription) in one TX
        await db.commit()
        return {"status": "ok"}
