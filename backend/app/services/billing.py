"""Billing domain logic — pure orchestration, no HTTP, no FastAPI.

All functions take a db session and ORM objects; no raw SQL here.
Callers (routers) handle HTTP concerns (status codes, auth).

Phase 5 TODO: call record_failed_attempt from the renewal cron job
              when a renewal invoice goes past_due.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from dateutil.relativedelta import relativedelta
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.invoice import Invoice, InvoiceStatus
from app.models.payment_attempt import PaymentAttempt, PaymentAttemptStatus
from app.models.plan import Plan, PlanInterval
from app.models.subscription import Subscription, SubscriptionStatus
from app.models.user import User


async def create_subscription(
    db: AsyncSession,
    user: User,
    plan: Plan,
) -> tuple[Subscription, Invoice]:
    """Create a new subscription (trialing) and its first open invoice.

    - Subscription starts in `trialing` status.
    - Invoice due_at = now + plan.trial_days (0 days → due immediately).
    - All writes flushed inside this call; caller must commit the transaction.
    """
    now = datetime.now(tz=timezone.utc)
    due_at = now + timedelta(days=plan.trial_days)

    subscription = Subscription(
        user_id=user.id,
        plan_id=plan.id,
        status=SubscriptionStatus.trialing,
        current_period_start=now,
        # current_period_end will be set on first successful payment
    )
    db.add(subscription)
    await db.flush()  # assign PK

    invoice = Invoice(
        subscription_id=subscription.id,
        amount=plan.amount_minor,
        status=InvoiceStatus.open,
        due_at=due_at,
    )
    db.add(invoice)
    await db.flush()  # trigger server_default for basket_id
    await db.refresh(invoice)

    return subscription, invoice


async def apply_successful_payment(
    db: AsyncSession,
    invoice: Invoice,
    payfast_txn_id: str,
) -> None:
    """Transition an invoice to paid and activate its subscription.

    - Marks invoice as paid, sets paid_at and payfast_txn_id.
    - Loads the parent subscription, sets it active, extends the period.
    - Caller must commit the transaction.
    """
    from sqlalchemy import select  # noqa: PLC0415
    from app.models.subscription import Subscription  # noqa: PLC0415

    now = datetime.now(tz=timezone.utc)

    invoice.status = InvoiceStatus.paid
    invoice.paid_at = now
    invoice.payfast_txn_id = payfast_txn_id
    db.add(invoice)

    result = await db.execute(
        select(Subscription).where(Subscription.id == invoice.subscription_id)
    )
    sub = result.scalar_one()

    sub.status = SubscriptionStatus.active
    extend_subscription_period(sub)
    db.add(sub)

    await db.flush()


def extend_subscription_period(sub: Subscription) -> None:
    """Advance current_period_end by one billing interval (in-place, no DB call).

    For monthly plans: new_end = max(current_period_end, now) + 1 month.
    For yearly plans:  new_end = max(current_period_end, now) + 1 year.

    This function is pure (no DB/async) — callers flush/commit.
    """
    now = datetime.now(tz=timezone.utc)
    base = sub.current_period_end if sub.current_period_end and sub.current_period_end > now else now

    # Load plan interval — sub.plan may be eagerly loaded (lazy="joined" in model).
    interval = sub.plan.interval if sub.plan else PlanInterval.monthly

    if interval == PlanInterval.monthly:
        sub.current_period_end = base + relativedelta(months=1)
    else:
        sub.current_period_end = base + relativedelta(years=1)


async def cancel_subscription(
    db: AsyncSession,
    subscription: Subscription,
    at_period_end: bool = True,
) -> Subscription:
    """Cancel a subscription.

    at_period_end=True (default):
        Schedule cancellation for the end of the current billing period.
        Sets cancel_at_period_end=True; status is unchanged. The Phase 5
        renewal cron is responsible for flipping status to `canceled` when
        cancel_at_period_end=True AND current_period_end <= now.

    at_period_end=False:
        Cancel immediately. Sets status=canceled, canceled_at=now,
        current_period_end=now.

    Idempotent — if the subscription is already canceled (or already
    scheduled to be, depending on the flag), this is a no-op and returns
    the subscription as-is. The caller is responsible for committing.
    """
    now = datetime.now(tz=timezone.utc)

    if subscription.status == SubscriptionStatus.canceled:
        # Already terminally canceled — no further mutation.
        return subscription

    if at_period_end:
        # Idempotent: already scheduled? leave as-is.
        if not subscription.cancel_at_period_end:
            subscription.cancel_at_period_end = True
            db.add(subscription)
            await db.flush()
        return subscription

    # Immediate cancel
    subscription.status = SubscriptionStatus.canceled
    subscription.canceled_at = now
    subscription.current_period_end = now
    subscription.cancel_at_period_end = True
    db.add(subscription)
    await db.flush()
    return subscription


async def record_failed_attempt(
    db: AsyncSession,
    invoice: Invoice,
    reason: str,
) -> None:
    """Insert a PaymentAttempt row with status=failed.

    Used by:
    - GET /payfast/cancel handler (user_cancelled).
    - Phase 5 renewal cron (renewal_failed, payment_declined, etc.).
    """
    attempt = PaymentAttempt(
        invoice_id=invoice.id,
        basket_id=invoice.basket_id,
        status=PaymentAttemptStatus.failed,
        raw_response={"reason": reason},
    )
    db.add(attempt)
    await db.flush()
