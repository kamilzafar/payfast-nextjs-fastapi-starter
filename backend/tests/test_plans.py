"""Plans endpoint — seeds plans directly into the test DB and asserts list."""

from __future__ import annotations

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession


@pytest.mark.asyncio
async def test_list_plans_returns_seeded_plans(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    from app.models.plan import Plan, PlanInterval  # noqa: PLC0415

    db_session.add_all(
        [
            Plan(
                name="Basic",
                amount_minor=150000,  # 1500.00 PKR in paisa
                currency="PKR",
                interval=PlanInterval.monthly,
                trial_days=7,
                is_active=True,
            ),
            Plan(
                name="Pro",
                amount_minor=450000,  # 4500.00 PKR in paisa
                currency="PKR",
                interval=PlanInterval.monthly,
                trial_days=7,
                is_active=True,
            ),
            Plan(
                name="Legacy",
                amount_minor=10000,  # 100.00 PKR in paisa
                currency="PKR",
                interval=PlanInterval.monthly,
                trial_days=0,
                is_active=False,  # should NOT appear in output
            ),
        ]
    )
    await db_session.commit()

    r = await client.get("/plans")
    assert r.status_code == 200, r.text
    plans = r.json()
    names = [p["name"] for p in plans]
    assert names == ["Basic", "Pro"]  # ordered by amount_minor ascending
    assert all(p["is_active"] for p in plans)
    assert plans[0]["amount_minor"] == 150000
    assert plans[1]["amount_minor"] == 450000
    assert plans[0]["currency"] == "PKR"
    assert plans[1]["currency"] == "PKR"
