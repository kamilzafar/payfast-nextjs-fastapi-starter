"""Tests for POST /webhooks/payfast IPN endpoint.

TDD: written BEFORE implementation — all should be RED initially.
"""

from __future__ import annotations

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from tests.helpers.auth import create_user_and_token


async def _seed_plan_and_sub(
    client: AsyncClient,
    db_session: AsyncSession,
    email: str,
    plan_name: str,
) -> tuple[int, int, str]:
    """Returns (subscription_id, invoice_id, basket_id)."""
    from app.models.plan import Plan, PlanInterval  # noqa: PLC0415

    plan = Plan(
        name=plan_name,
        amount_minor=150000,
        currency="PKR",
        interval=PlanInterval.monthly,
        trial_days=7,
        is_active=True,
    )
    db_session.add(plan)
    await db_session.commit()
    await db_session.refresh(plan)

    _, token = await create_user_and_token(client, email=email)
    r = await client.post(
        "/subscriptions",
        json={"plan_id": plan.id},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 201, r.text
    body = r.json()
    return body["subscription_id"], body["invoice_id"], body["basket_id"]


@pytest.mark.asyncio
async def test_webhook_valid_signature_marks_paid(
    client: AsyncClient,
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Valid IPN: invoice becomes paid, subscription becomes active, period extended."""
    import app.routers.webhooks_payfast as wh_module  # noqa: PLC0415
    from app.models.invoice import Invoice, InvoiceStatus  # noqa: PLC0415
    from app.models.subscription import Subscription, SubscriptionStatus  # noqa: PLC0415
    from sqlalchemy import select  # noqa: PLC0415

    monkeypatch.setattr(wh_module, "verify_ipn", lambda *args, **kwargs: True)

    sub_id, inv_id, basket_id = await _seed_plan_and_sub(
        client, db_session, "ipn_ok@example.com", "PlanWebhookOk"
    )
    txn_id = "TXN123ABC"

    payload = f"basket_id={basket_id}&txn_id={txn_id}&status=paid".encode()
    r = await client.post(
        "/webhooks/payfast",
        content=payload,
        headers={
            "Content-Type": "application/x-www-form-urlencoded",
            "X-PayFast-Signature": "fake-sig",
        },
    )
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "ok"

    # Verify DB state — invoice paid
    await db_session.refresh(
        (await db_session.execute(select(Invoice).where(Invoice.id == inv_id))).scalar_one()
    )
    inv = (await db_session.execute(select(Invoice).where(Invoice.id == inv_id))).scalar_one()
    assert inv.status == InvoiceStatus.paid
    assert inv.payfast_txn_id == txn_id

    # Verify DB state — subscription active
    sub = (await db_session.execute(select(Subscription).where(Subscription.id == sub_id))).scalar_one()
    assert sub.status == SubscriptionStatus.active
    assert sub.current_period_end is not None


@pytest.mark.asyncio
async def test_webhook_invalid_signature_rejected(
    client: AsyncClient,
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Invalid signature should return 403."""
    import app.routers.webhooks_payfast as wh_module  # noqa: PLC0415

    monkeypatch.setattr(wh_module, "verify_ipn", lambda *args, **kwargs: False)

    r = await client.post(
        "/webhooks/payfast",
        content=b"basket_id=abc&txn_id=xyz",
        headers={
            "Content-Type": "application/x-www-form-urlencoded",
            "X-PayFast-Signature": "bad-sig",
        },
    )
    assert r.status_code == 403


@pytest.mark.asyncio
async def test_webhook_duplicate_event_idempotent(
    client: AsyncClient,
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Sending same IPN twice returns 200 both times; state only changed once."""
    import app.routers.webhooks_payfast as wh_module  # noqa: PLC0415
    from app.models.invoice import Invoice  # noqa: PLC0415
    from sqlalchemy import select, func  # noqa: PLC0415
    from app.models.webhook_event import WebhookEvent  # noqa: PLC0415

    monkeypatch.setattr(wh_module, "verify_ipn", lambda *args, **kwargs: True)

    sub_id, inv_id, basket_id = await _seed_plan_and_sub(
        client, db_session, "ipn_dupe@example.com", "PlanWebhookDupe"
    )
    txn_id = "TXN_DUPE_001"
    payload = f"basket_id={basket_id}&txn_id={txn_id}&status=paid".encode()
    headers = {
        "Content-Type": "application/x-www-form-urlencoded",
        "X-PayFast-Signature": "fake-sig",
    }

    r1 = await client.post("/webhooks/payfast", content=payload, headers=headers)
    assert r1.status_code == 200

    r2 = await client.post("/webhooks/payfast", content=payload, headers=headers)
    assert r2.status_code == 200

    # Only one webhook_event row for this txn_id
    count = (
        await db_session.execute(
            select(func.count(WebhookEvent.id)).where(
                WebhookEvent.provider_event_id == txn_id
            )
        )
    ).scalar_one()
    assert count == 1


@pytest.mark.asyncio
async def test_webhook_atomic(
    client: AsyncClient,
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """If DB commit fails mid-transaction, nothing should be persisted."""
    import app.routers.webhooks_payfast as wh_module  # noqa: PLC0415
    from app.models.invoice import Invoice, InvoiceStatus  # noqa: PLC0415
    from sqlalchemy import select  # noqa: PLC0415
    import app.repositories.webhook_events as we_repo  # noqa: PLC0415

    monkeypatch.setattr(wh_module, "verify_ipn", lambda *args, **kwargs: True)

    sub_id, inv_id, basket_id = await _seed_plan_and_sub(
        client, db_session, "ipn_atomic@example.com", "PlanWebhookAtomic"
    )
    txn_id = "TXN_ATOMIC_001"

    # Patch try_insert to raise an exception to simulate mid-TX failure
    original_try_insert = we_repo.try_insert

    async def _exploding_try_insert(db, provider_event_id, payload):
        raise RuntimeError("Simulated DB failure")

    monkeypatch.setattr(we_repo, "try_insert", _exploding_try_insert)

    payload = f"basket_id={basket_id}&txn_id={txn_id}&status=paid".encode()
    headers_dict = {
        "Content-Type": "application/x-www-form-urlencoded",
        "X-PayFast-Signature": "fake-sig",
    }

    # The RuntimeError raised by _exploding_try_insert propagates through the ASGI
    # transport (raise_app_exceptions=True) as an unhandled exception.
    # We verify atomicity by confirming the invoice is NOT updated.
    import httpx as _httpx  # noqa: PLC0415
    try:
        await client.post("/webhooks/payfast", content=payload, headers=headers_dict)
    except (RuntimeError, _httpx.HTTPStatusError, Exception):
        pass

    # Invoice should still be open (nothing was committed)
    await db_session.refresh(
        (await db_session.execute(select(Invoice).where(Invoice.id == inv_id))).scalar_one()
    )
    inv = (await db_session.execute(select(Invoice).where(Invoice.id == inv_id))).scalar_one()
    assert inv.status == InvoiceStatus.open
