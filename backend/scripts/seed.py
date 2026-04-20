"""Seed script — inserts Basic and Pro monthly plans (idempotent).

Amounts are stored in minor units (paisa):
  Basic = 150000 paisa = 1500.00 PKR
  Pro   = 450000 paisa = 4500.00 PKR
"""

from __future__ import annotations

import asyncio

from sqlalchemy import select

from app.db import AsyncSessionLocal
from app.models.plan import Plan, PlanInterval

PLANS = [
    {
        "name": "Basic",
        "amount_minor": 150000,  # 1500.00 PKR in paisa
        "currency": "PKR",
        "interval": PlanInterval.monthly,
        "trial_days": 7,
        "is_active": True,
    },
    {
        "name": "Pro",
        "amount_minor": 450000,  # 4500.00 PKR in paisa
        "currency": "PKR",
        "interval": PlanInterval.monthly,
        "trial_days": 7,
        "is_active": True,
    },
]


async def seed() -> None:
    async with AsyncSessionLocal() as session:
        for plan_data in PLANS:
            existing = await session.execute(
                select(Plan).where(Plan.name == plan_data["name"])
            )
            if existing.scalar_one_or_none() is None:
                session.add(Plan(**plan_data))
                print(f"Inserted plan: {plan_data['name']}")
            else:
                print(f"Plan already exists, skipping: {plan_data['name']}")
        await session.commit()


if __name__ == "__main__":
    asyncio.run(seed())
