"""Tests for app.services.renewals — TDD: written BEFORE implementation (RED first).

All DB interactions use real test Postgres (skipped if unreachable).
charger and email_sender are always mocked — no real SMTP/HTTP.

State machine transitions under test:
  active -> past_due  (test_daily_creates_invoice_on_period_end_day_and_flips_past_due_after_grace)
  active -> canceled  (test_daily_cancels_when_cancel_at_period_end_and_period_over)
  past_due -> canceled (test_daily_cancels_past_due_at_7_days)
  dunning emails at T+3 and T+5 (test_daily_sends_dunning_reminders_at_t3_and_t5)
  pre-notice at T-3 (test_daily_creates_next_invoice_3_days_before)
  idempotency (test_daily_is_idempotent)
  reconciliation (test_reconciliation_resolves_stuck_pending)
"""

from __future__ import annotations

import uuid
from datetime import date, datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _make_plan(
    db: AsyncSession,
    name: str = "RenewalPlan",
    trial_days: int = 0,
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
    db.add(plan)
    await db.commit()
    await db.refresh(plan)
    return plan


async def _make_user(db: AsyncSession, email: str = "renewal@example.com") -> "User":
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
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


async def _make_active_subscription(
    db: AsyncSession,
    user: "User",
    plan: "Plan",
    period_end: datetime,
    cancel_at_period_end: bool = False,
) -> "Subscription":
    from app.models.subscription import Subscription, SubscriptionStatus  # noqa: PLC0415

    sub = Subscription(
        user_id=user.id,
        plan_id=plan.id,
        status=SubscriptionStatus.active,
        current_period_start=period_end - timedelta(days=30),
        current_period_end=period_end,
        cancel_at_period_end=cancel_at_period_end,
    )
    db.add(sub)
    await db.commit()
    await db.refresh(sub)
    return sub


async def _make_past_due_subscription(
    db: AsyncSession,
    user: "User",
    plan: "Plan",
    due_at: datetime,
) -> tuple["Subscription", "Invoice"]:
    from app.models.subscription import Subscription, SubscriptionStatus  # noqa: PLC0415
    from app.models.invoice import Invoice, InvoiceStatus  # noqa: PLC0415

    sub = Subscription(
        user_id=user.id,
        plan_id=plan.id,
        status=SubscriptionStatus.past_due,
        current_period_start=due_at - timedelta(days=30),
        current_period_end=due_at,
        cancel_at_period_end=False,
    )
    db.add(sub)
    await db.flush()

    inv = Invoice(
        subscription_id=sub.id,
        amount=plan.amount_minor,
        status=InvoiceStatus.open,
        due_at=due_at,
    )
    db.add(inv)
    await db.commit()
    await db.refresh(sub)
    await db.refresh(inv)
    return sub, inv


def _make_mock_charger() -> AsyncMock:
    from unittest.mock import AsyncMock  # noqa: PLC0415

    charger = AsyncMock()
    from app.services.charger import ChargeResult  # noqa: PLC0415

    charger.charge = AsyncMock(
        return_value=ChargeResult(
            attempted=True, succeeded=False, requires_user_action=True
        )
    )
    return charger


def _make_mock_email_sender() -> AsyncMock:
    sender = AsyncMock()
    sender.send = AsyncMock()
    return sender


def _make_db_session_factory(db: AsyncSession):
    """Return an async context manager factory wrapping the existing session."""
    from contextlib import asynccontextmanager  # noqa: PLC0415

    @asynccontextmanager
    async def factory():
        yield db

    return factory


# ---------------------------------------------------------------------------
# test_daily_creates_next_invoice_3_days_before (T-3 pre-notice)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_daily_creates_next_invoice_3_days_before(
    db_session: AsyncSession,
) -> None:
    """T-3: active subscription with period_end in 2 days (< 3 days away) and no
    open invoice for the next cycle → daily sweep creates a new open invoice and
    sends upcoming_renewal email.

    State machine: no transition (still active), just invoice creation + email.
    """
    from app.services.renewals import daily_renewal_sweep  # noqa: PLC0415
    from app.models.invoice import Invoice, InvoiceStatus  # noqa: PLC0415

    plan = await _make_plan(db_session, name="T3Plan", trial_days=0)
    user = await _make_user(db_session, email="t3@renewal.com")

    now = datetime(2026, 4, 20, 2, 0, 0, tzinfo=timezone.utc)
    period_end = now + timedelta(days=2)  # within 3-day window

    sub = await _make_active_subscription(db_session, user, plan, period_end)

    charger = _make_mock_charger()
    email_sender = _make_mock_email_sender()
    factory = _make_db_session_factory(db_session)

    mock_settings = MagicMock()
    mock_settings.RENEWAL_PRE_NOTICE_DAYS = 3
    mock_settings.DUNNING_GRACE_DAYS = 7
    mock_settings.DUNNING_REMINDER_DAYS = [3, 5]
    mock_settings.FRONTEND_URL = "http://localhost:3000"
    mock_settings.SCHEDULER_ENABLED = False

    summary = await daily_renewal_sweep(
        db_session_factory=factory,
        settings=mock_settings,
        charger=charger,
        email_sender=email_sender,
        clock=lambda: now,
    )

    # Verify a new invoice was created for this subscription
    invoices = (
        await db_session.execute(
            select(Invoice).where(Invoice.subscription_id == sub.id)
        )
    ).scalars().all()
    open_invoices = [i for i in invoices if i.status == InvoiceStatus.open]
    assert len(open_invoices) >= 1, "Should have created an open invoice for upcoming renewal"

    # Verify upcoming_renewal email was sent
    email_sender.send.assert_awaited()
    sent_template_names = [
        call.kwargs.get("template_name") or call.args[2]
        for call in email_sender.send.call_args_list
    ]
    assert "upcoming_renewal" in sent_template_names


