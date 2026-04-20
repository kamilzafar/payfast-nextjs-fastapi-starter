"""Tests for GET /me/subscription endpoint.

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
    name: str = "MeSubPlan",
    amount_minor: int = 150000,
    trial_days: int = 7,
) -> int:
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
    return plan.id


@pytest.mark.asyncio
async def test_me_subscription_requires_auth(client: AsyncClient) -> None:
    r = await client.get("/me/subscription")
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_me_subscription_returns_null_when_none(
    client: AsyncClient,
) -> None:
    """No subscription -> 200 null (not 404)."""
    _, token = await create_user_and_token(client, email="no-sub@example.com")

    r = await client.get(
        "/me/subscription",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200
    assert r.json() is None


@pytest.mark.asyncio
async def test_me_subscription_returns_current_with_plan(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """Returns the current subscription with nested plan info."""
    plan_id = await _seed_plan(db_session, name="MeSubReturnsPlan")
    _, token = await create_user_and_token(client, email="with-sub@example.com")

    r = await client.post(
        "/subscriptions",
        json={"plan_id": plan_id},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 201, r.text

    r = await client.get(
        "/me/subscription",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body is not None
    assert body["status"] == "trialing"
    assert body["cancel_at_period_end"] is False
    assert body["canceled_at"] is None
    assert "plan" in body
    assert body["plan"]["id"] == plan_id
    assert body["plan"]["name"] == "MeSubReturnsPlan"
    assert body["plan"]["amount_minor"] == 150000
    assert body["plan"]["currency"] == "PKR"
    assert body["plan"]["interval"] in ("monthly", "month")
    assert body["plan"]["trial_days"] == 7


@pytest.mark.asyncio
async def test_me_subscription_ignores_canceled(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """Canceled (immediate) subscription should return null."""
    from sqlalchemy import select  # noqa: PLC0415
    from datetime import datetime, timezone  # noqa: PLC0415
    from app.models.subscription import Subscription, SubscriptionStatus  # noqa: PLC0415

    plan_id = await _seed_plan(db_session, name="MeSubCanceledPlan")
    _, token = await create_user_and_token(client, email="canc@example.com")

    r = await client.post(
        "/subscriptions",
        json={"plan_id": plan_id},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 201, r.text

    # Manually cancel
    sub = (
        await db_session.execute(select(Subscription))
    ).scalar_one()
    sub.status = SubscriptionStatus.canceled
    sub.canceled_at = datetime.now(tz=timezone.utc)
    await db_session.commit()

    r = await client.get(
        "/me/subscription",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200
    assert r.json() is None
