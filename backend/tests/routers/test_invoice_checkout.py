"""Tests for POST /invoices/{invoice_id}/checkout endpoint.

TDD: written BEFORE implementation — all should be RED initially.
"""

from __future__ import annotations

import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from tests.helpers.auth import create_user_and_token


async def _seed_plan(db_session: AsyncSession, name: str = "CheckoutPlan") -> int:
    from app.models.plan import Plan, PlanInterval  # noqa: PLC0415

    plan = Plan(
        name=name,
        amount_minor=150000,
        currency="PKR",
        interval=PlanInterval.monthly,
        trial_days=0,
        is_active=True,
    )
    db_session.add(plan)
    await db_session.commit()
    await db_session.refresh(plan)
    return plan.id


async def _create_subscription_and_invoice(
    client: AsyncClient,
    db_session: AsyncSession,
    email: str,
    plan_name: str = "CheckoutPlan",
) -> tuple[str, int]:
    """Returns (token, invoice_id)."""
    plan_id = await _seed_plan(db_session, name=plan_name)
    _, token = await create_user_and_token(client, email=email)

    r = await client.post(
        "/subscriptions",
        json={"plan_id": plan_id},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 201, r.text
    return token, r.json()["invoice_id"]


@pytest.mark.asyncio
async def test_checkout_requires_auth(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    r = await client.post("/invoices/1/checkout")
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_checkout_returns_action_url_and_fields(
    client: AsyncClient, db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Mock PayFast token call; assert response shape matches frontend contract."""
    import app.routers.invoices as inv_router_module  # noqa: PLC0415
    from app.services.payfast.types import AccessToken  # noqa: PLC0415

    async def _fake_get_access_token(**kwargs):  # noqa: ARG001
        return AccessToken(token="tok123")

    monkeypatch.setattr(inv_router_module, "get_access_token", _fake_get_access_token)

    token, invoice_id = await _create_subscription_and_invoice(
        client, db_session, email="checkout@example.com", plan_name="CheckoutPlanOk"
    )

    r = await client.post(
        f"/invoices/{invoice_id}/checkout",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert "action_url" in body
    assert "fields" in body
    fields = body["fields"]
    assert "MERCHANT_ID" in fields
    assert fields.get("TOKEN") == "tok123"


@pytest.mark.asyncio
async def test_checkout_rejects_other_users_invoice(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """Another user's invoice should return 404."""
    # Create invoice owned by user A
    token_a, invoice_id = await _create_subscription_and_invoice(
        client, db_session, email="owner@example.com", plan_name="PlanOwner"
    )

    # Login as user B
    _, token_b = await create_user_and_token(
        client, email="thief@example.com"
    )

    r = await client.post(
        f"/invoices/{invoice_id}/checkout",
        headers={"Authorization": f"Bearer {token_b}"},
    )
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_checkout_rejects_already_paid(
    client: AsyncClient, db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Calling checkout on a paid invoice should return 409."""
    import app.routers.invoices as inv_router_module  # noqa: PLC0415
    from app.services.payfast.types import AccessToken  # noqa: PLC0415
    from app.models.invoice import Invoice, InvoiceStatus  # noqa: PLC0415
    from sqlalchemy import select  # noqa: PLC0415
    from datetime import datetime, timezone  # noqa: PLC0415

    async def _fake_get_access_token(**kwargs):  # noqa: ARG001
        return AccessToken(token="tok_paid")

    monkeypatch.setattr(inv_router_module, "get_access_token", _fake_get_access_token)

    token, invoice_id = await _create_subscription_and_invoice(
        client, db_session, email="paid@example.com", plan_name="PlanPaid"
    )

    # Manually mark invoice as paid
    inv = (
        await db_session.execute(select(Invoice).where(Invoice.id == invoice_id))
    ).scalar_one()
    inv.status = InvoiceStatus.paid
    inv.paid_at = datetime.now(tz=timezone.utc)
    await db_session.commit()

    r = await client.post(
        f"/invoices/{invoice_id}/checkout",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 409
    assert r.json()["detail"] == "already paid"


@pytest.mark.asyncio
async def test_checkout_propagates_payfast_error(
    client: AsyncClient, db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    """When get_access_token raises PayFastError, endpoint should return 502."""
    import app.routers.invoices as inv_router_module  # noqa: PLC0415
    from app.services.payfast.exceptions import PayFastError  # noqa: PLC0415

    async def _raise_payfast_error(**kwargs):  # noqa: ARG001
        raise PayFastError("PayFast is down")

    monkeypatch.setattr(inv_router_module, "get_access_token", _raise_payfast_error)

    token, invoice_id = await _create_subscription_and_invoice(
        client, db_session, email="pfdown@example.com", plan_name="PlanPFDown"
    )

    r = await client.post(
        f"/invoices/{invoice_id}/checkout",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 502
