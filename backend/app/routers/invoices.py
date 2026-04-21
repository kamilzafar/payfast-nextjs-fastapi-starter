"""Invoices router — Phase 3/4 implementation."""

from __future__ import annotations

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.users import current_active_user
from app.config import settings
from app.deps import get_db, get_http_client
from app.models.invoice import Invoice, InvoiceStatus
from app.models.user import User
from app.rate_limit import limiter
from app.repositories import invoices as inv_repo
from app.schemas.invoices import InvoiceCheckoutResponse, InvoiceList, InvoiceOut
from app.services.payfast import PayFastError, build_checkout_payload, get_access_token
from app.services.payfast.constants import POST_TRANSACTION_PATH

router = APIRouter(prefix="/invoices", tags=["invoices"])


def _invoice_to_out(inv: Invoice) -> InvoiceOut:
    """Serialize an Invoice ORM row to the frontend-facing shape.

    - `amount` (backend field) -> `amount_minor` (frontend naming)
    - `currency` is hard-coded PKR today (invoice has no currency column
      yet; plans are single-currency). Keeping the key in the response
      makes it safe to introduce per-invoice currency later without a
      contract break.
    """
    return InvoiceOut(
        id=inv.id,
        basket_id=str(inv.basket_id),
        subscription_id=inv.subscription_id,
        amount_minor=inv.amount,
        currency="PKR",
        status=inv.status.value if hasattr(inv.status, "value") else str(inv.status),
        due_at=inv.due_at,
        paid_at=inv.paid_at,
        created_at=inv.created_at,
        payfast_txn_id=inv.payfast_txn_id,
    )


@router.get("", response_model=InvoiceList)
async def list_invoices(
    user: User = Depends(current_active_user),
    db: AsyncSession = Depends(get_db),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> InvoiceList:
    """List the caller's invoices, newest first (paginated)."""
    items, total = await inv_repo.list_for_user(
        db, user.id, limit=limit, offset=offset
    )
    return InvoiceList(
        items=[_invoice_to_out(inv) for inv in items],
        total=total,
    )


@router.post("/{invoice_id}/checkout", response_model=InvoiceCheckoutResponse)
@limiter.limit("10/minute")
async def checkout_invoice(
    request: Request,
    invoice_id: int,
    user: User = Depends(current_active_user),
    db: AsyncSession = Depends(get_db),
    http_client: httpx.AsyncClient = Depends(get_http_client),
) -> InvoiceCheckoutResponse:
    """Initiate PayFast hosted checkout for an open invoice.

    - 404 if invoice not found or not owned by user.
    - 409 if invoice is already paid.
    - 502 if PayFast access-token call fails.
    - 200 with { action_url, fields } on success.
    """
    # 1. Load invoice scoped to this user
    invoice = await inv_repo.get_by_id_for_user(db, invoice_id, user.id)
    if invoice is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="invoice not found",
        )

    # 2. Reject already-paid invoices
    if invoice.status == InvoiceStatus.paid:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="already paid",
        )

    # 3. Fetch PayFast access token
    try:
        access_token = await get_access_token(
            merchant_id=settings.PAYFAST_MERCHANT_ID,
            secured_key=settings.PAYFAST_SECURED_KEY,
            amount_minor=invoice.amount,
            basket_id=str(invoice.basket_id),
            currency="PKR",
            base_url=settings.PAYFAST_BASE_URL,
            http_client=http_client,
        )
    except PayFastError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"PayFast error: {exc}",
        ) from exc

    # 4. Build the checkout form payload
    fields = build_checkout_payload(
        invoice=invoice,
        user=user,
        token=access_token.token,
        return_url=settings.PAYFAST_RETURN_URL,
        cancel_url=settings.PAYFAST_CANCEL_URL,
        checkout_url=settings.PAYFAST_CHECKOUT_URL,
        merchant_id=settings.PAYFAST_MERCHANT_ID,
        merchant_name=settings.PAYFAST_MERCHANT_NAME,
    )

    action_url = f"{settings.PAYFAST_BASE_URL}{POST_TRANSACTION_PATH}"

    return InvoiceCheckoutResponse(action_url=action_url, fields=fields)
