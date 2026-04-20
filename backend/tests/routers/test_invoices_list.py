"""Tests for GET /invoices endpoint (listing user's invoices).

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
    name: str = "InvListPlan",
    amount_minor: int = 150000,
) -> int:
    from app.models.plan import Plan, PlanInterval  # noqa: PLC0415

    plan = Plan(
        name=name,
        amount_minor=amount_minor,
        currency="PKR",
        interval=PlanInterval.monthly,
        trial_days=0,
        is_active=True,
    )
    db_session.add(plan)
    await db_session.commit()
    await db_session.refresh(plan)
    return plan.id


async def _create_sub_with_invoices(
    client: AsyncClient,
    db_session: AsyncSession,
    *,
    email: str,
    plan_name: str,
    extra_invoices: int = 0,
) -> tuple[str, int]:
    """Creates sub (adds first invoice) and optionally extra open invoices.

    Returns (token, subscription_id).
    """
    plan_id = await _seed_plan(db_session, name=plan_name)
    _, token = await create_user_and_token(client, email=email)

    r = await client.post(
        "/subscriptions",
        json={"plan_id": plan_id},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 201, r.text
    sub_id = r.json()["subscription_id"]

    if extra_invoices:
        from app.models.invoice import Invoice, InvoiceStatus  # noqa: PLC0415

        for _ in range(extra_invoices):
            db_session.add(
                Invoice(
                    subscription_id=sub_id,
                    amount=150000,
                    status=InvoiceStatus.open,
                )
            )
        await db_session.commit()

    return token, sub_id


@pytest.mark.asyncio
async def test_list_invoices_requires_auth(client: AsyncClient) -> None:
    r = await client.get("/invoices")
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_list_invoices_returns_empty(
    client: AsyncClient,
) -> None:
    """User without invoices gets empty items + total 0."""
    _, token = await create_user_and_token(client, email="empty-inv@example.com")

    r = await client.get(
        "/invoices",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body == {"items": [], "total": 0}


@pytest.mark.asyncio
async def test_list_invoices_shape(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """Returned items include id, basket_id, amount_minor, currency, status."""
    token, _ = await _create_sub_with_invoices(
        client, db_session, email="shape@example.com", plan_name="InvShapePlan"
    )

    r = await client.get(
        "/invoices",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["total"] == 1
    assert len(body["items"]) == 1
    item = body["items"][0]
    assert item["amount_minor"] == 150000
    assert item["currency"] == "PKR"
    assert item["status"] == "open"
    assert "basket_id" in item
    assert "subscription_id" in item
    assert "created_at" in item


@pytest.mark.asyncio
async def test_list_invoices_pagination(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """limit + offset paginate correctly, newest first."""
    # 1 initial invoice + 4 extra = 5 total
    token, _ = await _create_sub_with_invoices(
        client,
        db_session,
        email="pag@example.com",
        plan_name="InvPagPlan",
        extra_invoices=4,
    )

    r = await client.get(
        "/invoices?limit=2&offset=0",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["total"] == 5
    assert len(body["items"]) == 2
    first_page_ids = [i["id"] for i in body["items"]]

    r2 = await client.get(
        "/invoices?limit=2&offset=2",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r2.status_code == 200
    body2 = r2.json()
    assert len(body2["items"]) == 2
    second_page_ids = [i["id"] for i in body2["items"]]
    assert set(first_page_ids).isdisjoint(second_page_ids)

    # Newest first — IDs should be descending since they're inserted in order
    assert first_page_ids == sorted(first_page_ids, reverse=True)


@pytest.mark.asyncio
async def test_list_invoices_only_returns_callers_invoices(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """User B cannot see user A's invoices."""
    _, _ = await _create_sub_with_invoices(
        client, db_session, email="userA@example.com", plan_name="InvIsolA"
    )

    _, token_b = await create_user_and_token(client, email="userB@example.com")

    r = await client.get(
        "/invoices",
        headers={"Authorization": f"Bearer {token_b}"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body == {"items": [], "total": 0}