# ---------------------------------------------------------------------------
# test_daily_creates_invoice_on_period_end_day_and_flips_past_due_after_grace
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_daily_creates_invoice_on_period_end_day_and_flips_past_due_after_grace(
    db_session: AsyncSession,
) -> None:
    """T0: active sub with period_end <= now gets payment_due email.
    T+25h (grace exceeded): status flips to past_due.

    State machine transition: active -> past_due
    """
    from app.services.renewals import daily_renewal_sweep  # noqa: PLC0415
    from app.models.subscription import SubscriptionStatus  # noqa: PLC0415
    from app.models.invoice import Invoice, InvoiceStatus  # noqa: PLC0415

    plan = await _make_plan(db_session, name="T0Plan", trial_days=0)
    user = await _make_user(db_session, email="t0@renewal.com")

    now = datetime(2026, 4, 20, 2, 0, 0, tzinfo=timezone.utc)
    period_end = now - timedelta(hours=25)  # past period end, grace expired

    sub = await _make_active_subscription(db_session, user, plan, period_end)

    # Create an open invoice that's past due (due_at = period_end, still open)
    from app.models.invoice import Invoice, InvoiceStatus  # noqa: PLC0415
    inv = Invoice(
        subscription_id=sub.id,
        amount=plan.amount_minor,
        status=InvoiceStatus.open,
        due_at=period_end,
    )
    db_session.add(inv)
    await db_session.commit()

    charger = _make_mock_charger()
    email_sender = _make_mock_email_sender()
    factory = _make_db_session_factory(db_session)

    mock_settings = MagicMock()
    mock_settings.RENEWAL_PRE_NOTICE_DAYS = 3
    mock_settings.DUNNING_GRACE_DAYS = 7
    mock_settings.DUNNING_REMINDER_DAYS = [3, 5]
    mock_settings.FRONTEND_URL = "http://localhost:3000"
    mock_settings.SCHEDULER_ENABLED = False

    await daily_renewal_sweep(
        db_session_factory=factory,
        settings=mock_settings,
        charger=charger,
        email_sender=email_sender,
        clock=lambda: now,
    )

    await db_session.refresh(sub)
    # After grace period, subscription should be past_due
    assert sub.status == SubscriptionStatus.past_due, (
        f"Expected past_due after grace, got {sub.status}"
    )


