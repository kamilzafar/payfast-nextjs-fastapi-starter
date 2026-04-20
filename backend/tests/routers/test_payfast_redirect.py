"""Tests for GET /payfast/return and GET /payfast/cancel.

TDD: written BEFORE implementation — all should be RED initially.
"""

from __future__ import annotations

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from tests.helpers.auth import create_user_and_token


async def _seed_invoice(
    client: AsyncClient, db_session: AsyncSession, email: str, plan_name: str
) -> tuple[int, str]:
    """Returns (invoice_id, basket_id)."""
    from app.models.plan import Plan, PlanInterval  # noqa: PLC0415

    plan = Plan(
        name=plan_name,
        amount_minor=150000,
        currency="PKR",
        interval=PlanInterval.monthly,
        trial_days=0,
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
    return body["invoice_id"], body["basket_id"]


@pytest.mark.asyncio
async def test_return_redirects_to_frontend_success(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """Valid basket_id on return should 302 to /checkout/success."""
    invoice_id, basket_id = await _seed_invoice(
        client, db_session, "return_ok@example.com", "PlanReturnOk"
    )

    r = await client.get(
        f"/payfast/return?basket_id={basket_id}&txn_id=TXN999&status=paid",
        follow_redirects=False,
    )
    assert r.status_code == 302
    location = r.headers["location"]
    assert "/checkout/success" in location
    assert basket_id in location


@pytest.mark.asyncio
async def test_return_invalid_basket_redirects_to_cancel_invalid(
    client: AsyncClient,
) -> None:
    """Invalid basket_id on return should 302 to /checkout/cancel?reason=invalid."""
    r = await client.get(
        "/payfast/return?basket_id=not-a-valid-uuid",
        follow_redirects=False,
    )
    assert r.status_code == 302
    location = r.headers["location"]
    assert "/checkout/cancel" in location
    assert "invalid" in location


@pytest.mark.asyncio
async def test_cancel_redirects_to_frontend_cancel(
    client: AsyncClient,
) -> None:
    """GET /payfast/cancel (no basket) should 302 to /checkout/cancel."""
    r = await client.get("/payfast/cancel", follow_redirects=False)
    assert r.status_code == 302
    location = r.headers["location"]
    assert "/checkout/cancel" in location


@pytest.mark.asyncio
async def test_cancel_records_failed_attempt_when_basket_valid(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """Valid basket_id on cancel should insert a failed PaymentAttempt row."""
    from app.models.payment_attempt import PaymentAttempt, PaymentAttemptStatus  # noqa: PLC0415
    from sqlalchemy import select  # noqa: PLC0415

    invoice_id, basket_id = await _seed_invoice(
        client, db_session, "cancel_ok@example.com", "PlanCancelOk"
    )

    r = await client.get(
        f"/payfast/cancel?basket_id={basket_id}",
        follow_redirects=False,
    )
    assert r.status_code == 302
    location = r.headers["location"]
    assert "/checkout/cancel" in location

    # A failed payment attempt should have been recorded
    attempts = (
        await db_session.execute(
            select(PaymentAttempt).where(PaymentAttempt.invoice_id == invoice_id)
        )
    ).scalars().all()
    failed = [a for a in attempts if a.status == PaymentAttemptStatus.failed]
    assert len(failed) >= 1
