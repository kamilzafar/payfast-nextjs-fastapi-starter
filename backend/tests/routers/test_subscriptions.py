"""Tests for POST /subscriptions endpoint.

TDD: written BEFORE implementation — all should be RED initially.
"""

from __future__ import annotations

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from tests.helpers.auth import create_user_and_token


async def _seed_plan(
    db_session: AsyncSession,
    *,
    name: str = "Basic",
    amount_minor: int = 150000,
    is_active: bool = True,
    trial_days: int = 7,
) -> int:
    from app.models.plan import Plan, PlanInterval  # noqa: PLC0415

    plan = Plan(
        name=name,
        amount_minor=amount_minor,
        currency="PKR",
        interval=PlanInterval.monthly,
        trial_days=trial_days,
        is_active=is_active,
    )
    db_session.add(plan)
    await db_session.commit()
    await db_session.refresh(plan)
    return plan.id


@pytest.mark.asyncio
async def test_create_subscription_requires_auth(client: AsyncClient) -> None:
    """POST /subscriptions without a token should return 401."""
    r = await client.post("/subscriptions", json={"plan_id": 1})
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_create_subscription_creates_sub_and_invoice(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """Happy path: returns 201 with subscription_id, invoice_id, basket_id UUID."""
    plan_id = await _seed_plan(db_session)
    _, token = await create_user_and_token(client)

    r = await client.post(
        "/subscriptions",
        json={"plan_id": plan_id},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 201, r.text
    body = r.json()
    assert "subscription_id" in body
    assert "invoice_id" in body
    assert "basket_id" in body
    assert body["checkout_url"] is None

    # basket_id must be a valid UUID string
    import uuid  # noqa: PLC0415
    uuid.UUID(body["basket_id"])  # raises ValueError if invalid

    # Verify DB state
    from sqlalchemy import select  # noqa: PLC0415
    from app.models.subscription import Subscription, SubscriptionStatus  # noqa: PLC0415
    from app.models.invoice import Invoice, InvoiceStatus  # noqa: PLC0415

    sub = (
        await db_session.execute(
            select(Subscription).where(Subscription.id == body["subscription_id"])
        )
    ).scalar_one()
    assert sub.status == SubscriptionStatus.trialing

    inv = (
        await db_session.execute(
            select(Invoice).where(Invoice.id == body["invoice_id"])
        )
    ).scalar_one()
    assert inv.status == InvoiceStatus.open
    assert str(inv.basket_id) == body["basket_id"]


@pytest.mark.asyncio
async def test_create_subscription_rejects_duplicate_active(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """A user with an active subscription should get 409."""
    plan_id = await _seed_plan(db_session, name="PlanDupe")
    _, token = await create_user_and_token(client, email="dupe@example.com")

    # First subscription — should succeed
    r = await client.post(
        "/subscriptions",
        json={"plan_id": plan_id},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 201, r.text

    # Second subscription — should be rejected
    r = await client.post(
        "/subscriptions",
        json={"plan_id": plan_id},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 409
    assert r.json()["detail"] == "already subscribed"


@pytest.mark.asyncio
async def test_create_subscription_rejects_missing_plan(
    client: AsyncClient,
) -> None:
    """A non-existent plan_id should return 404."""
    _, token = await create_user_and_token(client, email="noplan@example.com")

    r = await client.post(
        "/subscriptions",
        json={"plan_id": 99999},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 404
    assert r.json()["detail"] == "plan not found"


@pytest.mark.asyncio
async def test_create_subscription_rejects_inactive_plan(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """An inactive plan should return 404."""
    plan_id = await _seed_plan(
        db_session, name="InactivePlan", is_active=False
    )
    _, token = await create_user_and_token(client, email="inactive@example.com")

    r = await client.post(
        "/subscriptions",
        json={"plan_id": plan_id},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 404
    assert r.json()["detail"] == "plan not found"


# ---------------------------------------------------------------------------
# POST /subscriptions/{id}/cancel
# ---------------------------------------------------------------------------


async def _create_sub_for(
    client: AsyncClient, db_session: AsyncSession, email: str, plan_name: str
) -> tuple[str, int]:
    """Helper: creates user + subscription, returns (token, subscription_id)."""
    plan_id = await _seed_plan(db_session, name=plan_name)
    _, token = await create_user_and_token(client, email=email)
    r = await client.post(
        "/subscriptions",
        json={"plan_id": plan_id},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 201, r.text
    return token, r.json()["subscription_id"]


@pytest.mark.asyncio
async def test_cancel_subscription_requires_auth(client: AsyncClient) -> None:
    r = await client.post("/subscriptions/1/cancel")
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_cancel_at_period_end_sets_flag(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """POST cancel (default at_period_end=True) flips the flag; status stays."""
    token, sub_id = await _create_sub_for(
        client, db_session, email="cpe@example.com", plan_name="CancelAPEPlan"
    )

    r = await client.post(
        f"/subscriptions/{sub_id}/cancel",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["id"] == sub_id
    assert body["cancel_at_period_end"] is True
    # status should remain trialing/active — cron flips it at period_end
    assert body["status"] == "trialing"
    assert body["canceled_at"] is None


@pytest.mark.asyncio
async def test_cancel_immediate_sets_canceled(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """POST cancel with at_period_end=false immediately cancels."""
    token, sub_id = await _create_sub_for(
        client, db_session, email="imm@example.com", plan_name="CancelImmPlan"
    )

    r = await client.post(
        f"/subscriptions/{sub_id}/cancel",
        json={"at_period_end": False},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["status"] == "canceled"
    assert body["canceled_at"] is not None


@pytest.mark.asyncio
async def test_cancel_is_idempotent(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """Calling cancel twice should return the same state without error."""
    token, sub_id = await _create_sub_for(
        client, db_session, email="idem@example.com", plan_name="CancelIdemPlan"
    )

    r1 = await client.post(
        f"/subscriptions/{sub_id}/cancel",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r1.status_code == 200, r1.text
    r2 = await client.post(
        f"/subscriptions/{sub_id}/cancel",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r2.status_code == 200, r2.text
    assert r1.json()["cancel_at_period_end"] == r2.json()["cancel_at_period_end"] is True
    assert r1.json()["status"] == r2.json()["status"]


@pytest.mark.asyncio
async def test_cancel_other_users_subscription_returns_404(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """Cancelling someone else's subscription returns 404."""
    _, sub_id = await _create_sub_for(
        client, db_session, email="ownerA@example.com", plan_name="CancelAuthPlan"
    )

    _, token_b = await create_user_and_token(client, email="attackerB@example.com")

    r = await client.post(
        f"/subscriptions/{sub_id}/cancel",
        headers={"Authorization": f"Bearer {token_b}"},
    )
    assert r.status_code == 404