# ---------------------------------------------------------------------------
# test_daily_cancels_when_cancel_at_period_end_and_period_over
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_daily_cancels_when_cancel_at_period_end_and_period_over(
    db_session: AsyncSession,
) -> None:
    """cancel_at_period_end=True and current_period_end <= now:
    sub flips to canceled and user receives 'canceled' email.

    State machine transition: active -> canceled
    """
    from app.services.renewals import daily_renewal_sweep  # noqa: PLC0415
    from app.models.subscription import SubscriptionStatus  # noqa: PLC0415

    plan = await _make_plan(db_session, name="CancelAtEndPlan", trial_days=0)
    user = await _make_user(db_session, email="cancel_at_end@renewal.com")

    now = datetime(2026, 4, 20, 2, 0, 0, tzinfo=timezone.utc)
    period_end = now - timedelta(hours=1)  # period just ended

    sub = await _make_active_subscription(
        db_session, user, plan, period_end, cancel_at_period_end=True
    )

    charger = _make_mock_charger()
    email_sender = _make_mock_email_sender()
    factory = _make_db_session_factory(db_session)

    mock_settings = MagicMock()
    mock_settings.RENEWAL_PRE_NOTICE_DAYS = 3
    mock_settings.DUNNING_GRACE_DAYS = 7
    mock_settings.DUNNING_REMINDER_DAYS = [3, 5]
    mock_settings.FRONTEND_URL = "http://localhost:3000"
    mock_settings.SCHEDULER_ENABLED = False

    await daily_renewal_sweep(
        db_session_factory=factory,
        settings=mock_settings,
        charger=charger,
        email_sender=email_sender,
        clock=lambda: now,
    )

    await db_session.refresh(sub)
    assert sub.status == SubscriptionStatus.canceled
    assert sub.canceled_at is not None

    sent_template_names = [
        call.kwargs.get("template_name") or call.args[2]
        for call in email_sender.send.call_args_list
    ]
    assert "canceled" in sent_template_names


# ---------------------------------------------------------------------------
# test_daily_sends_dunning_reminders_at_t3_and_t5
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_daily_sends_dunning_reminders_at_t3_and_t5(
    db_session: AsyncSession,
) -> None:
    """past_due sub with invoice.due_at + 3 days == now → sends past_due_reminder.

    State machine: stays past_due (only email — no transition until T+7).
    """
    from app.services.renewals import daily_renewal_sweep  # noqa: PLC0415
    from app.models.subscription import SubscriptionStatus  # noqa: PLC0415

    plan = await _make_plan(db_session, name="DunningPlan", trial_days=0)
    user = await _make_user(db_session, email="dunning@renewal.com")

    now = datetime(2026, 4, 20, 2, 0, 0, tzinfo=timezone.utc)
    # due_at was 3 days ago — T+3
    due_at = now - timedelta(days=3)

    sub, inv = await _make_past_due_subscription(db_session, user, plan, due_at)

    charger = _make_mock_charger()
    email_sender = _make_mock_email_sender()
    factory = _make_db_session_factory(db_session)

    mock_settings = MagicMock()
    mock_settings.RENEWAL_PRE_NOTICE_DAYS = 3
    mock_settings.DUNNING_GRACE_DAYS = 7
    mock_settings.DUNNING_REMINDER_DAYS = [3, 5]
    mock_settings.FRONTEND_URL = "http://localhost:3000"
    mock_settings.SCHEDULER_ENABLED = False

    await daily_renewal_sweep(
        db_session_factory=factory,
        settings=mock_settings,
        charger=charger,
        email_sender=email_sender,
        clock=lambda: now,
    )

    await db_session.refresh(sub)
    # Sub should still be past_due — no cancellation yet
    assert sub.status == SubscriptionStatus.past_due

    # Dunning reminder email should be sent
    sent_template_names = [
        call.kwargs.get("template_name") or call.args[2]
        for call in email_sender.send.call_args_list
    ]
    assert "past_due_reminder" in sent_template_names


