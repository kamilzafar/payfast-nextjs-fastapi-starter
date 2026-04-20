"""Tests for app.services.billing domain logic.

TDD: written BEFORE implementation — all should be RED initially.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy.ext.asyncio import AsyncSession


async def _make_plan(
    db_session: AsyncSession,
    name: str = "TestBillingPlan",
    trial_days: int = 7,
    amount_minor: int = 150000,
) -> "Plan":
    from app.models.plan import Plan, PlanInterval  # noqa: PLC0415

    plan = Plan(
        name=name,
        amount_minor=amount_minor,
        currency="PKR",
        interval=PlanInterval.monthly,
        trial_days=trial_days,
        is_active=True,
    )
    db_session.add(plan)
    await db_session.commit()
    await db_session.refresh(plan)
    return plan


async def _make_user(db_session: AsyncSession, email: str = "billing@example.com") -> "User":
    from app.models.user import User  # noqa: PLC0415
    from fastapi_users.password import PasswordHelper  # noqa: PLC0415

    ph = PasswordHelper()
    user = User(
        email=email,
        hashed_password=ph.hash("testpass"),
        is_active=True,
        is_superuser=False,
        is_verified=True,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest.mark.asyncio
async def test_create_subscription_sets_trialing_and_period(
    db_session: AsyncSession,
) -> None:
    """create_subscription sets status=trialing and due_at = now + trial_days."""
    from app.services.billing import create_subscription  # noqa: PLC0415
    from app.models.subscription import SubscriptionStatus  # noqa: PLC0415
    from app.models.invoice import InvoiceStatus  # noqa: PLC0415

    plan = await _make_plan(db_session, name="BillingTrialPlan", trial_days=7)
    user = await _make_user(db_session, email="trial@billing.com")

    sub, inv = await create_subscription(db_session, user, plan)

    assert sub.status == SubscriptionStatus.trialing
    assert sub.plan_id == plan.id
    assert sub.user_id == user.id

    assert inv.status == InvoiceStatus.open
    assert inv.amount == plan.amount_minor
    assert inv.due_at is not None
    # due_at should be approximately now + 7 days
    expected_due = datetime.now(tz=timezone.utc) + timedelta(days=7)
    delta = abs((inv.due_at - expected_due).total_seconds())
    assert delta < 5  # within 5 seconds


@pytest.mark.asyncio
async def test_apply_successful_payment_transitions_state(
    db_session: AsyncSession,
) -> None:
    """apply_successful_payment sets invoice=paid and subscription=active."""
    from app.services.billing import create_subscription, apply_successful_payment  # noqa: PLC0415
    from app.models.subscription import SubscriptionStatus  # noqa: PLC0415
    from app.models.invoice import InvoiceStatus  # noqa: PLC0415

    plan = await _make_plan(db_session, name="BillingPayPlan", trial_days=0)
    user = await _make_user(db_session, email="pay@billing.com")
    sub, inv = await create_subscription(db_session, user, plan)

    await apply_successful_payment(db_session, inv, "TXN_APPLY_001")

    await db_session.refresh(inv)
    await db_session.refresh(sub)

    assert inv.status == InvoiceStatus.paid
    assert inv.payfast_txn_id == "TXN_APPLY_001"
    assert inv.paid_at is not None
    assert sub.status == SubscriptionStatus.active
    assert sub.current_period_end is not None


@pytest.mark.asyncio
async def test_extend_subscription_period_one_month(
    db_session: AsyncSession,
) -> None:
    """extend_subscription_period advances current_period_end by one month."""
    from app.services.billing import create_subscription, extend_subscription_period  # noqa: PLC0415
    from app.models.subscription import Subscription  # noqa: PLC0415

    plan = await _make_plan(db_session, name="BillingExtendPlan", trial_days=0)
    user = await _make_user(db_session, email="extend@billing.com")
    sub, _ = await create_subscription(db_session, user, plan)

    # Set a known future current_period_end (future so max() picks it over now)
    known_start = datetime(2030, 1, 15, tzinfo=timezone.utc)
    sub.current_period_end = known_start
    await db_session.commit()

    extend_subscription_period(sub)

    # Should be 2030-02-15
    assert sub.current_period_end is not None
    assert sub.current_period_end.month == 2
    assert sub.current_period_end.year == 2030
    assert sub.current_period_end.day == 15


@pytest.mark.asyncio
async def test_cancel_subscription_at_period_end_sets_flag(
    db_session: AsyncSession,
) -> None:
    """cancel_subscription(at_period_end=True) flips flag, keeps status."""
    from app.services.billing import create_subscription, cancel_subscription  # noqa: PLC0415
    from app.models.subscription import SubscriptionStatus  # noqa: PLC0415

    plan = await _make_plan(db_session, name="CancelAPEBillingPlan", trial_days=0)
    user = await _make_user(db_session, email="cancel-ape@billing.com")
    sub, _ = await create_subscription(db_session, user, plan)

    result = await cancel_subscription(db_session, sub, at_period_end=True)

    assert result.cancel_at_period_end is True
    # Status unchanged — trialing (cron will flip later)
    assert result.status == SubscriptionStatus.trialing
    assert result.canceled_at is None


@pytest.mark.asyncio
async def test_cancel_subscription_immediate_sets_canceled(
    db_session: AsyncSession,
) -> None:
    """cancel_subscription(at_period_end=False) immediately cancels."""
    from app.services.billing import create_subscription, cancel_subscription  # noqa: PLC0415
    from app.models.subscription import SubscriptionStatus  # noqa: PLC0415

    plan = await _make_plan(db_session, name="CancelImmBillingPlan", trial_days=0)
    user = await _make_user(db_session, email="cancel-imm@billing.com")
    sub, _ = await create_subscription(db_session, user, plan)

    result = await cancel_subscription(db_session, sub, at_period_end=False)

    assert result.status == SubscriptionStatus.canceled
    assert result.canceled_at is not None


@pytest.mark.asyncio
async def test_cancel_subscription_idempotent(
    db_session: AsyncSession,
) -> None:
    """Calling cancel twice returns same state — no error."""
    from app.services.billing import create_subscription, cancel_subscription  # noqa: PLC0415

    plan = await _make_plan(db_session, name="CancelIdemBillingPlan", trial_days=0)
    user = await _make_user(db_session, email="cancel-idem@billing.com")
    sub, _ = await create_subscription(db_session, user, plan)

    first = await cancel_subscription(db_session, sub, at_period_end=True)
    first_flag = first.cancel_at_period_end
    first_status = first.status

    second = await cancel_subscription(db_session, sub, at_period_end=True)
    assert second.cancel_at_period_end == first_flag
    assert second.status == first_status


@pytest.mark.asyncio
async def test_record_failed_attempt_inserts_row(
    db_session: AsyncSession,
) -> None:
    """record_failed_attempt inserts a PaymentAttempt with status=failed."""
    from app.services.billing import create_subscription, record_failed_attempt  # noqa: PLC0415
    from app.models.payment_attempt import PaymentAttempt, PaymentAttemptStatus  # noqa: PLC0415
    from sqlalchemy import select  # noqa: PLC0415

    plan = await _make_plan(db_session, name="BillingFailPlan", trial_days=0)
    user = await _make_user(db_session, email="fail@billing.com")
    _, inv = await create_subscription(db_session, user, plan)

    await record_failed_attempt(db_session, inv, reason="user_cancelled")

    attempts = (
        await db_session.execute(
            select(PaymentAttempt).where(PaymentAttempt.invoice_id == inv.id)
        )
    ).scalars().all()
    assert len(attempts) == 1
    assert attempts[0].status == PaymentAttemptStatus.failed
    assert attempts[0].raw_response == {"reason": "user_cancelled"}
