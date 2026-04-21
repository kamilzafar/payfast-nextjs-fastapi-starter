"""Tests for POST /webhooks/payfast IPN endpoint.

IPN contract (Apr 2026 docs):
  - PayFast POSTs form-urlencoded or JSON body to our CHECKOUT_URL
  - Auth via validation_hash field in body (not a header)
  - err_code '000' means success
"""

from __future__ import annotations

from urllib.parse import urlencode

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


def _ipn_body(
    basket_id: str,
    *,
    err_code: str = "000",
    err_msg: str = "Transaction has been completed.",
    transaction_id: str = "TXN-UNIT-001",
) -> bytes:
    """Build a form-urlencoded IPN body. validation_hash is added by the test
    after patching verify_ipn, so its value is irrelevant here."""
    return urlencode(
        {
            "basket_id": basket_id,
            "err_code": err_code,
            "err_msg": err_msg,
            "transaction_id": transaction_id,
            "validation_hash": "stubbed-by-monkeypatch",
            "transaction_amount": "1500.00",
            "transaction_currency": "PKR",
        }
    ).encode()


@pytest.mark.asyncio
async def test_webhook_valid_hash_marks_paid(
    client: AsyncClient,
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Valid IPN (err_code=000): invoice paid, sub active, period extended."""
    import app.routers.webhooks_payfast as wh_module  # noqa: PLC0415
    from app.models.invoice import Invoice, InvoiceStatus  # noqa: PLC0415
    from app.models.subscription import Subscription, SubscriptionStatus  # noqa: PLC0415
    from sqlalchemy import select  # noqa: PLC0415

    monkeypatch.setattr(wh_module, "verify_ipn", lambda *a, **kw: True)

    sub_id, inv_id, basket_id = await _seed_plan_and_sub(
        client, db_session, "ipn_ok@example.com", "PlanWebhookOk"
    )
    txn_id = "TXN-PAID-001"

    r = await client.post(
        "/webhooks/payfast",
        content=_ipn_body(basket_id, transaction_id=txn_id),
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "ok"

    inv = (
        await db_session.execute(select(Invoice).where(Invoice.id == inv_id))
    ).scalar_one()
    await db_session.refresh(inv)
    assert inv.status == InvoiceStatus.paid
    assert inv.payfast_txn_id == txn_id

    sub = (
        await db_session.execute(select(Subscription).where(Subscription.id == sub_id))
    ).scalar_one()
    await db_session.refresh(sub)
    assert sub.status == SubscriptionStatus.active
    assert sub.current_period_end is not None


@pytest.mark.asyncio
async def test_webhook_failed_err_code_records_failed_attempt(
    client: AsyncClient,
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """err_code != '000' records a failed payment_attempt; invoice stays open."""
    import app.routers.webhooks_payfast as wh_module  # noqa: PLC0415
    from app.models.invoice import Invoice, InvoiceStatus  # noqa: PLC0415
    from app.models.payment_attempt import PaymentAttempt, PaymentAttemptStatus  # noqa: PLC0415
    from sqlalchemy import select  # noqa: PLC0415

    monkeypatch.setattr(wh_module, "verify_ipn", lambda *a, **kw: True)

    _, inv_id, basket_id = await _seed_plan_and_sub(
        client, db_session, "ipn_fail@example.com", "PlanWebhookFail"
    )

    r = await client.post(
        "/webhooks/payfast",
        content=_ipn_body(
            basket_id,
            err_code="101",
            err_msg="Transaction declined by issuer",
            transaction_id="TXN-FAIL-001",
        ),
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    assert r.status_code == 200

    inv = (
        await db_session.execute(select(Invoice).where(Invoice.id == inv_id))
    ).scalar_one()
    await db_session.refresh(inv)
    assert inv.status == InvoiceStatus.open

    attempts = (
        await db_session.execute(
            select(PaymentAttempt).where(PaymentAttempt.invoice_id == inv_id)
        )
    ).scalars().all()
    assert any(a.status == PaymentAttemptStatus.failed for a in attempts)


@pytest.mark.asyncio
async def test_webhook_invalid_hash_rejected(
    client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Invalid validation_hash should return 403."""
    import app.routers.webhooks_payfast as wh_module  # noqa: PLC0415

    monkeypatch.setattr(wh_module, "verify_ipn", lambda *a, **kw: False)

    r = await client.post(
        "/webhooks/payfast",
        content=_ipn_body("BAS-01"),
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    assert r.status_code == 403


@pytest.mark.asyncio
async def test_webhook_json_body_accepted(
    client: AsyncClient,
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """PayFast may send the IPN as JSON — handler must parse both."""
    import app.routers.webhooks_payfast as wh_module  # noqa: PLC0415
    import json  # noqa: PLC0415
    from app.models.invoice import Invoice, InvoiceStatus  # noqa: PLC0415
    from sqlalchemy import select  # noqa: PLC0415

    monkeypatch.setattr(wh_module, "verify_ipn", lambda *a, **kw: True)

    _, inv_id, basket_id = await _seed_plan_and_sub(
        client, db_session, "ipn_json@example.com", "PlanWebhookJson"
    )

    body = json.dumps(
        {
            "basket_id": basket_id,
            "err_code": "000",
            "err_msg": "OK",
            "transaction_id": "TXN-JSON-001",
            "validation_hash": "stub",
        }
    ).encode()

    r = await client.post(
        "/webhooks/payfast",
        content=body,
        headers={"Content-Type": "application/json"},
    )
    assert r.status_code == 200

    inv = (
        await db_session.execute(select(Invoice).where(Invoice.id == inv_id))
    ).scalar_one()
    await db_session.refresh(inv)
    assert inv.status == InvoiceStatus.paid


@pytest.mark.asyncio
async def test_webhook_duplicate_event_idempotent(
    client: AsyncClient,
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Duplicate IPN (same transaction_id) is acknowledged without re-processing."""
    import app.routers.webhooks_payfast as wh_module  # noqa: PLC0415
    from app.models.webhook_event import WebhookEvent  # noqa: PLC0415
    from sqlalchemy import select, func  # noqa: PLC0415

    monkeypatch.setattr(wh_module, "verify_ipn", lambda *a, **kw: True)

    _, _, basket_id = await _seed_plan_and_sub(
        client, db_session, "ipn_dupe@example.com", "PlanWebhookDupe"
    )
    txn_id = "TXN-DUPE-001"
    body = _ipn_body(basket_id, transaction_id=txn_id)
    headers = {"Content-Type": "application/x-www-form-urlencoded"}

    r1 = await client.post("/webhooks/payfast", content=body, headers=headers)
    r2 = await client.post("/webhooks/payfast", content=body, headers=headers)
    assert r1.status_code == 200
    assert r2.status_code == 200

    count = (
        await db_session.execute(
            select(func.count(WebhookEvent.id)).where(
                WebhookEvent.provider_event_id == txn_id
            )
        )
    ).scalar_one()
    assert count == 1


@pytest.mark.asyncio
async def test_webhook_atomic_on_db_failure(
    client: AsyncClient,
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """DB failure mid-transaction: nothing is persisted."""
    import app.routers.webhooks_payfast as wh_module  # noqa: PLC0415
    import app.repositories.webhook_events as we_repo  # noqa: PLC0415
    from app.models.invoice import Invoice, InvoiceStatus  # noqa: PLC0415
    from sqlalchemy import select  # noqa: PLC0415

    monkeypatch.setattr(wh_module, "verify_ipn", lambda *a, **kw: True)

    _, inv_id, basket_id = await _seed_plan_and_sub(
        client, db_session, "ipn_atomic@example.com", "PlanWebhookAtomic"
    )

    async def _explode(db, provider_event_id, payload):
        raise RuntimeError("Simulated DB failure")

    monkeypatch.setattr(we_repo, "try_insert", _explode)

    try:
        await client.post(
            "/webhooks/payfast",
            content=_ipn_body(basket_id),
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
    except Exception:
        pass

    inv = (
        await db_session.execute(select(Invoice).where(Invoice.id == inv_id))
    ).scalar_one()
    await db_session.refresh(inv)
    assert inv.status == InvoiceStatus.open