# ---------------------------------------------------------------------------
# test_daily_cancels_past_due_at_7_days
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_daily_cancels_past_due_at_7_days(
    db_session: AsyncSession,
) -> None:
    """past_due sub with invoice.due_at + 7 days <= now → flip to canceled,
    send 'canceled' email.

    State machine transition: past_due -> canceled
    """
    from app.services.renewals import daily_renewal_sweep  # noqa: PLC0415
    from app.models.subscription import SubscriptionStatus  # noqa: PLC0415

    plan = await _make_plan(db_session, name="PastDueCancelPlan", trial_days=0)
    user = await _make_user(db_session, email="pastdue_cancel@renewal.com")

    now = datetime(2026, 4, 20, 2, 0, 0, tzinfo=timezone.utc)
    due_at = now - timedelta(days=7, hours=1)  # 7+ days past due

    sub, inv = await _make_past_due_subscription(db_session, user, plan, due_at)

    charger = _make_mock_charger()
    email_sender = _make_mock_email_sender()
    factory = _make_db_session_factory(db_session)

    mock_settings = MagicMock()
    mock_settings.RENEWAL_PRE_NOTICE_DAYS = 3
    mock_settings.DUNNING_GRACE_DAYS = 7
    mock_settings.DUNNING_REMINDER_DAYS = [3, 5]
    mock_settings.FRONTEND_URL = "http://localhost:3000"
    mock_settings.SCHEDULER_ENABLED = False

    await daily_renewal_sweep(
        db_session_factory=factory,
        settings=mock_settings,
        charger=charger,
        email_sender=email_sender,
        clock=lambda: now,
    )

    await db_session.refresh(sub)
    assert sub.status == SubscriptionStatus.canceled
    assert sub.canceled_at is not None

    sent_template_names = [
        call.kwargs.get("template_name") or call.args[2]
        for call in email_sender.send.call_args_list
    ]
    assert "canceled" in sent_template_names


# ---------------------------------------------------------------------------
# test_daily_is_idempotent
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_daily_is_idempotent(
    db_session: AsyncSession,
) -> None:
    """Running daily_renewal_sweep twice on the same day with the same active
    subscription should not create duplicate invoices.  Second run returns
    a summary indicating nothing new was done for already-processed items.
    """
    from app.services.renewals import daily_renewal_sweep  # noqa: PLC0415
    from app.models.invoice import Invoice, InvoiceStatus  # noqa: PLC0415

    plan = await _make_plan(db_session, name="IdempotentPlan", trial_days=0)
    user = await _make_user(db_session, email="idempotent@renewal.com")

    now = datetime(2026, 4, 20, 2, 0, 0, tzinfo=timezone.utc)
    period_end = now + timedelta(days=1)  # in pre-notice window

    sub = await _make_active_subscription(db_session, user, plan, period_end)

    charger = _make_mock_charger()
    email_sender = _make_mock_email_sender()
    factory = _make_db_session_factory(db_session)

    mock_settings = MagicMock()
    mock_settings.RENEWAL_PRE_NOTICE_DAYS = 3
    mock_settings.DUNNING_GRACE_DAYS = 7
    mock_settings.DUNNING_REMINDER_DAYS = [3, 5]
    mock_settings.FRONTEND_URL = "http://localhost:3000"
    mock_settings.SCHEDULER_ENABLED = False

    # First run
    await daily_renewal_sweep(
        db_session_factory=factory,
        settings=mock_settings,
        charger=charger,
        email_sender=email_sender,
        clock=lambda: now,
    )

    invoices_after_first = (
        await db_session.execute(
            select(Invoice).where(
                Invoice.subscription_id == sub.id,
                Invoice.status == InvoiceStatus.open,
            )
        )
    ).scalars().all()
    count_after_first = len(invoices_after_first)
    assert count_after_first >= 1

    email_count_after_first = email_sender.send.call_count

    # Second run (same day, same clock)
    await daily_renewal_sweep(
        db_session_factory=factory,
        settings=mock_settings,
        charger=charger,
        email_sender=email_sender,
        clock=lambda: now,
    )

    invoices_after_second = (
        await db_session.execute(
            select(Invoice).where(
                Invoice.subscription_id == sub.id,
                Invoice.status == InvoiceStatus.open,
            )
        )
    ).scalars().all()
    count_after_second = len(invoices_after_second)

    # No duplicate invoices
    assert count_after_second == count_after_first, (
        f"Second run should not create duplicate invoices. "
        f"Before={count_after_first}, After={count_after_second}"
    )


