"""Renewal cron job bodies — Phase 5.

Three async job functions consumed by the APScheduler wiring in workers/scheduler.py:

  daily_renewal_sweep    — 02:00 daily
  reconciliation_sweep   — every 15 minutes
  hourly_dunning_check   — every hour

All functions:
  - Accept dependency-injected clock, db_session_factory, charger, email_sender
    so they are pure / testable without global state.
  - Are idempotent: re-running on the same day/minute is safe.
  - Return a summary dict describing what was done (useful for logging).

-------------------------------------------------------------------------------
STATE MACHINE TRANSITIONS
-------------------------------------------------------------------------------

  trialing  -> active     (first payment succeeds — webhook handles; cron is passive)
  active    -> past_due   (open invoice with due_at + 24h has elapsed, still unpaid)
  active    -> canceled   (cancel_at_period_end=True and current_period_end <= now)
  past_due  -> active     (payment succeeds — webhook handles; cron sends dunning only)
  past_due  -> canceled   (7 days since due_at and still no payment)

-------------------------------------------------------------------------------
INFER past_due_since
-------------------------------------------------------------------------------

We do NOT add a separate `past_due_since` column to subscriptions.
Instead we infer it from the latest open invoice's `due_at`.  The elapsed
dunning days = (now - invoice.due_at).days.  This is sufficient because:
  - We only have one open invoice per renewal cycle.
  - The invoice.due_at is set at creation time (= subscription.current_period_end).
  - The daily sweep checks elapsed days against DUNNING_REMINDER_DAYS and
    DUNNING_GRACE_DAYS to decide what action to take.

-------------------------------------------------------------------------------
IDEMPOTENCY
-------------------------------------------------------------------------------

Pre-notice invoice creation: guarded by checking whether an open invoice
already exists for the subscription (subscription_id + status=open).  If one
already exists, no second invoice is created.

Dunning emails at T+3 / T+5: guarded by checking elapsed days using the
clock parameter — only exact matches trigger a send, so hourly reruns are safe.
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from datetime import date, datetime, timedelta, timezone
from typing import Any, Callable

import structlog
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.invoice import Invoice, InvoiceStatus
from app.models.payment_attempt import PaymentAttempt, PaymentAttemptStatus
from app.models.subscription import Subscription, SubscriptionStatus

log = structlog.get_logger(__name__)


# ---------------------------------------------------------------------------
# daily_renewal_sweep
# ---------------------------------------------------------------------------


async def daily_renewal_sweep(
    db_session_factory: Any,
    settings: Any,
    charger: Any,
    email_sender: Any,
    clock: Callable[[], datetime] = datetime.utcnow,
) -> dict[str, int]:
    """Run all dunning/renewal logic for today.

    Steps:
    1. Pre-notice (T-RENEWAL_PRE_NOTICE_DAYS): active subs approaching renewal
       with no existing open invoice → create invoice + send upcoming_renewal email.
    2. Cancel-at-period-end: active subs with cancel_at_period_end=True and
       current_period_end <= now → flip to canceled + send canceled email.
    3. Grace-period flip: active subs with an open invoice past due by > 24h
       → flip status to past_due.
    4. Dunning reminders: past_due subs at T+3 and T+5 → send past_due_reminder.
    5. Cancellation at T+7: past_due subs with invoice.due_at + DUNNING_GRACE_DAYS
       <= now → flip to canceled + send canceled email.

    Returns a summary dict with counts of each action taken.
    """
    now = clock()
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)

    summary = {
        "pre_notice_invoices_created": 0,
        "cancel_at_period_end_canceled": 0,
        "flipped_to_past_due": 0,
        "dunning_reminders_sent": 0,
        "past_due_canceled": 0,
    }

    pre_notice_horizon = now + timedelta(days=settings.RENEWAL_PRE_NOTICE_DAYS)

    async with db_session_factory() as db:

        # -----------------------------------------------------------------
        # Step 1: Pre-notice — active subs with period_end within notice window
        # -----------------------------------------------------------------
        active_approaching = (
            await db.execute(
                select(Subscription).where(
                    and_(
                        Subscription.status == SubscriptionStatus.active,
                        Subscription.current_period_end <= pre_notice_horizon,
                        Subscription.current_period_end > now,
                        Subscription.cancel_at_period_end.is_(False),
                    )
                )
            )
        ).scalars().all()

        for sub in active_approaching:
            # Check if an open invoice already exists for this sub (idempotency)
            existing = (
                await db.execute(
                    select(Invoice).where(
                        and_(
                            Invoice.subscription_id == sub.id,
                            Invoice.status == InvoiceStatus.open,
                        )
                    )
                )
            ).scalars().first()

            if existing is not None:
                continue  # already has an open invoice — idempotent skip

            # Fetch user separately (lazy relationship may not be loaded)
            from app.models.user import User  # noqa: PLC0415
            user = await db.get(User, sub.user_id)

            invoice = Invoice(
                subscription_id=sub.id,
                amount=sub.plan.amount_minor,
                status=InvoiceStatus.open,
                due_at=sub.current_period_end,
            )
            db.add(invoice)
            await db.flush()
            await db.refresh(invoice)

            await email_sender.send(
                to=user.email,
                subject=f"Your {sub.plan.name} subscription renews soon",
                template_name="upcoming_renewal",
                context={
                    "user": user,
                    "plan": sub.plan,
                    "invoice": invoice,
                    "pay_url": f"{settings.FRONTEND_URL}/checkout/{invoice.id}",
                    "due_at": sub.current_period_end,
                },
            )
            summary["pre_notice_invoices_created"] += 1

        # -----------------------------------------------------------------
        # Step 2: cancel_at_period_end — period has expired
        # -----------------------------------------------------------------
        cancel_at_end_subs = (
            await db.execute(
                select(Subscription).where(
                    and_(
                        Subscription.status == SubscriptionStatus.active,
                        Subscription.cancel_at_period_end.is_(True),
                        Subscription.current_period_end <= now,
                    )
                )
            )
        ).scalars().all()

        for sub in cancel_at_end_subs:
            from app.models.user import User  # noqa: PLC0415
            user = await db.get(User, sub.user_id)

            sub.status = SubscriptionStatus.canceled
            sub.canceled_at = now
            db.add(sub)

            await email_sender.send(
                to=user.email,
                subject=f"Your {sub.plan.name} subscription has ended",
                template_name="canceled",
                context={
                    "user": user,
                    "plan": sub.plan,
                    "period_end": sub.current_period_end,
                },
            )
            summary["cancel_at_period_end_canceled"] += 1

        # -----------------------------------------------------------------
        # Step 3: active subs with past-due open invoice → flip to past_due
        #         Grace period: 24h after due_at before we flip
        # -----------------------------------------------------------------
        grace_cutoff = now - timedelta(hours=24)

        active_overdue_invoices = (
            await db.execute(
                select(Invoice).join(
                    Subscription, Invoice.subscription_id == Subscription.id
                ).where(
                    and_(
                        Subscription.status == SubscriptionStatus.active,
                        Invoice.status == InvoiceStatus.open,
                        Invoice.due_at <= grace_cutoff,
                    )
                )
            )
        ).scalars().all()

        for invoice in active_overdue_invoices:
            sub = await db.get(Subscription, invoice.subscription_id)
            if sub is None or sub.status != SubscriptionStatus.active:
                continue
            sub.status = SubscriptionStatus.past_due
            db.add(sub)
            summary["flipped_to_past_due"] += 1

        # -----------------------------------------------------------------
        # Step 4 & 5: past_due subs — dunning reminders and cancellations
        # -----------------------------------------------------------------
        past_due_subs = (
            await db.execute(
                select(Subscription).where(
                    Subscription.status == SubscriptionStatus.past_due
                )
            )
        ).scalars().all()

        for sub in past_due_subs:
            # Find the latest open invoice to infer past_due_since
            open_invoice = (
                await db.execute(
                    select(Invoice).where(
                        and_(
                            Invoice.subscription_id == sub.id,
                            Invoice.status == InvoiceStatus.open,
                        )
                    ).order_by(Invoice.due_at.asc())
                )
            ).scalars().first()

            if open_invoice is None or open_invoice.due_at is None:
                continue

            due_at = open_invoice.due_at
            if due_at.tzinfo is None:
                due_at = due_at.replace(tzinfo=timezone.utc)

            elapsed_days = (now - due_at).days

            from app.models.user import User  # noqa: PLC0415
            user = await db.get(User, sub.user_id)

            pay_url = f"{settings.FRONTEND_URL}/checkout/{open_invoice.id}"

            # Step 5: T+GRACE_DAYS → cancel
            if elapsed_days >= settings.DUNNING_GRACE_DAYS:
                sub.status = SubscriptionStatus.canceled
                sub.canceled_at = now
                db.add(sub)

                await email_sender.send(
                    to=user.email,
                    subject=f"Your {sub.plan.name} subscription has been canceled",
                    template_name="canceled",
                    context={
                        "user": user,
                        "plan": sub.plan,
                        "invoice": open_invoice,
                        "period_end": sub.current_period_end,
                    },
                )
                summary["past_due_canceled"] += 1

            # Step 4: Dunning reminders at T+3, T+5 (or any configured days)
            elif elapsed_days in settings.DUNNING_REMINDER_DAYS:
                remaining_days = settings.DUNNING_GRACE_DAYS - elapsed_days

                await email_sender.send(
                    to=user.email,
                    subject=f"Reminder: Your {sub.plan.name} subscription is past due",
                    template_name="past_due_reminder",
                    context={
                        "user": user,
                        "plan": sub.plan,
                        "invoice": open_invoice,
                        "pay_url": pay_url,
                        "remaining_days": remaining_days,
                        "elapsed_days": elapsed_days,
                    },
                )
                summary["dunning_reminders_sent"] += 1

        await db.commit()

    log.info("daily_renewal_sweep.complete", now=now.isoformat(), **summary)
    return summary


# ---------------------------------------------------------------------------
# reconciliation_sweep
# ---------------------------------------------------------------------------


async def reconciliation_sweep(
    db_session_factory: Any,
    settings: Any,
    http_client: Any,
    clock: Callable[[], datetime] = datetime.utcnow,
) -> dict[str, int]:
    """Every 15 minutes: find stale pending payment_attempts and resolve them.

    For each pending attempt older than 10 minutes:
      - Call PayFast's status API.
        TODO: Confirm exact endpoint path — currently using
              /Ecommerce/api/Transaction/GetTransactionStatus
              (path uncertain; update when confirmed with PayFast docs).
      - If response indicates PAID: call billing.apply_successful_payment.
      - If response indicates failed/expired: call billing.record_failed_attempt.
      - If API is inconclusive: leave as pending (will be retried next run).

    Idempotent: the 10-minute staleness window means fresh attempts are left
    alone, so re-running within the same minute window is safe.
    """
    now = clock()
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)

    stale_cutoff = now - timedelta(minutes=10)

    summary = {
        "resolved_succeeded": 0,
        "resolved_failed": 0,
        "skipped_inconclusive": 0,
    }

    async with db_session_factory() as db:
        stale_attempts = (
            await db.execute(
                select(PaymentAttempt).where(
                    and_(
                        PaymentAttempt.status == PaymentAttemptStatus.pending,
                        PaymentAttempt.created_at <= stale_cutoff,
                    )
                )
            )
        ).scalars().all()

        for attempt in stale_attempts:
            invoice = await db.get(Invoice, attempt.invoice_id)
            if invoice is None:
                continue

            # TODO: Confirm exact PayFast transaction status endpoint.
            #       Path /Ecommerce/api/Transaction/GetTransactionStatus is
            #       inferred from PayFast docs — verify with live credentials.
            status_url = (
                f"{settings.PAYFAST_BASE_URL}"
                f"/Ecommerce/api/Transaction/GetTransactionStatus"
                f"?basket_id={attempt.basket_id}"
            )

            try:
                resp = await http_client.get(status_url)
                data = resp.json()
            except Exception as exc:
                log.warning(
                    "reconciliation.api_error",
                    attempt_id=attempt.id,
                    error=str(exc),
                )
                summary["skipped_inconclusive"] += 1
                continue

            txn_data = data.get("data", {})
            txn_status = txn_data.get("transactionStatus", "").upper()
            txn_id = txn_data.get("transactionId", "")

            if txn_status in ("PAID", "COMPLETED", "SUCCESS"):
                from app.services.billing import apply_successful_payment  # noqa: PLC0415

                attempt.status = PaymentAttemptStatus.succeeded
                db.add(attempt)
                await apply_successful_payment(db, invoice, txn_id or str(attempt.basket_id))
                summary["resolved_succeeded"] += 1

            elif txn_status in ("FAILED", "CANCELLED", "EXPIRED", "ERROR"):
                from app.services.billing import record_failed_attempt  # noqa: PLC0415

                attempt.status = PaymentAttemptStatus.failed
                db.add(attempt)
                await record_failed_attempt(db, invoice, reason=f"payfast_status:{txn_status}")
                summary["resolved_failed"] += 1

            else:
                # Inconclusive — leave pending for next sweep
                summary["skipped_inconclusive"] += 1

        await db.commit()

    log.info("reconciliation_sweep.complete", now=now.isoformat(), **summary)
    return summary


# ---------------------------------------------------------------------------
# hourly_dunning_check
# ---------------------------------------------------------------------------


async def hourly_dunning_check(
    db_session_factory: Any,
    settings: Any,
    email_sender: Any,
    clock: Callable[[], datetime] = datetime.utcnow,
) -> dict[str, int]:
    """Hourly catch-up for cancel_at_period_end flips and status transitions.

    Handles edge cases that fall between daily runs — e.g., a subscription
    whose period_end lands mid-day, or a cancel_at_period_end flag set after
    the daily 02:00 run.

    This function is intentionally lightweight: it only handles the clearest
    in-between cases and defers complex dunning logic to daily_renewal_sweep.
    """
    now = clock()
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)

    summary = {
        "cancel_at_period_end_canceled": 0,
        "flipped_to_past_due": 0,
    }

    async with db_session_factory() as db:

        # cancel_at_period_end that daily sweep may have missed
        cancel_subs = (
            await db.execute(
                select(Subscription).where(
                    and_(
                        Subscription.status == SubscriptionStatus.active,
                        Subscription.cancel_at_period_end.is_(True),
                        Subscription.current_period_end <= now,
                    )
                )
            )
        ).scalars().all()

        for sub in cancel_subs:
            from app.models.user import User  # noqa: PLC0415
            user = await db.get(User, sub.user_id)

            sub.status = SubscriptionStatus.canceled
            sub.canceled_at = now
            db.add(sub)

            await email_sender.send(
                to=user.email,
                subject=f"Your {sub.plan.name} subscription has ended",
                template_name="canceled",
                context={
                    "user": user,
                    "plan": sub.plan,
                    "period_end": sub.current_period_end,
                },
            )
            summary["cancel_at_period_end_canceled"] += 1

        # Active subs with overdue open invoices (24h grace)
        grace_cutoff = now - timedelta(hours=24)
        overdue_invoices = (
            await db.execute(
                select(Invoice).join(
                    Subscription, Invoice.subscription_id == Subscription.id
                ).where(
                    and_(
                        Subscription.status == SubscriptionStatus.active,
                        Invoice.status == InvoiceStatus.open,
                        Invoice.due_at <= grace_cutoff,
                    )
                )
            )
        ).scalars().all()

        for invoice in overdue_invoices:
            sub = await db.get(Subscription, invoice.subscription_id)
            if sub is None or sub.status != SubscriptionStatus.active:
                continue
            sub.status = SubscriptionStatus.past_due
            db.add(sub)
            summary["flipped_to_past_due"] += 1

        await db.commit()

    log.info("hourly_dunning_check.complete", now=now.isoformat(), **summary)
    return summary
