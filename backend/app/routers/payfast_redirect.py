"""PayFast return/cancel redirect handlers — Phase 3 implementation.

These endpoints handle the user's browser being redirected back from
PayFast's hosted checkout page.  They are NOT authoritative on payment
status — real payment truth comes via IPN (POST /webhooks/payfast).

GET /payfast/return  — user completed the checkout flow (may still be pending)
GET /payfast/cancel  — user cancelled / pressed back on the PayFast page
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Query
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.deps import get_db
from app.repositories import invoices as inv_repo
from app.services.billing import record_failed_attempt

router = APIRouter(prefix="/payfast", tags=["payfast"])


@router.get("/return")
async def handle_return(
    basket_id: str | None = Query(default=None),
    txn_id: str | None = Query(default=None),
    status: str | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
) -> RedirectResponse:
    """Redirect user back to frontend after PayFast checkout.

    Does NOT trust the return-URL payload as authoritative — real payment
    confirmation comes via IPN.  Just passes the query params to the
    frontend so it can show a reassuring UI.

    basket_id invalid / missing → 302 to /checkout/cancel?reason=invalid
    basket_id valid → 302 to /checkout/success?basket_id=...&txn_id=...&status=...
    """
    if not basket_id:
        return RedirectResponse(
            url=f"{settings.FRONTEND_URL}/checkout/cancel?reason=invalid",
            status_code=302,
        )

    # Validate basket_id is a UUID
    try:
        basket_uuid = uuid.UUID(basket_id)
    except ValueError:
        return RedirectResponse(
            url=f"{settings.FRONTEND_URL}/checkout/cancel?reason=invalid",
            status_code=302,
        )

    # Build success redirect URL with all available params
    params = f"basket_id={basket_id}"
    if txn_id:
        params += f"&txn_id={txn_id}"
    if status:
        params += f"&status={status}"

    return RedirectResponse(
        url=f"{settings.FRONTEND_URL}/checkout/success?{params}",
        status_code=302,
    )


@router.get("/cancel")
async def handle_cancel(
    basket_id: str | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
) -> RedirectResponse:
    """Handle user cancellation from the PayFast hosted page.

    If basket_id is valid and an invoice is found:
      - Insert a PaymentAttempt with status=failed, reason=user_cancelled.

    Always 302 to FRONTEND_URL/checkout/cancel.
    """
    if basket_id:
        try:
            basket_uuid = uuid.UUID(basket_id)
            invoice = await inv_repo.get_by_basket_id(db, basket_uuid)
            if invoice is not None:
                await record_failed_attempt(db, invoice, reason="user_cancelled")
                await db.commit()
        except (ValueError, Exception):
            # Invalid UUID or DB error — still redirect cleanly
            pass

    return RedirectResponse(
        url=f"{settings.FRONTEND_URL}/checkout/cancel",
        status_code=302,
    )