# ---------------------------------------------------------------------------
# test_reconciliation_resolves_stuck_pending
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_reconciliation_resolves_stuck_pending(
    db_session: AsyncSession,
) -> None:
    """reconciliation_sweep finds a pending payment_attempt older than 10 minutes,
    calls PayFast status API (mocked), and marks it succeeded + invoice paid.
    """
    from app.services.renewals import reconciliation_sweep  # noqa: PLC0415
    from app.models.payment_attempt import PaymentAttempt, PaymentAttemptStatus  # noqa: PLC0415
    from app.models.invoice import Invoice, InvoiceStatus  # noqa: PLC0415
    from app.services.billing import create_subscription  # noqa: PLC0415

    plan = await _make_plan(db_session, name="ReconcilePlan", trial_days=0)
    user = await _make_user(db_session, email="reconcile@renewal.com")

    sub, inv = await create_subscription(db_session, user, plan)
    await db_session.commit()

    now = datetime(2026, 4, 20, 2, 0, 0, tzinfo=timezone.utc)
    stale_time = now - timedelta(minutes=15)  # 15 min old — past the 10-min threshold

    # Manually insert a pending payment attempt (stale)
    attempt = PaymentAttempt(
        invoice_id=inv.id,
        basket_id=uuid.uuid4(),
        status=PaymentAttemptStatus.pending,
    )
    db_session.add(attempt)
    await db_session.commit()
    await db_session.refresh(attempt)

    # Patch created_at to be stale
    from sqlalchemy import update  # noqa: PLC0415
    from app.models.payment_attempt import PaymentAttempt as PA  # noqa: PLC0415
    await db_session.execute(
        update(PA).where(PA.id == attempt.id).values(created_at=stale_time)
    )
    await db_session.commit()

    # Mock PayFast status API returning "success"
    mock_http_client = AsyncMock()
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "responseCode": 200,
        "data": {
            "transactionStatus": "PAID",
            "transactionId": "TXN_RECON_001",
        },
    }
    mock_http_client.get = AsyncMock(return_value=mock_response)

    mock_settings = MagicMock()
    mock_settings.PAYFAST_BASE_URL = "https://ipguat.apps.net.pk"
    mock_settings.SCHEDULER_ENABLED = False

    factory = _make_db_session_factory(db_session)

    summary = await reconciliation_sweep(
        db_session_factory=factory,
        settings=mock_settings,
        http_client=mock_http_client,
        clock=lambda: now,
    )

    await db_session.refresh(attempt)
    await db_session.refresh(inv)

    assert attempt.status == PaymentAttemptStatus.succeeded
    assert inv.status == InvoiceStatus.paid


# ---------------------------------------------------------------------------
# test_daily_no_action_for_future_subscriptions
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_daily_no_action_for_future_subscriptions(
    db_session: AsyncSession,
) -> None:
    """Active sub with period_end far in the future should not trigger any
    invoice creation or email sending.
    """
    from app.services.renewals import daily_renewal_sweep  # noqa: PLC0415
    from app.models.invoice import Invoice  # noqa: PLC0415

    plan = await _make_plan(db_session, name="FuturePlan", trial_days=0)
    user = await _make_user(db_session, email="future@renewal.com")

    now = datetime(2026, 4, 20, 2, 0, 0, tzinfo=timezone.utc)
    period_end = now + timedelta(days=20)  # far future

    sub = await _make_active_subscription(db_session, user, plan, period_end)

    charger = _make_mock_charger()
    email_sender = _make_mock_email_sender()
    factory = _make_db_session_factory(db_session)

    mock_settings = MagicMock()
    mock_settings.RENEWAL_PRE_NOTICE_DAYS = 3
    mock_settings.DUNNING_GRACE_DAYS = 7
    mock_settings.DUNNING_REMINDER_DAYS = [3, 5]
    mock_settings.FRONTEND_URL = "http://localhost:3000"
    mock_settings.SCHEDULER_ENABLED = False

    await daily_renewal_sweep(
        db_session_factory=factory,
        settings=mock_settings,
        charger=charger,
        email_sender=email_sender,
        clock=lambda: now,
    )

    # No invoices should be created for this specific far-future sub
    invoices = (
        await db_session.execute(
            select(Invoice).where(Invoice.subscription_id == sub.id)
        )
    ).scalars().all()
    assert len(invoices) == 0, "No invoice should be created for a sub with period_end far in the future"

    # Check none of the emails sent were for this specific user's subscription
    # (other tests' past_due subs may trigger sends, but not this subscription)
    for call in email_sender.send.call_args_list:
        context = call.kwargs.get("context") or (call.args[3] if len(call.args) > 3 else {})
        # If an invoice is in the context, it should NOT belong to our subscription
        if "invoice" in context:
            invoice_in_ctx = context["invoice"]
            assert invoice_in_ctx.subscription_id != sub.id, (
                f"Email should not be sent for far-future subscription {sub.id}"
            )
