"""Invoice repository — DB access helpers."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.invoice import Invoice, InvoiceStatus
from app.models.subscription import Subscription


async def create(
    db: AsyncSession,
    *,
    subscription_id: int,
    amount_minor: int,
    due_at: datetime | None = None,
) -> Invoice:
    """Create a new open invoice with a fresh basket_id (DB-generated UUID)."""
    invoice = Invoice(
        subscription_id=subscription_id,
        amount=amount_minor,
        status=InvoiceStatus.open,
        due_at=due_at,
    )
    db.add(invoice)
    await db.flush()   # assigns PK and triggers server_default for basket_id
    await db.refresh(invoice)
    return invoice


async def get_by_id_for_user(
    db: AsyncSession, invoice_id: int, user_id: int
) -> Invoice | None:
    """Return an invoice only if the owning subscription belongs to user_id."""
    result = await db.execute(
        select(Invoice)
        .join(Subscription, Invoice.subscription_id == Subscription.id)
        .where(Invoice.id == invoice_id)
        .where(Subscription.user_id == user_id)
    )
    return result.scalar_one_or_none()


async def get_by_basket_id(
    db: AsyncSession, basket_id: uuid.UUID
) -> Invoice | None:
    """Look up an invoice by its UUID basket_id."""
    result = await db.execute(
        select(Invoice).where(Invoice.basket_id == basket_id)
    )
    return result.scalar_one_or_none()


async def list_for_user(
    db: AsyncSession,
    user_id: int,
    *,
    limit: int = 20,
    offset: int = 0,
) -> tuple[list[Invoice], int]:
    """Return (items, total) for the caller's invoices, newest first.

    Joins invoices -> subscriptions to filter by ownership. Total is a
    separate COUNT so the frontend can build pagination controls without
    running the paginated query to completion.
    """
    base_q = (
        select(Invoice)
        .join(Subscription, Invoice.subscription_id == Subscription.id)
        .where(Subscription.user_id == user_id)
    )

    count_q = (
        select(func.count(Invoice.id))
        .join(Subscription, Invoice.subscription_id == Subscription.id)
        .where(Subscription.user_id == user_id)
    )

    items_result = await db.execute(
        base_q.order_by(Invoice.id.desc()).limit(limit).offset(offset)
    )
    count_result = await db.execute(count_q)

    items = list(items_result.scalars().all())
    total = int(count_result.scalar_one())
    return items, total
