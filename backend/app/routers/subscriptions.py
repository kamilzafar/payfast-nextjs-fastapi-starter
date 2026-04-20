"""Subscriptions router — Phase 3/4 implementation."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.users import current_active_user
from app.deps import get_db
from app.models.plan import Plan
from app.models.user import User
from app.rate_limit import limiter
from app.repositories import subscriptions as sub_repo
from app.schemas.subscriptions import (
    CancelSubscriptionRequest,
    CancelSubscriptionResponse,
    CreateSubscriptionRequest,
    CreateSubscriptionResponse,
    PlanEmbedded,
    SubscriptionOut,
)
from app.services.billing import cancel_subscription, create_subscription

router = APIRouter(prefix="/subscriptions", tags=["subscriptions"])


def _subscription_to_out(sub) -> SubscriptionOut:
    """Serialize a Subscription ORM row (with eager-loaded plan) to SubscriptionOut."""
    plan = sub.plan
    # PlanInterval is a str-Enum → .value yields "monthly"/"yearly"
    interval_val = plan.interval.value if hasattr(plan.interval, "value") else str(plan.interval)
    return SubscriptionOut(
        id=sub.id,
        status=sub.status.value if hasattr(sub.status, "value") else str(sub.status),
        current_period_start=sub.current_period_start,
        current_period_end=sub.current_period_end,
        next_billing_at=sub.next_billing_at,
        canceled_at=sub.canceled_at,
        cancel_at_period_end=sub.cancel_at_period_end,
        plan=PlanEmbedded(
            id=plan.id,
            name=plan.name,
            amount_minor=plan.amount_minor,
            currency=plan.currency,
            interval=interval_val,
            trial_days=plan.trial_days,
        ),
    )


@router.post("", status_code=status.HTTP_201_CREATED, response_model=CreateSubscriptionResponse)
@limiter.limit("5/minute")
async def create_subscription_endpoint(
    request: Request,
    body: CreateSubscriptionRequest,
    user: User = Depends(current_active_user),
    db: AsyncSession = Depends(get_db),
) -> CreateSubscriptionResponse:
    """Create a subscription for the authenticated user.

    - 404 if plan not found or inactive.
    - 409 if user already has an active/trialing subscription.
    - 201 on success with subscription_id, invoice_id, basket_id, checkout_url=null.
    """
    # 1. Resolve plan — reject missing or inactive
    plan_result = await db.execute(select(Plan).where(Plan.id == body.plan_id))
    plan = plan_result.scalar_one_or_none()
    if plan is None or not plan.is_active:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="plan not found",
        )

    # 2. Reject duplicate active/trialing subscription
    existing = await sub_repo.get_active_for_user(db, user.id)
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="already subscribed",
        )

    # 3. Create subscription + invoice atomically
    sub, inv = await create_subscription(db, user, plan)
    await db.commit()

    return CreateSubscriptionResponse(
        subscription_id=sub.id,
        invoice_id=inv.id,
        basket_id=str(inv.basket_id),
        checkout_url=None,
    )


@router.post(
    "/{subscription_id}/cancel",
    response_model=CancelSubscriptionResponse,
)
async def cancel_subscription_endpoint(
    subscription_id: int,
    body: CancelSubscriptionRequest | None = None,
    user: User = Depends(current_active_user),
    db: AsyncSession = Depends(get_db),
) -> SubscriptionOut:
    """Cancel the authenticated user's subscription.

    - 404 if the subscription is not found or not owned by the caller.
    - 200 with the updated subscription on success.
    - Idempotent: cancelling twice returns the same state.
    """
    sub = await sub_repo.get_for_user(db, subscription_id, user.id)
    if sub is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="subscription not found",
        )

    at_period_end = True if body is None else body.at_period_end
    updated = await cancel_subscription(db, sub, at_period_end=at_period_end)
    await db.commit()
    await db.refresh(updated)

    return _subscription_to_out(updated)
