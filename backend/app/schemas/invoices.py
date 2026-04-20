"""Pydantic schemas for invoice endpoints."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class InvoiceCheckoutResponse(BaseModel):
    """Response for POST /invoices/{id}/checkout.

    action_url — the PayFast POST_TRANSACTION_PATH endpoint URL.
    fields     — key/value pairs for the hidden form / POST payload.
    """

    action_url: str
    fields: dict[str, str]


class InvoiceOut(BaseModel):
    """Outbound invoice representation (Phase 4).

    Amounts are always in minor units so the frontend can format them
    consistently via `formatAmount(amount_minor)`. Currency is duplicated
    on each invoice for forward-compatibility (future multi-currency plans).
    """

    model_config = ConfigDict(from_attributes=True)

    id: int
    basket_id: str
    subscription_id: int
    amount_minor: int
    currency: str
    status: str
    due_at: datetime | None = None
    paid_at: datetime | None = None
    created_at: datetime
    payfast_txn_id: str | None = None


class InvoiceList(BaseModel):
    """Paginated list response for GET /invoices."""

    items: list[InvoiceOut]
    total: int
