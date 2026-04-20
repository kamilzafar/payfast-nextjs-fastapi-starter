"""Subscription repository — DB access helpers."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.subscription import Subscription, SubscriptionStatus


async def get_active_for_user(
    db: AsyncSession, user_id: int
) -> Subscription | None:
    """Return the current active or trialing subscription for a user, or None."""
    result = await db.execute(
        select(Subscription)
        .where(Subscription.user_id == user_id)
        .where(
            Subscription.status.in_(
                [SubscriptionStatus.active, SubscriptionStatus.trialing]
            )
        )
        .limit(1)
    )
    return result.scalar_one_or_none()


async def get_current_for_user(
    db: AsyncSession, user_id: int
) -> Subscription | None:
    """Return the current (non-canceled) subscription for a user, or None.

    Includes statuses: trialing, active, past_due.
    Used by GET /me/subscription — surfaces a past_due sub so the UI can
    prompt the user to pay the overdue invoice.
    """
    result = await db.execute(
        select(Subscription)
        .where(Subscription.user_id == user_id)
        .where(Subscription.status != SubscriptionStatus.canceled)
        .order_by(Subscription.id.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()


async def get_by_id(db: AsyncSession, subscription_id: int) -> Subscription | None:
    """Fetch a subscription by its primary key."""
    result = await db.execute(
        select(Subscription).where(Subscription.id == subscription_id)
    )
    return result.scalar_one_or_none()


async def get_for_user(
    db: AsyncSession, subscription_id: int, user_id: int
) -> Subscription | None:
    """Fetch a subscription by id, scoped to the given user."""
    result = await db.execute(
        select(Subscription)
        .where(Subscription.id == subscription_id)
        .where(Subscription.user_id == user_id)
    )
    return result.scalar_one_or_none()
